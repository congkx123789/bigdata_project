import os
import subprocess
import requests
from tqdm import tqdm

# Configuration
HF_REPO = "Cong123779/bigdata-milvus-backup"
FILES = [
    "infra_milvus_data.tar.gz",
    "infra_postgres_data.tar.gz",
    "infra_minio_data.tar.gz",
    "infra_etcd_data.tar.gz"
]
DATA_DIR = "./data"
BASE_URL = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main"

def download_file(filename):
    url = f"{BASE_URL}/{filename}"
    print(f"📥 Downloading {filename}...")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    
    with open(filename, 'wb') as f, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as bar:
        for data in response.iter_content(chunk_size=1024):
            size = f.write(data)
            bar.update(size)

def restore():
    # 1. Create data directory if not exists
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created directory {DATA_DIR}")

    # 2. Download each file
    for file in FILES:
        if not os.path.exists(file):
            download_file(file)
        else:
            print(f"✅ {file} already exists, skipping download.")

    # 3. Extract files
    print("\n📦 Extracting archives to Drive D...")
    for file in FILES:
        print(f"Extracting {file}...")
        # Mapping filename to subfolder
        # infra_milvus_data.tar.gz -> data/milvus
        # We use -C to extract into the data folder
        try:
            # tar -xzf infra_milvus_data.tar.gz -C ./data
            # Note: The tar files in backup_brain.sh were created with -C infra <folder>
            # So they contain the folder itself.
            subprocess.run(["tar", "-xzf", file, "-C", DATA_DIR], check=True)
            print(f"✅ Extracted {file}")
        except Exception as e:
            print(f"❌ Error extracting {file}: {e}")

    print("\n✨ All data restored successfully to Drive D!")
    print("🚀 You can now restart your Docker containers.")

if __name__ == "__main__":
    restore()
