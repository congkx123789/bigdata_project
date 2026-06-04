"""Runtime configuration for the Vietnamese Legal Documents BigData Pipeline.

All environment variables are read here and packaged into an immutable AppConfig
dataclass. Pipeline files must NEVER hardcode credentials — they import this
module instead. Supports two deployment profiles: 'laptop' (dev) and 'server'.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Raw env-var readers with typed defaults
# ---------------------------------------------------------------------------

def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# AppConfig dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration container for the entire pipeline.

    Every pipeline stage receives this object — no hardcoded credentials
    anywhere else in the codebase.
    """

    # Deployment
    environment: str
    deployment_profile: str
    project_name: str

    # MinIO / S3
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_use_ssl: bool
    s3_bucket_bronze: str
    s3_bucket_silver: str
    s3_bucket_gold: str
    s3_bucket_warehouse: str
    s3_bucket_checkpoints: str

    # PostgreSQL / Iceberg Catalog
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    iceberg_catalog: str
    iceberg_warehouse: str

    # Kafka
    kafka_bootstrap_servers: str
    kafka_topic_raw: str          # Raw document text from OCR/extraction
    kafka_topic_dlq: str          # Dead-letter queue for bad records
    kafka_topic_partitions: int
    kafka_topic_replication_factor: int

    # Milvus (Vector Store)
    milvus_host: str
    milvus_port: int
    milvus_collection: str
    milvus_dim: int

    # Embedding Model
    embedding_model: str
    embedding_device: str

    # LLM
    ollama_url: str
    ollama_model: str
    gemini_api_key: str

    # Spark
    spark_master: str
    spark_app_name_prefix: str
    spark_sql_shuffle_partitions: int

    # Streaming
    stream_trigger_seconds: int
    stream_max_offsets_per_trigger: int
    stream_timeout_seconds: int

    # HuggingFace Dataset
    hf_dataset_repo: str
    hf_token: str

    # Observability
    manifest_root: Path
    pipeline_metrics_log_path: str
    log_level: str
    dq_fail_on_error: bool

    # Local paths
    local_data_root: Path
    checkpoint_root: Path

    # ---------------------------------------------------------------------------
    # Derived helpers
    # ---------------------------------------------------------------------------

    @property
    def minio_s3_endpoint(self) -> str:
        scheme = "https" if self.minio_use_ssl else "http"
        return f"{scheme}://{self.minio_endpoint}"

    @property
    def postgres_jdbc_uri(self) -> str:
        return (
            f"jdbc:postgresql://{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def iceberg_jdbc_catalog_uri(self) -> str:
        return self.postgres_jdbc_uri


def load_config(
    *,
    manifest_root: Optional[str | Path] = None,
    local_data_root: Optional[str | Path] = None,
    checkpoint_root: Optional[str | Path] = None,
) -> AppConfig:
    """Build AppConfig from environment variables.

    Args:
        manifest_root: Override default manifest directory.
        local_data_root: Override default local data root.
        checkpoint_root: Override default checkpoint root.

    Returns:
        Fully populated, immutable AppConfig.
    """
    resolved_manifest_root = Path(manifest_root) if manifest_root else Path(
        _env("MANIFEST_ROOT", "./data/manifests")
    )
    resolved_local_data_root = Path(local_data_root) if local_data_root else Path(
        _env("LOCAL_DATA_ROOT", "./data")
    )
    resolved_checkpoint_root = Path(checkpoint_root) if checkpoint_root else Path(
        _env("CHECKPOINT_ROOT", "./data/checkpoints")
    )

    return AppConfig(
        # Deployment
        environment=_env("ENV", "local"),
        deployment_profile=_env("DEPLOYMENT_PROFILE", "laptop"),
        project_name=_env("PROJECT_NAME", "vn-legal-rag"),

        # MinIO / S3
        minio_endpoint=_env("MINIO_ENDPOINT", "minio:9000"),
        minio_access_key=_env("MINIO_ACCESS_KEY", "admin"),
        minio_secret_key=_env("MINIO_SECRET_KEY", "password123"),
        minio_use_ssl=_env_bool("MINIO_USE_SSL", False),
        s3_bucket_bronze=_env("S3_BUCKET_BRONZE", "legal-bronze"),
        s3_bucket_silver=_env("S3_BUCKET_SILVER", "legal-silver"),
        s3_bucket_gold=_env("S3_BUCKET_GOLD", "legal-gold"),
        s3_bucket_warehouse=_env("S3_BUCKET_WAREHOUSE", "documents"),
        s3_bucket_checkpoints=_env("S3_BUCKET_CHECKPOINTS", "legal-checkpoints"),

        # PostgreSQL / Iceberg Catalog
        postgres_host=_env("POSTGRES_HOST", "postgres"),
        postgres_port=_env_int("POSTGRES_PORT", 5432),
        postgres_db=_env("POSTGRES_DB", "document_db"),
        postgres_user=_env("POSTGRES_USER", "admin"),
        postgres_password=_env("POSTGRES_PASSWORD", "password123"),
        iceberg_catalog=_env("ICEBERG_CATALOG", "lakehouse"),
        iceberg_warehouse=_env("ICEBERG_WAREHOUSE", "s3a://documents/warehouse"),

        # Kafka
        kafka_bootstrap_servers=_env("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        kafka_topic_raw=_env("KAFKA_TOPIC_RAW", "document-extracted-text"),
        kafka_topic_dlq=_env("KAFKA_TOPIC_DLQ", "document-dlq"),
        kafka_topic_partitions=_env_int("KAFKA_TOPIC_PARTITIONS", 3),
        kafka_topic_replication_factor=_env_int("KAFKA_TOPIC_REPLICATION_FACTOR", 1),

        # Milvus
        milvus_host=_env("MILVUS_HOST", "milvus-standalone"),
        milvus_port=_env_int("MILVUS_PORT", 19530),
        milvus_collection=_env("MILVUS_COLLECTION", "document_vectors"),
        milvus_dim=_env_int("MILVUS_DIM", 1024),

        # Embedding
        embedding_model=_env("EMBEDDING_MODEL", "BAAI/bge-m3"),
        embedding_device=_env("EMBEDDING_DEVICE", "cuda"),

        # LLM
        ollama_url=_env("OLLAMA_URL", "http://heritage_ollama:11434"),
        ollama_model=_env("OLLAMA_MODEL", "llama3.2:1b"),
        gemini_api_key=_env("GEMINI_API_KEY", ""),

        # Spark
        spark_master=_env("SPARK_MASTER", "local[*]"),
        spark_app_name_prefix=_env("SPARK_APP_NAME_PREFIX", "VNLegal"),
        spark_sql_shuffle_partitions=_env_int("SPARK_SQL_SHUFFLE_PARTITIONS", 8),

        # Streaming
        stream_trigger_seconds=_env_int("STREAM_TRIGGER_SECONDS", 60),
        stream_max_offsets_per_trigger=_env_int("STREAM_MAX_OFFSETS_PER_TRIGGER", 500),
        stream_timeout_seconds=_env_int("STREAM_TIMEOUT_SECONDS", 3600),

        # HuggingFace
        hf_dataset_repo=_env(
            "HF_DATASET_REPO", "th1nhng0/vietnamese-legal-documents"
        ),
        hf_token=_env("HF_TOKEN", ""),

        # Observability
        manifest_root=resolved_manifest_root,
        pipeline_metrics_log_path=_env("PIPELINE_METRICS_LOG_PATH", ""),
        log_level=_env("LOG_LEVEL", "INFO"),
        dq_fail_on_error=_env_bool("DQ_FAIL_ON_ERROR", True),

        # Local paths
        local_data_root=resolved_local_data_root,
        checkpoint_root=resolved_checkpoint_root,
    )
