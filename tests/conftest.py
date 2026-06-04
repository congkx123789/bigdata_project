"""Pytest configuration and shared fixtures for bigdata_project tests."""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_env(monkeypatch):
    """Remove all pipeline env-vars for isolation."""
    env_keys = [
        "MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY",
        "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB",
        "POSTGRES_USER", "POSTGRES_PASSWORD",
        "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_TOPIC_RAW", "KAFKA_TOPIC_DLQ",
        "MILVUS_HOST", "MILVUS_PORT",
        "SPARK_MASTER", "SPARK_SQL_SHUFFLE_PARTITIONS",
        "HF_DATASET_REPO", "HF_TOKEN",
        "MANIFEST_ROOT", "PIPELINE_METRICS_LOG_PATH", "DQ_FAIL_ON_ERROR",
    ]
    for key in env_keys:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def tmp_manifest_root(tmp_path: Path) -> Path:
    """Temporary manifest directory for test isolation."""
    manifest_root = tmp_path / "manifests"
    manifest_root.mkdir(parents=True)
    return manifest_root


@pytest.fixture
def sample_bronze_record() -> dict:
    """A valid Bronze record for testing."""
    return {
        "doc_id": "12345",
        "source_bucket": "huggingface",
        "source_path": "th1nhng0/vietnamese-legal-documents",
        "raw_text": "Điều 1. Phạm vi điều chỉnh: Luật này quy định về tổ chức và hoạt động của Quốc hội.",
        "content_html": "<p>Điều 1. Phạm vi điều chỉnh: Luật này...</p>",
        "title": "Luật Quốc hội 2014",
        "so_ky_hieu": "57/2014/QH13",
        "loai_van_ban": "luật",
        "ngay_ban_hanh": "20/11/2014",
        "co_quan_ban_hanh": "Quốc hội",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "record_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "dedupe_key": "12345|luật",
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
        "ingest_date": "2024-06-01",
        "pipeline_run_id": "test_run_001",
    }


@pytest.fixture
def sample_silver_record() -> dict:
    """A valid Silver record for testing."""
    return {
        "doc_id": "12345",
        "record_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
        "clean_text": "Điều 1. Phạm vi điều chỉnh: Luật này quy định về tổ chức và hoạt động của Quốc hội Việt Nam.",
        "title": "Luật Quốc hội 2014",
        "char_count": 95,
        "word_count": 18,
        "quality_score": 0.0475,
        "so_ky_hieu": "57/2014/QH13",
        "loai_van_ban": "luật",
        "issuance_date": "2014-11-20",
        "effective_date": "2016-01-01",
        "expiry_date": None,
        "co_quan_ban_hanh": "Quốc hội",
        "linh_vuc": "Tổ chức bộ máy nhà nước",
        "nganh": "Nhà nước",
        "nguoi_ky": "Nguyễn Sinh Hùng",
        "effect_status": "còn hiệu lực",
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
        "processed_at": datetime.now(tz=timezone.utc).isoformat(),
        "ingest_date": "2024-06-01",
        "pipeline_run_id": "test_run_001",
    }
