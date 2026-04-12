#!/bin/bash
# Unified Setup Script for AI Document Processing System

echo "Setting up AI Document Processing System..."

# 0. Enforce GPU power cap (150W max)
GPU_INDEX=${GPU_INDEX:-0}
GPU_POWER_CAP=${GPU_POWER_CAP:-150}

echo "Enforcing GPU power cap: ${GPU_POWER_CAP}W on GPU ${GPU_INDEX}..."
if command -v nvidia-smi >/dev/null 2>&1; then
  if ! nvidia-smi -i "$GPU_INDEX" -pl "$GPU_POWER_CAP" >/tmp/gpu_power_cap.log 2>&1; then
    echo "Cannot set GPU power cap to ${GPU_POWER_CAP}W."
    echo "Reason:"
    cat /tmp/gpu_power_cap.log
    echo "Please run: sudo nvidia-smi -i ${GPU_INDEX} -pl ${GPU_POWER_CAP}"
    echo "Setup aborted to prevent running above allowed power."
    exit 1
  fi
  nvidia-smi --query-gpu=index,name,power.limit --format=csv,noheader | cat
else
  echo "nvidia-smi not found. Setup aborted for safety."
  exit 1
fi

# 1. Start Infrastructure
echo "Starting core infrastructure (MinIO, Milvus, Postgres, Kafka)..."
docker compose -f infra/docker-compose.yaml up -d

# 2. Start Monitoring
echo "Starting monitoring stack (Prometheus, Grafana, ELK)..."
docker compose -f monitoring/docker-compose-monitoring.yaml up -d

# 3. Install Python Dependencies
echo "Installing Python dependencies for services..."
pip install -r services/ingestion/requirements.txt
pip install -r services/processing/requirements.txt
pip install -r services/rag/requirements.txt
pip install -r frontend/requirements.txt

echo "Setup complete! Please ensure local Docker daemon is running."
echo "To start services locally:"
echo "- Ingestion: python services/ingestion/main.py"
echo "- Processing: python services/processing/spark_processor.py"
echo "- RAG: python services/rag/rag_pipeline.py"
echo "- Frontend: streamlit run frontend/app.py"
