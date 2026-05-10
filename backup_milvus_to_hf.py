import os
import subprocess
import tarfile
import time
from pathlib import Path
from huggingface_hub import HfApi, create_repo

# --- Configuration ---
TOKEN = os.getenv("HF_TOKEN", "") # REDACTED
REPO_ID = "Cong123779/bigdata-milvus-backup"
VOLUMES = [
    "infra_milvus_data",
    "infra_etcd_data",
    "infra_minio_data",
    "infra_postgres_data",
]
BACKUP_DIR = Path("./hf_snapshots")
# ---------------------

def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result

def backup_volume(volume_name):
    print(f"\n--- Backing up volume: {volume_name} ---")
    tar_name = f"{volume_name}.tar.gz"
    tar_path = BACKUP_DIR / tar_name
    
    # Use a temporary container to tar the volume
    # This is a safe way to access Docker volume data
    cmd = (
        f"docker run --rm -v {volume_name}:/data -v {BACKUP_DIR.absolute()}:/backup "
        f"alpine tar czf /backup/{tar_name} -C /data ."
    )
    run_command(cmd)
    return tar_path

def main():
    # 1. Prepare
    BACKUP_DIR.mkdir(exist_ok=True)
    api = HfApi(token=TOKEN)
    
    print(f"🚀 Starting backup to Hugging Face (Private Repo: {REPO_ID})")
    
    try:
        # Create private repo if not exists
        create_repo(repo_id=REPO_ID, repo_type="dataset", token=TOKEN, private=True)
        print(f"✅ Created/Verified private repository: {REPO_ID}")
    except Exception as e:
        if "already" in str(e).lower() or "conflict" in str(e).lower():
            print(f"ℹ️ Repository {REPO_ID} already exists, continuing.")
        else:
            print(f"❌ Error creating repository: {e}")
            return

    # 2. Backup volumes
    uploaded_files = []
    for vol in VOLUMES:
        tar_name = f"{vol}.tar.gz"
        tar_path = BACKUP_DIR / tar_name
        
        # Skip compression if file exists and is "fresh" (created in the last hour)
        if tar_path.exists() and (time.time() - tar_path.stat().st_mtime < 3600):
            print(f"⏩ Found existing backup for {vol}, skipping compression.")
        else:
            tar_path = backup_volume(vol)
            
        if tar_path.exists():
            size_gb = tar_path.stat().st_size / (1024**3)
            print(f"📦 Created/Found {tar_path.name} ({size_gb:.2f} GB)")
            print(f"⬆️ Uploading to Hugging Face...")
            
            api.upload_file(
                path_or_fileobj=str(tar_path),
                path_in_repo=tar_path.name,
                repo_id=REPO_ID,
                repo_type="dataset",
            )
            print(f"✅ Uploaded {tar_path.name}")
            uploaded_files.append(tar_path.name)
        else:
            print(f"❌ Failed to create/find backup for {vol}")

    # 3. Cleanup
    print("\n" + "="*30)
    print("🎉 BACKUP COMPLETE!")
    print(f"URL: https://huggingface.co/datasets/{REPO_ID}")
    print(f"Uploaded files: {', '.join(uploaded_files)}")
    print("="*30)

if __name__ == "__main__":
    main()
