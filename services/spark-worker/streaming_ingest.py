import os
import json
import time
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType
from pymilvus import connections, Collection, utility, FieldSchema, CollectionSchema, DataType
from sentence_transformers import SentenceTransformer

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SparkStreamingIngest")

# --- CONFIGURATION ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "bd_legal_kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "legal_documents")
MILVUS_HOST = os.getenv("MILVUS_HOST", "bd_legal_milvus")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")

# --- INITIALIZE MILVUS & MODEL ---
def setup_milvus():
    """Đảm bảo Milvus sẵn sàng và collection được khởi tạo."""
    max_retries = 10
    for i in range(max_retries):
        try:
            logger.info(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT} (Attempt {i+1}/{max_retries})...")
            connections.connect("default", host=MILVUS_HOST, port=int(MILVUS_PORT))
            
            collection_name = "vi_legal_rag"
            if not utility.has_collection(collection_name):
                logger.info(f"Creating collection {collection_name}...")
                fields = [
                    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                    FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=255),
                    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1024) # BGE-M3 dim
                ]
                schema = CollectionSchema(fields, "Legal documents RAG collection")
                collection = Collection(collection_name, schema)
                
                # Create Index
                index_params = {
                    "metric_type": "L2",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128}
                }
                collection.create_index(field_name="vector", index_params=index_params)
                logger.info(f"✅ Collection {collection_name} created and indexed.")
            else:
                logger.info(f"✅ Collection {collection_name} already exists.")
            
            collection = Collection(collection_name)
            collection.load()
            return collection
        except Exception as e:
            logger.error(f"❌ Failed to connect to Milvus: {e}")
            if i < max_retries - 1:
                time.sleep(5)
            else:
                raise

# Khởi tạo model embedding
logger.info("Loading SentenceTransformer model...")
model = SentenceTransformer("BAAI/bge-m3")

def process_batch(df, batch_id):
    """Xử lý từng micro-batch từ Spark Stream."""
    rows = df.collect()
    if not rows:
        return
        
    logger.info(f"🚀 Processing batch {batch_id} with {len(rows)} records...")
    
    # Đảm bảo kết nối Milvus trong worker
    try:
        connections.connect("default", host=MILVUS_HOST, port=int(MILVUS_PORT))
        collection = Collection("vi_legal_rag")
    except Exception as e:
        logger.error(f"Worker failed to connect to Milvus: {e}")
        return
    
    filenames = []
    titles = []
    contents = []
    vectors = []
    
    for row in rows:
        filename = row.filename or "kafka_ingest"
        title = row.title or "Văn bản mới"
        content = row.content or ""
        
        if not content:
            continue
            
        # Tạo embedding vector
        vector = model.encode(content).tolist()
        
        filenames.append(filename)
        titles.append(title)
        contents.append(content)
        vectors.append(vector)
        
    if titles:
        data = [
            filenames,
            titles,
            contents,
            vectors
        ]
        try:
            collection.insert(data)
            collection.flush()
            logger.info(f"✅ Successfully inserted {len(titles)} records into Milvus.")
        except Exception as e:
            logger.error(f"❌ Failed to insert into Milvus: {e}")

def main():
    # 1. Khởi tạo Spark Session
    logger.info(f"Starting Spark session with master: {SPARK_MASTER}")
    spark = SparkSession.builder \
        .appName("NexusLegalIngestion") \
        .master(SPARK_MASTER) \
        .config("spark.driver.host", "bd-legal-spark-ingest") \
        .config("spark.driver.bindAddress", "0.0.0.0") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1") \
        .config("spark.executor.memory", "2g") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")

    # 2. Đảm bảo Milvus sẵn sàng
    setup_milvus()

    # 3. Định nghĩa Schema
    schema = StructType([
        StructField("filename", StringType(), True),
        StructField("title", StringType(), True),
        StructField("content", StringType(), True)
    ])

    # 4. Đọc dữ liệu từ Kafka
    logger.info(f"Subscribing to Kafka topic: {KAFKA_TOPIC}")
    raw_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # 5. Parse JSON
    parsed_df = raw_df.selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), schema).alias("data")) \
        .select("data.*")

    # 6. Ghi dữ liệu vào Milvus thông qua foreachBatch
    query = parsed_df.writeStream \
        .foreachBatch(process_batch) \
        .start()

    query.awaitTermination()

if __name__ == "__main__":
    main()
