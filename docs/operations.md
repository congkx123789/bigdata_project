# Hướng Dẫn Vận Hành — Quy Tắc DQ, Manifest và Runbook

## Nơi Kiểm Tra Thông Tin

| Nguồn Thông Tin | Mục Đích |
|-----------------|---------|
| Run manifests (`MANIFEST_ROOT/`) | Một file JSON cho mỗi lần chạy — đầu vào, đầu ra, số dòng, kết quả DQ |
| Pipeline metrics (`PIPELINE_METRICS_LOG_PATH`) | Log JSONL dạng thêm mới, một sự kiện mỗi stage, tương thích Grafana |
| Airflow DAG UI (`http://localhost:8090`) | Trạng thái pipeline, lịch sử retry, cảnh báo SLA |
| Trino SQL validation (`infra/trino/sql/`) | Truy vấn DQ ad-hoc trên bảng Iceberg |
| ELK/Kibana (`http://localhost:5601`) | Tìm kiếm log trên tất cả stage pipeline |

---

## Biến Môi Trường Quan Trọng

| Biến | Mặc Định | Mô Tả |
|------|---------|-------|
| `DQ_FAIL_ON_ERROR` | `true` | Chặn pipeline khi có lỗi DQ critical |
| `LOG_LEVEL` | `INFO` | Mức độ chi tiết log (DEBUG/INFO/WARNING/ERROR) |
| `PIPELINE_METRICS_LOG_PATH` | *(rỗng)* | Đường dẫn file JSONL metrics (tùy chọn) |
| `MANIFEST_ROOT` | `./data/manifests` | Thư mục gốc chứa run manifest |
| `HF_TOKEN` | *(rỗng)* | Token HuggingFace để tải dataset |
| `SPARK_MASTER` | `local[*]` | Địa chỉ Spark cluster |

---

## Phạm Vi Kiểm Tra Chất Lượng Dữ Liệu

### Quy Tắc DQ Bronze

| Tên Quy Tắc | Mức Độ | Kiểm Tra Gì |
|-------------|--------|------------|
| `bronze_doc_id_not_null` | **critical** | Mỗi bản ghi phải có `doc_id` |
| `bronze_raw_text_not_empty` | **critical** | `raw_text` không được null hoặc rỗng |
| `bronze_record_hash_present` | **critical** | Hash SHA256 phải được tính toán |
| `bronze_dedupe_key_present` | **critical** | Khóa khử trùng tổng hợp phải được tính toán |
| `bronze_no_duplicate_hashes_in_batch` | warning | Bản ghi trùng được ghi log nhưng cho qua |

### Quy Tắc DQ Silver

| Tên Quy Tắc | Mức Độ | Ngưỡng |
|-------------|--------|--------|
| `silver_critical_fields_not_null` | **critical** | doc_id, clean_text, processed_at không null |
| `silver_min_char_count` | **critical** | char_count >= 50 |
| `silver_min_word_count` | warning | word_count >= 5 |
| `silver_quality_score_range` | warning | quality_score trong [0.0, 1.0] |
| `silver_no_duplicate_doc_ids_in_batch` | warning | Chỉ ghi log |

### Quy Tắc DQ Gold

| Mẫu Quy Tắc | Mức Độ |
|-------------|--------|
| `<table>_required_columns` | **critical** |
| `<table>_non_negative_metrics` | **critical** |
| `<table>_ingest_date_not_null` | **critical** |

---

## Schema Run Manifest

Mỗi stage ghi một file `<MANIFEST_ROOT>/<stage>/<run_id>.json`:

```json
{
  "stage": "silver_cleanse",
  "run_id": "20240601T020000_a1b2c3d4",
  "status": "success",
  "started_at": "2024-06-01T02:00:00+00:00",
  "finished_at": "2024-06-01T02:12:34+00:00",
  "inputs": ["lakehouse.public.bronze_documents"],
  "outputs": ["lakehouse.public.silver_documents", "lakehouse.public.silver_quarantine"],
  "metrics": {
    "rows_in": 50000,
    "rows_out": 48750,
    "rows_quarantined": 1250,
    "duration_ms": 754321.5,
    "dq_passed": true
  },
  "details": {
    "dq": {
      "dq_passed": true,
      "critical_failures": 0,
      "warnings": 1,
      "dq_rules": [...]
    }
  }
}
```

---

## Runbook Vận Hành

### Chạy Pipeline Hàng Ngày (Bình Thường)

1. Airflow kích hoạt `vn_legal_document_pipeline` lúc 02:00 UTC
2. `sensor_new_data` kiểm tra HuggingFace API → rẽ nhánh sang `load_hf_dataset`
3. `load_hf_dataset` tải file Parquet vào `data/raw/` và MinIO
4. `bronze_ingest` Spark job → ghi vào `bronze_documents`
5. `silver_cleanse` Spark job → ghi vào `silver_documents` + `silver_quarantine`
6. `dq_gate_check` đọc manifest Silver mới nhất → rẽ nhánh sang `gold_aggregate`
7. `gold_aggregate` Spark job → làm mới 5 bảng Gold

**Thời gian dự kiến**: 1–3 giờ tùy kích thước dataset

### Bảo Trì Hàng Tuần

Airflow `vn_legal_iceberg_maintenance` chạy mỗi Chủ Nhật lúc 03:00 UTC:
1. Nén file: gộp các file nhỏ thành file Parquet kích thước tối ưu
2. Xóa snapshot: loại bỏ snapshot cũ hơn 30 ngày (giữ lại 3 snapshot gần nhất)
3. Dọn file mồ côi: xóa file không được tham chiếu cũ hơn 72 giờ

**Báo cáo**: `data/manifests/iceberg_maintenance/<run_id>.json`

### Kiểm Tra Trạng Thái Pipeline

```bash
# Xem manifest Silver mới nhất
cat data/manifests/silver_cleanse/$(ls -t data/manifests/silver_cleanse/ | head -1)

# Kiểm tra số lượng kiểm dịch qua Trino
docker exec trino trino --execute \
  "SELECT dq_rule, COUNT(*) FROM iceberg.public.silver_quarantine GROUP BY dq_rule"

# Xem dữ liệu Gold qua Trino
docker exec trino trino --catalog iceberg < infra/trino/sql/validate_gold.sql

# Xem pipeline metrics JSONL theo thời gian thực
tail -f data/metrics/pipeline_metrics.jsonl | python -m json.tool
```

### Quy Trình Phục Hồi

#### Bronze thất bại (DLQ tràn)

1. Kiểm tra `lakehouse.public.bronze_dlq`:
   ```sql
   SELECT error_message, COUNT(*) FROM iceberg.public.bronze_dlq
   GROUP BY error_message ORDER BY 2 DESC;
   ```
2. Kiểm tra Kafka topic: `kafka-console-consumer --topic document-extracted-text`
3. Sửa định dạng tin nhắn trong HF loader hoặc Kafka producer
4. Kích hoạt lại DAG từ task `bronze_ingest`

#### Cổng DQ Silver thất bại

1. Mở manifest mới nhất: `data/manifests/silver_cleanse/<latest>.json`
2. Kiểm tra `details.dq.dq_rules` để tìm quy tắc thất bại
3. Kiểm tra bảng kiểm dịch để xem mẫu bản ghi xấu
4. Nếu vấn đề dữ liệu: sửa bản ghi Bronze; kích hoạt lại từ `silver_cleanse`
5. Nếu ngưỡng quá nghiêm: điều chỉnh `MIN_CLEAN_TEXT_CHARS` trong `common/dq_checks.py`

#### Tổng hợp Gold thất bại

1. Mở manifest mới nhất: `data/manifests/gold_refresh/<latest>.json`
2. Kiểm tra bảng Gold nào có lỗi DQ
3. Xác minh bảng Silver có dữ liệu: `SELECT COUNT(*) FROM iceberg.public.silver_documents`
4. Kích hoạt lại từ task `gold_aggregate` trong Airflow

#### Reset Toàn Bộ Pipeline (Phát Triển)

```bash
# Dừng tất cả container
docker compose -f infra/docker-compose.yaml down

# Xóa data volumes (CẢNH BÁO: mất toàn bộ dữ liệu)
docker volume prune -f

# Dọn artifact cục bộ
rm -rf data/manifests data/metrics data/raw data/checkpoints

# Khởi động lại từ đầu
docker compose -f infra/docker-compose.yaml up -d
python services/ingestion/hf_dataset_loader.py
python pipelines/bronze/ingest_raw.py --mode batch
python pipelines/silver/cleanse_documents.py --mode batch
python pipelines/gold/aggregate_metrics.py
```
