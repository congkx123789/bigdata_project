"""Unit tests for common/config.py — AppConfig loading and env-var overrides."""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from common.config import load_config, AppConfig


class TestLoadConfig:
    def test_default_config_loads(self):
        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.project_name == "vn-legal-rag"
        assert cfg.environment == "local"

    def test_env_override_minio_endpoint(self):
        with patch.dict(os.environ, {"MINIO_ENDPOINT": "custom-minio:9000"}):
            cfg = load_config()
        assert cfg.minio_endpoint == "custom-minio:9000"

    def test_env_override_kafka_servers(self):
        with patch.dict(os.environ, {"KAFKA_BOOTSTRAP_SERVERS": "broker1:9092,broker2:9092"}):
            cfg = load_config()
        assert cfg.kafka_bootstrap_servers == "broker1:9092,broker2:9092"

    def test_env_override_hf_repo(self):
        with patch.dict(os.environ, {
            "HF_DATASET_REPO": "custom-user/custom-dataset"
        }):
            cfg = load_config()
        assert cfg.hf_dataset_repo == "custom-user/custom-dataset"

    def test_default_hf_repo_is_correct(self):
        cfg = load_config()
        assert cfg.hf_dataset_repo == "th1nhng0/vietnamese-legal-documents"

    def test_minio_s3_endpoint_http(self):
        cfg = load_config()
        assert cfg.minio_s3_endpoint.startswith("http://")

    def test_minio_s3_endpoint_https_when_ssl(self):
        with patch.dict(os.environ, {"MINIO_USE_SSL": "true"}):
            cfg = load_config()
        assert cfg.minio_s3_endpoint.startswith("https://")

    def test_postgres_jdbc_uri_format(self):
        with patch.dict(os.environ, {
            "POSTGRES_HOST": "db-host",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "mydb",
        }):
            cfg = load_config()
        assert "jdbc:postgresql://db-host:5432/mydb" == cfg.postgres_jdbc_uri

    def test_manifest_root_override(self):
        cfg = load_config(manifest_root="/tmp/test_manifests")
        assert cfg.manifest_root == Path("/tmp/test_manifests")

    def test_dq_fail_on_error_true_by_default(self):
        cfg = load_config()
        assert cfg.dq_fail_on_error is True

    def test_dq_fail_on_error_can_be_disabled(self):
        with patch.dict(os.environ, {"DQ_FAIL_ON_ERROR": "false"}):
            cfg = load_config()
        assert cfg.dq_fail_on_error is False

    def test_int_env_vars_parsed_correctly(self):
        with patch.dict(os.environ, {
            "MILVUS_PORT": "19531",
            "SPARK_SQL_SHUFFLE_PARTITIONS": "16",
        }):
            cfg = load_config()
        assert cfg.milvus_port == 19531
        assert cfg.spark_sql_shuffle_partitions == 16

    def test_config_is_immutable(self):
        cfg = load_config()
        with pytest.raises(Exception):  # dataclass(frozen=True) raises FrozenInstanceError
            cfg.project_name = "hacked"

    def test_s3_buckets_configurable(self):
        with patch.dict(os.environ, {
            "S3_BUCKET_BRONZE": "my-bronze",
            "S3_BUCKET_SILVER": "my-silver",
            "S3_BUCKET_GOLD": "my-gold",
        }):
            cfg = load_config()
        assert cfg.s3_bucket_bronze == "my-bronze"
        assert cfg.s3_bucket_silver == "my-silver"
        assert cfg.s3_bucket_gold == "my-gold"
