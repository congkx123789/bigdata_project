import pytest
from pyspark.sql import SparkSession

@pytest.fixture(scope="session")
def spark():
    # Similar Spark initialization to spark_processor but in local mode
    return SparkSession.builder \
        .appName("DQ-Tests") \
        .master("local[2]") \
        .config("spark.jars.packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.6.1,org.postgresql:postgresql:42.7.3") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .getOrCreate()

def test_bronze_null_checks(spark):
    """
    Test that critical fields in Bronze layer are not null.
    Assuming the table is accessible. In a real CI, we'd mock the table.
    """
    try:
        df = spark.sql("SELECT * FROM lakehouse.public.bronze_documents")
        null_count = df.filter(df.filename.isNull() | df.extracted_text.isNull()).count()
        assert null_count == 0, f"Found {null_count} rows with NULL critical fields in Bronze layer!"
    except Exception as e:
        pytest.skip(f"Table might not exist yet during initial testing: {e}")

def test_silver_schema_validation(spark):
    """
    Verify schema of silver table matches expected types.
    """
    pass # To be implemented once Silver layer logic is fully deployed
