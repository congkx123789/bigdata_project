#!/bin/bash

# ==============================================================================
# Bigdata Project Assets Backup Script
# This script compresses the "Brain" of the Bigdata AI Document Processing system
# including Vector Embeddings (Milvus), Metadata (Postgres), Object Storage (Minio),
# and cluster configurations (Etcd).
# ==============================================================================

set -e

echo "🧠 Starting Bigdata Brain Backup Process..."
echo "=========================================="

# Ensure we are in the project root directory
cd "$(dirname "$0")"

# 1. Check if infra directory exists
if [ ! -d "infra" ]; then
    echo "❌ Error: 'infra' directory not found. Please run this script from the project root."
    exit 1
fi

# 2. Safely stop the database containers to ensure data integrity before archiving
echo "⏳ Stopping database containers to ensure data integrity..."
docker compose stop milvus-standalone milvus-etcd milvus-minio postgres || true

# 3. Create the archives
echo "📦 Archiving Milvus Vector Embeddings (infra_milvus_data.tar.gz)..."
tar -czf infra_milvus_data.tar.gz -C infra milvus

echo "📦 Archiving Metadata and Configurations (infra_postgres_data.tar.gz)..."
if [ -d "infra/postgres" ]; then
    tar -czf infra_postgres_data.tar.gz -C infra postgres
else
    echo "⚠️ Warning: 'infra/postgres' directory not found. Skipping."
fi

echo "📦 Archiving Object Storage Metadata (infra_minio_data.tar.gz)..."
tar -czf infra_minio_data.tar.gz -C infra minio

echo "📦 Archiving Etcd Cluster States (infra_etcd_data.tar.gz)..."
tar -czf infra_etcd_data.tar.gz -C infra etcd

# 4. Restart the containers
echo "🚀 Restarting database containers..."
docker compose start milvus-standalone milvus-etcd milvus-minio postgres || true

echo "=========================================="
echo "✅ Backup Completed Successfully!"
echo "The following files have been generated in $(pwd):"
ls -lh infra_*.tar.gz
echo ""
echo "🚀 You can now upload these files to Hugging Face:"
echo "https://huggingface.co/datasets/Cong123779/bigdata-assets"
