"""Production-grade Airflow DAG for the Vietnamese Legal Documents Pipeline.

Schedule: Daily at 02:00 UTC (after dataset is refreshed)
Weekly:   Iceberg maintenance runs every Sunday at 03:00 UTC

Task flow:
  sensor_new_data
      ↓
  load_hf_dataset      ← Download Vietnamese legal docs from HuggingFace
      ↓
  bronze_ingest        ← Spark batch: HF Parquet → Iceberg Bronze
      ↓
  silver_cleanse       ← Spark batch: Bronze → Silver (DQ gate)
      ↓
  dq_gate_check        ← Read latest manifests, fail DAG on critical DQ failures
      ↓
  gold_aggregate       ← Spark batch: Silver → Gold (5 tables)
      ↓
  [weekly] iceberg_maintenance

SLA: Full pipeline must complete within 4 hours of start.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.utils.trigger_rule import TriggerRule

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------

_DEFAULT_ARGS = {
    "owner": "data-team",
    "depends_on_past": False,
    "start_date": datetime(2024, 1, 1),
    "email": [os.getenv("ALERT_EMAIL", "data-team@example.com")],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=4),
}

_SPARK_CONF = {
    "spark.sql.extensions": "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
    "spark.jars.packages": (
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,"
        "org.apache.iceberg:iceberg-aws-bundle:1.6.1,"
        "org.postgresql:postgresql:42.7.3,"
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
        "org.apache.hadoop:hadoop-aws:3.3.4"
    ),
    "spark.driver.memory": "2g",
    "spark.executor.memory": "2g",
    "spark.sql.files.maxPartitionBytes": "8388608",  # 8MB chunks to avoid OOM on large text
    "spark.sql.execution.arrow.pyspark.enabled": "false",  # Disable Arrow; avoids OOM when pandas serializes huge strings
    "spark.sql.parquet.enableVectorizedReader": "false", # Prevent batch memory allocation OOM for huge strings
}

_MANIFEST_ROOT = os.getenv("MANIFEST_ROOT", "./data/manifests")
_PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/airflow")

# ---------------------------------------------------------------------------
# Helper functions (PythonOperator callables)
# ---------------------------------------------------------------------------


def check_new_data_available(**context) -> str:
    """Sensor: check if new HuggingFace data or new MinIO files are available.

    Returns branch name: 'load_hf_dataset' (proceed) or 'skip_pipeline' (no new data).
    """
    import urllib.request
    hf_repo = os.getenv("HF_DATASET_REPO", "th1nhng0/vietnamese-legal-documents")

    # Check HuggingFace API for dataset info (no auth needed for public datasets)
    api_url = f"https://datasets-server.huggingface.co/info?dataset={hf_repo}"
    try:
        with urllib.request.urlopen(api_url, timeout=15) as resp:
            info = json.loads(resp.read())
            dataset_info = info.get("dataset_info", {})
            # Log dataset stats for debugging
            print(f"Dataset info retrieved: {list(dataset_info.keys())}")
    except Exception as e:
        print(f"Could not fetch HF dataset info: {e} — proceeding anyway")

    # Always proceed in production (sensor logic can be enhanced with watermark tracking)
    return "load_hf_dataset"


def run_hf_dataset_loader(**context) -> None:
    """Download Vietnamese legal documents from HuggingFace to MinIO."""
    import subprocess
    result = subprocess.run(
        ["python", f"{_PROJECT_ROOT}/services/ingestion/hf_dataset_loader.py"],
        capture_output=True,
        text=True,
        timeout=7200,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"HuggingFace loader failed (exit {result.returncode}):\n{result.stderr}"
        )
    print(result.stdout)


def check_dq_gate(**context) -> str:
    """Read Silver manifest and branch on DQ result.

    Returns 'gold_aggregate' if DQ passed, 'quarantine_alert' if failed.
    """
    manifest_dir = Path(_MANIFEST_ROOT) / "silver_cleanse"
    if not manifest_dir.exists():
        print("No Silver manifests found — proceeding to Gold")
        return "gold_aggregate"

    manifests = sorted(manifest_dir.glob("*.json"))
    if not manifests:
        print("No Silver manifests — proceeding to Gold")
        return "gold_aggregate"

    with manifests[-1].open(encoding="utf-8") as fp:
        manifest = json.load(fp)

    status = manifest.get("status", "unknown")
    dq_passed = manifest.get("details", {}).get("dq", {}).get("dq_passed", True)
    rows_quarantined = manifest.get("metrics", {}).get("rows_quarantined", 0)

    print(f"Latest Silver manifest: status={status}, dq_passed={dq_passed}, "
          f"rows_quarantined={rows_quarantined}")

    if status == "failed" or not dq_passed:
        print(f"DQ GATE FAILED — routing to quarantine_alert")
        return "quarantine_alert"

    print(f"DQ GATE PASSED — proceeding to gold_aggregate")
    return "gold_aggregate"


def send_quarantine_alert(**context) -> None:
    """Alert on critical DQ failures in Silver stage."""
    manifest_dir = Path(_MANIFEST_ROOT) / "silver_cleanse"
    manifests = sorted(manifest_dir.glob("*.json")) if manifest_dir.exists() else []

    latest = {}
    if manifests:
        with manifests[-1].open(encoding="utf-8") as fp:
            latest = json.load(fp)

    alert_msg = (
        f"🚨 SILVER DQ GATE FAILED\n"
        f"Run ID: {latest.get('run_id', 'unknown')}\n"
        f"Status: {latest.get('status', 'unknown')}\n"
        f"DQ Report: {json.dumps(latest.get('details', {}).get('dq', {}), indent=2)}\n"
        f"Manifest: {manifests[-1] if manifests else 'not found'}\n\n"
        f"Action required: Review quarantine table "
        f"(lakehouse.public.silver_quarantine) and fix upstream data."
    )

    # In production, integrate with Slack/PagerDuty here
    print(alert_msg)
    raise ValueError(f"Silver DQ gate failed — see alert above for details")


def run_iceberg_maintenance(**context) -> None:
    """Run Iceberg compaction + snapshot expiry + orphan cleanup."""
    import subprocess
    result = subprocess.run(
        ["python", f"{_PROJECT_ROOT}/infra/jobs/iceberg_maintenance.py"],
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Iceberg maintenance failed (exit {result.returncode}):\n{result.stderr}"
        )
    print(result.stdout)


def skip_pipeline_fn(**context) -> None:
    """No-op skip task."""
    print("No new data detected — pipeline skipped for this run.")


# ---------------------------------------------------------------------------
# Main DAG — Daily pipeline
# ---------------------------------------------------------------------------

with DAG(
    dag_id="vn_legal_document_pipeline",
    default_args=_DEFAULT_ARGS,
    description="Vietnamese Legal Documents: HuggingFace → Bronze → Silver → Gold (Iceberg)",
    schedule_interval="0 2 * * *",    # Daily at 02:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "spark", "iceberg", "vietnamese-legal", "bigdata"],
    sla_miss_callback=None,           # Add Slack/PagerDuty callback in production
) as dag:

    # Task 1: Sensor (branch)
    sensor_new_data = BranchPythonOperator(
        task_id="sensor_new_data",
        python_callable=check_new_data_available,
        provide_context=True,
    )

    # Task 2a: Load HuggingFace dataset
    load_hf_dataset = PythonOperator(
        task_id="load_hf_dataset",
        python_callable=run_hf_dataset_loader,
        provide_context=True,
        sla=timedelta(hours=1),
    )

    # Task 2b: Skip (no new data)
    skip_pipeline = PythonOperator(
        task_id="skip_pipeline",
        python_callable=skip_pipeline_fn,
        provide_context=True,
    )

    # Task 3: Bronze Spark ingestion
    bronze_ingest = SparkSubmitOperator(
        task_id="bronze_ingest",
        application=f"{_PROJECT_ROOT}/pipelines/bronze/ingest_raw.py",
        application_args=["--mode", "batch"],
        name="VNLegal-Bronze-Ingestion",
        conn_id="spark_local",
        verbose=False,
        conf={
            **_SPARK_CONF,
            "spark.master": "local[*]",
        },
        sla=timedelta(hours=1, minutes=30),
    )

    # Task 4: Silver Spark cleansing
    silver_cleanse = SparkSubmitOperator(
        task_id="silver_cleanse",
        application=f"{_PROJECT_ROOT}/pipelines/silver/cleanse_documents.py",
        application_args=["--mode", "batch"],
        name="VNLegal-Silver-Cleansing",
        conn_id="spark_local",
        verbose=False,
        conf={
            **_SPARK_CONF,
            "spark.master": "local[*]",
        },
        sla=timedelta(hours=1),
    )

    # Task 5: DQ gate check (branch)
    dq_gate = BranchPythonOperator(
        task_id="dq_gate_check",
        python_callable=check_dq_gate,
        provide_context=True,
    )

    # Task 6a: Gold aggregation
    gold_aggregate = SparkSubmitOperator(
        task_id="gold_aggregate",
        application=f"{_PROJECT_ROOT}/pipelines/gold/aggregate_metrics.py",
        name="VNLegal-Gold-Aggregation",
        conn_id="spark_local",
        verbose=False,
        conf={
            **_SPARK_CONF,
            "spark.master": "local[*]",
        },
        sla=timedelta(minutes=30),
    )

    # Task 6b: Quarantine alert (DQ failed)
    quarantine_alert = PythonOperator(
        task_id="quarantine_alert",
        python_callable=send_quarantine_alert,
        provide_context=True,
    )

    # Task graph
    sensor_new_data >> [load_hf_dataset, skip_pipeline]
    load_hf_dataset >> bronze_ingest >> silver_cleanse >> dq_gate
    dq_gate >> [gold_aggregate, quarantine_alert]


# ---------------------------------------------------------------------------
# Weekly Maintenance DAG
# ---------------------------------------------------------------------------

with DAG(
    dag_id="vn_legal_iceberg_maintenance",
    default_args=_DEFAULT_ARGS,
    description="Weekly Iceberg compaction, snapshot expiry, and orphan file cleanup",
    schedule_interval="0 3 * * 0",   # Every Sunday at 03:00 UTC
    catchup=False,
    max_active_runs=1,
    tags=["maintenance", "iceberg", "bigdata"],
) as maintenance_dag:

    iceberg_maintenance = PythonOperator(
        task_id="iceberg_maintenance",
        python_callable=run_iceberg_maintenance,
        provide_context=True,
        execution_timeout=timedelta(hours=2),
    )
