"""Unit tests for common/dq_checks.py — Data Quality gate rules.

Tests cover:
  - Bronze DQ: null doc_id, empty text, missing hashes, duplicates
  - Silver DQ: text length, word count, quality score, quarantine splitting
  - Gold DQ: required columns, non-negative metrics
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from common.dq_checks import (
    validate_bronze_records,
    validate_silver_records,
    validate_gold_tables,
    DQ_SEVERITY_CRITICAL,
    DQ_SEVERITY_WARNING,
)


# ---------------------------------------------------------------------------
# Bronze DQ tests
# ---------------------------------------------------------------------------

class TestBronzeDQ:
    def _make_bronze_record(self, **overrides) -> dict:
        base = {
            "doc_id": "doc_001",
            "raw_text": "Luật này quy định về quyền và nghĩa vụ của công dân Việt Nam.",
            "record_hash": "abc123",
            "dedupe_key": "doc_001|luật",
            "ingested_at": datetime.now(tz=timezone.utc),
        }
        base.update(overrides)
        return base

    def test_valid_batch_passes(self):
        records = [self._make_bronze_record(doc_id=f"doc_{i:03d}", record_hash=f"hash_{i}")
                   for i in range(5)]
        report = validate_bronze_records(records)
        assert report.passed
        assert len(report.critical_failures) == 0

    def test_empty_batch_is_warning_only(self):
        report = validate_bronze_records([])
        # Empty batch is a warning, not a critical failure
        assert report.passed  # No critical failures
        assert len(report.warnings) >= 1

    def test_null_doc_id_fails_critical(self):
        records = [
            self._make_bronze_record(doc_id=None),
            self._make_bronze_record(doc_id="doc_002", record_hash="hash_002"),
        ]
        report = validate_bronze_records(records)
        assert not report.passed
        failing = [r for r in report.rules
                   if r.name == "bronze_doc_id_not_null" and not r.passed]
        assert len(failing) == 1
        assert failing[0].severity == DQ_SEVERITY_CRITICAL

    def test_empty_raw_text_fails_critical(self):
        records = [self._make_bronze_record(raw_text="")]
        report = validate_bronze_records(records)
        assert not report.passed
        failing = [r for r in report.rules
                   if r.name == "bronze_raw_text_not_empty" and not r.passed]
        assert len(failing) == 1

    def test_missing_record_hash_fails_critical(self):
        records = [self._make_bronze_record(record_hash=None)]
        report = validate_bronze_records(records)
        assert not report.passed

    def test_duplicate_hashes_in_batch_is_warning(self):
        records = [
            self._make_bronze_record(record_hash="same_hash"),
            self._make_bronze_record(doc_id="doc_002", record_hash="same_hash"),
        ]
        report = validate_bronze_records(records)
        # Duplicate hash is warning, not critical — overall should pass critical check
        dup_rule = next(r for r in report.rules
                        if r.name == "bronze_no_duplicate_hashes_in_batch")
        assert dup_rule.severity == DQ_SEVERITY_WARNING
        assert not dup_rule.passed


# ---------------------------------------------------------------------------
# Silver DQ tests
# ---------------------------------------------------------------------------

class TestSilverDQ:
    def _make_silver_record(self, **overrides) -> dict:
        base = {
            "doc_id": "doc_001",
            "record_hash": "abc123",
            "clean_text": "Điều 1. Quy định về phạm vi áp dụng của Luật này.",
            "char_count": 60,
            "word_count": 12,
            "quality_score": 0.03,
            "processed_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        base.update(overrides)
        return base

    def test_valid_batch_passes_all_to_silver(self):
        records = [self._make_silver_record(doc_id=f"d{i}", record_hash=f"h{i}")
                   for i in range(3)]
        report, valid, quarantine = validate_silver_records(records)
        assert report.passed
        assert len(valid) == 3
        assert len(quarantine) == 0

    def test_null_clean_text_routes_to_quarantine(self):
        records = [
            self._make_silver_record(clean_text=None, char_count=0, word_count=0),
            self._make_silver_record(doc_id="d2", record_hash="h2"),
        ]
        report, valid, quarantine = validate_silver_records(records)
        assert len(quarantine) == 1
        assert len(valid) == 1
        assert quarantine[0]["dq_rule"] == "silver_critical_fields_not_null"

    def test_too_short_text_routes_to_quarantine(self):
        records = [self._make_silver_record(char_count=10, word_count=2)]
        report, valid, quarantine = validate_silver_records(records)
        assert len(quarantine) == 1
        assert "char_count" in quarantine[0]["rejection_reason"]

    def test_quality_score_out_of_range_is_warning(self):
        records = [self._make_silver_record(quality_score=1.5)]
        report, valid, quarantine = validate_silver_records(records)
        # Out-of-range quality score is a warning — record still goes to Silver
        qs_rule = next(r for r in report.rules
                       if r.name == "silver_quality_score_range")
        assert qs_rule.severity == DQ_SEVERITY_WARNING

    def test_empty_batch_returns_empty_valid_quarantine(self):
        report, valid, quarantine = validate_silver_records([])
        assert len(valid) == 0
        assert len(quarantine) == 0

    def test_multiple_records_mixed(self):
        records = [
            self._make_silver_record(doc_id="good1", record_hash="h1"),
            self._make_silver_record(doc_id="short", char_count=5, word_count=1,
                                     clean_text="short", record_hash="h2"),
            self._make_silver_record(doc_id="good2", record_hash="h3"),
            self._make_silver_record(doc_id="null_text", clean_text=None,
                                     char_count=0, word_count=0, record_hash="h4"),
        ]
        report, valid, quarantine = validate_silver_records(records)
        assert len(valid) == 2
        assert len(quarantine) == 2


# ---------------------------------------------------------------------------
# Gold DQ tests
# ---------------------------------------------------------------------------

class TestGoldDQ:
    def _make_daily_stats_row(self, **overrides) -> dict:
        base = {
            "ingest_date": "2024-06-01",
            "total_documents": 1000,
            "avg_word_count": 250.5,
            "avg_quality_score": 0.42,
            "quarantined_count": 50,
        }
        base.update(overrides)
        return base

    def test_valid_gold_tables_pass(self):
        tables = {
            "daily_ingestion_stats": [self._make_daily_stats_row()],
            "legal_type_breakdown": [
                {"ingest_date": "2024-06-01", "loai_van_ban": "nghị định",
                 "document_count": 100}
            ],
        }
        report = validate_gold_tables(tables)
        assert report.passed

    def test_negative_document_count_fails(self):
        tables = {
            "legal_type_breakdown": [
                {"ingest_date": "2024-06-01", "loai_van_ban": "luật",
                 "document_count": -1}
            ]
        }
        report = validate_gold_tables(tables)
        assert not report.passed
        neg_rule = next(
            r for r in report.rules
            if "non_negative" in r.name and not r.passed
        )
        assert neg_rule.severity == DQ_SEVERITY_CRITICAL

    def test_missing_required_column_fails(self):
        tables = {
            "daily_ingestion_stats": [
                {"ingest_date": "2024-06-01"}  # Missing total_documents etc.
            ]
        }
        report = validate_gold_tables(tables)
        assert not report.passed

    def test_null_ingest_date_fails(self):
        tables = {
            "daily_ingestion_stats": [
                {"ingest_date": None, "total_documents": 100,
                 "avg_word_count": 200, "avg_quality_score": 0.5,
                 "quarantined_count": 0}
            ]
        }
        report = validate_gold_tables(tables)
        assert not report.passed

    def test_empty_tables_pass(self):
        report = validate_gold_tables({})
        assert report.passed  # Nothing to validate
