#!/bin/bash

#Nexus AI Platform - Unified Startup Script
echo "🚀 Starting Nexus AI Enterprise Platform..."

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
echo "💻 Starting Frontend (Port 3000)..."
cd frontend/frontend/chatbot-web
npm run dev -- --host 0.0.0.0 --port 3000

echo "✅ All services initiated!"
