#!/usr/bin/env python3
"""Verify local pipeline outputs after running all 3 stages.

Usage:
    python scripts/verify_local.py

Checks:
  1. Latest Bronze manifest: status == 'success', rows_out > 0
  2. Latest Silver manifest: status == 'success', dq_passed == True
  3. Latest Gold manifest: status == 'success', gold_tables_written == 5
  4. Manifest reconciliation: Silver.rows_out + Silver.rows_quarantined ≈ Bronze.rows_out
  5. Pipeline metrics JSONL exists and has entries
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import load_config
from common.manifests import load_latest_manifest


def _check(condition: bool, message: str, *, warning_only: bool = False) -> bool:
    icon = "✓" if condition else ("⚠️" if warning_only else "✗")
    status = "PASS" if condition else ("WARN" if warning_only else "FAIL")
    print(f"  {icon} [{status}] {message}")
    return condition


def verify_pipeline() -> bool:
    cfg = load_config()
    all_passed = True
    print("\n=== Vietnamese Legal Documents Pipeline — Verification ===\n")

    # -------------------------------------------------------------------
    # 1. Bronze manifest
    # -------------------------------------------------------------------
    print("[1/5] Bronze manifest:")
    bronze_manifest = load_latest_manifest(cfg.manifest_root, "bronze_ingest")
    if bronze_manifest is None:
        bronze_manifest = load_latest_manifest(cfg.manifest_root, "bronze_ingest_batch")

    if bronze_manifest is None:
        _check(False, "No Bronze manifest found — run bronze/ingest_raw.py first")
        all_passed = False
    else:
        ok1 = _check(bronze_manifest.get("status") == "success",
                     f"Bronze status={bronze_manifest.get('status')}")
        rows_out = bronze_manifest.get("metrics", {}).get("rows_out", 0)
        ok2 = _check(rows_out > 0, f"Bronze rows_out={rows_out}")
        all_passed = all_passed and ok1 and ok2

    # -------------------------------------------------------------------
    # 2. Silver manifest
    # -------------------------------------------------------------------
    print("\n[2/5] Silver manifest:")
    silver_manifest = load_latest_manifest(cfg.manifest_root, "silver_cleanse")
    if silver_manifest is None:
        _check(False, "No Silver manifest found — run silver/cleanse_documents.py first")
        all_passed = False
    else:
        ok1 = _check(silver_manifest.get("status") == "success",
                     f"Silver status={silver_manifest.get('status')}")
        dq_passed = silver_manifest.get("details", {}).get("dq", {}).get("dq_passed", False)
        ok2 = _check(dq_passed, f"Silver DQ passed={dq_passed}")
        rows_out = silver_manifest.get("metrics", {}).get("rows_out", 0)
        rows_q = silver_manifest.get("metrics", {}).get("rows_quarantined", 0)
        ok3 = _check(rows_out > 0, f"Silver rows_out={rows_out}, quarantined={rows_q}")
        all_passed = all_passed and ok1 and ok2 and ok3

    # -------------------------------------------------------------------
    # 3. Gold manifest
    # -------------------------------------------------------------------
    print("\n[3/5] Gold manifest:")
    gold_manifest = load_latest_manifest(cfg.manifest_root, "gold_refresh")
    if gold_manifest is None:
        _check(False, "No Gold manifest found — run gold/aggregate_metrics.py first")
        all_passed = False
    else:
        ok1 = _check(gold_manifest.get("status") == "success",
                     f"Gold status={gold_manifest.get('status')}")
        tables_written = gold_manifest.get("metrics", {}).get("gold_tables_written", 0)
        ok2 = _check(tables_written == 5,
                     f"Gold tables_written={tables_written} (expected 5)")
        all_passed = all_passed and ok1 and ok2

    # -------------------------------------------------------------------
    # 4. Bronze → Silver reconciliation
    # -------------------------------------------------------------------
    print("\n[4/5] Bronze → Silver reconciliation:")
    if bronze_manifest and silver_manifest:
        bronze_rows = bronze_manifest.get("metrics", {}).get("rows_out", 0)
        silver_rows = silver_manifest.get("metrics", {}).get("rows_out", 0)
        silver_quarantine = silver_manifest.get("metrics", {}).get("rows_quarantined", 0)
        silver_total = silver_rows + silver_quarantine

        if bronze_rows > 0:
            pct_accounted = 100.0 * silver_total / bronze_rows
            _check(
                pct_accounted >= 80.0,
                f"Bronze={bronze_rows}, Silver+Quarantine={silver_total} "
                f"({pct_accounted:.1f}% accounted for)",
                warning_only=pct_accounted < 100.0,
            )
        else:
            _check(False, "Cannot reconcile — Bronze has 0 rows", warning_only=True)
    else:
        _check(False, "Cannot reconcile — missing manifests", warning_only=True)

    # -------------------------------------------------------------------
    # 5. Pipeline metrics JSONL
    # -------------------------------------------------------------------
    print("\n[5/5] Pipeline metrics JSONL:")
    metrics_path = cfg.pipeline_metrics_log_path
    if metrics_path:
        mpath = Path(metrics_path)
        if mpath.exists():
            lines = mpath.read_text().strip().splitlines()
            _check(len(lines) > 0, f"Metrics file has {len(lines)} entries at {mpath}")
        else:
            _check(False, f"Metrics file not found: {mpath}", warning_only=True)
    else:
        _check(False, "PIPELINE_METRICS_LOG_PATH not configured", warning_only=True)

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print()
    if all_passed:
        print("✅ All checks PASSED — pipeline is healthy")
    else:
        print("❌ Some checks FAILED — see above for details")

    return all_passed


if __name__ == "__main__":
    ok = verify_pipeline()
    sys.exit(0 if ok else 1)
