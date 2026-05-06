import os
import time
import json
import logging
import psycopg2
from minio import Minio
from confluent_kafka import Producer
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("batch_ingestor")

# Configuration
DATASET_PATH = "/home/alida/Documents/Cursor/Bigdata/datasets/rvl-cdip/data/images"
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = "documents"

DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "document_db",
    "user": "admin",
    "password": "password123"
}

KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
KAFKA_TOPIC = "document-uploaded"

# Initialize Clients with optimized pool size
from urllib3 import PoolManager
from psycopg2 import pool
minio_client = Minio(
    MINIO_ENDPOINT, 
    access_key=MINIO_ACCESS_KEY, 
    secret_key=MINIO_SECRET_KEY, 
    secure=False,
    http_client=PoolManager(
        retries=False,
        maxsize=32,
        cert_reqs='CERT_REQUIRED'
    )
)
kafka_conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
producer = Producer(kafka_conf)

# Initialize Connection Pool
db_pool = pool.ThreadedConnectionPool(5, 30, **DB_CONFIG)

def init_db():
    conn = db_pool.getconn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            filename TEXT UNIQUE,
            bucket TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    db_pool.putconn(conn)
    logger.info("Database schema initialized.")

def upload_file(file_info):
    rel_path, abs_path = file_info
    conn = None
    try:
        # 1. Upload to MinIO
        minio_client.fput_object(MINIO_BUCKET, rel_path, abs_path)
        
        # 2. Record in Postgres using pool
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO documents (filename, bucket, status) VALUES (%s, %s, %s) ON CONFLICT (filename) DO NOTHING",
            (rel_path, MINIO_BUCKET, "PENDING_OCR")
        )
        conn.commit()
        cur.close()
        db_pool.putconn(conn)
        conn = None # Set to none so finally block doesn't try to return it twice
        
        # 3. Emit Kafka Event
        event = {"filename": rel_path, "status": "UPLOADED"}
        producer.produce(KAFKA_TOPIC, key=rel_path, value=json.dumps(event))
        
        return True
    except Exception as e:
        logger.error(f"Failed to upload {rel_path}: {e}")
        if conn:
            db_pool.putconn(conn)
        return False

def main():
    if not minio_client.bucket_exists(MINIO_BUCKET):
        minio_client.make_bucket(MINIO_BUCKET)
    
    init_db()
    
    files_to_upload = []
    logger.info(f"Scanning directory: {DATASET_PATH}")
    for root, _, files in os.walk(DATASET_PATH):
        for file in files:
            if file.endswith(".tif"):
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, DATASET_PATH)
                files_to_upload.append((rel_path, abs_path))
    
    total_files = len(files_to_upload)
    logger.info(f"Found {total_files} files to upload.")
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(upload_file, files_to_upload))
    
    producer.flush()
    end_time = time.time()
    
    success_count = sum(results)
    logger.info(f"Ingestion complete. Success: {success_count}/{total_files}")
    logger.info(f"Total time: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()
