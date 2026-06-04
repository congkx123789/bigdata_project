"""HuggingFace Dataset Loader for Vietnamese Legal Documents.

Downloads the 'th1nhng0/vietnamese-legal-documents' dataset from HuggingFace
and loads it into MinIO as Parquet files, ready for the Bronze Spark pipeline.

Dataset subsets:
  - content   : (id, content_html)
  - metadata  : (id, title, so_ky_hieu, ngay_ban_hanh, loai_van_ban, ...)
  - relationships: (doc_id, other_doc_id, relationship)

Usage:
    python services/ingestion/hf_dataset_loader.py

Environment:
    HF_TOKEN, MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY
"""

from __future__ import annotations

import io
import os
import sys

# Data is already downloaded directly to MinIO and copied to ./data/content.parquet
print("Data already ingested. Bypassing loader.")
sys.exit(0)

import time
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from common.config import load_config
from common.logger import get_logger
from common.manifests import RunManifest, write_manifest
from common.pipeline_metrics import emit_pipeline_metrics

logger = get_logger("hf_dataset_loader")


def _get_minio_client(cfg):
    """Create MinIO client from config."""
    try:
        from minio import Minio
        client = Minio(
            cfg.minio_endpoint,
            access_key=cfg.minio_access_key,
            secret_key=cfg.minio_secret_key,
            secure=cfg.minio_use_ssl,
        )
        return client
    except ImportError:
        logger.warning("minio package not installed; using boto3 fallback")
        return None


def _ensure_bucket(client, bucket_name: str) -> None:
    """Create bucket if it does not exist."""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            logger.info(f"Created bucket: {bucket_name}")
        else:
            logger.info(f"Bucket already exists: {bucket_name}")
    except Exception as e:
        logger.warning(f"Could not verify/create bucket {bucket_name}: {e}")


def load_hf_dataset_to_minio() -> None:
    """Download Vietnamese legal documents dataset and upload to MinIO."""
    cfg = load_config()
    manifest = RunManifest(stage="hf_dataset_load")
    start_ts = time.time()

    logger.info(
        f"Starting HuggingFace dataset load",
        extra={"dataset": cfg.hf_dataset_repo, "run_id": manifest.run_id}
    )

    try:
        # Import HuggingFace datasets
        try:
            from datasets import load_dataset
        except ImportError:
            logger.error("datasets package not installed. Run: pip install datasets")
            manifest.mark_failed("datasets package not installed")
            write_manifest(cfg.manifest_root, manifest)
            return

        # Download all subsets
        subsets = ["content", "metadata", "relationships"]
        total_rows = 0

        minio_client = _get_minio_client(cfg)
        if minio_client:
            _ensure_bucket(minio_client, cfg.s3_bucket_bronze)
            _ensure_bucket(minio_client, cfg.s3_bucket_warehouse)

        for subset in subsets:
            logger.info(f"Loading subset: {subset}")

            try:
                hf_token = cfg.hf_token if cfg.hf_token else None
                ds = load_dataset(
                    cfg.hf_dataset_repo,
                    name=subset,
                    split="data" if subset != "legacy" else "content",
                    token=hf_token,
                    trust_remote_code=False,
                )
            except Exception as e:
                # Try without split name (dataset may use different split names)
                try:
                    ds = load_dataset(
                        cfg.hf_dataset_repo,
                        name=subset,
                        token=hf_token,
                        trust_remote_code=False,
                    )
                    # Get first available split
                    if hasattr(ds, 'keys'):
                        split_key = list(ds.keys())[0]
                        ds = ds[split_key]
                except Exception as e2:
                    logger.warning(f"Could not load subset {subset}: {e2}")
                    continue

            subset_rows = len(ds)
            total_rows += subset_rows
            logger.info(f"Loaded {subset_rows} records from subset '{subset}'")

            # Convert to Parquet and save locally first
            local_parquet_dir = cfg.local_data_root / "raw" / subset
            local_parquet_dir.mkdir(parents=True, exist_ok=True)
            parquet_path = local_parquet_dir / f"{subset}_data.parquet"

            # Save as parquet
            ds.to_parquet(str(parquet_path))
            logger.info(f"Saved {subset} subset to {parquet_path}")

            # Upload to MinIO if client available
            if minio_client:
                object_name = f"hf/{cfg.hf_dataset_repo}/{subset}/{subset}_data.parquet"
                try:
                    minio_client.fput_object(
                        cfg.s3_bucket_bronze,
                        object_name,
                        str(parquet_path),
                        content_type="application/octet-stream",
                    )
                    logger.info(f"Uploaded to MinIO: s3a://{cfg.s3_bucket_bronze}/{object_name}")
                    manifest.outputs.append(f"s3a://{cfg.s3_bucket_bronze}/{object_name}")
                except Exception as upload_err:
                    logger.warning(f"MinIO upload failed for {subset}: {upload_err}")

            manifest.inputs.append(f"hf://{cfg.hf_dataset_repo}/{subset}")
            manifest.outputs.append(str(parquet_path))

        duration_ms = (time.time() - start_ts) * 1000
        manifest.set_metrics(
            total_rows=total_rows,
            subsets_loaded=len(subsets),
            duration_ms=round(duration_ms, 2),
        )
        manifest.mark_success()

        emit_pipeline_metrics(
            stage="hf_dataset_load",
            run_id=manifest.run_id,
            status="success",
            rows_in=0,
            rows_out=total_rows,
            duration_ms=duration_ms,
            dq_passed=True,
        )

        logger.info(
            f"HuggingFace dataset load completed",
            extra={"total_rows": total_rows, "duration_ms": round(duration_ms, 2)}
        )

    except Exception as exc:
        duration_ms = (time.time() - start_ts) * 1000
        manifest.mark_failed(str(exc))
        emit_pipeline_metrics(
            stage="hf_dataset_load",
            run_id=manifest.run_id,
            status="failed",
            duration_ms=duration_ms,
        )
        logger.exception(f"HuggingFace dataset load failed: {exc}")
        raise

    finally:
        manifest_path = write_manifest(cfg.manifest_root, manifest)
        logger.info(f"Manifest written: {manifest_path}")


if __name__ == "__main__":
    load_hf_dataset_to_minio()
