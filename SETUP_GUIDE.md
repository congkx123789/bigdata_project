# 🚀 Hướng dẫn Setup Hệ thống Nexus Legal AI (New Machine)

Tài liệu này hướng dẫn cách cài đặt lại toàn bộ dự án từ đầu trên một máy tính mới.

---

## 1. Yêu cầu phần mềm (Prerequisites)
- **Windows**: Cài đặt [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Bật WSL2).
- **Linux**: Cài đặt Docker & Docker Compose.
- **NVIDIA Container Toolkit**: Bắt buộc để Docker sử dụng được GPU. [Xem hướng dẫn cài đặt](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

---

## 2. Các bước cài đặt

### Bước 1: Clone mã nguồn
```bash
git clone https://github.com/congkx123789/bigdata_project.git
cd bigdata_project
```

### Bước 2: Thiết lập biến môi trường
Tạo file `.env` tại thư mục gốc và dán nội dung sau:
```env
# Google Gemini API Key (Lấy tại AI Studio)
GEMINI_API_KEY=your_api_key_here
GEMINI_API_URL=https://generativelanguage.googleapis.com

# Hugging Face Token (Chỉ cần nếu muốn Backup hoặc dùng Dataset Private)
# HF_TOKEN=your_hf_token_here
```

### Bước 3: Khởi chạy hạ tầng (Infrastructure)
Mở terminal và chạy lệnh để khởi động Milvus, Postgres, Kafka, MinIO:
```bash
docker compose up -d --build
```

---

## 3. Khôi phục dữ liệu (Data Recovery)

Bạn có 2 lựa chọn để có dữ liệu 178,000 văn bản pháp luật:

### Cách 1: Khôi phục từ Hugging Face (Nhanh nhất - 5 phút)
Sử dụng bộ nhớ "Brain" đã được backup sẵn để không phải chạy AI nạp lại từ đầu:
1. Đảm bảo đã điền `HF_TOKEN` trong file `.env`.
2. Chạy script setup:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Khi hệ thống hỏi `Do you want to restore data from Hugging Face?`, chọn **`y`**.

### Cách 2: Nạp dữ liệu từ file gốc (Lâu - 2-5 tiếng)
Nếu bạn muốn hệ thống tự đọc lại từ file `.parquet`:
```bash
docker exec -it bd_legal_ai_engine python3 /app/services/ai-rag-engine/vector_store/ingest_to_milvus.py
```

---

## 4. Truy cập ứng dụng

Sau khi khởi chạy thành công, bạn có thể truy cập:
- **Giao diện người dùng**: [http://localhost:8080](http://localhost:8080)
- **API Backend**: [http://localhost:8003/docs](http://localhost:8003/docs)
- **Quản lý dữ liệu MinIO**: [http://localhost:9001](http://localhost:9001) (User: `admin`, Pass: `password123`)

---

## 5. Xử lý sự cố thường gặp (Troubleshooting)

- **Lỗi GPU**: Nếu máy không có GPU, hãy mở `docker-compose.yml`, tìm phần `deploy.resources.reservations` và xóa bỏ yêu cầu `nvidia` driver.
- **Lỗi Port**: Nếu port 8080 hoặc 19530 đã bị chiếm, hãy đổi port ở cột bên trái trong phần `ports` của `docker-compose.yml`.
- **Dữ liệu trống**: Chạy script `check_milvus.py` (nếu có) để kiểm tra số lượng bản ghi trong Milvus.

---
**Nexus Legal AI - Optimized for High Performance RAG.**
