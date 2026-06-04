"""Silver Cleansing Pipeline — Vietnamese Legal Documents.

Reads from Bronze Iceberg table, applies:
  - HTML stripping and text normalization
  - Accurate word_count (Vietnamese-aware space splitting)
  - char_count
  - quality_score (0.0–1.0 proxy based on length)
  - Vietnamese date parsing (ngay_ban_hanh → issuance_date DATE)
  - effect_status normalization
  - Deduplication by record_hash (within-batch)
  - DQ gate → bad records routed to silver_quarantine table
  - Partition by ingest_date for incremental refresh
  - Run manifests and pipeline_metrics

Stream trigger: every 5 minutes (reads from Bronze Iceberg).
Table:          lakehouse.public.silver_documents (Iceberg)
Quarantine:     lakehouse.public.silver_quarantine (Iceberg)
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, current_timestamp, lit, size, split, to_date,
    trim, lower, regexp_replace, udf, when, length as spark_length,
)
from pyspark.sql.types import DoubleType, IntegerType, StringType, DateType

from common.config import load_config, AppConfig
from common.dq_checks import validate_silver_records
from common.logger import get_logger
from common.manifests import RunManifest, write_manifest
from common.pipeline_metrics import emit_pipeline_metrics

logger = get_logger("silver_pipeline")
_STAGE = "silver_cleanse"


# ---------------------------------------------------------------------------
# Spark Session Builder (reuses same Iceberg/MinIO config)
# ---------------------------------------------------------------------------

def _build_spark(cfg: AppConfig) -> SparkSession:
    return (
        SparkSession.builder
        .appName(f"{cfg.spark_app_name_prefix}-Silver-Cleansing")
        .config("spark.sql.shuffle.partitions", cfg.spark_sql_shuffle_partitions)
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1",
                "org.apache.iceberg:iceberg-aws-bundle:1.6.1",
                "org.postgresql:postgresql:42.7.3",
                "org.apache.hadoop:hadoop-aws:3.3.4",
            ]),
        )
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}",
                "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.type", "jdbc")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.uri", cfg.postgres_jdbc_uri)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.jdbc.user", cfg.postgres_user)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.jdbc.password", cfg.postgres_password)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.jdbc.driver", "org.postgresql.Driver")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.warehouse", cfg.iceberg_warehouse)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.io-impl",
                "org.apache.iceberg.aws.s3.S3FileIO")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.endpoint", cfg.minio_s3_endpoint)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.access-key-id", cfg.minio_access_key)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.secret-access-key",
                cfg.minio_secret_key)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.path-style-access", "true")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.client.region", "us-east-1")
        .config("spark.hadoop.fs.s3a.endpoint", cfg.minio_s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", cfg.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", cfg.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

def _create_silver_table(spark: SparkSession, cfg: AppConfig) -> None:
    catalog = cfg.iceberg_catalog
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.silver_documents (
            doc_id              STRING NOT NULL,
            record_hash         STRING NOT NULL,
            clean_text          STRING,
            title               STRING,
            char_count          INT,
            word_count          INT,
            quality_score       DOUBLE,
            so_ky_hieu          STRING,
            loai_van_ban        STRING,
            issuance_date       DATE,
            effective_date      DATE,
            expiry_date         DATE,
            co_quan_ban_hanh    STRING,
            linh_vuc            STRING,
            nganh               STRING,
            nguoi_ky            STRING,
            effect_status       STRING,
            ingested_at         TIMESTAMP NOT NULL,
            processed_at        TIMESTAMP NOT NULL,
            ingest_date         DATE NOT NULL,
            pipeline_run_id     STRING
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)
    logger.info(f"Silver table ready: {catalog}.public.silver_documents")


def _create_quarantine_table(spark: SparkSession, cfg: AppConfig) -> None:
    catalog = cfg.iceberg_catalog
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.silver_quarantine (
            doc_id              STRING,
            record_hash         STRING,
            raw_text_preview    STRING,
            rejection_reason    STRING NOT NULL,
            dq_rule             STRING NOT NULL,
            quarantined_at      TIMESTAMP NOT NULL,
            pipeline_run_id     STRING
        )
        USING iceberg
        PARTITIONED BY (quarantined_at)
    """)
    logger.info(f"Quarantine table ready: {catalog}.public.silver_quarantine")


# ---------------------------------------------------------------------------
# Text normalization UDFs
# ---------------------------------------------------------------------------

_VN_DATE_PATTERNS = [
    r"(\d{2})/(\d{2})/(\d{4})",   # DD/MM/YYYY
    r"(\d{4})-(\d{2})-(\d{2})",   # YYYY-MM-DD
    r"(\d{2})-(\d{2})-(\d{4})",   # DD-MM-YYYY
]


def _parse_vn_date(date_str: str | None) -> str | None:
    """Parse Vietnamese date strings to ISO YYYY-MM-DD format."""
    if not date_str:
        return None
    date_str = date_str.strip()

    # DD/MM/YYYY → YYYY-MM-DD
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date_str)
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

    # YYYY-MM-DD (already ISO)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        return date_str[:10]

    return None


def _normalize_effect_status(status: str | None) -> str | None:
    """Normalize tinh_trang_hieu_luc to canonical Vietnamese values."""
    if not status:
        return "không xác định"
    s = status.strip().lower()
    if "còn" in s or "hieu luc" in s:
        return "còn hiệu lực"
    if "hết" in s or "het" in s:
        return "hết hiệu lực"
    if "chưa" in s or "chua" in s:
        return "chưa có hiệu lực"
    return "không xác định"


def _quality_score(char_count: int | None) -> float:
    """Compute a simple quality proxy: min(1.0, char_count / 2000)."""
    if not char_count:
        return 0.0
    return min(1.0, char_count / 2000.0)


_parse_date_udf = udf(_parse_vn_date, StringType())
_normalize_status_udf = udf(_normalize_effect_status, StringType())
_quality_score_udf = udf(_quality_score, DoubleType())


# ---------------------------------------------------------------------------
# Processing logic (used by both batch and streaming)
# ---------------------------------------------------------------------------

def _transform_bronze_to_silver(
    df: DataFrame, run_id: str
) -> tuple[DataFrame, DataFrame]:
    """Transform Bronze records to Silver and quarantine bad ones.

    Args:
        df: Bronze DataFrame.
        run_id: Current pipeline run_id for lineage.

    Returns:
        Tuple of (silver_df, quarantine_df).
    """
    # Text cleaning
    cleaned = (
        df
        .withColumn("clean_text",
            trim(
                regexp_replace(
                    regexp_replace(col("raw_text"), r"\s+", " "),
                    r"[^\w\s\.\,\;\:\!\?\-\(\)\[\]\/\%\d]", ""
                )
            )
        )
        .withColumn("char_count", spark_length(col("clean_text")).cast(IntegerType()))
        # Vietnamese word count: split on whitespace
        .withColumn("word_count", size(split(col("clean_text"), r"\s+")).cast(IntegerType()))
        .withColumn("quality_score", _quality_score_udf(col("char_count")))
        # Date normalization
        .withColumn("issuance_date",
            to_date(_parse_date_udf(col("ngay_ban_hanh")), "yyyy-MM-dd"))
        .withColumn("effective_date",
            to_date(_parse_date_udf(col("ngay_co_hieu_luc")), "yyyy-MM-dd"))
        .withColumn("expiry_date",
            to_date(_parse_date_udf(col("ngay_het_hieu_luc")), "yyyy-MM-dd"))
        .withColumn("effect_status", _normalize_status_udf(col("tinh_trang_hieu_luc")))
        .withColumn("processed_at", current_timestamp())
        .withColumn("pipeline_run_id", lit(run_id))
    )

    # Split: silver (valid) vs quarantine (too short)
    silver = (
        cleaned.filter(
            col("clean_text").isNotNull() &
            (col("char_count") >= 50) &
            (col("word_count") >= 5)
        )
        .dropDuplicates(["record_hash"])
        .select(
            "doc_id", "record_hash", "clean_text", "title",
            "char_count", "word_count", "quality_score",
            "so_ky_hieu", "loai_van_ban",
            "issuance_date", "effective_date", "expiry_date",
            "co_quan_ban_hanh", "linh_vuc", "nganh", "nguoi_ky", "effect_status",
            "ingested_at", "processed_at", "ingest_date", "pipeline_run_id",
        )
    )

    quarantine = (
        cleaned.filter(
            col("clean_text").isNull() |
            (col("char_count") < 50) |
            (col("word_count") < 5)
        )
        .withColumn("raw_text_preview", col("raw_text").substr(1, 200))
        .withColumn(
            "rejection_reason",
            when(col("clean_text").isNull(), "clean_text is null")
            .when(col("char_count") < 50, "char_count below minimum")
            .otherwise("word_count below minimum")
        )
        .withColumn("dq_rule", lit("silver_min_length"))
        .withColumn("quarantined_at", current_timestamp())
        .select(
            "doc_id", "record_hash", "raw_text_preview",
            "rejection_reason", "dq_rule", "quarantined_at", "pipeline_run_id",
        )
    )

    return silver, quarantine


# ---------------------------------------------------------------------------
# Batch cleansing (recommended for initial load)
# ---------------------------------------------------------------------------

def cleanse_batch(spark: SparkSession, cfg: AppConfig) -> None:
    """Read all Bronze records and write to Silver (batch mode)."""
    _create_silver_table(spark, cfg)
    _create_quarantine_table(spark, cfg)

    manifest = RunManifest(stage=_STAGE)
    start_ts = time.time()
    manifest.inputs.append(f"{cfg.iceberg_catalog}.public.bronze_documents")

    df = spark.read.table(f"{cfg.iceberg_catalog}.public.bronze_documents")
    rows_in = df.count()
    logger.info(f"Bronze records to process: {rows_in}")

    silver_df, quarantine_df = _transform_bronze_to_silver(df, manifest.run_id)

    rows_out = silver_df.count()
    rows_quarantined = quarantine_df.count()

    logger.info(f"Silver: {rows_out} valid, {rows_quarantined} quarantined")

    # DQ gate on Silver output sample
    sample = silver_df.limit(500).toPandas().to_dict("records")
    dq_report, _, _ = validate_silver_records(sample)
    logger.info(dq_report.summary_str())

    if not dq_report.passed and cfg.dq_fail_on_error:
        manifest.mark_failed(f"Silver DQ gate failed: {dq_report.summary_str()}")
        manifest.details["dq"] = dq_report.to_metrics()
        write_manifest(cfg.manifest_root, manifest)
        raise RuntimeError(f"Silver DQ gate failed: {dq_report.summary_str()}")

    # Write Silver
    (
        silver_df.writeTo(f"{cfg.iceberg_catalog}.public.silver_documents")
        .append()
    )
    manifest.outputs.append(f"{cfg.iceberg_catalog}.public.silver_documents")

    # Write Quarantine
    if rows_quarantined > 0:
        (
            quarantine_df.writeTo(f"{cfg.iceberg_catalog}.public.silver_quarantine")
            .append()
        )
        manifest.outputs.append(f"{cfg.iceberg_catalog}.public.silver_quarantine")

    duration_ms = (time.time() - start_ts) * 1000
    manifest.set_metrics(
        rows_in=rows_in,
        rows_out=rows_out,
        rows_quarantined=rows_quarantined,
        duration_ms=round(duration_ms, 2),
        dq_passed=dq_report.passed,
    )
    manifest.details["dq"] = dq_report.to_metrics()
    manifest.mark_success()
    manifest_path = write_manifest(cfg.manifest_root, manifest)

    emit_pipeline_metrics(
        stage=_STAGE, run_id=manifest.run_id, status="success",
        rows_in=rows_in, rows_out=rows_out, rows_quarantined=rows_quarantined,
        duration_ms=duration_ms,
        dq_passed=dq_report.passed,
        dq_critical_failures=len(dq_report.critical_failures),
        dq_warnings=len(dq_report.warnings),
        manifest_path=manifest_path,
    )
    logger.info(f"Silver cleansing completed. Manifest: {manifest_path}")


# ---------------------------------------------------------------------------
# Streaming cleansing
# ---------------------------------------------------------------------------

def cleanse_stream(spark: SparkSession, cfg: AppConfig) -> None:
    """Stream from Bronze Iceberg table and write to Silver (streaming mode)."""
    _create_silver_table(spark, cfg)
    _create_quarantine_table(spark, cfg)

    manifest = RunManifest(stage=f"{_STAGE}_stream")
    start_ts = time.time()
    rows_out_total = 0
    rows_quarantined_total = 0

    bronze_stream = (
        spark.readStream
        .format("iceberg")
        .load(f"{cfg.iceberg_catalog}.public.bronze_documents")
    )

    def process_batch(batch_df: DataFrame, batch_id: int) -> None:
        nonlocal rows_out_total, rows_quarantined_total

        if batch_df.isEmpty():
            return

        silver_df, quarantine_df = _transform_bronze_to_silver(batch_df, manifest.run_id)

        rows_out = silver_df.count()
        rows_q = quarantine_df.count()
        rows_out_total += rows_out
        rows_quarantined_total += rows_q

        (silver_df.writeTo(f"{cfg.iceberg_catalog}.public.silver_documents").append())

        if rows_q > 0:
            (quarantine_df.writeTo(f"{cfg.iceberg_catalog}.public.silver_quarantine").append())

        logger.info(f"Silver batch {batch_id}: silver={rows_out}, quarantine={rows_q}")

    query = (
        bronze_stream.writeStream
        .foreachBatch(process_batch)
        .trigger(processingTime=f"{cfg.stream_trigger_seconds * 5} seconds")
        .option("checkpointLocation", f"s3a://{cfg.s3_bucket_checkpoints}/silver/")
        .start()
    )

    try:
        query.awaitTermination(timeout=cfg.stream_timeout_seconds)
    finally:
        query.stop()

    duration_ms = (time.time() - start_ts) * 1000
    manifest.set_metrics(
        rows_out=rows_out_total,
        rows_quarantined=rows_quarantined_total,
        duration_ms=round(duration_ms, 2),
    )
    manifest.mark_success()
    manifest_path = write_manifest(cfg.manifest_root, manifest)
    emit_pipeline_metrics(
        stage=f"{_STAGE}_stream", run_id=manifest.run_id, status="success",
        rows_out=rows_out_total, rows_quarantined=rows_quarantined_total,
        duration_ms=duration_ms, manifest_path=manifest_path,
    )
    logger.info(f"Silver streaming completed. Manifest: {manifest_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Silver Cleansing Pipeline")
    parser.add_argument("--mode", choices=["batch", "stream"], default="batch")
    args = parser.parse_args()

    cfg = load_config()
    spark = _build_spark(cfg)
    spark.sparkContext.setLogLevel("WARN")

    if args.mode == "stream":
        cleanse_stream(spark, cfg)
    else:
        cleanse_batch(spark, cfg)

    spark.stop()
