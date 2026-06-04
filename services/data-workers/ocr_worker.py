import os
import json
import logging
import io
from minio import Minio
from confluent_kafka import Consumer, Producer
from paddleocr import PaddleOCR
from unstructured.partition.auto import partition
import paddle.inference

# Fix compatibility issue in PaddlePaddle 2.6+ for PaddleOCR
if not hasattr(paddle.inference.Config, 'set_optimization_level'):
    paddle.inference.Config.set_optimization_level = lambda self, level: None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_worker")

# Configs
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
IN_TOPIC = os.getenv("IN_TOPIC", "document-uploaded")
OUT_TOPIC = os.getenv("OUT_TOPIC", "document-extracted-text")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")

# Initialize MinIO
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

# Initialize OCR
ocr = PaddleOCR(use_textline_orientation=True, lang='vi')

# Kafka Config
consumer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'ocr_workers_group',
    'auto.offset.reset': 'earliest'
}
consumer = Consumer(consumer_conf)
producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})

def process_file(filename, bucket):
    try:
        response = minio_client.get_object(bucket, filename)
        file_bytes = response.read()
        
        ext = filename.split('.')[-1].lower()
        extracted_text = ""
        
        if ext in ['png', 'jpg', 'jpeg', 'pdf', 'tif']:
            result = ocr.ocr(file_bytes, cls=True)
            for line in result:
                for word_info in line:
                    extracted_text += word_info[1][0] + " "
        else:
            elements = partition(file_wrapper=io.BytesIO(file_bytes))
            extracted_text = "\n".join([str(el) for el in elements])
            
        return extracted_text.strip()
    except Exception as e:
        logger.error(f"Error processing {filename}: {str(e)}")
        return ""

def main():
    consumer.subscribe([IN_TOPIC])
    logger.info(f"Subscribed to {IN_TOPIC}. Waiting for messages...")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                continue
            
            data = json.loads(msg.value().decode('utf-8'))
            filename = data.get("filename")
            bucket = data.get("bucket", "documents")
            
            logger.info(f"Processing file: {filename}")
            
            text = process_file(filename, bucket)
            
            if text:
                out_msg = {
                    "filename": filename,
                    "extracted_text": text,
                    "bucket": bucket,
                    "status": "EXTRACTED"
                }
                producer.produce(OUT_TOPIC, key=filename, value=json.dumps(out_msg))
                producer.flush()
                logger.info(f"Successfully processed {filename} and published to {OUT_TOPIC}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == '__main__':
    main()
