# Big Data Project: AI Document Processing System

This repository contains the architecture and processing pipelines for an AI-powered Document Processing System.

## Repository Structure

- `frontend/`: Web applications and interfaces.
- `infra/`: Internal Infrastructure components (MinIO, Milvus, Postgres, Kafka).
- `monitoring/`: Monitoring stack (Prometheus, Grafana, ELK).
- `services/`: Core microservices including data ingestion, processing, and RAG pipelines.
- `datasets/`: (Git-ignored) Houses large raw/processed datasets like RVL-CDIP.

## Quick Start

You can spin up the full infrastructure and install dependencies using:
```bash
./setup.sh
```
