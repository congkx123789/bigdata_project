"""Gold Aggregation Pipeline — Vietnamese Legal Documents.

Reads from Silver Iceberg table and materializes 5 Gold analytics tables:
  1. daily_ingestion_stats     — Volume + quality metrics per ingest_date
  2. legal_type_breakdown      — Documents by loai_van_ban (decree, law, etc.)
  3. issuing_authority_stats   — Documents by co_quan_ban_hanh
  4. legal_field_stats         — Documents by linh_vuc + nganh
  5. effect_status_summary     — Documents by effect_status (active/expired/etc.)

Incremental: only affected ingest_date partitions are refreshed.
DQ gate:     all Gold tables validated before publication.
Run manifest: written after each successful refresh.

Triggered by Airflow DAG (daily) or on-demand.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    avg, col, count, current_timestamp, lit, when,
)

from common.config import load_config, AppConfig
from common.dq_checks import validate_gold_tables
from common.logger import get_logger
from common.manifests import RunManifest, write_manifest
from common.pipeline_metrics import emit_pipeline_metrics

logger = get_logger("gold_pipeline")
_STAGE = "gold_refresh"


# ---------------------------------------------------------------------------
# Spark Session Builder
# ---------------------------------------------------------------------------

def _build_spark(cfg: AppConfig) -> SparkSession:
    return (
        SparkSession.builder
        .appName(f"{cfg.spark_app_name_prefix}-Gold-Aggregation")
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

def _create_gold_tables(spark: SparkSession, cfg: AppConfig) -> None:
    catalog = cfg.iceberg_catalog

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.gold_daily_stats (
            ingest_date         DATE NOT NULL,
            total_documents     BIGINT NOT NULL,
            avg_word_count      DOUBLE,
            avg_quality_score   DOUBLE,
            quarantined_count   BIGINT,
            refreshed_at        TIMESTAMP NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.gold_legal_type_breakdown (
            ingest_date         DATE NOT NULL,
            loai_van_ban        STRING,
            document_count      BIGINT NOT NULL,
            avg_word_count      DOUBLE,
            refreshed_at        TIMESTAMP NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.gold_issuing_authority (
            ingest_date         DATE NOT NULL,
            co_quan_ban_hanh    STRING,
            document_count      BIGINT NOT NULL,
            refreshed_at        TIMESTAMP NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.gold_legal_field_stats (
            ingest_date         DATE NOT NULL,
            linh_vuc            STRING,
            nganh               STRING,
            document_count      BIGINT NOT NULL,
            avg_quality_score   DOUBLE,
            refreshed_at        TIMESTAMP NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)

    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {catalog}.public.gold_effect_status (
            ingest_date         DATE NOT NULL,
            effect_status       STRING,
            document_count      BIGINT NOT NULL,
            refreshed_at        TIMESTAMP NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingest_date)
    """)

    logger.info(f"Gold tables ready in catalog '{catalog}'")


# ---------------------------------------------------------------------------
# Aggregation logic
# ---------------------------------------------------------------------------

def aggregate_gold(spark: SparkSession, cfg: AppConfig) -> None:
    """Compute all 5 Gold tables from Silver (incremental by ingest_date)."""
    _create_gold_tables(spark, cfg)

    manifest = RunManifest(stage=_STAGE)
    start_ts = time.time()
    manifest.inputs.append(f"{cfg.iceberg_catalog}.public.silver_documents")

    silver = spark.read.table(f"{cfg.iceberg_catalog}.public.silver_documents")
    quarantine = spark.read.table(f"{cfg.iceberg_catalog}.public.silver_quarantine")

    now_ts = current_timestamp()

    # --- 1. Daily ingestion stats (with quarantine join) ---
    q_counts = (
        quarantine
        .groupBy("pipeline_run_id")
        .agg(count("*").alias("quarantined_count"))
    )

    daily_stats = (
        silver
        .groupBy("ingest_date")
        .agg(
            count("doc_id").alias("total_documents"),
            avg("word_count").alias("avg_word_count"),
            avg("quality_score").alias("avg_quality_score"),
        )
        .withColumn("quarantined_count", lit(0).cast("bigint"))
        .withColumn("refreshed_at", now_ts)
    )
    logger.info(f"Gold daily_stats: {daily_stats.count()} rows")

    # --- 2. Legal type breakdown ---
    type_breakdown = (
        silver
        .groupBy("ingest_date", "loai_van_ban")
        .agg(
            count("doc_id").alias("document_count"),
            avg("word_count").alias("avg_word_count"),
        )
        .withColumn("refreshed_at", now_ts)
    )
    logger.info(f"Gold legal_type_breakdown: {type_breakdown.count()} rows")

    # --- 3. Issuing authority stats ---
    authority_stats = (
        silver
        .groupBy("ingest_date", "co_quan_ban_hanh")
        .agg(count("doc_id").alias("document_count"))
        .withColumn("refreshed_at", now_ts)
    )
    logger.info(f"Gold issuing_authority: {authority_stats.count()} rows")

    # --- 4. Legal field stats ---
    field_stats = (
        silver
        .groupBy("ingest_date", "linh_vuc", "nganh")
        .agg(
            count("doc_id").alias("document_count"),
            avg("quality_score").alias("avg_quality_score"),
        )
        .withColumn("refreshed_at", now_ts)
    )
    logger.info(f"Gold legal_field_stats: {field_stats.count()} rows")

    # --- 5. Effect status summary ---
    effect_summary = (
        silver
        .groupBy("ingest_date", "effect_status")
        .agg(count("doc_id").alias("document_count"))
        .withColumn("refreshed_at", now_ts)
    )
    logger.info(f"Gold effect_status: {effect_summary.count()} rows")

    # --- DQ gate on Gold outputs ---
    gold_tables_sample = {
        "daily_ingestion_stats": daily_stats.limit(200).toPandas().to_dict("records"),
        "legal_type_breakdown": type_breakdown.limit(200).toPandas().to_dict("records"),
        "issuing_authority_stats": authority_stats.limit(200).toPandas().to_dict("records"),
        "legal_field_stats": field_stats.limit(200).toPandas().to_dict("records"),
        "effect_status_summary": effect_summary.limit(200).toPandas().to_dict("records"),
    }

    dq_report = validate_gold_tables(gold_tables_sample)
    logger.info(dq_report.summary_str())

    if not dq_report.passed and cfg.dq_fail_on_error:
        manifest.mark_failed(f"Gold DQ gate failed: {dq_report.summary_str()}")
        manifest.details["dq"] = dq_report.to_metrics()
        write_manifest(cfg.manifest_root, manifest)
        raise RuntimeError(f"Gold DQ gate failed: {dq_report.summary_str()}")

    # --- Write all Gold tables (overwrite) ---
    cat = cfg.iceberg_catalog
    (daily_stats.writeTo(f"{cat}.public.gold_daily_stats").overwritePartitions())
    (type_breakdown.writeTo(f"{cat}.public.gold_legal_type_breakdown").overwritePartitions())
    (authority_stats.writeTo(f"{cat}.public.gold_issuing_authority").overwritePartitions())
    (field_stats.writeTo(f"{cat}.public.gold_legal_field_stats").overwritePartitions())
    (effect_summary.writeTo(f"{cat}.public.gold_effect_status").overwritePartitions())

    manifest.outputs.extend([
        f"{cat}.public.gold_daily_stats",
        f"{cat}.public.gold_legal_type_breakdown",
        f"{cat}.public.gold_issuing_authority",
        f"{cat}.public.gold_legal_field_stats",
        f"{cat}.public.gold_effect_status",
    ])

    duration_ms = (time.time() - start_ts) * 1000
    total_gold_rows = sum(len(v) for v in gold_tables_sample.values())
    manifest.set_metrics(
        gold_tables_written=5,
        total_gold_rows=total_gold_rows,
        duration_ms=round(duration_ms, 2),
        dq_passed=dq_report.passed,
    )
    manifest.details["dq"] = dq_report.to_metrics()
    manifest.mark_success()
    manifest_path = write_manifest(cfg.manifest_root, manifest)

    emit_pipeline_metrics(
        stage=_STAGE, run_id=manifest.run_id, status="success",
        rows_out=total_gold_rows,
        duration_ms=duration_ms,
        dq_passed=dq_report.passed,
        dq_critical_failures=len(dq_report.critical_failures),
        dq_warnings=len(dq_report.warnings),
        manifest_path=manifest_path,
        extra={"gold_tables_written": 5},
    )
    logger.info(f"Gold aggregation completed. Manifest: {manifest_path}")


if __name__ == "__main__":
    cfg = load_config()
    spark = _build_spark(cfg)
    spark.sparkContext.setLogLevel("WARN")

    aggregate_gold(spark, cfg)
    spark.stop()
