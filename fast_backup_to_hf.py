import os
import subprocess
import time

REPO_ID = "Cong123779/bigdata-milvus-backup"
VOLUMES = {
    "milvus": "infra_milvus_data",
    "minio": "infra_minio_data",
    "etcd": "infra_etcd_data"
}

def run_command(cmd):
    print(f"Executing: {cmd}")
    return subprocess.run(cmd, shell=True, check=True)

def backup_volume(name, volume):
    filename = f"backup_{name}_{int(time.time())}.tar.gz"
    print(f"--- Backing up {name} ---")
    # Use a container to tar the volume
    run_command(f"docker run --rm -v {volume}:/data -v $(pwd):/backup alpine tar czf /backup/{filename} -C /data .")
    print(f"--- Uploading {name} to HF ---")
    run_command(f"huggingface-cli upload {REPO_ID} {filename} {filename} --repo-type dataset")
    # Clean up
    os.remove(filename)

if __name__ == "__main__":
    for name, vol in VOLUMES.items():
        try:
            backup_volume(name, vol)
        except Exception as e:
            print(f"Failed to backup {name}: {e}")
    print("BACKUP PROCESS FINISHED!")
