"""Data Quality gates for the Vietnamese Legal Documents pipeline.

Rules are applied immediately before writing each stage:
- Bronze: null/empty raw_text, missing doc_id
- Silver: text length thresholds, quality_score floor, critical null checks
- Gold: non-negative aggregates, required columns

Severity model:
  critical → block publication (DQ_FAIL_ON_ERROR=true)
  warning  → log and continue
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from common.schemas import (
    BRONZE_REQUIRED_COLS,
    SILVER_CRITICAL_COLS,
    SILVER_REQUIRED_COLS,
)

# ---------------------------------------------------------------------------
# DQ Result primitives
# ---------------------------------------------------------------------------

DQ_SEVERITY_CRITICAL = "critical"
DQ_SEVERITY_WARNING = "warning"

# Quality thresholds
MIN_CLEAN_TEXT_CHARS = 50       # Silver: reject below this char count
MIN_QUALITY_SCORE = 0.0         # Silver: quality_score >= 0
MAX_QUALITY_SCORE = 1.0
MIN_WORD_COUNT = 5              # Silver: at least 5 words


@dataclass(frozen=True)
class DQRuleResult:
    """Outcome of a single named DQ rule."""
    name: str
    passed: bool
    detail: str = ""
    severity: str = DQ_SEVERITY_CRITICAL


@dataclass
class DQReport:
    """Aggregated DQ outcome for a pipeline stage."""
    stage: str
    rules: list[DQRuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True only if all critical rules passed."""
        return all(
            rule.passed
            for rule in self.rules
            if rule.severity == DQ_SEVERITY_CRITICAL
        )

    @property
    def critical_failures(self) -> list[DQRuleResult]:
        return [r for r in self.rules if not r.passed and r.severity == DQ_SEVERITY_CRITICAL]

    @property
    def warnings(self) -> list[DQRuleResult]:
        return [r for r in self.rules if not r.passed and r.severity == DQ_SEVERITY_WARNING]

    def to_metrics(self) -> dict[str, Any]:
        """Serialize for run manifests and pipeline_metrics logs."""
        return {
            "dq_passed": self.passed,
            "critical_failures": len(self.critical_failures),
            "warnings": len(self.warnings),
            "dq_rules": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "detail": r.detail,
                    "severity": r.severity,
                }
                for r in self.rules
            ],
        }

    def summary_str(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"DQ[{self.stage}] {status} — "
            f"{sum(r.passed for r in self.rules)}/{len(self.rules)} rules passed, "
            f"{len(self.critical_failures)} critical failures, "
            f"{len(self.warnings)} warnings"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _missing_cols(row: dict, required: tuple[str, ...]) -> list[str]:
    return [c for c in required if c not in row]


# ---------------------------------------------------------------------------
# Bronze DQ
# ---------------------------------------------------------------------------

def validate_bronze_records(records: list[dict]) -> DQReport:
    """Validate a batch of Bronze records before writing to Iceberg.

    Args:
        records: List of dicts with Bronze schema fields.

    Returns:
        DQReport with rule results.
    """
    report = DQReport(stage="bronze_ingest")
    n = len(records)

    if n == 0:
        report.rules.append(DQRuleResult(
            "bronze_batch_non_empty", False,
            "Bronze batch is empty — no records to ingest",
            DQ_SEVERITY_WARNING,
        ))
        return report

    missing_doc_id = 0
    empty_raw_text = 0
    missing_record_hash = 0
    missing_dedupe_key = 0
    duplicate_hashes: set[str] = set()
    duplicate_count = 0

    for rec in records:
        if _is_missing(rec.get("doc_id")):
            missing_doc_id += 1
        if _is_missing(rec.get("raw_text")):
            empty_raw_text += 1
        if _is_missing(rec.get("record_hash")):
            missing_record_hash += 1
        if _is_missing(rec.get("dedupe_key")):
            missing_dedupe_key += 1

        rh = rec.get("record_hash", "")
        if rh in duplicate_hashes:
            duplicate_count += 1
        else:
            duplicate_hashes.add(rh)

    report.rules.extend([
        DQRuleResult(
            "bronze_doc_id_not_null",
            missing_doc_id == 0,
            f"missing_doc_id={missing_doc_id} / total={n}",
        ),
        DQRuleResult(
            "bronze_raw_text_not_empty",
            empty_raw_text == 0,
            f"empty_raw_text={empty_raw_text} / total={n}",
        ),
        DQRuleResult(
            "bronze_record_hash_present",
            missing_record_hash == 0,
            f"missing_record_hash={missing_record_hash} / total={n}",
        ),
        DQRuleResult(
            "bronze_dedupe_key_present",
            missing_dedupe_key == 0,
            f"missing_dedupe_key={missing_dedupe_key} / total={n}",
        ),
        DQRuleResult(
            "bronze_no_duplicate_hashes_in_batch",
            duplicate_count == 0,
            f"duplicate_record_hashes={duplicate_count} / total={n}",
            DQ_SEVERITY_WARNING,
        ),
    ])

    return report


# ---------------------------------------------------------------------------
# Silver DQ
# ---------------------------------------------------------------------------

def validate_silver_records(records: list[dict]) -> tuple[DQReport, list[dict], list[dict]]:
    """Validate Silver records, splitting into valid and quarantine sets.

    Args:
        records: List of dicts with Silver schema fields.

    Returns:
        Tuple of (DQReport, valid_records, quarantine_records).
    """
    report = DQReport(stage="silver_cleanse")
    n = len(records)

    if n == 0:
        report.rules.append(DQRuleResult(
            "silver_batch_non_empty", False,
            "Silver batch is empty",
            DQ_SEVERITY_WARNING,
        ))
        return report, [], []

    valid: list[dict] = []
    quarantine: list[dict] = []

    missing_critical = 0
    text_too_short = 0
    word_count_too_low = 0
    bad_quality_score = 0
    duplicate_ids: set[str] = set()
    duplicate_count = 0

    for rec in records:
        reject_reasons: list[str] = []
        dq_rule: str = ""

        # Check critical fields
        if any(_is_missing(rec.get(c)) for c in SILVER_CRITICAL_COLS):
            missing_critical += 1
            reject_reasons.append("missing_critical_field")
            dq_rule = "silver_critical_fields_not_null"

        # Text length check
        cc = rec.get("char_count") or 0
        if cc < MIN_CLEAN_TEXT_CHARS:
            text_too_short += 1
            reject_reasons.append(f"char_count={cc} < min={MIN_CLEAN_TEXT_CHARS}")
            dq_rule = dq_rule or "silver_min_char_count"

        # Word count check
        wc = rec.get("word_count") or 0
        if wc < MIN_WORD_COUNT:
            word_count_too_low += 1
            reject_reasons.append(f"word_count={wc} < min={MIN_WORD_COUNT}")
            dq_rule = dq_rule or "silver_min_word_count"

        # Quality score check
        qs = rec.get("quality_score")
        if qs is not None and not (MIN_QUALITY_SCORE <= qs <= MAX_QUALITY_SCORE):
            bad_quality_score += 1
            reject_reasons.append(f"quality_score={qs} out of [0,1]")
            dq_rule = dq_rule or "silver_quality_score_range"

        # Dedup within batch
        doc_id = rec.get("doc_id", "")
        if doc_id in duplicate_ids:
            duplicate_count += 1
        else:
            duplicate_ids.add(doc_id)

        if reject_reasons:
            quarantine.append({
                **rec,
                "rejection_reason": "; ".join(reject_reasons),
                "dq_rule": dq_rule,
            })
        else:
            valid.append(rec)

    # Add DQ rules to report
    report.rules.extend([
        DQRuleResult(
            "silver_critical_fields_not_null",
            missing_critical == 0,
            f"rows_with_null_critical={missing_critical} / total={n}",
        ),
        DQRuleResult(
            "silver_min_char_count",
            text_too_short == 0,
            f"text_too_short_rows={text_too_short} / total={n}",
        ),
        DQRuleResult(
            "silver_min_word_count",
            word_count_too_low == 0,
            f"word_count_too_low_rows={word_count_too_low} / total={n}",
            DQ_SEVERITY_WARNING,
        ),
        DQRuleResult(
            "silver_quality_score_range",
            bad_quality_score == 0,
            f"bad_quality_score_rows={bad_quality_score} / total={n}",
            DQ_SEVERITY_WARNING,
        ),
        DQRuleResult(
            "silver_no_duplicate_doc_ids_in_batch",
            duplicate_count == 0,
            f"duplicate_doc_ids={duplicate_count} / total={n}",
            DQ_SEVERITY_WARNING,
        ),
    ])

    return report, valid, quarantine


# ---------------------------------------------------------------------------
# Gold DQ
# ---------------------------------------------------------------------------

_GOLD_REQUIRED_COLS: dict[str, tuple[str, ...]] = {
    "daily_ingestion_stats": (
        "ingest_date", "total_documents", "avg_word_count",
        "avg_quality_score", "quarantined_count",
    ),
    "legal_type_breakdown": (
        "ingest_date", "loai_van_ban", "document_count",
    ),
    "issuing_authority_stats": (
        "ingest_date", "co_quan_ban_hanh", "document_count",
    ),
    "legal_field_stats": (
        "ingest_date", "linh_vuc", "document_count", "avg_quality_score",
    ),
    "effect_status_summary": (
        "ingest_date", "effect_status", "document_count",
    ),
}

_GOLD_NON_NEGATIVE_COLS: dict[str, tuple[str, ...]] = {
    "daily_ingestion_stats": ("total_documents", "quarantined_count"),
    "legal_type_breakdown": ("document_count",),
    "issuing_authority_stats": ("document_count",),
    "legal_field_stats": ("document_count",),
    "effect_status_summary": ("document_count",),
}


def validate_gold_tables(tables: dict[str, list[dict]]) -> DQReport:
    """Validate Gold aggregation tables before publication.

    Args:
        tables: Mapping of table_name → list of row dicts.

    Returns:
        DQReport with per-table rule results.
    """
    report = DQReport(stage="gold_refresh")

    for table_name, rows in tables.items():
        required = _GOLD_REQUIRED_COLS.get(table_name, ())
        non_neg = _GOLD_NON_NEGATIVE_COLS.get(table_name, ())
        n = len(rows)

        # Required columns
        missing_cols_count = sum(1 for row in rows if _missing_cols(row, required))
        report.rules.append(DQRuleResult(
            f"{table_name}_required_columns",
            missing_cols_count == 0,
            f"rows_missing_cols={missing_cols_count} / total={n} in {table_name}",
        ))

        # Non-negative metrics
        bad_neg = sum(
            1 for row in rows
            if any(
                isinstance(row.get(c), (int, float)) and row.get(c) < 0
                for c in non_neg
            )
        )
        report.rules.append(DQRuleResult(
            f"{table_name}_non_negative_metrics",
            bad_neg == 0,
            f"rows_with_negative_metrics={bad_neg} / total={n} in {table_name}",
        ))

        # ingest_date not null
        if "ingest_date" in required:
            null_dates = sum(1 for row in rows if _is_missing(row.get("ingest_date")))
            report.rules.append(DQRuleResult(
                f"{table_name}_ingest_date_not_null",
                null_dates == 0,
                f"rows_with_null_date={null_dates} / total={n} in {table_name}",
            ))

    return report
