import os
from huggingface_hub import HfApi
from pathlib import Path

# --- Configuration ---
TOKEN = os.getenv("HF_TOKEN", "") # REDACTED
REPO_ID = "Cong123779/bigdata-milvus-backup"
DATA_DIR = Path("/home/alida/Documents/Cursor/Bigdata/datasets/vi-legal/data")
FILES_TO_UPLOAD = ["content.parquet", "metadata.parquet", "relationships.parquet"]
# ---------------------

def sync_to_hf():
    api = HfApi(token=TOKEN)
    
    print(f"🚀 Starting synchronization of parquet files to {REPO_ID}")
    
    for file_name in FILES_TO_UPLOAD:
        local_path = DATA_DIR / file_name
        if local_path.exists():
            print(f"⬆️ Uploading {file_name}...")
            api.upload_file(
                path_or_fileobj=str(local_path),
                path_in_repo=f"data/{file_name}",
                repo_id=REPO_ID,
                repo_type="dataset",
            )
            print(f"✅ Uploaded {file_name}")
        else:
            print(f"❌ File not found: {local_path}")

    print("\n🎉 Sync Complete!")
    print(f"URL: https://huggingface.co/datasets/{REPO_ID}")

if __name__ == "__main__":
    sync_to_hf()
