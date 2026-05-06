import os
import subprocess
from pathlib import Path
from huggingface_hub import hf_hub_download

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

def ensure_volume(volume_name):
    # Check if volume exists, if not create it
    result = run_command(f"docker volume inspect {volume_name}")
    if result.returncode != 0:
        print(f"Creating volume: {volume_name}")
        run_command(f"docker volume create {volume_name}")

def restore_volume(volume_name):
    print(f"--- Restoring volume: {volume_name} ---")
    tar_name = f"{volume_name}.tar.gz"
    tar_path = BACKUP_DIR / tar_name
    
    if not tar_path.exists():
        print(f"Downloading {tar_name} from Hugging Face...")
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
            return

    ensure_volume(volume_name)
    
    # Use a temporary container to untar the volume
    # We use 'rm -rf /data/*' to clear existing data before restore
    cmd = (
        f"docker run --rm -v {volume_name}:/data -v {BACKUP_DIR.absolute()}:/backup "
        f"alpine sh -c 'rm -rf /data/* && tar xzf /backup/{tar_name} -C /data'"
    )
    run_command(cmd)

def main():
    BACKUP_DIR.mkdir(exist_ok=True)
    
    print(f"--- Starting Restoration from {REPO_ID} ---")
    for vol in VOLUMES:
        restore_volume(vol)
        
    print("\n--- Restoration Complete ---")
    print("You can now start the infrastructure using: docker compose -f infra/docker-compose.yaml up -d")

if __name__ == "__main__":
    main()
