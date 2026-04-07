import os
import io
import json
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from minio import Minio
from confluent_kafka import Producer
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingestion_service")

app = FastAPI(title="AI Document Ingestion Service")

# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "document-uploaded")

# Initialize MinIO Client
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# Ensure bucket exists
if not minio_client.bucket_exists(MINIO_BUCKET):
    minio_client.make_bucket(MINIO_BUCKET)
    logger.info(f"Created bucket: {MINIO_BUCKET}")

# Initialize Kafka Producer
kafka_conf = {'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS}
producer = Producer(kafka_conf)

def delivery_report(err, msg):
    if err is not None:
        logger.error(f"Message delivery failed: {err}")
    else:
        logger.info(f"Message delivered to {msg.topic()} [{msg.partition()}]")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        # 1. Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # 2. Upload to MinIO
        minio_client.put_object(
            MINIO_BUCKET,
            file.filename,
            io.BytesIO(file_content),
            file_size,
            content_type=file.content_type
        )
        logger.info(f"Uploaded {file.filename} to MinIO")
        
        # 3. Emit Kafka Event
        event = {
            "filename": file.filename,
            "bucket": MINIO_BUCKET,
            "size": file_size,
            "content_type": file.content_type,
            "status": "UPLOADED"
        }
        producer.produce(
            KAFKA_TOPIC, 
            key=file.filename, 
            value=json.dumps(event), 
            callback=delivery_report
        )
        producer.flush()
        
        return {
            "message": "File uploaded and event emitted",
            "filename": file.filename,
            "bucket": MINIO_BUCKET
        }
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
