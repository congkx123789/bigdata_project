import os
from huggingface_hub import snapshot_download

DATASET_NAME = "th1nhng0/vietnamese-legal-documents"
LOCAL_DIR = "datasets/vi-legal/raw_parquet"

def main():
    os.makedirs(LOCAL_DIR, exist_ok=True)
    print(f"=== Bắt đầu tải Parquet raw từ: {DATASET_NAME} ===")
    print(f"Thư mục lưu trữ: {os.path.abspath(LOCAL_DIR)}\n")

    # Tải trực tiếp tất cả file Parquet từ repo (bỏ qua bước parse của PyArrow)
    # Điều này tránh được lỗi "Failed casting from large_string to string"
    try:
        snapshot_download(
            repo_id=DATASET_NAME,
            repo_type="dataset",
            local_dir=LOCAL_DIR,
            allow_patterns="*.parquet",
            max_workers=8
        )
        print("\n[Thành công] Tải toàn bộ file Parquet hoàn tất!")
    except Exception as e:
        print(f"\n[Lỗi] Quá trình tải thất bại: {e}")

if __name__ == "__main__":
    main()
