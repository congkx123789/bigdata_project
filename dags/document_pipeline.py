import os
import subprocess
from datetime import datetime

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

PROJECT_ROOT = "/home/alida/Documents/Cursor/Bigdata"
VECTORIZER_SCRIPT = os.path.join(
    PROJECT_ROOT,
    "services/ai-rag-engine/vector_store/ingest_to_milvus.py",
)


def check_kafka_trigger():
    print("Kafka message listening mock...")


def trigger_ocr_job():
    print("Triggering GPU PaddleOCR Worker...")


def trigger_embedding_job():
    print("Triggering GPU BAAI/bge-m3 Embedding into Milvus...")

    env = os.environ.copy()
    env.setdefault("MILVUS_HOST", "localhost")
    env.setdefault("MILVUS_PORT", "19530")
    env.setdefault("MILVUS_COLLECTION", "document_vectors")
    env.setdefault("EMBEDDING_MODEL", "BAAI/bge-m3")
    env.setdefault("MAX_DOCS", "178665")
    env.setdefault("START_OFFSET", "0")
    env.setdefault("BATCH_SIZE", "64")

    subprocess.run(
        ["python", VECTORIZER_SCRIPT],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


with DAG(
    "document_processing_pipeline",
    start_date=datetime(2023, 1, 1),
    schedule_interval=None,
    catchup=False,
) as dag:
    t1 = PythonOperator(task_id="listen_upload_event", python_callable=check_kafka_trigger)
    t2 = PythonOperator(task_id="paddle_ocr_extraction", python_callable=trigger_ocr_job)
    t3 = PythonOperator(task_id="milvus_vectorizing", python_callable=trigger_embedding_job)

    t1 >> t2 >> t3
