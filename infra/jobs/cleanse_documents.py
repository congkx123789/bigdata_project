import os
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr, length, current_timestamp, regexp_replace, trim, broadcast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanse_documents")

def get_spark_session():
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
    
    return SparkSession.builder \
        .appName("Silver-Cleansing") \
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
        .config("spark.sql.parquet.enableVectorizedReader", "false") \
        .getOrCreate()

def main():
    spark = get_spark_session()
    
    # 1. Tạo database silver
    spark.sql("CREATE NAMESPACE IF NOT EXISTS lakehouse.silver")
    
    # 2. Đọc metadata từ bronze
    logger.info("Reading bronze metadata...")
    df_meta = spark.read.table("lakehouse.bronze.van_ban_metadata")
    
    # 3. Đọc content từ file parquet (trong thư mục workspace)
    # File content chứa nội dung các điều khoản (id: string, content_html: string)
    content_path = "/workspace/datasets/vi-legal/raw_parquet/data/content.parquet"
    if not os.path.exists(content_path):
        logger.warning(f"Không tìm thấy {content_path}! Có thể file lưu ở pattern khác, thử regex...")
        content_path = "/workspace/datasets/vi-legal/raw_parquet/data/content*.parquet"
        
    df_content = spark.read.parquet(content_path)
    
    # id trong content là "doc_id_dieu_id" ví dụ "86161_2299066" -> ta cần split lấy doc_id làm int
    # Để join với metadata
    df_content = df_content.withColumn("doc_id", expr("split(id, '_')[0]").cast("bigint"))
    
    # 4. Join và Clean HTML
    logger.info("Joining & Cleaning HTML...")
    # Strip HTML siêu cơ bản bằng regex
    clean_html_expr = regexp_replace(col("content_html"), "<[^>]*>", "")
    clean_html_expr = trim(regexp_replace(clean_html_expr, "&nbsp;|\\n|\\r", " "))
    
    df_joined = df_content.join(broadcast(df_meta), df_content.doc_id == df_meta.id, "inner")
    
    df_silver = df_joined.select(
        df_content["id"].alias("id_dieu_khoan"),
        df_meta["id"].alias("id_van_ban"),
        col("so_ky_hieu"),
        col("loai_van_ban"),
        col("tinh_trang_hieu_luc"),
        clean_html_expr.alias("noi_dung_sach"),
        length(clean_html_expr).alias("char_count"),
        expr("size(split(trim(regexp_replace(content_html, '<[^>]*>', '')), ' '))").alias("word_count"),
        current_timestamp().alias("silver_at")
    )
    
    # 5. Ghi vào Iceberg Silver
    logger.info("Writing to Iceberg: lakehouse.silver.dieu_khoan_sach")
    df_silver.writeTo("lakehouse.silver.dieu_khoan_sach") \
        .tableProperty("format-version", "2") \
        .tableProperty("write.merge.mode", "merge-on-read") \
        .partitionedBy("loai_van_ban") \
        .createOrReplace()
        
    count = spark.read.table("lakehouse.silver.dieu_khoan_sach").count()
    logger.info(f"Silver processing successful! Total rows: {count}")

if __name__ == "__main__":
    main()
