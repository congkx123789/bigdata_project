"""Run manifest utilities for pipeline observability and lineage tracking.

Each pipeline stage writes a manifest file after completion. Manifests form
the operational audit trail used for debugging, idempotency analysis, SLA
tracking, and incident response.

Manifest files are stored under:
  <MANIFEST_ROOT>/<stage>/<run_id>.json
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _new_run_id() -> str:
    """Generate a short unique run ID: <timestamp_compact>_<uuid4_short>."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    short = str(uuid.uuid4()).split("-")[0]
    return f"{ts}_{short}"


# ---------------------------------------------------------------------------
# RunManifest dataclass
# ---------------------------------------------------------------------------

@dataclass
class RunManifest:
    """Structured metadata describing one pipeline stage execution.

    Fields:
        stage: Stage name e.g. 'bronze_ingest', 'silver_cleanse', 'gold_refresh'.
        run_id: Unique ID auto-generated if not supplied.
        status: 'started' → 'success' or 'failed'.
        started_at: ISO UTC timestamp when the stage started.
        finished_at: ISO UTC timestamp when the stage finished.
        inputs: Source paths / topics consumed by this run.
        outputs: Paths / table names written by this run.
        metrics: Counters — rows_in, rows_out, rows_quarantined, duration_ms, etc.
        details: Stage-specific metadata including DQ report, config snapshot, etc.
    """
    stage: str
    run_id: str = field(default_factory=_new_run_id)
    status: str = "started"
    started_at: str = field(default_factory=_utc_now_iso)
    finished_at: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def mark_success(self) -> None:
        """Mark this run as successful and record finish time."""
        self.status = "success"
        self.finished_at = _utc_now_iso()

    def mark_failed(self, error: str) -> None:
        """Mark this run as failed with an error message."""
        self.status = "failed"
        self.finished_at = _utc_now_iso()
        self.details["error"] = error

    def set_metrics(self, **kwargs: Any) -> None:
        """Convenience method to bulk-set metric counters."""
        self.metrics.update(kwargs)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_manifest(manifest_root: Path, manifest: RunManifest) -> Path:
    """Persist a run manifest to disk.

    Args:
        manifest_root: Root directory for manifests (from AppConfig).
        manifest: Fully populated RunManifest (mark_success or mark_failed called).

    Returns:
        Absolute path to the written manifest file.
    """
    stage_dir = manifest_root / manifest.stage
    stage_dir.mkdir(parents=True, exist_ok=True)

    if manifest.finished_at is None:
        manifest.finished_at = _utc_now_iso()

    manifest_path = stage_dir / f"{manifest.run_id}.json"
    with manifest_path.open("w", encoding="utf-8") as fp:
        json.dump(asdict(manifest), fp, indent=2, sort_keys=True, ensure_ascii=False)

    return manifest_path


def load_latest_manifest(manifest_root: Path, stage: str) -> dict | None:
    """Load the most recent manifest for a stage (by filename sort).

    Args:
        manifest_root: Root directory for manifests.
        stage: Stage name.

    Returns:
        Parsed manifest dict, or None if no manifests exist.
    """
    stage_dir = manifest_root / stage
    if not stage_dir.exists():
        return None

    manifests = sorted(stage_dir.glob("*.json"))
    if not manifests:
        return None

    with manifests[-1].open(encoding="utf-8") as fp:
        return json.load(fp)
