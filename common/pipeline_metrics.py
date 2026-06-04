"""Structured pipeline metrics emitter.

Every stage calls emit_pipeline_metrics() after completion. The metric is:
1. Logged as a structured JSON log line with logger 'pipeline_metrics'.
2. Optionally appended to PIPELINE_METRICS_LOG_PATH (JSONL) for Grafana/ELK ingestion.

Metric schema (per stage run):
{
  "event": "pipeline_metrics",
  "stage": "<stage_name>",
  "run_id": "<run_id>",
  "status": "success" | "failed",
  "rows_in": <int>,
  "rows_out": <int>,
  "rows_quarantined": <int>,
  "duration_ms": <float>,
  "dq_passed": <bool>,
  "dq_critical_failures": <int>,
  "dq_warnings": <int>,
  "manifest_path": "<path>" | null,
  "timestamp": "<iso utc>"
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from common.logger import get_logger

_logger = get_logger("pipeline_metrics")


def emit_pipeline_metrics(
    *,
    stage: str,
    run_id: str,
    status: str,
    rows_in: int = 0,
    rows_out: int = 0,
    rows_quarantined: int = 0,
    duration_ms: float = 0.0,
    dq_passed: bool = True,
    dq_critical_failures: int = 0,
    dq_warnings: int = 0,
    manifest_path: Optional[str | Path] = None,
    extra: Optional[dict[str, Any]] = None,
) -> None:
    """Emit structured pipeline metrics.

    Args:
        stage: Pipeline stage name.
        run_id: Run identifier from RunManifest.
        status: 'success' or 'failed'.
        rows_in: Input row count.
        rows_out: Output row count (post-DQ, post-dedup).
        rows_quarantined: Rows rejected to quarantine.
        duration_ms: Wall-clock duration in milliseconds.
        dq_passed: Whether all critical DQ rules passed.
        dq_critical_failures: Number of failing critical DQ rules.
        dq_warnings: Number of failing warning DQ rules.
        manifest_path: Path to the written manifest file (for audit links).
        extra: Additional stage-specific fields.
    """
    payload: dict[str, Any] = {
        "event": "pipeline_metrics",
        "stage": stage,
        "run_id": run_id,
        "status": status,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_quarantined": rows_quarantined,
        "duration_ms": round(duration_ms, 2),
        "dq_passed": dq_passed,
        "dq_critical_failures": dq_critical_failures,
        "dq_warnings": dq_warnings,
        "manifest_path": str(manifest_path) if manifest_path else None,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }

    if extra:
        payload.update(extra)

    # Structured log (picked up by ELK / Grafana Loki)
    _logger.info(json.dumps(payload, ensure_ascii=False))

    # Optional JSONL file sink
    metrics_log_path = os.getenv("PIPELINE_METRICS_LOG_PATH", "")
    if metrics_log_path:
        try:
            metrics_file = Path(metrics_log_path)
            metrics_file.parent.mkdir(parents=True, exist_ok=True)
            with metrics_file.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            _logger.warning(f"Could not write to PIPELINE_METRICS_LOG_PATH={metrics_log_path}")
