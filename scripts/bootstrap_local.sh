#!/bin/bash
# Bootstrap local development environment for Vietnamese Legal Documents Pipeline
# Usage: bash scripts/bootstrap_local.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Vietnamese Legal Documents BigData Pipeline — Bootstrap ==="
echo "Project root: $PROJECT_ROOT"
cd "$PROJECT_ROOT"

# ---------------------------------------------------------------------------
# Step 1: Environment file
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo ""
    echo "[1/5] Creating .env from .env.example..."
    cp .env.example .env
    echo "  ✓ .env created"
    echo "  ⚠️  Edit .env and set HF_TOKEN, MINIO_SECRET_KEY, POSTGRES_PASSWORD"
else
    echo "[1/5] .env already exists — skipping"
fi

# ---------------------------------------------------------------------------
# Step 2: Create local data directories
# ---------------------------------------------------------------------------
echo ""
echo "[2/5] Creating local data directories..."
mkdir -p data/raw/content data/raw/metadata data/raw/relationships
mkdir -p data/manifests/bronze_ingest data/manifests/silver_cleanse
mkdir -p data/manifests/gold_refresh data/manifests/iceberg_maintenance
mkdir -p data/metrics
mkdir -p data/checkpoints/bronze data/checkpoints/silver
echo "  ✓ Local data directories created"

# ---------------------------------------------------------------------------
# Step 3: Python dependencies check
# ---------------------------------------------------------------------------
echo ""
echo "[3/5] Checking Python dependencies..."
if ! python -c "import pyspark" 2>/dev/null; then
    echo "  ⚠️  PySpark not found — install with: pip install pyspark==3.5.0"
fi
if ! python -c "import datasets" 2>/dev/null; then
    echo "  ⚠️  HuggingFace datasets not found — install with: pip install datasets"
fi
if ! python -c "import minio" 2>/dev/null; then
    echo "  ⚠️  MinIO client not found — install with: pip install minio"
fi
if ! python -c "import pytest" 2>/dev/null; then
    echo "  ⚠️  pytest not found — install with: pip install pytest"
fi
echo "  ✓ Dependency check complete"

# ---------------------------------------------------------------------------
# Step 4: Start infrastructure
# ---------------------------------------------------------------------------
echo ""
echo "[4/5] Starting Docker infrastructure..."
if ! command -v docker &>/dev/null; then
    echo "  ✗ Docker not found — install Docker Desktop first"
    exit 1
fi

docker compose -f infra/docker-compose.yaml up -d
echo "  ✓ Infrastructure started"
echo "  Waiting 30s for services to become healthy..."
sleep 30

# ---------------------------------------------------------------------------
# Step 5: Run unit tests
# ---------------------------------------------------------------------------
echo ""
echo "[5/5] Running unit tests..."
python -m pytest tests/unit/ -v --tb=short 2>&1 | head -50 || echo "  ⚠️  Some tests failed — check output above"

echo ""
echo "=== Bootstrap Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env — set HF_TOKEN (required for dataset download)"
echo "  2. python services/ingestion/hf_dataset_loader.py"
echo "  3. python pipelines/bronze/ingest_raw.py --mode batch"
echo "  4. python pipelines/silver/cleanse_documents.py --mode batch"
echo "  5. python pipelines/gold/aggregate_metrics.py"
echo "  6. bash scripts/verify_local.py"
echo ""
echo "Service URLs:"
echo "  MinIO:    http://localhost:9001"
echo "  Trino:    http://localhost:8088"
echo "  Airflow:  http://localhost:8090"
echo "  Superset: http://localhost:8089"
