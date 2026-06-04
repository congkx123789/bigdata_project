#!/bin/bash
set -e

echo "=========================================="
echo "Starting Lakehouse Benchmarking Process"
echo "=========================================="

echo "Running Spark Benchmark Job..."
docker exec spark-master /opt/spark/bin/spark-submit \
    --master local[*] \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.apache.iceberg:iceberg-aws-bundle:1.6.1,org.postgresql:postgresql:42.7.3,org.apache.hadoop:hadoop-aws:3.3.4 \
    --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
    /infra/jobs/benchmark_iceberg_vs_parquet.py

echo "Benchmark Complete."
echo "Results saved to /workspace/data/benchmarks/iceberg_vs_parquet.json"
cat /workspace/data/benchmarks/iceberg_vs_parquet.json
