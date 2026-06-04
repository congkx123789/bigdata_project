"""Spark schema definitions for the Vietnamese Legal Documents pipeline.

All Spark StructType schemas are defined here as the single source of truth.
Pipeline files import these schemas instead of redefining them inline.

Dataset: th1nhng0/vietnamese-legal-documents (HuggingFace)
Subsets:  content (id, content_html)
          metadata (id, title, so_ky_hieu, ngay_ban_hanh, loai_van_ban,
                    ngay_co_hieu_luc, ngay_het_hieu_luc, nguon_thu_thap,
                    nganh, linh_vuc, co_quan_ban_hanh, nguoi_ky,
                    tinh_trang_hieu_luc, ...)
          relationships (doc_id, other_doc_id, relationship)
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
    BooleanType,
    DateType,
)

# ---------------------------------------------------------------------------
# HuggingFace raw subsets (as they arrive from the dataset)
# ---------------------------------------------------------------------------

HF_CONTENT_SCHEMA = StructType([
    StructField("id", StringType(), nullable=True),
    StructField("content_html", StringType(), nullable=True),
])

HF_METADATA_SCHEMA = StructType([
    StructField("id", LongType(), nullable=True),
    StructField("title", StringType(), nullable=True),
    StructField("so_ky_hieu", StringType(), nullable=True),       # Document number
    StructField("ngay_ban_hanh", StringType(), nullable=True),    # Issuance date
    StructField("loai_van_ban", StringType(), nullable=True),     # Document type
    StructField("ngay_co_hieu_luc", StringType(), nullable=True), # Effective date
    StructField("ngay_het_hieu_luc", StringType(), nullable=True),# Expiry date
    StructField("nguon_thu_thap", StringType(), nullable=True),   # Source URL
    StructField("ngay_dang_cong_bao", StringType(), nullable=True),
    StructField("nganh", StringType(), nullable=True),            # Industry sector
    StructField("linh_vuc", StringType(), nullable=True),         # Legal field
    StructField("co_quan_ban_hanh", StringType(), nullable=True), # Issuing authority
    StructField("chuc_danh", StringType(), nullable=True),        # Signer title
    StructField("nguoi_ky", StringType(), nullable=True),         # Signer name
    StructField("pham_vi", StringType(), nullable=True),          # Scope
    StructField("thong_tin_ap_dung", StringType(), nullable=True),
    StructField("tinh_trang_hieu_luc", StringType(), nullable=True), # Effect status
])

HF_RELATIONSHIPS_SCHEMA = StructType([
    StructField("doc_id", LongType(), nullable=True),
    StructField("other_doc_id", StringType(), nullable=True),
    StructField("relationship", StringType(), nullable=True),  # amends, cites, repeals...
])

# ---------------------------------------------------------------------------
# Bronze Layer — append-only raw ingestion from Kafka/HuggingFace
# Deterministic dedup identity added here for rerun-safety.
# ---------------------------------------------------------------------------

BRONZE_SCHEMA = StructType([
    # Source identity
    StructField("doc_id", StringType(), nullable=False),
    StructField("source_bucket", StringType(), nullable=True),   # minio bucket or "huggingface"
    StructField("source_path", StringType(), nullable=True),     # s3 path or hf subset

    # Raw document content
    StructField("raw_text", StringType(), nullable=True),        # Stripped HTML text
    StructField("content_html", StringType(), nullable=True),    # Original HTML

    # Legal metadata (from HF metadata subset)
    StructField("title", StringType(), nullable=True),
    StructField("so_ky_hieu", StringType(), nullable=True),
    StructField("loai_van_ban", StringType(), nullable=True),
    StructField("ngay_ban_hanh", StringType(), nullable=True),
    StructField("ngay_co_hieu_luc", StringType(), nullable=True),
    StructField("ngay_het_hieu_luc", StringType(), nullable=True),
    StructField("co_quan_ban_hanh", StringType(), nullable=True),
    StructField("linh_vuc", StringType(), nullable=True),
    StructField("nganh", StringType(), nullable=True),
    StructField("nguoi_ky", StringType(), nullable=True),
    StructField("tinh_trang_hieu_luc", StringType(), nullable=True),

    # Dedup identity (deterministic, rerun-safe)
    StructField("record_hash", StringType(), nullable=False),    # SHA256(doc_id + raw_text[:200])
    StructField("dedupe_key", StringType(), nullable=False),     # doc_id + loai_van_ban

    # Ingestion metadata
    StructField("ingested_at", TimestampType(), nullable=False),
    StructField("ingest_date", DateType(), nullable=False),      # Partition key
    StructField("pipeline_run_id", StringType(), nullable=True),
])

# ---------------------------------------------------------------------------
# Silver Layer — normalized, validated, deduplicated
# ---------------------------------------------------------------------------

SILVER_SCHEMA = StructType([
    # Identity
    StructField("doc_id", StringType(), nullable=False),
    StructField("record_hash", StringType(), nullable=False),

    # Cleaned content
    StructField("clean_text", StringType(), nullable=True),      # HTML stripped + normalized
    StructField("title", StringType(), nullable=True),

    # Structural metrics
    StructField("char_count", IntegerType(), nullable=True),     # Accurate character count
    StructField("word_count", IntegerType(), nullable=True),     # Vietnamese-aware word count
    StructField("quality_score", DoubleType(), nullable=True),   # 0.0 – 1.0 quality proxy

    # Legal metadata (normalized)
    StructField("so_ky_hieu", StringType(), nullable=True),
    StructField("loai_van_ban", StringType(), nullable=True),    # Normalized doc type
    StructField("issuance_date", DateType(), nullable=True),     # Parsed from ngay_ban_hanh
    StructField("effective_date", DateType(), nullable=True),
    StructField("expiry_date", DateType(), nullable=True),
    StructField("co_quan_ban_hanh", StringType(), nullable=True),
    StructField("linh_vuc", StringType(), nullable=True),
    StructField("nganh", StringType(), nullable=True),
    StructField("nguoi_ky", StringType(), nullable=True),
    StructField("effect_status", StringType(), nullable=True),   # còn_hiệu_lực / hết_hiệu_lực

    # Silver metadata
    StructField("ingested_at", TimestampType(), nullable=False),
    StructField("processed_at", TimestampType(), nullable=False),
    StructField("ingest_date", DateType(), nullable=False),      # Partition key
    StructField("pipeline_run_id", StringType(), nullable=True),
])

# ---------------------------------------------------------------------------
# Silver Quarantine — records rejected by DQ gates
# ---------------------------------------------------------------------------

SILVER_QUARANTINE_SCHEMA = StructType([
    StructField("doc_id", StringType(), nullable=True),
    StructField("record_hash", StringType(), nullable=True),
    StructField("raw_text_preview", StringType(), nullable=True),
    StructField("rejection_reason", StringType(), nullable=False),
    StructField("dq_rule", StringType(), nullable=False),
    StructField("quarantined_at", TimestampType(), nullable=False),
    StructField("pipeline_run_id", StringType(), nullable=True),
])

# ---------------------------------------------------------------------------
# Gold Layer — business-facing aggregations
# ---------------------------------------------------------------------------

GOLD_DAILY_STATS_SCHEMA = StructType([
    StructField("ingest_date", DateType(), nullable=False),
    StructField("total_documents", LongType(), nullable=False),
    StructField("avg_word_count", DoubleType(), nullable=True),
    StructField("avg_quality_score", DoubleType(), nullable=True),
    StructField("quarantined_count", LongType(), nullable=True),
    StructField("refreshed_at", TimestampType(), nullable=False),
])

GOLD_LEGAL_TYPE_BREAKDOWN_SCHEMA = StructType([
    StructField("ingest_date", DateType(), nullable=False),
    StructField("loai_van_ban", StringType(), nullable=True),    # Document type
    StructField("document_count", LongType(), nullable=False),
    StructField("avg_word_count", DoubleType(), nullable=True),
    StructField("refreshed_at", TimestampType(), nullable=False),
])

GOLD_ISSUING_AUTHORITY_SCHEMA = StructType([
    StructField("ingest_date", DateType(), nullable=False),
    StructField("co_quan_ban_hanh", StringType(), nullable=True),
    StructField("document_count", LongType(), nullable=False),
    StructField("refreshed_at", TimestampType(), nullable=False),
])

GOLD_LEGAL_FIELD_SCHEMA = StructType([
    StructField("ingest_date", DateType(), nullable=False),
    StructField("linh_vuc", StringType(), nullable=True),        # Legal field
    StructField("nganh", StringType(), nullable=True),           # Industry
    StructField("document_count", LongType(), nullable=False),
    StructField("avg_quality_score", DoubleType(), nullable=True),
    StructField("refreshed_at", TimestampType(), nullable=False),
])

GOLD_EFFECT_STATUS_SCHEMA = StructType([
    StructField("ingest_date", DateType(), nullable=False),
    StructField("effect_status", StringType(), nullable=True),
    StructField("document_count", LongType(), nullable=False),
    StructField("refreshed_at", TimestampType(), nullable=False),
])

# Allowed values for validation
ALLOWED_EFFECT_STATUSES = frozenset({
    "còn hiệu lực",
    "hết hiệu lực",
    "chưa có hiệu lực",
    "không xác định",
})

ALLOWED_DOC_TYPES = frozenset({
    "luật",
    "bộ luật",
    "pháp lệnh",
    "nghị định",
    "nghị quyết",
    "thông tư",
    "quyết định",
    "chỉ thị",
    "công văn",
    "hiến pháp",
    "lệnh",
    "thông báo",
    "hướng dẫn",
})

# Required columns for DQ checks
BRONZE_REQUIRED_COLS = ("doc_id", "raw_text", "record_hash", "dedupe_key", "ingested_at")
SILVER_REQUIRED_COLS = ("doc_id", "record_hash", "clean_text", "char_count", "word_count",
                        "quality_score", "processed_at")
SILVER_CRITICAL_COLS = ("doc_id", "clean_text", "processed_at")
