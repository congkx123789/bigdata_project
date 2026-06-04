import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, current_timestamp, length, word_count
from pyspark.sql.types import StringType, StructType, StructField

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spark_processor")

# Environment variables
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "document-extracted-text")
CHECKPOINT_LOCATION = "s3a://documents/checkpoints/bronze_documents"

# Initialize Spark Session with Iceberg and Kafka
spark = SparkSession.builder \
    .appName("BigData-Lakehouse-Processor") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.postgresql:postgresql:42.7.3") \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.lakehouse.type", "jdbc") \
    .config("spark.sql.catalog.lakehouse.uri", "jdbc:postgresql://postgres:5432/document_db") \
    .config("spark.sql.catalog.lakehouse.jdbc.user", "admin") \
    .config("spark.sql.catalog.lakehouse.jdbc.password", "password123") \
    .config("spark.sql.catalog.lakehouse.jdbc.driver", "org.postgresql.Driver") \
    .config("spark.sql.catalog.lakehouse.warehouse", "s3a://documents/warehouse") \
    .config("spark.sql.catalog.lakehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
    .config("spark.sql.catalog.lakehouse.s3.endpoint", f"http://{MINIO_ENDPOINT}") \
    .config("spark.sql.catalog.lakehouse.s3.access-key-id", MINIO_ACCESS_KEY) \
    .config("spark.sql.catalog.lakehouse.s3.secret-access-key", MINIO_SECRET_KEY) \
    .config("spark.sql.catalog.lakehouse.s3.path-style-access", "true") \
    .getOrCreate()

# Create table if not exists
spark.sql("""
CREATE TABLE IF NOT EXISTS lakehouse.public.bronze_documents (
    filename STRING,
    extracted_text STRING,
    bucket STRING,
    status STRING,
    ingested_at TIMESTAMP
)
USING iceberg
""")

# Schema for incoming Kafka Message
schema = StructType([
    StructField("filename", StringType()),
    StructField("extracted_text", StringType()),
    StructField("bucket", StringType()),
    StructField("status", StringType())
])

def process_stream():
    # Read from Kafka
    df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # Parse JSON values
    parsed_df = df.selectExpr("CAST(value AS STRING)") \
        .select(from_json(col("value"), schema).alias("data")) \
        .select("data.*") \
        .withColumn("ingested_at", current_timestamp())

    # Write to Iceberg Bronze Table
    query = parsed_df.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .trigger(processingTime="1 minute") \
        .option("checkpointLocation", CHECKPOINT_LOCATION) \
        .toTable("lakehouse.public.bronze_documents")

    logger.info("Started streaming job into lakehouse.public.bronze_documents")
    query.awaitTermination()

if __name__ == "__main__":
    process_stream()
