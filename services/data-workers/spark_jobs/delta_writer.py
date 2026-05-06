"""
Spark Job: Nhận text đã bóc tách, làm sạch và lưu vào Delta Lake.
Chạy dưới dạng PySpark job, được trigger bởi Airflow.
"""

def clean_text(text: str) -> str:
    """Loại bỏ ký tự rác, normalize whitespace."""
    import re
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def write_to_delta_lake(chunks: list, doc_id: str):
    """
    Ghi các text chunks đã qua làm sạch vào Delta Lake.
    TODO: Tích hợp PySpark + Delta Lake writer.
    """
    # from pyspark.sql import SparkSession
    # spark = SparkSession.builder.appName("DeltaWriter").getOrCreate()
    # df = spark.createDataFrame([(doc_id, c) for c in chunks], ["doc_id", "chunk"])
    # df.write.format("delta").mode("append").save("/data/delta/documents")
    print(f"[SPARK] Written {len(chunks)} chunks for doc {doc_id} to Delta Lake.")

if __name__ == "__main__":
    # Test
    sample = ["Đây là đoạn text mẫu số 1.", "Đây là đoạn text mẫu số 2."]
    write_to_delta_lake(sample, "test-doc-001")
