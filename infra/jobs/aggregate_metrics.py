import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, year, count, sum as spark_sum, avg, current_date, when

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aggregate_metrics")

def get_spark_session():
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
    
    return SparkSession.builder \
        .appName("Gold-Aggregation") \
        .config("spark.jars.packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.postgresql:postgresql:42.7.3,org.apache.hadoop:hadoop-aws:3.3.4,com.amazonaws:aws-java-sdk-bundle:1.12.262") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.lakehouse", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.lakehouse.type", "jdbc") \
        .config("spark.sql.catalog.lakehouse.uri", "jdbc:postgresql://postgres:5432/document_db") \
        .config("spark.sql.catalog.lakehouse.jdbc.user", "admin") \
        .config("spark.sql.catalog.lakehouse.jdbc.password", "password123") \
        .config("spark.sql.catalog.lakehouse.jdbc.driver", "org.postgresql.Driver") \
        .config("spark.sql.catalog.lakehouse.warehouse", "s3a://lakehouse/warehouse") \
        .config("spark.sql.catalog.lakehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
        .config("spark.sql.catalog.lakehouse.s3.endpoint", f"http://{MINIO_ENDPOINT}") \
        .config("spark.sql.catalog.lakehouse.s3.access-key-id", MINIO_ACCESS_KEY) \
        .config("spark.sql.catalog.lakehouse.s3.secret-access-key", MINIO_SECRET_KEY) \
        .config("spark.sql.catalog.lakehouse.s3.path-style-access", "true") \
        .config("spark.sql.catalog.lakehouse.client.region", "us-east-1") \
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{MINIO_ENDPOINT}") \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def main():
    spark = get_spark_session()
    
    # 1. Tạo database gold
    spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.gold")
    
    # 2. Đọc Silver layer
    logger.info("Reading silver layer...")
    df_silver = spark.read.table("lakehouse.silver.dieu_khoan_sach")
    df_meta = spark.read.table("lakehouse.bronze.van_ban_metadata")
    
    # 3. Tính toán tổng hợp cho Dashboard (Ví dụ: Thống kê văn bản theo năm và loại)
    logger.info("Aggregating metrics...")
    
    # Bảng 1: Thống kê số lượng văn bản theo loại và năm
    df_gold = df_meta.groupBy("loai_van_ban", year("ngay_ban_hanh").alias("nam_ban_hanh")) \
        .agg(
            count("*").alias("so_van_ban"),
            spark_sum(when(col("tinh_trang_hieu_luc").contains("Còn"), 1).otherwise(0)).alias("van_ban_con_hl"),
            spark_sum(when(col("tinh_trang_hieu_luc").contains("Hết"), 1).otherwise(0)).alias("van_ban_het_hl")
        ).withColumn("agg_date", current_date())
        
    # Ghi đè vào Iceberg Gold
    logger.info("Writing to Iceberg: lakehouse.gold.thong_ke_phap_luat")
    df_gold.writeTo("lakehouse.gold.thong_ke_phap_luat") \
        .tableProperty("format-version", "2") \
        .createOrReplace()
        
    count = spark.read.table("lakehouse.gold.thong_ke_phap_luat").count()
    logger.info(f"Gold processing successful! Total rows in aggregation table: {count}")

if __name__ == "__main__":
    main()
