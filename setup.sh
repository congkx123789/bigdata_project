#!/bash
# Unified Setup Script for AI Document Processing System

echo "Setting up AI Document Processing System..."

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
