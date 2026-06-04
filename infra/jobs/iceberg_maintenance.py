"""Iceberg Table Maintenance — Vietnamese Legal Documents Pipeline.

Runs scheduled maintenance operations on all Iceberg tables to prevent
unbounded file accumulation and keep query performance optimal:

  1. rewrite_data_files    — Compact small files into optimal-size files
  2. expire_snapshots      — Remove snapshots older than SNAPSHOT_RETENTION_DAYS
  3. remove_orphan_files   — Delete unreferenced files in the warehouse

Emits a maintenance report JSON with table health metrics.

Usage (via Airflow weekly task or manual):
    python infra/jobs/iceberg_maintenance.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pyspark.sql import SparkSession

from common.config import load_config, AppConfig
from common.logger import get_logger
from common.manifests import RunManifest, write_manifest
from common.pipeline_metrics import emit_pipeline_metrics

logger = get_logger("iceberg_maintenance")
_STAGE = "iceberg_maintenance"

# Tables to maintain (in dependency order: Gold first, then Silver, Bronze last)
_MANAGED_TABLES = [
    "public.gold_daily_stats",
    "public.gold_legal_type_breakdown",
    "public.gold_issuing_authority",
    "public.gold_legal_field_stats",
    "public.gold_effect_status",
    "public.silver_documents",
    "public.silver_quarantine",
    "public.bronze_documents",
    "public.bronze_dlq",
]

SNAPSHOT_RETENTION_DAYS = 30
ORPHAN_OLDER_THAN_HOURS = 72


def _build_spark(cfg: AppConfig) -> SparkSession:
    return (
        SparkSession.builder
        .appName(f"{cfg.spark_app_name_prefix}-Iceberg-Maintenance")
        .master(cfg.spark_master)
        .config(
            "spark.jars.packages",
            ",".join([
                "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1",
                "org.apache.iceberg:iceberg-aws-bundle:1.6.1",
                "org.postgresql:postgresql:42.7.3",
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
        .config("spark.hadoop.fs.s3a.endpoint", cfg.minio_s3_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", cfg.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", cfg.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def _table_exists(spark: SparkSession, full_table: str) -> bool:
    try:
        spark.sql(f"SELECT 1 FROM {full_table} LIMIT 1")
        return True
    except Exception:
        return False


def run_maintenance(spark: SparkSession, cfg: AppConfig) -> dict:
    """Run all maintenance operations and return a report dict."""
    catalog = cfg.iceberg_catalog
    manifest = RunManifest(stage=_STAGE)
    start_ts = time.time()

    expire_before = (
        datetime.now(tz=timezone.utc) - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    ).strftime("%Y-%m-%d %H:%M:%S")

    orphan_before = (
        datetime.now(tz=timezone.utc) - timedelta(hours=ORPHAN_OLDER_THAN_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")

    report = {
        "maintenance_run_id": manifest.run_id,
        "started_at": manifest.started_at,
        "tables": {},
        "snapshot_retention_days": SNAPSHOT_RETENTION_DAYS,
        "orphan_cutoff_hours": ORPHAN_OLDER_THAN_HOURS,
    }

    for table_suffix in _MANAGED_TABLES:
        full_table = f"{catalog}.{table_suffix}"
        table_report: dict = {"table": full_table}

        if not _table_exists(spark, full_table):
            logger.info(f"Table not found, skipping: {full_table}")
            table_report["status"] = "skipped"
            report["tables"][table_suffix] = table_report
            continue

        logger.info(f"Maintaining: {full_table}")

        # 1. File compaction
        try:
            compaction_result = spark.sql(f"""
                CALL {catalog}.system.rewrite_data_files(
                    table => '{table_suffix}',
                    options => map('rewrite-all', 'false')
                )
            """).collect()
            table_report["compaction"] = {
                "rewritten_files": compaction_result[0][0] if compaction_result else 0,
                "added_files": compaction_result[0][1] if compaction_result else 0,
            }
            logger.info(f"Compaction done: {full_table} → {table_report['compaction']}")
        except Exception as e:
            table_report["compaction"] = {"error": str(e)}
            logger.warning(f"Compaction failed for {full_table}: {e}")

        # 2. Snapshot expiry
        try:
            expire_result = spark.sql(f"""
                CALL {catalog}.system.expire_snapshots(
                    table => '{table_suffix}',
                    older_than => TIMESTAMP '{expire_before}',
                    retain_last => 3
                )
            """).collect()
            table_report["snapshot_expiry"] = {
                "deleted_data_files": expire_result[0][0] if expire_result else 0,
                "deleted_manifest_files": expire_result[0][1] if expire_result else 0,
                "deleted_manifests": expire_result[0][2] if expire_result else 0,
            }
            logger.info(f"Snapshot expiry done: {full_table}")
        except Exception as e:
            table_report["snapshot_expiry"] = {"error": str(e)}
            logger.warning(f"Snapshot expiry failed for {full_table}: {e}")

        # 3. Orphan file removal
        try:
            orphan_result = spark.sql(f"""
                CALL {catalog}.system.remove_orphan_files(
                    table => '{table_suffix}',
                    older_than => TIMESTAMP '{orphan_before}'
                )
            """).collect()
            table_report["orphan_cleanup"] = {
                "orphan_file_locations": len(orphan_result),
            }
            logger.info(f"Orphan cleanup done: {full_table}")
        except Exception as e:
            table_report["orphan_cleanup"] = {"error": str(e)}
            logger.warning(f"Orphan cleanup failed for {full_table}: {e}")

        table_report["status"] = "completed"
        report["tables"][table_suffix] = table_report

    # Write maintenance report to manifests dir
    duration_ms = (time.time() - start_ts) * 1000
    report["duration_ms"] = round(duration_ms, 2)
    report["finished_at"] = datetime.now(tz=timezone.utc).isoformat()

    report_path = cfg.manifest_root / "iceberg_maintenance" / f"{manifest.run_id}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fp:
        json.dump(report, fp, indent=2, ensure_ascii=False)

    logger.info(f"Maintenance report: {report_path}")

    manifest.set_metrics(
        tables_maintained=sum(
            1 for t in report["tables"].values() if t.get("status") == "completed"
        ),
        duration_ms=round(duration_ms, 2),
    )
    manifest.mark_success()
    write_manifest(cfg.manifest_root, manifest)

    emit_pipeline_metrics(
        stage=_STAGE, run_id=manifest.run_id, status="success",
        duration_ms=duration_ms, manifest_path=report_path,
    )

    return report


if __name__ == "__main__":
    cfg = load_config()
    spark = _build_spark(cfg)
    spark.sparkContext.setLogLevel("WARN")

    report = run_maintenance(spark, cfg)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    spark.stop()
