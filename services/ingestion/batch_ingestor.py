import os
import io
import json
import time
import logging
import psycopg2
from datetime import datetime
from minio import Minio
from confluent_kafka import Producer
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("legal_batch_ingestor")

# ── Configuration ──────────────────────────────────────────────────────────────
METADATA_PARQUET = os.getenv("METADATA_PARQUET", "datasets/vi-legal/raw_parquet/data/metadata.parquet")
MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET      = "raw-legal-docs"

KAFKA_BOOTSTRAP   = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC       = "legal-doc-ingested"

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5433"),
    "database": "document_db",
    "user":     "admin",
    "password": "password123",
}

BATCH_SIZE   = 500    # Số bản ghi mỗi file JSON batch
MAX_WORKERS  = 8      # Luồng upload song song

# ── Clients ────────────────────────────────────────────────────────────────────
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP})

# ── Database Init ──────────────────────────────────────────────────────────────
def init_db():
    conn = psycopg2.connect(**DB_CONFIG)
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS legal_ingest_log (
            id          SERIAL PRIMARY KEY,
            batch_key   TEXT UNIQUE,
            record_count INT,
            status      TEXT,
            created_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database schema initialized.")

# ── MinIO Bucket ───────────────────────────────────────────────────────────────
def ensure_bucket():
    if not minio_client.bucket_exists(MINIO_BUCKET):
        minio_client.make_bucket(MINIO_BUCKET)
        logger.info(f"Bucket '{MINIO_BUCKET}' created.")
    else:
        logger.info(f"Bucket '{MINIO_BUCKET}' already exists.")

# ── Upload Batch ───────────────────────────────────────────────────────────────
def upload_batch(args):
    batch_idx, records = args
    batch_key = f"metadata/batch_{batch_idx:05d}.json"
    payload   = json.dumps(records, ensure_ascii=False, default=str).encode("utf-8")

    try:
        minio_client.put_object(
            MINIO_BUCKET,
            batch_key,
            data=io.BytesIO(payload),
            length=len(payload),
            content_type="application/json",
        )
        # Bắn Kafka event
        event = {
            "batch_key":    batch_key,
            "record_count": len(records),
            "dataset":      "th1nhng0/vietnamese-legal-documents",
            "config":       "metadata",
            "timestamp":    datetime.utcnow().isoformat(),
        }
        producer.produce(
            KAFKA_TOPIC,
            key=batch_key,
            value=json.dumps(event, ensure_ascii=False),
        )
        return (batch_idx, len(records), True)
    except Exception as e:
        logger.error(f"Batch {batch_idx} FAILED: {e}")
        return (batch_idx, 0, False)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    logger.info("=== Legal Batch Ingestor Start ===")
    logger.info(f"Metadata Parquet: {os.path.abspath(METADATA_PARQUET)}")

    try:
        import pandas as pd
        logger.info("Loading 'metadata.parquet' using pandas...")
        df = pd.read_parquet(METADATA_PARQUET)
        
        # Chuyển đổi timestamp thành chuỗi nếu cần, điền nan bằng None
        df = df.where(pd.notnull(df), None)
        
        records_list = df.to_dict(orient='records')
        total = len(records_list)
        logger.info(f"Loaded {total:,} records. Columns: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        logger.error("Hãy chạy 'python resume_hf_download.py' trước để tải file parquet.")
        raise

    ensure_bucket()
    init_db()

    # Chia thành batches
    batches = []
    for i in range(0, total, BATCH_SIZE):
        chunk = records_list[i:min(i + BATCH_SIZE, total)]
        batches.append((i // BATCH_SIZE, chunk))

    logger.info(f"Uploading {len(batches)} batches ({BATCH_SIZE} records/batch) → MinIO '{MINIO_BUCKET}'")

    start_time = time.time()
    success_count = 0
    fail_count    = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_idx, count, ok in executor.map(upload_batch, batches):
            if ok:
                success_count += count
            else:
                fail_count += 1
            if (batch_idx + 1) % 20 == 0:
                elapsed = time.time() - start_time
                pct = (batch_idx + 1) / len(batches) * 100
                logger.info(f"Progress: {pct:.1f}% | Uploaded: {success_count:,} | Time: {elapsed:.1f}s")

    producer.flush()
    elapsed = time.time() - start_time

    logger.info("=" * 50)
    logger.info(f"✅ Ingestion Complete!")
    logger.info(f"   Records uploaded  : {success_count:,}/{total:,}")
    logger.info(f"   Failed batches    : {fail_count}")
    logger.info(f"   Total time        : {elapsed:.2f}s")
    logger.info(f"   Throughput        : {success_count/elapsed:.0f} records/sec")
    logger.info(f"   Kafka topic       : {KAFKA_TOPIC}")
    logger.info(f"   MinIO bucket      : {MINIO_BUCKET}")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()
