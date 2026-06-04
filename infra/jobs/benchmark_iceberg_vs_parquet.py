import os
import time
import json
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import rand, expr

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("benchmark")

def get_spark_session():
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "password123")
    
    return SparkSession.builder \
        .appName("Benchmark-Iceberg-Vs-Parquet") \
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
        .config("spark.sql.catalog.lakehouse.client.region", "us-east-1") \
        .config("spark.hadoop.fs.s3a.endpoint", f"http://{MINIO_ENDPOINT}") \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def run_benchmark():
    spark = get_spark_session()
    
    # Generate 10M dummy records for heavier load
    num_records = 10000000
    logger.info(f"Generating {num_records} dummy records for benchmark...")
    
    df = spark.range(0, num_records).selectExpr(
        "id",
        "concat('doc_', cast(id as string), '.pdf') as filename",
        "concat('extracted text block number ', cast(rand()*1000 as string)) as extracted_text",
        "cast(rand() * 1000 as int) as word_count"
    )

    results = {}

    # 1. Write Parquet
    start = time.time()
    df.write.mode("overwrite").parquet("s3a://documents/benchmarks/raw_parquet")
    results['write_parquet_time_sec'] = time.time() - start
    logger.info(f"Parquet Write Time: {results['write_parquet_time_sec']:.2f}s")

    # 2. Write Iceberg
    spark.sql("DROP TABLE IF EXISTS lakehouse.public.bench_iceberg")
    start = time.time()
    df.writeTo("lakehouse.public.bench_iceberg").create()
    results['write_iceberg_time_sec'] = time.time() - start
    logger.info(f"Iceberg Write Time: {results['write_iceberg_time_sec']:.2f}s")

    # 3. Query Parquet
    start = time.time()
    spark.read.parquet("s3a://documents/benchmarks/raw_parquet").filter("word_count > 500").count()
    results['query_parquet_time_sec'] = time.time() - start

    # 4. Query Iceberg
    start = time.time()
    spark.read.table("lakehouse.public.bench_iceberg").filter("word_count > 500").count()
    results['query_iceberg_time_sec'] = time.time() - start

    # 5. Row-level Update Parquet (Read -> Modify -> Overwrite)
    start = time.time()
    pq_df = spark.read.parquet("s3a://documents/benchmarks/raw_parquet")
    from pyspark.sql.functions import when, col
    pq_df_updated = pq_df.withColumn("word_count", when(col("id") == 1500000, 9999).otherwise(col("word_count")))
    pq_df_updated.write.mode("overwrite").parquet("s3a://documents/benchmarks/raw_parquet_updated")
    results['update_parquet_time_sec'] = time.time() - start

    # 6. Row-level Update Iceberg (SQL UPDATE)
    start = time.time()
    spark.sql("UPDATE lakehouse.public.bench_iceberg SET word_count = 9999 WHERE id = 1500000")
    results['update_iceberg_time_sec'] = time.time() - start

    logger.info("Benchmark complete.")
    print(json.dumps(results, indent=4))

    # Write results out
    os.makedirs("/workspace/data/benchmarks", exist_ok=True)
    with open("/workspace/data/benchmarks/iceberg_vs_parquet.json", "w") as f:
        json.dump(results, f, indent=4)

if __name__ == "__main__":
    run_benchmark()
