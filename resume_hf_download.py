import os
import sys
from datasets import load_dataset

def main():
    cache_dir = "/home/alida/Documents/Cursor/Bigdata/datasets/rvl-cdip/.cache"
    print(f"Resuming download of rvl_cdip to {cache_dir}...")
    
    try:
        # RVL-CDIP is a large dataset, we just want to ensure it downloads/resumes
        dataset = load_dataset(
            "rvl_cdip", 
            cache_dir=cache_dir,
            verification_mode="no_checks",
            trust_remote_code=True
        )
        print("Download complete or already present.")
    except Exception as e:
        print(f"Error during download: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
