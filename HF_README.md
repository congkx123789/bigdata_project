---
title: Bigdata Project Assets (The Brain)
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: static
pinned: false
---

# Bigdata Project Assets (The "Brain") 🧠

Đây là repository lưu trữ các bản sao lưu (snapshots) cơ sở dữ liệu cho hệ thống **Bigdata AI Document Processing**. 

## 🎯 Mục đích & Ý nghĩa
Trong các hệ thống AI xử lý dữ liệu lớn, việc tách biệt **Dữ liệu thô (Raw Data)** và **Dữ liệu đã xử lý (Processed/Brain Data)** là cực kỳ quan trọng:
-   **Raw Data (~48GB)**: Là các file ảnh/PDF ban đầu. Việc tải và xử lý lại từ đầu tốn rất nhiều thời gian.
-   **Brain Data (Vài MB - GB)**: Là kết quả của quá trình index (Vector embeddings, Metadata). Đây là những gì được lưu trữ tại repository này.

**=> Lợi ích:** Bạn có thể setup máy mới và Chat được ngay lập tức chỉ bằng cách tải "Bộ não" này về, mà không cần tải 48GB dữ liệu thô ngay lúc đó.

## 📦 Danh sách Assets
-   **`infra_milvus_data.tar.gz`**: Chứa toàn bộ Vector Embeddings của tài liệu (BGE-M3).
-   **`infra_postgres_data.tar.gz`**: Chứa thông tin Metadata, cấu hình hệ thống và lịch sử.
-   **`infra_minio_data.tar.gz`**: Chứa metadata của Object Storage và các file đã xử lý quy mô nhỏ.
-   **`infra_etcd_data.tar.gz`**: Trạng thái cấu hình của cluster Milvus.

## 🛠️ Quy trình khôi phục nhanh (Quick Restore)
Các assets này được thiết kế để hoạt động cùng với script `setup.sh` trong mã nguồn chính.

1.  **Clone mã nguồn từ GitHub**:
    ```bash
    git clone https://github.com/congkx123789/bigdata_project.git
    cd bigdata_project
    ```
2.  **Chạy script Setup thông minh**:
    ```bash
    export HF_TOKEN="your_huggingface_token_here"
    ./setup.sh
    ```
3.  **Xác nhận Restore**: Khi script hỏi `Do you want to restore data from Hugging Face?`, hãy chọn `y`.

---

## 🔗 Liên kết quan trọng
-   **Mã nguồn chính (Github)**: [bigdata_project](https://github.com/congkx123789/bigdata_project)
-   **Tác giả**: Cong123779

---
*Lưu ý: Nếu bạn muốn tải dữ liệu thô (48GB RVL-CDIP), hãy sử dụng công cụ `download_datasets.sh` có sẵn trong repository GitHub.*
