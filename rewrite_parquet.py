import os
import pyarrow.parquet as pq
import urllib3
from minio import Minio

def main():
    print("Connecting to MinIO...")
    client = Minio(
        "localhost:9000",
        access_key="admin",
        secret_key="changeme_in_production",
        secure=False
    )
    
    bucket = "legal-bronze"
    object_name = "hf/th1nhng0/vietnamese-legal-documents/content/content_data.parquet"
    local_file = "content_data.parquet"
    rewritten_file = "content_data_rewritten.parquet"
    
    print(f"Downloading {object_name} to {local_file}...")
    client.fget_object(bucket, object_name, local_file)
    
    print(f"Opening Parquet file {local_file}...")
    pf = pq.ParquetFile(local_file)
    schema = pf.schema_arrow
    
    print(f"Rewriting to {rewritten_file} without dictionary encoding...")
    with pq.ParquetWriter(rewritten_file, schema, use_dictionary=False, write_statistics=False) as writer:
        for i, batch in enumerate(pf.iter_batches(batch_size=1000)):
            writer.write_batch(batch)
            if i % 10 == 0:
                print(f"Wrote batch {i}")
                
    print(f"Uploading {rewritten_file} back to MinIO...")
    client.fput_object(bucket, object_name, rewritten_file)
    print("Done!")

if __name__ == "__main__":
    main()
