from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime

def check_kafka_trigger():
    print("Kafka message listening mock...")

def trigger_ocr_job():
    print("Triggering GPU PaddleOCR Worker...")

def trigger_embedding_job():
    print("Triggering GPU BAAI/bge-m3 Embedding...")

with DAG('document_processing_pipeline', start_date=datetime(2023, 1, 1), schedule_interval=None) as dag:
    # This is a sample representation of the SOA pipeline orchestration.
    
    t1 = PythonOperator(task_id='listen_upload_event', python_callable=check_kafka_trigger)
    t2 = PythonOperator(task_id='paddle_ocr_extraction', python_callable=trigger_ocr_job)
    t3 = PythonOperator(task_id='milvus_vectorizing', python_callable=trigger_embedding_job)

    t1 >> t2 >> t3
