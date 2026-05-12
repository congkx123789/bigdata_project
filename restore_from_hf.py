import os
import subprocess
from pathlib import Path
from huggingface_hub import hf_hub_download

# --- Configuration ---
TOKEN = os.getenv("HF_TOKEN", None) # Optional: Will work if repo is public
REPO_ID = "Cong123779/bigdata-milvus-backup"

# Mapping: volume_name -> specific_filename_on_hf
BACKUP_MAPPING = {
    "infra_etcd_data": "backup_etcd_1778149642.tar.gz",
    "infra_milvus_data": "backup_milvus_1778147969.tar.gz",
    "infra_minio_data": "backup_minio_1778149147.tar.gz",
}

BACKUP_DIR = Path("./hf_snapshots")
# ---------------------

def run_command(cmd):
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
    return result

def ensure_volume(volume_name):
    # Check if volume exists, if not create it
    result = run_command(f"docker volume inspect {volume_name}")
    if result.returncode != 0:
        print(f"Creating volume: {volume_name}")
        run_command(f"docker volume create {volume_name}")

def restore_volume(volume_name, tar_name):
    print(f"\n--- Restoring volume: {volume_name} ({tar_name}) ---")
    tar_path = BACKUP_DIR / tar_name
    
    if not tar_path.exists():
        print(f"Downloading {tar_name} from Hugging Face ({REPO_ID})...")
        try:
            downloaded_path = hf_hub_download(
                repo_id=REPO_ID,
                filename=tar_name,
                repo_type="dataset",
                token=TOKEN,
                local_dir=BACKUP_DIR
            )
            print(f"Downloaded to {downloaded_path}")
        except Exception as e:
            print(f"Failed to download {tar_name}: {e}")
            print("If this is a private repo, please set HF_TOKEN environment variable.")
            return

    ensure_volume(volume_name)
    
    # Use a temporary container to untar the volume
    # We use 'rm -rf /data/*' to clear existing data before restore
    cmd = (
        f"docker run --rm -v {volume_name}:/data -v {BACKUP_DIR.absolute()}:/backup "
        f"alpine sh -c 'echo \"Cleaning /data...\" && rm -rf /data/* && echo \"Extracting {tar_name}...\" && tar xzf /backup/{tar_name} -C /data && echo \"Done.\"' "
    )
    run_command(cmd)

def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    
    print(f"--- Starting Restoration from {REPO_ID} ---")
    for vol, tar in BACKUP_MAPPING.items():
        restore_volume(vol, tar)
        
    print("\n--- Restoration Complete ---")
    print("Infrastructure data has been restored to Docker volumes.")

if __name__ == "__main__":
    main()
