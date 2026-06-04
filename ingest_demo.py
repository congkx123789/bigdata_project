import os
import sys
from pathlib import Path

# Thêm thư mục gốc vào đường dẫn để import common
sys.path.insert(0, str(Path(__file__).parent))
from common.config import load_config

# Ép hệ thống dùng localhost để kết nối MinIO khi chạy lệnh ngoài Windows
os.environ["MINIO_ENDPOINT"] = "localhost:9000"

from datasets import load_dataset
import pandas as pd
from minio import Minio

cfg = load_config()

client = Minio(
    cfg.minio_endpoint, 
    access_key=cfg.minio_access_key, 
    secret_key=cfg.minio_secret_key, 
    secure=cfg.minio_use_ssl
)

if not client.bucket_exists(cfg.s3_bucket_bronze):
    client.make_bucket(cfg.s3_bucket_bronze)

subsets = ["content", "metadata", "relationships"]
for subset in subsets:
    print(f"Streaming 1000 rows from subset {subset}...")
    try:
        ds = load_dataset(cfg.hf_dataset_repo, name=subset, streaming=True, split="data", trust_remote_code=False)
    except Exception:
        ds = load_dataset(cfg.hf_dataset_repo, name=subset, streaming=True, trust_remote_code=False)
        ds = list(ds.values())[0]
        
    rows = list(ds.take(1000))
    df = pd.DataFrame(rows)
    
    parquet_path = f"data/raw/{subset}_demo.parquet"
    os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
    df.to_parquet(parquet_path)
    
    object_name = f"hf/{cfg.hf_dataset_repo}/{subset}/{subset}_data.parquet"
    client.fput_object(cfg.s3_bucket_bronze, object_name, parquet_path)
    print(f"Upload complete for subset {subset} to MinIO (s3a://{cfg.s3_bucket_bronze}/{object_name})")

print("\nDemo data ingestion completed successfully!")
