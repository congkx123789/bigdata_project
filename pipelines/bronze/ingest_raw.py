"""Bronze Ingestion Pipeline — Vietnamese Legal Documents.

Reads raw documents from Kafka topic (published by the HuggingFace loader
or OCR workers) and writes to the Iceberg Bronze table with:
  - record_hash  (SHA256 deterministic dedup identity)
  - dedupe_key   (doc_id + loai_van_ban composite key)
  - DQ validation before write
  - Run manifests for lineage
  - Dead-Letter Queue (DLQ) routing for unparse-able records

Stream trigger: every STREAM_TRIGGER_SECONDS (default 60s).
Checkpoint:     s3a://legal-checkpoints/bronze/
Table:          lakehouse.public.bronze_documents (Iceberg)
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, current_timestamp, from_json, lit,
    sha2, concat_ws, to_date, regexp_replace, trim,
)

from common.config import load_config, AppConfig
from common.dq_checks import validate_bronze_records
from common.logger import get_logger
from common.manifests import RunManifest, write_manifest
from common.pipeline_metrics import emit_pipeline_metrics
from common.schemas import BRONZE_SCHEMA, HF_METADATA_SCHEMA

logger = get_logger("bronze_pipeline")
_STAGE = "bronze_ingest"


# ---------------------------------------------------------------------------
# Spark Session Builder
# ---------------------------------------------------------------------------

def _build_spark(cfg: AppConfig) -> SparkSession:
    """Build a Spark session wired to MinIO (S3A) and Iceberg JDBC catalog."""
    return (
        SparkSession.builder
        .appName(f"{cfg.spark_app_name_prefix}-Bronze-Ingestion")
        .config("spark.sql.shuffle.partitions", cfg.spark_sql_shuffle_partitions)
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1",
                "org.apache.iceberg:iceberg-aws-bundle:1.6.1",
                "org.postgresql:postgresql:42.7.3",
                "org.apache.hadoop:hadoop-aws:3.3.4",
            ]),
        )
        .config("spark.sql.extensions",
                "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        # Iceberg JDBC catalog
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
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.endpoint",
                cfg.minio_s3_endpoint)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.access-key-id",
                cfg.minio_access_key)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.secret-access-key",
                cfg.minio_secret_key)
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.s3.path-style-access", "true")
        .config(f"spark.sql.catalog.{cfg.iceberg_catalog}.client.region", "us-east-1")
        # S3A config for direct MinIO reads
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

def _create_bronze_table(spark: SparkSession, cfg: AppConfig) -> None:
    """Create Bronze Iceberg table if it does not exist."""
    catalog = cfg.iceberg_catalog
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.bronze_documents (
            doc_id              STRING,
            source_bucket       STRING,
            source_path         STRING,
            raw_text            STRING,
            title               STRING,
            so_ky_hieu          STRING,
            loai_van_ban        STRING,
            ngay_ban_hanh       STRING,
            ngay_co_hieu_luc    STRING,
            ngay_het_hieu_luc   STRING,
            co_quan_ban_hanh    STRING,
            linh_vuc            STRING,
            nganh               STRING,
            nguoi_ky            STRING,
            tinh_trang_hieu_luc STRING,
            record_hash         STRING,
            dedupe_key          STRING,
            ingested_at         TIMESTAMP,
            ingest_date         DATE,
            pipeline_run_id     STRING
        )
        USING iceberg
    """)
    logger.info(f"Bronze table ready: {catalog}.public.bronze_documents")


def _create_dlq_table(spark: SparkSession, cfg: AppConfig) -> None:
    """Create Dead-Letter Queue table for malformed Kafka messages."""
    catalog = cfg.iceberg_catalog
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.bronze_dlq (
            raw_value       STRING,
            error_message   STRING,
            kafka_offset    BIGINT,
            kafka_partition INT,
            arrived_at      TIMESTAMP NOT NULL,
            pipeline_run_id STRING
        )
        USING iceberg
        PARTITIONED BY (arrived_at)
    """)
    logger.info(f"DLQ table ready: {catalog}.public.bronze_dlq")


# ---------------------------------------------------------------------------
# Streaming ingestion
# ---------------------------------------------------------------------------

def _strip_html_native(html_col):
    """Strip HTML tags using native Spark regexp_replace — no Python UDF, no JVM→Python bridge."""
    # Remove all HTML tags <...>
    step1 = regexp_replace(html_col, r"<[^>]+>", " ")
    # Collapse multiple whitespace
    step2 = regexp_replace(step1, r"\s+", " ")
    return trim(step2)


def ingest_stream(spark: SparkSession, cfg: AppConfig) -> None:
    """Run the Bronze Kafka → Iceberg streaming job."""
    _create_bronze_table(spark, cfg)
    _create_dlq_table(spark, cfg)

    # Kafka schema: JSON envelope matching HF metadata fields
    kafka_schema = HF_METADATA_SCHEMA

    # Read from Kafka
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", cfg.kafka_bootstrap_servers)
        .option("subscribe", cfg.kafka_topic_raw)
        .option("startingOffsets", "earliest")
        .option("maxOffsetsPerTrigger", cfg.stream_max_offsets_per_trigger)
        .option("failOnDataLoss", "false")
        .load()
    )

    manifest = RunManifest(stage=_STAGE)
    start_ts = time.time()
    rows_out = 0
    dlq_count = 0

    def process_batch(batch_df: DataFrame, batch_id: int) -> None:
        nonlocal rows_out, dlq_count

        if batch_df.isEmpty():
            logger.info(f"Batch {batch_id}: empty, skipping")
            return

        # Parse JSON
        parsed = (
            batch_df
            .selectExpr("CAST(value AS STRING) AS raw_value",
                        "offset AS kafka_offset",
                        "partition AS kafka_partition")
            .withColumn("parsed", from_json(col("raw_value"), kafka_schema))
        )

        # Split good vs DLQ (doc_id must exist)
        good = parsed.filter(col("parsed.id").isNotNull())
        bad = parsed.filter(col("parsed.id").isNull())

        # Route bad records to DLQ table
        if not bad.isEmpty():
            bad_count = bad.count()
            dlq_count += bad_count
            logger.warning(f"Batch {batch_id}: routing {bad_count} bad records to DLQ")
            (
                bad.select(
                    col("raw_value"),
                    lit("doc_id is null after JSON parse").alias("error_message"),
                    col("kafka_offset"),
                    col("kafka_partition"),
                    current_timestamp().alias("arrived_at"),
                    lit(manifest.run_id).alias("pipeline_run_id"),
                )
                .writeTo(f"{cfg.iceberg_catalog}.public.bronze_dlq")
                .append()
            )

        if good.isEmpty():
            return

        # Build Bronze records with dedup identity
        bronze = (
            good.select(
                col("parsed.id").cast("string").alias("doc_id"),
                lit("huggingface").alias("source_bucket"),
                lit(cfg.hf_dataset_repo).alias("source_path"),
                _strip_html_native(col("parsed.content_html")).alias("raw_text"),
                col("parsed.content_html"),
                col("parsed.title"),
                col("parsed.so_ky_hieu"),
                col("parsed.loai_van_ban"),
                col("parsed.ngay_ban_hanh"),
                col("parsed.ngay_co_hieu_luc"),
                col("parsed.ngay_het_hieu_luc"),
                col("parsed.co_quan_ban_hanh"),
                col("parsed.linh_vuc"),
                col("parsed.nganh"),
                col("parsed.nguoi_ky"),
                col("parsed.tinh_trang_hieu_luc"),
            )
            # Deterministic dedup identity (rerun-safe)
            .withColumn(
                "record_hash",
                sha2(concat_ws("|",
                    col("doc_id"),
                    col("raw_text").substr(1, 200),  # First 200 chars for hash stability
                ), 256)
            )
            .withColumn(
                "dedupe_key",
                concat_ws("|", col("doc_id"), col("loai_van_ban"))
            )
            .withColumn("ingested_at", current_timestamp())
            .withColumn("ingest_date", to_date(current_timestamp()))
            .withColumn("pipeline_run_id", lit(manifest.run_id))
        )

        # DQ validation (collect sample for quality check, not full scan)
        sample = bronze.limit(1000).toPandas().to_dict("records")
        dq_report = validate_bronze_records(sample)

        if not dq_report.passed and cfg.dq_fail_on_error:
            logger.error(f"Batch {batch_id}: {dq_report.summary_str()} — aborting batch")
            return

        logger.info(f"Batch {batch_id}: {dq_report.summary_str()}")

        # Write to Bronze (MERGE INTO for dedup, or append for new records)
        batch_count = bronze.count()
        rows_out += batch_count

        (
            bronze.writeTo(f"{cfg.iceberg_catalog}.public.bronze_documents")
            .append()
        )

        logger.info(f"Batch {batch_id}: wrote {batch_count} records to Bronze")

    # Start stream
    query = (
        raw_stream.writeStream
        .foreachBatch(process_batch)
        .trigger(processingTime=f"{cfg.stream_trigger_seconds} seconds")
        .option(
            "checkpointLocation",
            f"s3a://{cfg.s3_bucket_checkpoints}/bronze/"
        )
        .start()
    )

    logger.info(f"Bronze streaming started (run_id={manifest.run_id})")

    try:
        query.awaitTermination(timeout=cfg.stream_timeout_seconds)
    except Exception as exc:
        duration_ms = (time.time() - start_ts) * 1000
        manifest.mark_failed(str(exc))
        emit_pipeline_metrics(
            stage=_STAGE, run_id=manifest.run_id, status="failed",
            rows_out=rows_out, duration_ms=duration_ms,
        )
        write_manifest(cfg.manifest_root, manifest)
        raise
    finally:
        query.stop()

    duration_ms = (time.time() - start_ts) * 1000
    manifest.set_metrics(
        rows_out=rows_out,
        dlq_count=dlq_count,
        duration_ms=round(duration_ms, 2),
    )
    manifest.mark_success()
    manifest_path = write_manifest(cfg.manifest_root, manifest)

    emit_pipeline_metrics(
        stage=_STAGE, run_id=manifest.run_id, status="success",
        rows_out=rows_out, rows_quarantined=dlq_count,
        duration_ms=duration_ms,
        manifest_path=manifest_path,
    )
    logger.info(f"Bronze streaming completed. Manifest: {manifest_path}")


# ---------------------------------------------------------------------------
# Batch ingestion (from local Parquet files written by HF loader)
# ---------------------------------------------------------------------------

def ingest_batch_from_parquet(spark: SparkSession, cfg: AppConfig) -> None:
    """Ingest HuggingFace Parquet files directly into Bronze (batch mode)."""
    _create_bronze_table(spark, cfg)

    manifest = RunManifest(stage=f"{_STAGE}_batch")
    start_ts = time.time()

    parquet_content = f"s3a://{cfg.s3_bucket_bronze}/hf/th1nhng0/vietnamese-legal-documents/content"
    parquet_metadata = f"s3a://{cfg.s3_bucket_bronze}/hf/th1nhng0/vietnamese-legal-documents/metadata"

    logger.info(f"Reading content parquet from: {parquet_content}")
    content_df = spark.read.parquet(parquet_content)

    manifest.inputs.append(parquet_content)

    # Join with metadata if available
    try:
        logger.info(f"Reading metadata parquet from: {parquet_metadata}")
        meta_df = spark.read.parquet(parquet_metadata)
        manifest.inputs.append(parquet_metadata)

        # Join content + metadata on id
        joined = content_df.alias("c").join(
            meta_df.alias("m"),
            col("c.id") == col("m.id").cast("string"),
            how="left"
        )
    except Exception as e:
        logger.warning(f"Metadata parquet not found or error — proceeding with content only: {e}")
        joined = content_df.withColumnRenamed("id", "doc_id_raw")

    # Build Bronze records — dedup + text extraction all in one pass, no content_html retained.
    # content_html is not stored in Bronze (too large, causes OOM). raw_text is HTML-stripped text.
    try:
        # Step 1: Dedup on lightweight columns only
        keys_df = (
            joined
            .withColumn("doc_id", col("c.id").cast("string"))
            .withColumn("title", col("m.title"))
            .withColumn("so_ky_hieu", col("m.so_ky_hieu"))
            .withColumn("loai_van_ban", col("m.loai_van_ban"))
            .withColumn("ngay_ban_hanh", col("m.ngay_ban_hanh"))
            .withColumn("ngay_co_hieu_luc", col("m.ngay_co_hieu_luc"))
            .withColumn("ngay_het_hieu_luc", col("m.ngay_het_hieu_luc"))
            .withColumn("co_quan_ban_hanh", col("m.co_quan_ban_hanh"))
            .withColumn("linh_vuc", col("m.linh_vuc"))
            .withColumn("nganh", col("m.nganh"))
            .withColumn("nguoi_ky", col("m.nguoi_ky"))
            .withColumn("tinh_trang_hieu_luc", col("m.tinh_trang_hieu_luc"))
            .withColumn("source_bucket", lit("huggingface"))
            .withColumn("source_path", lit(cfg.hf_dataset_repo))
            .withColumn("record_hash", sha2(col("doc_id"), 256))
            .withColumn("dedupe_key", concat_ws("|", col("doc_id"), col("loai_van_ban")))
            .withColumn("ingested_at", current_timestamp())
            .withColumn("ingest_date", to_date(current_timestamp()))
            .withColumn("pipeline_run_id", lit(manifest.run_id))
            .select(
                "doc_id", "source_bucket", "source_path",
                "title", "so_ky_hieu", "loai_van_ban", "ngay_ban_hanh",
                "ngay_co_hieu_luc", "ngay_het_hieu_luc", "co_quan_ban_hanh",
                "linh_vuc", "nganh", "nguoi_ky", "tinh_trang_hieu_luc",
                "record_hash", "dedupe_key", "ingested_at", "ingest_date",
                "pipeline_run_id",
            )
            .dropDuplicates(["record_hash"])
        )

        # Step 2: Reattach heavy text AFTER dedup without shuffling the text!
        # Force broadcast of keys_df so content_small is joined map-side without any SortMergeJoin shuffle.
        from pyspark.sql.functions import broadcast
        content_small = content_df.select(
            col("id").cast("string").alias("_cid"),
            _strip_html_native(col("content_html")).alias("raw_text")
        )
        bronze = (
            content_small
            .join(broadcast(keys_df), keys_df["doc_id"] == content_small["_cid"], how="right")
            .drop("_cid")
        )
    except Exception as col_err:
        # Fallback for content-only mode
        logger.warning(f"Column resolution error, falling back to content-only: {col_err}")
        keys_df = (
            content_df
            .withColumn("doc_id", col("id").cast("string"))
            .withColumn("source_bucket", lit("huggingface"))
            .withColumn("source_path", lit(cfg.hf_dataset_repo))
            .withColumn("title", lit(None).cast("string"))
            .withColumn("so_ky_hieu", lit(None).cast("string"))
            .withColumn("loai_van_ban", lit(None).cast("string"))
            .withColumn("ngay_ban_hanh", lit(None).cast("string"))
            .withColumn("ngay_co_hieu_luc", lit(None).cast("string"))
            .withColumn("ngay_het_hieu_luc", lit(None).cast("string"))
            .withColumn("co_quan_ban_hanh", lit(None).cast("string"))
            .withColumn("linh_vuc", lit(None).cast("string"))
            .withColumn("nganh", lit(None).cast("string"))
            .withColumn("nguoi_ky", lit(None).cast("string"))
            .withColumn("tinh_trang_hieu_luc", lit(None).cast("string"))
            .withColumn("record_hash", sha2(col("doc_id"), 256))
            .withColumn("dedupe_key", concat_ws("|", col("doc_id"), lit("unknown")))
            .withColumn("ingested_at", current_timestamp())
            .withColumn("ingest_date", to_date(current_timestamp()))
            .withColumn("pipeline_run_id", lit(manifest.run_id))
            .select(
                "doc_id", "source_bucket", "source_path",
                "title", "so_ky_hieu", "loai_van_ban", "ngay_ban_hanh",
                "ngay_co_hieu_luc", "ngay_het_hieu_luc", "co_quan_ban_hanh",
                "linh_vuc", "nganh", "nguoi_ky", "tinh_trang_hieu_luc",
                "record_hash", "dedupe_key", "ingested_at", "ingest_date",
                "pipeline_run_id",
            )
            .dropDuplicates(["record_hash"])
        )

        from pyspark.sql.functions import broadcast
        content_small = content_df.select(
            col("id").cast("string").alias("_cid"),
            _strip_html_native(col("content_html")).alias("raw_text")
        )
        bronze = (
            content_small
            .join(broadcast(keys_df), keys_df["doc_id"] == content_small["_cid"], how="right")
            .drop("_cid")
        )

    rows_in = bronze.count()
    logger.info(f"Bronze batch: {rows_in} records after dedup")

    # DQ check on metadata-only sample — avoids materializing huge raw_text/content_html into driver
    sample_df = bronze.select(
        "doc_id", "record_hash", "dedupe_key", "ingested_at", "ingest_date",
        "loai_van_ban", "title", "source_bucket", "pipeline_run_id",
    ).limit(500)
    sample = sample_df.toPandas().to_dict("records")
    dq_report = validate_bronze_records(sample)
    logger.info(dq_report.summary_str())

    if not dq_report.passed and cfg.dq_fail_on_error:
        manifest.mark_failed(f"DQ gate failed: {dq_report.summary_str()}")
        manifest.details["dq"] = dq_report.to_metrics()
        write_manifest(cfg.manifest_root, manifest)
        raise RuntimeError(f"Bronze DQ gate failed: {dq_report.summary_str()}")

    # Write to Iceberg
    (
        bronze.writeTo(f"{cfg.iceberg_catalog}.public.bronze_documents")
        .append()
    )

    duration_ms = (time.time() - start_ts) * 1000
    manifest.set_metrics(
        rows_in=rows_in,
        rows_out=rows_in,
        duration_ms=round(duration_ms, 2),
        dq_passed=dq_report.passed,
    )
    manifest.details["dq"] = dq_report.to_metrics()
    manifest.outputs.append(f"{cfg.iceberg_catalog}.public.bronze_documents")
    manifest.mark_success()
    manifest_path = write_manifest(cfg.manifest_root, manifest)

    emit_pipeline_metrics(
        stage=f"{_STAGE}_batch", run_id=manifest.run_id, status="success",
        rows_in=rows_in, rows_out=rows_in,
        duration_ms=duration_ms,
        dq_passed=dq_report.passed,
        dq_critical_failures=len(dq_report.critical_failures),
        dq_warnings=len(dq_report.warnings),
        manifest_path=manifest_path,
    )
    logger.info(f"Bronze batch ingestion completed. Manifest: {manifest_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bronze Ingestion Pipeline")
    parser.add_argument(
        "--mode", choices=["stream", "batch"], default="batch",
        help="'batch' reads Parquet from local HF download; 'stream' reads from Kafka"
    )
    args = parser.parse_args()

    cfg = load_config()
    spark = _build_spark(cfg)
    spark.sparkContext.setLogLevel("WARN")

    if args.mode == "stream":
        ingest_stream(spark, cfg)
    else:
        ingest_batch_from_parquet(spark, cfg)

    spark.stop()
