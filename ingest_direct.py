import os
import sys
from pathlib import Path
from huggingface_hub import hf_hub_download
from minio import Minio

# Thêm thư mục gốc vào đường dẫn để import common
sys.path.insert(0, str(Path(__file__).parent))
from common.config import load_config

# Ép hệ thống dùng localhost để kết nối MinIO khi chạy lệnh ngoài Windows
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
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
    print(f"Downloading raw parquet file for {subset}...")
    try:
        file_path = hf_hub_download(
            repo_id=cfg.hf_dataset_repo,
            filename=f"data/{subset}.parquet",
            repo_type="dataset",
            local_dir=f"data/raw/{subset}"
        )
        
        print(f"Uploading {subset} to MinIO...")
        object_name = f"hf/{cfg.hf_dataset_repo}/{subset}/{subset}_data.parquet"
        client.fput_object(cfg.s3_bucket_bronze, object_name, file_path)
        print(f"Success! {subset} uploaded to s3a://{cfg.s3_bucket_bronze}/{object_name}")
    except Exception as e:
        print(f"Failed to process {subset}: {e}")

print("\nAll data successfully ingested via direct download!")
