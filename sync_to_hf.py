import os
import subprocess
import tarfile
import time
from pathlib import Path
from huggingface_hub import HfApi, create_repo, login

# --- Configuration ---
TOKEN = os.getenv("HF_TOKEN", "your_token_here")
REPO_ID = "Cong123779/bigdata-assets"
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
    print(f"--- Backing up volume: {volume_name} ---")
    tar_name = f"{volume_name}.tar.gz"
    tar_path = BACKUP_DIR / tar_name
    
    # Use a temporary container to tar the volume
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
    
    try:
        create_repo(repo_id=REPO_ID, repo_type="dataset", token=TOKEN, private=False)
        print(f"Created/Verified public repository: {REPO_ID}")
    except Exception as e:
        print(f"Repository {REPO_ID} already exists or error: {e}")

    # 2. Backup volumes
    uploaded_files = []
    for vol in VOLUMES:
        tar_path = backup_volume(vol)
        if tar_path.exists():
            print(f"Uploading {tar_path.name} to Hugging Face...")
            api.upload_file(
                path_or_fileobj=str(tar_path),
                path_in_repo=tar_path.name,
                repo_id=REPO_ID,
                repo_type="dataset",
            )
            uploaded_files.append(tar_path.name)
        else:
            print(f"Failed to create backup for {vol}")

    # 3. Cleanup
    print("\n--- Sync Complete ---")
    print(f"Uploaded files: {', '.join(uploaded_files)}")
    print("You can now restore this data on another machine using restore_from_hf.py")

if __name__ == "__main__":
    main()
