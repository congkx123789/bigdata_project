# Hướng Dẫn Triển Khai — Pipeline Văn Bản Pháp Luật Việt Nam

## Yêu Cầu Hệ Thống

- Docker Desktop (hoặc Docker Engine + Docker Compose v2)
- RAM 16 GB trở lên (Spark + Milvus + Kafka đòi hỏi nhiều bộ nhớ)
- GPU NVIDIA + nvidia-docker (tùy chọn, dùng cho embedding GPU)
- Python 3.11+ (chỉ cho các script cục bộ)
- Tài khoản HuggingFace + token (để tải bộ dữ liệu)

---

## Khởi Động Nhanh (Chế Độ Laptop/Dev)

### Bước 1: Clone và Cấu Hình

```bash
git clone https://github.com/congkx123789/bigdata_project.git
cd bigdata_project

# Sao chép template cấu hình môi trường
cp .env.example .env

# Chỉnh sửa .env — tối thiểu cần đặt các giá trị:
#   HF_TOKEN=hf_your_token_here
#   MINIO_SECRET_KEY=your_secure_password
#   POSTGRES_PASSWORD=your_secure_password
nano .env
```

### Bước 2: Khởi Động Cơ Sở Hạ Tầng

```bash
# Stack chính (MinIO, PostgreSQL, Kafka, Milvus, Spark, Trino, Airflow, Superset)
docker compose -f infra/docker-compose.yaml up -d

# Stack giám sát (Prometheus, Grafana, ELK)
docker compose -f monitoring/docker-compose-monitoring.yaml up -d
```

Chờ tất cả dịch vụ healthy (~2-3 phút):
```bash
docker compose -f infra/docker-compose.yaml ps
```

### Bước 3: Tải Bộ Dữ Liệu Văn Bản Pháp Luật

```bash
# Cài đặt các thư viện Python cần thiết
pip install datasets minio

# Tải từ HuggingFace → lưu vào data/raw/ + upload lên MinIO
export HF_TOKEN="hf_your_token_here"
python services/ingestion/hf_dataset_loader.py
```

### Bước 4: Chạy Pipeline

```bash
# Bronze: HuggingFace Parquet → Iceberg Bronze
python pipelines/bronze/ingest_raw.py --mode batch

# Silver: Bronze → Chuẩn hóa + Kiểm tra DQ
python pipelines/silver/cleanse_documents.py --mode batch

# Gold: Silver → 5 Bảng Phân Tích
python pipelines/gold/aggregate_metrics.py
```

### Bước 5: Xác Minh Kết Quả

```bash
# Chạy SQL kiểm tra qua Trino
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_bronze.sql
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_silver.sql
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_gold.sql

# Kiểm tra manifest
ls data/manifests/bronze_ingest/
ls data/manifests/silver_cleanse/
ls data/manifests/gold_refresh/

# Script kiểm tra tổng hợp
python scripts/verify_local.py
```

---

## Địa Chỉ Truy Cập Các Dịch Vụ

| Dịch Vụ | Địa Chỉ | Thông Tin Đăng Nhập |
|---------|---------|---------------------|
| MinIO Console | http://localhost:9001 | admin / (theo .env) |
| Spark Master UI | http://localhost:8080 | — |
| Trino UI | http://localhost:8088 | admin / (không cần mật khẩu) |
| Superset | http://localhost:8089 | admin / admin |
| Airflow | http://localhost:8090 | admin / admin |
| Keycloak | http://localhost:8081 | admin / (theo .env) |
| Grafana | http://localhost:3000 | admin / admin |
| Kibana | http://localhost:5601 | — |
| Prometheus | http://localhost:9090 | — |

---

## Thiết Lập Airflow

Sau khi khởi động stack, cấu hình kết nối Airflow:

1. Truy cập http://localhost:8090 → Admin → Connections
2. Thêm connection:
   - **Connection ID**: `spark_default`
   - **Connection Type**: `Spark`
   - **Host**: `spark://spark-master`
   - **Port**: `7077`
3. Các DAG sẽ tự động xuất hiện từ thư mục `dags/`

---

## Thông Tin Bộ Dữ Liệu HuggingFace

- **Repo**: `th1nhng0/vietnamese-legal-documents`
- **Các subset**: `content`, `metadata`, `relationships`
- **Nguồn**: vbpl.vn (Cổng thông tin pháp luật Chính phủ Việt Nam)
- **Tải xuống**: Yêu cầu token HuggingFace (`HF_TOKEN` trong `.env`)

---

## Xử Lý Sự Cố

### MinIO từ chối kết nối
```bash
# Kiểm tra sức khỏe MinIO
curl http://localhost:9000/minio/health/live

# Xem logs
docker logs minio
```

### Spark job thất bại lỗi S3A
```bash
# Kiểm tra bucket MinIO đã tồn tại chưa
docker exec minio mc ls local/

# Tạo bucket bị thiếu thủ công
docker exec minio mc mb local/legal-bronze
```

### Lỗi Iceberg catalog
```bash
# Kiểm tra PostgreSQL đang chạy
docker exec postgres psql -U admin -d document_db -c "SELECT count(*) FROM iceberg_tables;" 2>/dev/null || echo "Bảng Iceberg chưa được tạo"
```

### Thiếu Kafka topic
```bash
# Liệt kê các topic
docker exec kafka kafka-topics --bootstrap-server kafka:29092 --list

# Tạo DLQ topic thủ công
docker exec kafka kafka-topics --bootstrap-server kafka:29092 \
  --create --topic document-dlq --partitions 1 --replication-factor 1
```
