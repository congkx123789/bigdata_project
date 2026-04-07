import os
import json
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf, from_json
from pyspark.sql.types import StringType, StructType, StructField, IntegerType
from paddleocr import PaddleOCR
from unstructured.partition.auto import partition
from minio import Minio
import io

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spark_processor")

# Environment variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "documents")
DELTA_PATH = os.getenv("DELTA_PATH", "s3a://documents/delta_lake/processed_text")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "document-uploaded")

# Initialize PaddleOCR (Use GPU if RTX 5060 Ti is available)
ocr = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=True)

# MinIO Client for downloading files in UDF
minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

def process_file_udf(filename, bucket):
    """
    UDF to process file from MinIO using PaddleOCR or Unstructured.io
    """
    try:
        # Download file from MinIO
        response = minio_client.get_object(bucket, filename)
        file_bytes = response.read()
        
        # Decide processing based on extension
        ext = filename.split('.')[-1].lower()
        extracted_text = ""
        
        if ext in ['png', 'jpg', 'jpeg', 'pdf']:
            # Use PaddleOCR for images/PDFs
            result = ocr.ocr(file_bytes, cls=True)
            for line in result:
                for word_info in line:
                    extracted_text += word_info[1][0] + " "
        else:
            # Use Unstructured for other formats (docx, txt, etc.)
            elements = partition(file_wrapper=io.BytesIO(file_bytes))
            extracted_text = "\n".join([str(el) for el in elements])
            
        return extracted_text.strip()
    except Exception as e:
        logger.error(f"Error processing {filename}: {str(e)}")
        return f"ERROR: {str(e)}"

# Register UDF
spark_udf = udf(process_file_udf, StringType())

# Initialize Spark Session with Delta and Kafka
spark = SparkSession.builder \
    .appName("AI-Document-Processor") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.1,io.delta:delta-core_2.12:2.4.0,org.apache.hadoop:hadoop-aws:3.3.4") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.hadoop.fs.s3a.endpoint", f"http://{MINIO_ENDPOINT}") \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .get_builder().getOrCreate()

# Schema for Kafka Message
schema = StructType([
    StructField("filename", StringType()),
    StructField("bucket", StringType()),
    StructField("size", IntegerType()),
    StructField("content_type", StringType()),
    StructField("status", StringType())
])

# Read from Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
    .option("subscribe", KAFKA_TOPIC) \
    .load()

# Parse JSON values
parsed_df = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# Process and extract text
processed_df = parsed_df.withColumn("extracted_text", spark_udf(col("filename"), col("bucket")))

# Write to Delta Lake
query = processed_df.writeStream \
    .format("delta") \
    .outputMode("append") \
    .option("checkpointLocation", "s3a://documents/checkpoints/document_processor") \
    .start(DELTA_PATH)

query.awaitTermination()
