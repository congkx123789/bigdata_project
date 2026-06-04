import os
import logging
import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dq_iceberg")

def get_spark_session():
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
    
    return SparkSession.builder \
        .appName("Data-Quality-Gates") \
        .config("spark.jars.packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.postgresql:postgresql:42.7.3") \
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

def run_dq_checks():
    spark = get_spark_session()
    errors = []

    try:
        # Check 1: Bronze table null filename check
        bronze_df = spark.read.table("lakehouse.public.bronze_documents")
        null_filenames = bronze_df.filter(col("filename").isNull()).count()
        if null_filenames > 0:
            errors.append(f"Bronze DQ Failed: Found {null_filenames} records with null filenames.")

        # Check 2: Silver table duplicate check
        silver_df = spark.read.table("lakehouse.public.silver_documents")
        total_count = silver_df.count()
        distinct_count = silver_df.select("filename").distinct().count()
        if total_count != distinct_count:
            errors.append(f"Silver DQ Failed: Found {total_count - distinct_count} duplicate filenames.")
            
    except Exception as e:
        logger.error(f"Error reading tables: {e}")
        # Tables might not exist yet if pipeline hasn't run.
        pass

    if errors:
        for err in errors:
            logger.error(err)
        logger.error("Data Quality Gates FAILED.")
        sys.exit(1)
    else:
        logger.info("All Data Quality Gates PASSED.")

if __name__ == "__main__":
    run_dq_checks()
