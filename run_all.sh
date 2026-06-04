#!/bin/bash

#Nexus AI Platform - Unified Startup Script
echo "🚀 Starting Nexus AI Enterprise Platform..."

# 0. Enforce GPU power cap (150W max)
GPU_INDEX=${GPU_INDEX:-0}
GPU_POWER_CAP=${GPU_POWER_CAP:-150}

echo "🔒 Enforcing GPU power cap: ${GPU_POWER_CAP}W on GPU ${GPU_INDEX}..."
if command -v nvidia-smi >/dev/null 2>&1; then
  if ! nvidia-smi -i "$GPU_INDEX" -pl "$GPU_POWER_CAP" >/tmp/gpu_power_cap.log 2>&1; then
    echo "❌ Cannot set GPU power cap to ${GPU_POWER_CAP}W."
    echo "Reason:"
    cat /tmp/gpu_power_cap.log
    echo "Please run: sudo nvidia-smi -i ${GPU_INDEX} -pl ${GPU_POWER_CAP}"
    echo "Startup aborted to prevent running above allowed power."
    exit 1
  fi
  nvidia-smi --query-gpu=index,name,power.limit --format=csv,noheader | cat
else
  echo "❌ nvidia-smi not found. Startup aborted for safety."
  exit 1
fi

# 1. Start Infrastructure
echo "📂 Starting Infrastructure (Milvus, Kafka, MinIO, etc.)..."
cd infra && docker compose up -d
cd ..

# 2. Start AI RAG Engine
echo "🤖 Starting AI RAG Engine (Port 8002)..."
cd services/ai-rag-engine
nohup python main.py > server.log 2>&1 &
echo $! > ai_engine.pid
cd ../..

# 3. Start Core API
echo "🔌 Starting Core API (Port 8001)..."
cd services/core-api
nohup python main.py > server.log 2>&1 &
echo $! > core_api.pid
cd ../..

# 4. Start Frontend
echo "💻 Starting Frontend (Production)"
cd frontend
export NODE_ENV=production
npm run start -- -H 0.0.0.0 -p 8080

echo "✅ All services initiated!"
