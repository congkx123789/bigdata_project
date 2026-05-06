import pandas as pd
import json
import logging
import os
import re
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vi_legal_ingestor")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = "document-uploaded"

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleaner = re.compile('<.*?>')
    return re.sub(cleaner, '', raw_html)

def main():
    path = "datasets/vi-legal/data/content.parquet"
    logger.info(f"Reading parquet file: {path}")
    
    df = pd.read_parquet(path)
    
    producer = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS})
    
    count = 0
    total = len(df)
    
    for index, row in df.iterrows():
        clean_text = clean_html(row['content_html'])
        
        # We simulate the ingestion event
        event = {
            "id": str(row['id']),
            "content": clean_text, # Sending full text for embedding pipeline
            "filename": f"legal_doc_{row['id']}.txt",
            "status": "PROCESSING",
            "source": "vi-legal"
        }
        
        producer.produce(KAFKA_TOPIC, key=str(row['id']), value=json.dumps(event))
        
        count += 1
        if count % 100 == 0:
            logger.info(f"Sent {count}/{total} documents to Kafka...")
            producer.flush()
            
    producer.flush()
    logger.info(f"Successfully sent {count} legal documents for vectorization!")

if __name__ == "__main__":
    main()
