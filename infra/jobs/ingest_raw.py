import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, to_timestamp, current_timestamp, regexp_replace

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ingest_raw")

def get_spark_session():
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
    
    return SparkSession.builder \
        .appName("Bronze-Ingestion") \
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
    
    # 1. Tạo database bronze
    spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.bronze")
    
    # 2. Đọc JSON files từ MinIO
    raw_path = "s3a://raw-legal-docs/metadata/*.json"
    logger.info(f"Reading raw JSON from {raw_path}")
    
    df = spark.read.option("multiline", "true").json(raw_path)
    
    # Chuẩn hóa schema cho Bronze
    # Sửa định dạng ngày (dd/MM/yyyy) và lấy 10 ký tự đầu để tránh lỗi chuỗi thừa (vd: '08/06/1996 Ngày hết hiệu lực')
    from pyspark.sql.functions import substring
    def parse_vn_date(c):
        return to_date(substring(c, 1, 10), "dd/MM/yyyy")
        
    df_bronze = df.select(
        col("id").cast("bigint"),
        col("so_ky_hieu"),
        col("title"),
        col("loai_van_ban"),
        col("nganh"),
        col("linh_vuc"),
        col("co_quan_ban_hanh"),
        col("nguoi_ky"),
        parse_vn_date(col("ngay_ban_hanh")).alias("ngay_ban_hanh"),
        parse_vn_date(col("ngay_co_hieu_luc")).alias("ngay_co_hieu_luc"),
        parse_vn_date(col("ngay_het_hieu_luc")).alias("ngay_het_hieu_luc"),
        col("tinh_trang_hieu_luc"),
        current_timestamp().alias("ingested_at")
    ).filter(col("id").isNotNull())
    
    # 4. Ghi đè (Overwrite) vào Iceberg
    logger.info("Writing to Iceberg: lakehouse.bronze.van_ban_metadata")
    df_bronze.writeTo("lakehouse.bronze.van_ban_metadata") \
        .tableProperty("format-version", "2") \
        .tableProperty("write.merge.mode", "merge-on-read") \
        .partitionedBy("loai_van_ban") \
        .createOrReplace()
        
    count = spark.read.table("lakehouse.bronze.van_ban_metadata").count()
    logger.info(f"Ingestion successful! Total rows in bronze: {count}")

if __name__ == "__main__":
    main()
