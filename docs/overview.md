# 📋 Tổng Quan Dự Án — Pipeline Xử Lý Văn Bản Pháp Luật Việt Nam (RAG BigData)

> **Phục vụ thuyết trình** — Tài liệu này mô tả toàn bộ hệ thống, từng thành phần, cách kiểm tra vận hành và các output cụ thể thu được sau mỗi giai đoạn.

---

## 1. Giới Thiệu Dự Án

### 1.1 Bài Toán

Văn bản pháp luật Việt Nam rất đồ sộ (hàng chục nghìn văn bản từ vbpl.vn), nhưng khó tra cứu vì:
- Nội dung HTML phức tạp, không cấu trúc
- Metadata không đồng nhất (ngày tháng viết tắt nhiều kiểu)
- Không có công cụ tìm kiếm ngữ nghĩa (semantic search) cho tiếng Việt

### 1.2 Giải Pháp

Xây dựng một **Lakehouse BigData + AI RAG** hoàn chỉnh:

```
HuggingFace Dataset  →  Bronze (thô)  →  Silver (sạch)  →  Gold (tổng hợp)
                                                              ↓
                                              Trino/Superset (BI Dashboard)
                                              Milvus + BGE-M3 (RAG / AI Chat)
```

### 1.3 Bộ Dữ Liệu

| Thông Tin | Chi Tiết |
|-----------|---------|
| **Nguồn** | `th1nhng0/vietnamese-legal-documents` trên HuggingFace |
| **Gốc** | vbpl.vn — Cổng VBPL chính thức Chính phủ Việt Nam |
| **Nội dung** | Luật, Nghị định, Thông tư, Quyết định, Chỉ thị,... |
| **Subsets** | `content` (nội dung HTML), `metadata` (thông tin pháp lý), `relationships` (liên văn bản) |
| **Ngôn ngữ** | Tiếng Việt |

---

## 2. Kiến Trúc Tổng Thể

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NGUỒN DỮ LIỆU                                      │
│   HuggingFace Dataset           Kafka Stream (OCR / extract)                │
│   th1nhng0/vn-legal-docs        document-extracted-text topic               │
└──────────────┬──────────────────────────────┬──────────────────────────────┘
               │                              │
               ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TẦNG THU THẬP (BRONZE)                               │
│   hf_dataset_loader.py          ingest_raw.py                               │
│   - Tải 3 subsets từ HF         - Loại bỏ HTML                             │
│   - Lưu Parquet vào MinIO       - Thêm record_hash + dedupe_key             │
│                                 - DQ gate → DLQ routing                     │
│   Bảng: lakehouse.public.bronze_documents                                   │
│   Phân vùng: ingest_date  │  Format: Iceberg  │  Mode: Append-only          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TẦNG LÀM SẠCH (SILVER)                               │
│   cleanse_documents.py                                                       │
│   - Chuẩn hóa văn bản (loại ký tự đặc biệt)                               │
│   - Tính char_count, word_count (tiếng Việt)                               │
│   - Phân tích ngày DD/MM/YYYY → ISO DATE                                   │
│   - Chuẩn hóa tinh_trang_hieu_luc                                          │
│   - DQ gate → split valid / quarantine                                      │
│   Bảng: silver_documents + silver_quarantine                                │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TẦNG PHÂN TÍCH (GOLD — 5 BẢNG)                          │
│   aggregate_metrics.py                                                       │
│   ┌──────────────────┐  ┌─────────────────────┐  ┌────────────────────┐    │
│   │ gold_daily_stats │  │gold_legal_type_brk  │  │gold_issuing_auth   │    │
│   │ Thống kê ngày    │  │Phân loại văn bản    │  │Cơ quan ban hành    │    │
│   └──────────────────┘  └─────────────────────┘  └────────────────────┘    │
│   ┌──────────────────────────────┐  ┌──────────────────────────────────┐   │
│   │ gold_legal_field_stats       │  │ gold_effect_status               │   │
│   │ Lĩnh vực + Ngành             │  │ Tình trạng hiệu lực              │   │
│   └──────────────────────────────┘  └──────────────────────────────────┘   │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
               ┌───────────────────────┼────────────────────────┐
               ▼                       ▼                        ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌───────────────────────┐
│   TRINO 453          │  │   SUPERSET           │  │   AI RAG ENGINE       │
│   SQL Query Engine   │  │   BI Dashboard       │  │   FastAPI + BGE-M3    │
│   Truy vấn trực tiếp │  │   Biểu đồ trực quan  │  │   Milvus Vector DB    │
│   bảng Iceberg       │  │   (kết nối qua Trino)│  │   Chat hỏi đáp VB PL │
└─────────────────────┘  └─────────────────────┘  └───────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         ĐIỀU PHỐI (AIRFLOW 2.8)                               │
│   DAG hàng ngày: sensor → load_hf → bronze → silver → DQ gate → gold       │
│   DAG hàng tuần: iceberg_maintenance (nén + xóa snapshot + dọn file)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Mô Tả Chi Tiết Từng Thành Phần

### 3.1 MinIO — Lưu Trữ Đối Tượng (Object Storage)

**Vai trò**: Thay thế Amazon S3, lưu trữ tất cả file Parquet và data warehouse của Iceberg.

**Các bucket được tạo tự động:**

| Bucket | Nội Dung |
|--------|---------|
| `legal-bronze` | File Parquet tầng Bronze (thô từ HuggingFace) |
| `legal-silver` | File Parquet tầng Silver (đã làm sạch) |
| `legal-gold` | File Parquet tầng Gold (đã tổng hợp) |
| `documents` | Data warehouse Iceberg (metadata + data files) |
| `legal-checkpoints` | Spark Streaming checkpoints |

**Giao diện MinIO Console** — `http://localhost:9001`

```
┌─────────────────────────────────────────────────────────────┐
│  MinIO Console                                    [Buckets]  │
├─────────────────────────────────────────────────────────────┤
│  ► legal-bronze/                                            │
│      hf/th1nhng0/vietnamese-legal-documents/                │
│          content/content_data.parquet       (~ 500 MB)      │
│          metadata/metadata_data.parquet     (~ 50 MB)       │
│  ► documents/                                               │
│      warehouse/                                             │
│          public/bronze_documents/           (Iceberg files) │
│          public/silver_documents/           (Iceberg files) │
│          public/gold_daily_stats/           (Iceberg files) │
└─────────────────────────────────────────────────────────────┘
```

**Cách xác minh MinIO đang chạy thành công:**
```bash
# Terminal: kiểm tra API health
curl http://localhost:9000/minio/health/live
# Output mong đợi: HTTP 200 OK (không có body)

# Kiểm tra bucket đã được tạo
docker exec minio mc ls local/
# Output mong đợi:
# [2024-06-01 02:00:00 UTC]     0B legal-bronze/
# [2024-06-01 02:00:00 UTC]     0B legal-silver/
# [2024-06-01 02:00:00 UTC]     0B legal-gold/
# [2024-06-01 02:00:00 UTC]     0B documents/
# [2024-06-01 02:00:00 UTC]     0B legal-checkpoints/
```

---

### 3.2 Apache Kafka — Message Broker

**Vai trò**: Hàng đợi tin nhắn cho luồng dữ liệu thời gian thực (streaming mode). Trong chế độ batch, có thể bỏ qua Kafka và đọc trực tiếp từ Parquet.

**Các topic được tạo tự động:**

| Topic | Partitions | Mục Đích |
|-------|-----------|---------|
| `document-extracted-text` | 3 | Văn bản đã trích xuất sẵn sàng ghi Bronze |
| `document-dlq` | 1 | Dead-Letter Queue: tin nhắn lỗi không parse được |
| `legal-doc-processed` | 3 | Thông báo sau khi xử lý Silver |

**Cách xác minh Kafka đang chạy thành công:**
```bash
# Kiểm tra topics đã được tạo
docker exec kafka kafka-topics --bootstrap-server kafka:29092 --list
# Output mong đợi:
# document-extracted-text
# document-dlq
# legal-doc-processed

# Xem offset/lag (kiểm tra consumer group)
docker exec kafka kafka-consumer-groups \
  --bootstrap-server kafka:29092 --describe --all-groups
```

---

### 3.3 Apache Spark — Engine Xử Lý Dữ Liệu

**Vai trò**: Xử lý dữ liệu song song, đọc từ HuggingFace Parquet / Kafka và ghi vào Iceberg.

**Spark Master UI** — `http://localhost:8080`

```
┌─────────────────────────────────────────────────────────────┐
│  Spark Master at spark://spark-master:7077                  │
│  Status: ALIVE                                              │
├─────────────────────────────────────────────────────────────┤
│  Workers: 1                                                 │
│  Cores: 2 Total, 0 Used                                     │
│  Memory: 4.0 GB Total, 0.0 B Used                           │
├─────────────────────────────────────────────────────────────┤
│  Running Applications (0)                                   │
│  Completed Applications (3)                                 │
│  ┌─────────────────────────────────────────────┐           │
│  │ VNLegal-Bronze-Ingestion  | Finished | 2min  │           │
│  │ VNLegal-Silver-Cleansing  | Finished | 5min  │           │
│  │ VNLegal-Gold-Aggregation  | Finished | 1min  │           │
│  └─────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
```

**Cách xác minh Spark đang chạy thành công:**
```bash
# Truy cập Spark Master UI
# http://localhost:8080 → "Status: ALIVE"

# Kiểm tra worker đã kết nối
# Workers: 1  (hoặc nhiều hơn nếu scale)

# Sau khi chạy pipeline:
# "Completed Applications" phải có 3 jobs: Bronze, Silver, Gold
```

**Output khi chạy Bronze pipeline:**
```
{"timestamp": "2024-06-01T02:05:23.456Z", "level": "INFO", "logger": "bronze_pipeline",
 "message": "Bronze batch: 50000 records after dedup",
 "run_id": "20240601T020500_a1b2c3d4"}

{"timestamp": "2024-06-01T02:07:45.123Z", "level": "INFO", "logger": "pipeline_metrics",
 "message": "{\"event\": \"pipeline_metrics\", \"stage\": \"bronze_ingest_batch\",
 \"status\": \"success\", \"rows_out\": 49876, \"duration_ms\": 142300.5,
 \"dq_passed\": true, \"dq_critical_failures\": 0}"}
```

---

### 3.4 Apache Iceberg — Định Dạng Bảng

**Vai trò**: Định dạng bảng analytic thế hệ mới. Cho phép ACID transactions, time travel, schema evolution, partition pruning trên MinIO.

**Catalog**: PostgreSQL JDBC (`lakehouse` catalog)

**Các bảng Iceberg được tạo:**

| Bảng | Tầng | Phân Vùng |
|------|------|----------|
| `lakehouse.public.bronze_documents` | Bronze | ingest_date |
| `lakehouse.public.bronze_dlq` | Bronze | arrived_at |
| `lakehouse.public.silver_documents` | Silver | ingest_date |
| `lakehouse.public.silver_quarantine` | Silver | quarantined_at |
| `lakehouse.public.gold_daily_stats` | Gold | ingest_date |
| `lakehouse.public.gold_legal_type_breakdown` | Gold | ingest_date |
| `lakehouse.public.gold_issuing_authority` | Gold | ingest_date |
| `lakehouse.public.gold_legal_field_stats` | Gold | ingest_date |
| `lakehouse.public.gold_effect_status` | Gold | ingest_date |

**Cách kiểm tra bảng Iceberg qua Spark:**
```python
# Trong spark-shell hoặc pyspark
spark.sql("SHOW TABLES IN lakehouse.public").show()
# Output:
# +---------+-----------------------------+-----------+
# |namespace|tableName                    |isTemporary|
# +---------+-----------------------------+-----------+
# |public   |bronze_documents             |false      |
# |public   |bronze_dlq                   |false      |
# |public   |silver_documents             |false      |
# |public   |silver_quarantine            |false      |
# |public   |gold_daily_stats             |false      |
# |public   |gold_legal_type_breakdown    |false      |
# |public   |gold_issuing_authority       |false      |
# |public   |gold_legal_field_stats       |false      |
# |public   |gold_effect_status           |false      |
# +---------+-----------------------------+-----------+

# Xem lịch sử snapshot (Time Travel)
spark.sql("SELECT * FROM lakehouse.public.silver_documents.history").show()
```

---

### 3.5 Trino — SQL Query Engine

**Vai trò**: Query engine phân tán cho phép truy vấn trực tiếp các bảng Iceberg trên MinIO mà không cần load vào bộ nhớ. Superset và AI RAG đều kết nối qua Trino.

**Trino UI** — `http://localhost:8088`

```
┌─────────────────────────────────────────────────────────────┐
│  Trino — Query Editor                                       │
├─────────────────────────────────────────────────────────────┤
│  Catalog: iceberg                                           │
│  Schema:  public                                            │
├─────────────────────────────────────────────────────────────┤
│  Query:                                                     │
│  SELECT loai_van_ban, COUNT(*) as so_van_ban               │
│  FROM iceberg.public.silver_documents                       │
│  GROUP BY loai_van_ban ORDER BY 2 DESC                      │
│  LIMIT 10;                                                  │
├─────────────────────────────────────────────────────────────┤
│  Results (10 rows, 0.8s):                                   │
│  ┌─────────────────┬────────────┐                          │
│  │ loai_van_ban    │ so_van_ban │                          │
│  │ nghị định       │     12543  │                          │
│  │ thông tư        │      8921  │                          │
│  │ quyết định      │      7234  │                          │
│  │ luật            │      1823  │                          │
│  │ công văn        │       934  │                          │
│  └─────────────────┴────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

**Cách xác minh Trino đang chạy thành công:**
```bash
# Kiểm tra health API
curl http://localhost:8088/v1/info
# Output mong đợi:
# {"nodeVersion":{"version":"453"},"coordinator":true,"starting":false,"uptime":"2 minutes"}

# Chạy query test
docker exec trino trino --execute \
  "SELECT COUNT(*) FROM iceberg.public.bronze_documents"
# Output mong đợi:
# _col0
# -----
# 49876

# Chạy validation SQL đầy đủ
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_gold.sql
```

**Kết nối Trino với Superset:**
- URL: `trino://admin@trino:8080/iceberg`
- Không cần mật khẩu trong môi trường dev

---

### 3.6 Apache Airflow — Điều Phối Pipeline

**Vai trò**: Lên lịch và giám sát toàn bộ pipeline. Có 2 DAG chính.

**Airflow UI** — `http://localhost:8090` (admin/admin)

**DAG 1: `vn_legal_document_pipeline`** (Hàng ngày lúc 02:00 UTC)

```
sensor_new_data
      │
      ├─── (có data) ──→ load_hf_dataset ──→ bronze_ingest ──→ silver_cleanse
      │                                                               │
      └─── (không có) → skip_pipeline              ┌────────────────┘
                                                    ▼
                                              dq_gate_check
                                                    │
                                     ┌──────────────┴──────────────┐
                                     ▼                             ▼
                               gold_aggregate               quarantine_alert
                              (DQ passed ✓)               (DQ failed ✗ — báo động)
```

**DAG 2: `vn_legal_iceberg_maintenance`** (Hàng tuần Chủ Nhật 03:00 UTC)
```
iceberg_maintenance → (nén tất cả 9 bảng Iceberg)
```

**Giao diện Airflow — Trạng Thái DAG:**
```
┌─────────────────────────────────────────────────────────────────┐
│  DAGs                                                           │
├──────────────────────────────┬──────┬─────────┬────────────────┤
│ DAG                          │ Active│ Schedule│ Last Run       │
├──────────────────────────────┼──────┼─────────┼────────────────┤
│ vn_legal_document_pipeline   │  ON  │ 0 2 * * │ success ✓      │
│ vn_legal_iceberg_maintenance │  ON  │ 0 3 * 0 │ success ✓      │
└──────────────────────────────┴──────┴─────────┴────────────────┘
```

**Giao diện Graph View của DAG:**
```
[sensor_new_data] ──→ [load_hf_dataset] ──→ [bronze_ingest]
                           │                       │
                    [skip_pipeline]         [silver_cleanse]
                                                   │
                                           [dq_gate_check]
                                          /               \
                               [gold_aggregate]   [quarantine_alert]
```

**Cách xác minh Airflow đang chạy thành công:**
```bash
# Kiểm tra health
curl http://localhost:8090/health
# Output: {"metadatabase": {"status": "healthy"}, "scheduler": {"status": "healthy"}}

# Trigger DAG thủ công để test
docker exec airflow-scheduler airflow dags trigger vn_legal_document_pipeline

# Xem log của task
docker exec airflow-scheduler airflow tasks logs \
  vn_legal_document_pipeline bronze_ingest 2024-06-01
```

---

### 3.7 Apache Superset — BI Dashboard

**Vai trò**: Công cụ BI trực quan kết nối với Trino để tạo biểu đồ từ dữ liệu Gold.

**Superset** — `http://localhost:8089` (admin/admin)

**Các biểu đồ có thể tạo từ dữ liệu Gold:**

```
Dashboard: "Tổng Quan Văn Bản Pháp Luật Việt Nam"
┌────────────────────────────────────────────────────────────┐
│ 📊 Số văn bản theo loại         📈 Trend theo ngày         │
│ ┌─────────────────────────┐    ┌─────────────────────────┐ │
│ │ Nghị định    ████ 12543 │    │    /\   /\              │ │
│ │ Thông tư     ███  8921  │    │   /  \_/  \__           │ │
│ │ Quyết định   ██   7234  │    │  /           \          │ │
│ │ Luật         █    1823  │    └─────────────────────────┘ │
│ └─────────────────────────┘                                │
│                                                            │
│ 🏛️ Top 10 Cơ Quan Ban Hành     🔵 Tình trạng hiệu lực      │
│ ┌─────────────────────────┐    ┌─────────────────────────┐ │
│ │ Chính phủ        45%    │    │ Còn hiệu lực    65%     │ │
│ │ Bộ Tài chính     12%    │    │ Hết hiệu lực    28%     │ │
│ │ Bộ Tư pháp        8%    │    │ Chưa có HLực     7%     │ │
│ └─────────────────────────┘    └─────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

**Cách tạo dataset trong Superset:**
1. Vào `Data → Databases` → Add database → Chọn `Trino`
2. Connection: `trino://admin@trino:8080/iceberg`
3. Vào `Data → Datasets` → Add dataset → Schema `public`
4. Chọn bảng `gold_legal_type_breakdown`
5. Tạo chart → Bar Chart → `loai_van_ban` vs `document_count`

---

### 3.8 Milvus — Vector Database

**Vai trò**: Lưu trữ embedding vector của văn bản pháp luật (từ model BAAI/BGE-M3). Cho phép tìm kiếm ngữ nghĩa (semantic search) và hỏi đáp AI.

**Collection**: `document_vectors`
**Chiều vector**: 1024 (BGE-M3 output)
**Index**: HNSW

**Milvus UI** — Port 9091 (REST API)

```bash
# Kiểm tra Milvus đang chạy
curl http://localhost:9091/healthz
# Output: {"status":"healthy"}

# Kiểm tra collection qua Python
from pymilvus import connections, utility
connections.connect(host="localhost", port=19530)
print(utility.list_collections())
# Output: ['document_vectors']

print(utility.get_connection_addr('default'))
# Output: {'address': 'localhost:19530', 'user': ''}
```

---

### 3.9 AI RAG Engine — Hỏi Đáp Pháp Luật

**Vai trò**: API hỏi đáp thông minh về văn bản pháp luật Việt Nam.
- Embedding: BAAI/BGE-M3 (đa ngôn ngữ, hỗ trợ tốt tiếng Việt)
- LLM: Ollama (llama3.2:1b) hoặc Gemini API
- Vector search: Milvus
- API: FastAPI

**Endpoint test:**
```bash
# Hỏi đáp về pháp luật
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Luật doanh nghiệp 2020 quy định gì về vốn điều lệ?"}'

# Output mong đợi:
{
  "query": "Luật doanh nghiệp 2020 quy định gì về vốn điều lệ?",
  "answer": "Theo Luật Doanh nghiệp 2020, vốn điều lệ là tổng giá trị tài sản...",
  "sources": [
    {
      "doc_id": "12345",
      "title": "Luật Doanh nghiệp 2020",
      "so_ky_hieu": "59/2020/QH14",
      "score": 0.94,
      "text_preview": "Điều 34. Vốn điều lệ..."
    }
  ],
  "processing_time_ms": 2340
}
```

---

### 3.10 HuggingFace Dataset Loader

**File**: `services/ingestion/hf_dataset_loader.py`

**Output khi chạy thành công:**
```
{"timestamp": "...", "level": "INFO", "logger": "hf_dataset_loader",
 "message": "Starting HuggingFace dataset load",
 "dataset": "th1nhng0/vietnamese-legal-documents", "run_id": "20240601T020000_abc123"}

{"level": "INFO", "message": "Loading subset: content"}
{"level": "INFO", "message": "Loaded 74521 records from subset 'content'"}
{"level": "INFO", "message": "Saved content subset to data/raw/content/content_data.parquet"}
{"level": "INFO", "message": "Uploaded to MinIO: s3a://legal-bronze/hf/th1nhng0/.../content_data.parquet"}

{"level": "INFO", "message": "Loading subset: metadata"}
{"level": "INFO", "message": "Loaded 74521 records from subset 'metadata'"}

{"level": "INFO", "message": "HuggingFace dataset load completed",
 "total_rows": 149042, "duration_ms": 234567.89}
{"level": "INFO", "message": "Manifest written: data/manifests/hf_dataset_load/20240601T020000_abc123.json"}
```

**File manifest được tạo** (`data/manifests/hf_dataset_load/<run_id>.json`):
```json
{
  "stage": "hf_dataset_load",
  "run_id": "20240601T020000_abc123",
  "status": "success",
  "started_at": "2024-06-01T02:00:00+00:00",
  "finished_at": "2024-06-01T02:39:07+00:00",
  "inputs": [
    "hf://th1nhng0/vietnamese-legal-documents/content",
    "hf://th1nhng0/vietnamese-legal-documents/metadata",
    "hf://th1nhng0/vietnamese-legal-documents/relationships"
  ],
  "outputs": [
    "data/raw/content/content_data.parquet",
    "data/raw/metadata/metadata_data.parquet",
    "s3a://legal-bronze/hf/th1nhng0/.../content_data.parquet"
  ],
  "metrics": {
    "total_rows": 149042,
    "subsets_loaded": 3,
    "duration_ms": 2345678.9
  }
}
```

---

## 4. Luồng Xử Lý Chi Tiết và Output Mỗi Bước

### 4.1 Bước 1 — Thu Thập Bronze

**Chạy lệnh:**
```bash
python pipelines/bronze/ingest_raw.py --mode batch
```

**Quá trình xử lý:**
1. Đọc `data/raw/content/content_data.parquet` (74,521 dòng)
2. Join với `data/raw/metadata/metadata_data.parquet` theo `id`
3. Loại bỏ HTML tags từ `content_html` → `raw_text`
4. Tính `record_hash` = SHA256(doc_id + raw_text[:200])
5. Tính `dedupe_key` = concat(doc_id, loai_van_ban)
6. `dropDuplicates(["record_hash"])` → loại bỏ ~2-5% trùng lặp
7. DQ check trên mẫu 500 dòng
8. Ghi vào `lakehouse.public.bronze_documents`

**Output log:**
```
Bronze batch: 72,843 records after dedup
DQ[bronze_ingest_batch] PASS — 5/5 rules passed, 0 critical failures, 0 warnings
Bronze batch ingestion completed. Manifest: data/manifests/bronze_ingest_batch/...json
```

**Kiểm tra kết quả:**
```bash
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_bronze.sql
```
```
table_name          | total_rows | distinct_doc_ids | distinct_hashes | null_doc_ids | empty_raw_text
bronze_documents    |     72843  |           72843  |          72843  |            0 |             0
```

**Dấu hiệu THÀNH CÔNG:**
- ✅ `total_rows > 0`
- ✅ `null_doc_ids = 0`
- ✅ `empty_raw_text = 0`
- ✅ `distinct_hashes = distinct_doc_ids` (không trùng lặp)
- ✅ Manifest file có `"status": "success"`

---

### 4.2 Bước 2 — Làm Sạch Silver

**Chạy lệnh:**
```bash
python pipelines/silver/cleanse_documents.py --mode batch
```

**Quá trình xử lý:**
1. Đọc toàn bộ `bronze_documents` (72,843 dòng)
2. Chuẩn hóa văn bản (loại ký tự đặc biệt, chuẩn hóa khoảng trắng)
3. Tính `char_count = length(clean_text)`
4. Tính `word_count = size(split(clean_text, "\\s+"))`
5. Tính `quality_score = min(1.0, char_count / 2000)`
6. Parse ngày: `ngay_ban_hanh` "20/11/2014" → `issuance_date` 2014-11-20
7. Chuẩn hóa `effect_status`: "Còn hiệu lực" → "còn hiệu lực"
8. Split: `char_count < 50` hoặc `word_count < 5` → quarantine
9. Ghi Silver + Quarantine

**Output log:**
```
Bronze records to process: 72843
Silver: 71,205 valid, 1,638 quarantined
DQ[silver_cleanse] PASS — 5/5 rules passed, 0 critical failures, 2 warnings
Silver cleansing completed. Manifest: data/manifests/silver_cleanse/...json
```

**Kiểm tra kết quả:**
```bash
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_silver.sql
```
```
table_name        | total_rows | avg_word_count | avg_quality_score | unparsed_dates
silver_documents  |     71205  |        187.42  |             0.394 |           3421
```

```
Quarantine:
dq_rule               | quarantined_count
silver_min_length     |             1638
```

**Dấu hiệu THÀNH CÔNG:**
- ✅ `silver_rows + quarantine_rows ≈ bronze_rows` (±1%)
- ✅ `avg_word_count > 50` (văn bản pháp luật thường dài)
- ✅ `null_clean_text = 0`
- ✅ Manifest có `"dq_passed": true`

**Kiểm tra reconciliation (Bronze vs Silver+Quarantine):**
```sql
-- Qua Trino:
SELECT
  b.ingest_date,
  b.bronze_count,
  s.silver_count,
  q.quarantine_count,
  b.bronze_count - COALESCE(s.silver_count, 0) - COALESCE(q.quarantine_count, 0) AS unaccounted
FROM (SELECT ingest_date, COUNT(*) AS bronze_count FROM iceberg.public.bronze_documents GROUP BY 1) b
LEFT JOIN (SELECT ingest_date, COUNT(*) AS silver_count FROM iceberg.public.silver_documents GROUP BY 1) s ON b.ingest_date = s.ingest_date
LEFT JOIN (SELECT DATE(quarantined_at) AS ingest_date, COUNT(*) AS quarantine_count FROM iceberg.public.silver_quarantine GROUP BY 1) q ON b.ingest_date = q.ingest_date;
```
```
ingest_date | bronze_count | silver_count | quarantine_count | unaccounted
2024-06-01  |        72843 |        71205 |             1638 |           0  ← Lý tưởng!
```

---

### 4.3 Bước 3 — Tổng Hợp Gold

**Chạy lệnh:**
```bash
python pipelines/gold/aggregate_metrics.py
```

**Quá trình xử lý:**
1. Đọc Silver (71,205 dòng)
2. Nhóm theo 5 chiều → 5 bảng Gold
3. DQ check trên tất cả bảng
4. Ghi tất cả 5 bảng Gold (overwritePartitions)

**Output log:**
```
Gold daily_stats: 1 rows
Gold legal_type_breakdown: 14 rows
Gold issuing_authority: 287 rows
Gold legal_field_stats: 183 rows
Gold effect_status: 4 rows
DQ[gold_refresh] PASS — 15/15 rules passed, 0 critical failures, 0 warnings
Gold aggregation completed. Manifest: data/manifests/gold_refresh/...json
```

**Kiểm tra kết quả:**
```bash
docker exec -i trino trino --catalog iceberg < infra/trino/sql/validate_gold.sql
```

**Kết quả mẫu — Phân loại văn bản:**
```
loai_van_ban   | total_docs | avg_words
────────────────────────────────────────
nghị định      |     12,543 |    245.3
thông tư       |      8,921 |    312.7
quyết định     |      7,234 |    178.9
luật           |      1,823 |    892.4
chỉ thị        |        934 |    156.2
công văn       |        812 |    134.8
pháp lệnh      |        521 |    445.6
nghị quyết     |        498 |    367.2
```

**Kết quả mẫu — Tình trạng hiệu lực:**
```
effect_status      | document_count | pct
───────────────────────────────────────────
còn hiệu lực       |         46,283 | 65.0%
hết hiệu lực       |         19,926 | 28.0%
chưa có hiệu lực   |          4,996 |  7.0%
```

**Dấu hiệu THÀNH CÔNG:**
- ✅ `gold_tables_written = 5` trong manifest
- ✅ Tất cả `document_count >= 0`
- ✅ Tổng document count trong Gold ≈ Silver count

---

### 4.4 Kiểm Tra Tổng Hợp bằng Script

**Chạy:**
```bash
python scripts/verify_local.py
```

**Output khi THÀNH CÔNG:**
```
=== Vietnamese Legal Documents Pipeline — Verification ===

[1/5] Bronze manifest:
  ✓ [PASS] Bronze status=success
  ✓ [PASS] Bronze rows_out=72843

[2/5] Silver manifest:
  ✓ [PASS] Silver status=success
  ✓ [PASS] Silver DQ passed=True
  ✓ [PASS] Silver rows_out=71205, quarantined=1638

[3/5] Gold manifest:
  ✓ [PASS] Gold status=success
  ✓ [PASS] Gold tables_written=5 (expected 5)

[4/5] Bronze → Silver reconciliation:
  ⚠️ [WARN] Bronze=72843, Silver+Quarantine=72843 (100.0% accounted for)

[5/5] Pipeline metrics JSONL:
  ✓ [PASS] Metrics file has 6 entries at data/metrics/pipeline_metrics.jsonl

✅ All checks PASSED — pipeline is healthy
```

---

## 5. Giám Sát và Quan Sát

### 5.1 Run Manifests — Audit Trail

Mỗi lần chạy pipeline ghi 1 file JSON tại `data/manifests/<stage>/<run_id>.json`:

```bash
# Xem tất cả manifest
tree data/manifests/
# data/manifests/
# ├── bronze_ingest_batch/
# │   └── 20240601T020500_a1b2c3d4.json  ← Bronze run
# ├── silver_cleanse/
# │   └── 20240601T022134_b2c3d4e5.json  ← Silver run
# ├── gold_refresh/
# │   └── 20240601T023045_c3d4e5f6.json  ← Gold run
# └── hf_dataset_load/
#     └── 20240601T020000_abc12345.json  ← HF download
```

### 5.2 Pipeline Metrics JSONL

Mỗi stage emit 1 dòng JSON vào `data/metrics/pipeline_metrics.jsonl`:

```jsonl
{"event":"pipeline_metrics","stage":"hf_dataset_load","run_id":"...","status":"success","rows_out":149042,"duration_ms":2345678.9,"dq_passed":true,"timestamp":"2024-06-01T02:39:07Z"}
{"event":"pipeline_metrics","stage":"bronze_ingest_batch","run_id":"...","status":"success","rows_in":74521,"rows_out":72843,"duration_ms":142300.5,"dq_passed":true,"dq_critical_failures":0,"dq_warnings":0,"timestamp":"2024-06-01T02:47:02Z"}
{"event":"pipeline_metrics","stage":"silver_cleanse","run_id":"...","status":"success","rows_in":72843,"rows_out":71205,"rows_quarantined":1638,"duration_ms":754321.5,"dq_passed":true,"timestamp":"2024-06-01T03:00:23Z"}
{"event":"pipeline_metrics","stage":"gold_refresh","run_id":"...","status":"success","rows_out":489,"gold_tables_written":5,"duration_ms":98765.3,"dq_passed":true,"timestamp":"2024-06-01T03:15:42Z"}
```

### 5.3 Kibana Log Search (ELK Stack)

Truy cập `http://localhost:5601`:
- Index pattern: `logstash-*` hoặc `filebeat-*`
- Filter: `logger: "bronze_pipeline" AND level: "ERROR"` → Tìm lỗi Bronze
- Dashboard: "Pipeline Overview" → Trend các stage theo thời gian

---

## 6. So Sánh Dữ Liệu Trước và Sau Xử Lý

### 6.1 Bronze vs Silver — Ví Dụ Thực Tế

**Dữ liệu Bronze (thô từ HuggingFace):**
```
doc_id          : 12345
raw_text        : "Điều 1. Phạm vi điều chỉnh Luật này quy định về..."
                  (văn bản đã strip HTML nhưng còn nhiễu)
ngay_ban_hanh   : "20/11/2014"        ← Định dạng Việt Nam, chưa chuẩn
tinh_trang_hieu_luc: "Còn hiệu lực"  ← Không nhất quán (viết hoa)
```

**Dữ liệu Silver (đã chuẩn hóa):**
```
doc_id          : 12345
clean_text      : "Điều 1. Phạm vi điều chỉnh Luật này quy định về..."
                  (loại ký tự đặc biệt, chuẩn hóa khoảng trắng)
char_count      : 4521              ← Đếm chính xác
word_count      : 892               ← Đếm từ tiếng Việt
quality_score   : 1.0               ← Văn bản dài → chất lượng cao
issuance_date   : 2014-11-20        ← ISO DATE
effect_status   : "còn hiệu lực"   ← Chuẩn hóa nhất quán
```

### 6.2 Bảng Kiểm Dịch — Ví Dụ Bản Ghi Bị Từ Chối

```bash
docker exec trino trino --execute \
  "SELECT doc_id, rejection_reason, raw_text_preview FROM iceberg.public.silver_quarantine LIMIT 5"
```
```
doc_id | rejection_reason               | raw_text_preview
───────┼────────────────────────────────┼──────────────────────────────────
99999  | char_count=23 < min=50         | "Số: 01/TB-HĐND"
88888  | clean_text is null             | (null)
77777  | char_count=45 < min=50         | "Điều 1. Hiệu lực thi hành."
66666  | word_count=3 < min=5           | "Xem Luật số 59."
```

### 6.3 Gold — Ví Dụ Phân Tích Nghiệp Vụ

**Câu hỏi**: Cơ quan nào ban hành nhiều văn bản nhất?

```sql
-- Chạy trên Trino hoặc Superset
SELECT co_quan_ban_hanh, SUM(document_count) as tong
FROM iceberg.public.gold_issuing_authority
GROUP BY co_quan_ban_hanh
ORDER BY tong DESC LIMIT 10;
```
```
co_quan_ban_hanh               | tong
───────────────────────────────┼───────
Chính phủ                      | 12,345
Bộ Tài chính                   |  4,231
Bộ Tư pháp                     |  3,892
Bộ Y tế                        |  2,143
Ngân hàng Nhà nước Việt Nam    |  1,987
...
```

---

## 7. Điểm Nổi Bật Kỹ Thuật Cho Thuyết Trình

| Tính Năng | Giải Pháp | Ý Nghĩa |
|----------|----------|---------|
| **Dedup tất định** | `record_hash = SHA256(doc_id + raw_text[:200])` | Chạy lại pipeline nhiều lần → không bị trùng dữ liệu |
| **DQ Gate với nhánh** | Airflow `BranchPythonOperator` đọc manifest | Pipeline không tiến sang Gold nếu Silver có lỗi nghiêm trọng |
| **Dead-Letter Queue** | Bảng `bronze_dlq` chứa tin nhắn Kafka lỗi | Không mất dữ liệu, có thể replay sau khi sửa |
| **Quarantine** | Bảng `silver_quarantine` thay vì xóa | Văn bản ngắn được giữ lại để phân tích sau |
| **Time Travel** | Iceberg snapshots | `SELECT * FROM table FOR TIMESTAMP AS OF '2024-06-01'` |
| **Partition Pruning** | Phân vùng theo `ingest_date` | Trino query nhanh hơn 10-100x khi filter theo ngày |
| **Observability** | Manifest JSON + JSONL metrics | Mỗi run có audit trail đầy đủ, tích hợp Grafana |
| **Bảo trì tự động** | Airflow weekly: compaction + expire | Không tích lũy file nhỏ, giữ hiệu năng ổn định |
| **Config không hardcode** | `AppConfig` từ env-vars | Không bao giờ commit mật khẩu vào git |
| **31 unit tests** | pytest + 100% pass | Đảm bảo DQ logic đúng đắn |

---

## 8. Cấu Trúc Thư Mục Dự Án

```
bigdata_project/
├── common/                    ← Thư viện dùng chung (Phase 1)
│   ├── config.py              ← AppConfig: toàn bộ config từ env-var
│   ├── schemas.py             ← Schema Bronze/Silver/Gold
│   ├── dq_checks.py           ← DQ gates: validate_bronze/silver/gold
│   ├── manifests.py           ← Run manifest: ghi + đọc JSON
│   ├── pipeline_metrics.py    ← Emit metrics → log + JSONL
│   └── logger.py              ← JSON structured logger
│
├── pipelines/                 ← Spark pipelines (Phase 2)
│   ├── bronze/ingest_raw.py   ← Bronze: HF Parquet/Kafka → Iceberg
│   ├── silver/cleanse_documents.py  ← Silver: chuẩn hóa + DQ
│   └── gold/aggregate_metrics.py   ← Gold: 5 bảng phân tích
│
├── services/
│   ├── ingestion/hf_dataset_loader.py  ← Tải HuggingFace → MinIO
│   └── ai-rag-engine/main.py           ← FastAPI + BGE-M3 + Milvus
│
├── dags/document_pipeline.py  ← Airflow DAGs (Phase 3)
│
├── infra/
│   ├── docker-compose.yaml    ← Toàn bộ stack (không hardcode password)
│   ├── jobs/iceberg_maintenance.py  ← Nén + xóa snapshot
│   └── trino/
│       ├── catalog/iceberg.properties  ← Kết nối Trino → Iceberg
│       └── sql/validate_*.sql          ← SQL kiểm tra chất lượng
│
├── docs/                      ← Tài liệu tiếng Việt (Phase 4)
│   ├── overview.md            ← Tài liệu này
│   ├── architecture.md        ← Kiến trúc hệ thống
│   ├── pipeline.md            ← Hợp đồng dữ liệu
│   ├── deployment.md          ← Hướng dẫn triển khai
│   └── operations.md          ← Vận hành + Runbook
│
├── tests/
│   ├── conftest.py            ← Fixtures chung
│   └── unit/
│       ├── test_config.py     ← 14 tests cho AppConfig
│       └── test_dq_checks.py  ← 17 tests cho DQ gates
│
├── scripts/
│   ├── bootstrap_local.sh     ← Khởi tạo môi trường dev
│   └── verify_local.py        ← Kiểm tra health pipeline
│
└── .env.example               ← Template biến môi trường
```
