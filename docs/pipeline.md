# Hợp Đồng Pipeline — Bronze, Silver, Gold

## Nguồn Dữ Liệu

**HuggingFace**: `th1nhng0/vietnamese-legal-documents`
**Nguồn gốc**: vbpl.vn — Cổng thông tin pháp luật Chính phủ Việt Nam
**Ngôn ngữ**: Tiếng Việt

### Các Subset

| Subset | Các Cột | Mô Tả |
|--------|---------|-------|
| `content` | id, content_html | Nội dung HTML đầy đủ của mỗi văn bản pháp luật |
| `metadata` | id, title, so_ky_hieu, ngay_ban_hanh, loai_van_ban, ngay_co_hieu_luc, ngay_het_hieu_luc, nganh, linh_vuc, co_quan_ban_hanh, nguoi_ky, tinh_trang_hieu_luc | Siêu dữ liệu có cấu trúc |
| `relationships` | doc_id, other_doc_id, relationship | Quan hệ liên văn bản (sửa đổi, dẫn chiếu, bãi bỏ) |

---

## Hợp Đồng Tầng Bronze

**Bảng**: `lakehouse.public.bronze_documents`
**Định dạng**: Apache Iceberg
**Chế độ**: Chỉ thêm mới (Append-only)
**Phân vùng**: `ingest_date` (DATE)

### Schema

| Cột | Kiểu | Nullable | Mô Tả |
|-----|------|----------|-------|
| `doc_id` | STRING | NOT NULL | ID văn bản từ HuggingFace |
| `source_bucket` | STRING | YES | `huggingface` hoặc tên bucket MinIO |
| `source_path` | STRING | YES | Đường dẫn repo dataset |
| `raw_text` | STRING | YES | Văn bản thuần (đã loại bỏ HTML) |
| `content_html` | STRING | YES | HTML gốc (giữ lại để xử lý lại nếu cần) |
| `title` | STRING | YES | Tiêu đề văn bản |
| `so_ky_hieu` | STRING | YES | Số ký hiệu (vd: 36/2009/QH12) |
| `loai_van_ban` | STRING | YES | Loại văn bản (luật, nghị định, thông tư, ...) |
| `ngay_ban_hanh` | STRING | YES | Ngày ban hành (thô, DD/MM/YYYY hoặc YYYY-MM-DD) |
| `ngay_co_hieu_luc` | STRING | YES | Ngày có hiệu lực (thô) |
| `ngay_het_hieu_luc` | STRING | YES | Ngày hết hiệu lực (thô) |
| `co_quan_ban_hanh` | STRING | YES | Cơ quan ban hành |
| `linh_vuc` | STRING | YES | Lĩnh vực pháp lý |
| `nganh` | STRING | YES | Ngành |
| `nguoi_ky` | STRING | YES | Người ký |
| `tinh_trang_hieu_luc` | STRING | YES | Tình trạng hiệu lực (thô) |
| **`record_hash`** | STRING | NOT NULL | SHA256(doc_id + raw_text[:200]) — định danh khử trùng |
| **`dedupe_key`** | STRING | NOT NULL | concat(doc_id, loai_van_ban) — khóa tổng hợp an toàn khi chạy lại |
| `ingested_at` | TIMESTAMP | NOT NULL | Thời điểm thu thập |
| `ingest_date` | DATE | NOT NULL | Khóa phân vùng (từ ingested_at) |
| `pipeline_run_id` | STRING | YES | Liên kết đến run manifest |

### Quy Tắc DQ (Bronze)

| Quy Tắc | Mức Độ | Hành Động |
|---------|--------|-----------|
| `doc_id` không null | critical | Chuyển sang DLQ |
| `raw_text` không rỗng | critical | Chuyển sang DLQ |
| `record_hash` phải có | critical | Chặn batch |
| `dedupe_key` phải có | critical | Chặn batch |
| `record_hash` trùng trong batch | warning | Chỉ ghi log |

**Bảng DLQ**: `lakehouse.public.bronze_dlq`
Nhận các tin nhắn Kafka không phân tích được JSON hoặc có `doc_id` null.

---

## Hợp Đồng Tầng Silver

**Bảng**: `lakehouse.public.silver_documents`
**Kiểm dịch**: `lakehouse.public.silver_quarantine`
**Định dạng**: Apache Iceberg
**Chế độ**: Thêm mới có khử trùng
**Phân vùng**: `ingest_date` (DATE)

### Schema

| Cột | Kiểu | Nullable | Mô Tả |
|-----|------|----------|-------|
| `doc_id` | STRING | NOT NULL | ID văn bản |
| `record_hash` | STRING | NOT NULL | Từ Bronze |
| `clean_text` | STRING | YES | Văn bản thuần đã chuẩn hóa |
| `title` | STRING | YES | Tiêu đề văn bản |
| **`char_count`** | INT | YES | Số ký tự chính xác của `clean_text` |
| **`word_count`** | INT | YES | Số từ (tách theo khoảng trắng, phù hợp tiếng Việt) |
| **`quality_score`** | DOUBLE | YES | `min(1.0, char_count / 2000)` — từ 0.0 đến 1.0 |
| `so_ky_hieu` | STRING | YES | Số ký hiệu |
| `loai_van_ban` | STRING | YES | Loại văn bản đã chuẩn hóa |
| **`issuance_date`** | DATE | YES | Phân tích từ `ngay_ban_hanh` |
| **`effective_date`** | DATE | YES | Phân tích từ `ngay_co_hieu_luc` |
| **`expiry_date`** | DATE | YES | Phân tích từ `ngay_het_hieu_luc` |
| `co_quan_ban_hanh` | STRING | YES | Cơ quan ban hành |
| `linh_vuc` | STRING | YES | Lĩnh vực pháp lý |
| `nganh` | STRING | YES | Ngành |
| `nguoi_ky` | STRING | YES | Người ký |
| **`effect_status`** | STRING | YES | Chuẩn hóa: còn hiệu lực / hết hiệu lực / chưa có hiệu lực / không xác định |
| `ingested_at` | TIMESTAMP | NOT NULL | Từ Bronze |
| `processed_at` | TIMESTAMP | NOT NULL | Thời điểm xử lý Silver |
| `ingest_date` | DATE | NOT NULL | Khóa phân vùng |
| `pipeline_run_id` | STRING | YES | Liên kết đến run manifest |

### Quy Tắc DQ (Silver)

| Quy Tắc | Mức Độ | Ngưỡng | Hành Động |
|---------|--------|--------|-----------|
| `clean_text`, `processed_at` không null | critical | — | Chuyển sang kiểm dịch |
| `char_count >= 50` | critical | 50 ký tự | Chuyển sang kiểm dịch |
| `word_count >= 5` | warning | 5 từ | Chuyển sang kiểm dịch |
| `quality_score` trong [0.0, 1.0] | warning | — | Ghi log |
| Không trùng `doc_id` trong batch | warning | — | Ghi log |

### Schema Bảng Kiểm Dịch

| Cột | Mô Tả |
|-----|-------|
| `doc_id` | ID văn bản nguồn |
| `record_hash` | Từ Bronze |
| `raw_text_preview` | 200 ký tự đầu để debug |
| `rejection_reason` | Lý do từ chối dễ đọc |
| `dq_rule` | Tên quy tắc đã kích hoạt từ chối |
| `quarantined_at` | Thời điểm kiểm dịch |
| `pipeline_run_id` | Liên kết đến manifest |

---

## Hợp Đồng Tầng Gold

Tất cả bảng Gold:
- **Định dạng**: Apache Iceberg
- **Chế độ**: `overwritePartitions()` — làm mới hàng ngày idempotent
- **Phân vùng**: `ingest_date` (DATE)

### `gold_daily_stats` — Thống Kê Hàng Ngày

| Cột | Kiểu | Mô Tả |
|-----|------|-------|
| `ingest_date` | DATE | Khóa phân vùng |
| `total_documents` | BIGINT | Tổng văn bản Silver trong ngày |
| `avg_word_count` | DOUBLE | Số từ trung bình |
| `avg_quality_score` | DOUBLE | Điểm chất lượng trung bình |
| `quarantined_count` | BIGINT | Số văn bản bị kiểm dịch (thông tin) |
| `refreshed_at` | TIMESTAMP | Thời điểm làm mới Gold |

### `gold_legal_type_breakdown` — Phân Loại Theo Loại Văn Bản

| Cột | Kiểu | Mô Tả |
|-----|------|-------|
| `ingest_date` | DATE | Khóa phân vùng |
| `loai_van_ban` | STRING | Loại văn bản (luật, nghị định, ...) |
| `document_count` | BIGINT | Số văn bản theo loại theo ngày |
| `avg_word_count` | DOUBLE | Số từ trung bình |
| `refreshed_at` | TIMESTAMP | |

### `gold_issuing_authority` — Thống Kê Theo Cơ Quan Ban Hành

| Cột | Kiểu | Mô Tả |
|-----|------|-------|
| `ingest_date` | DATE | Khóa phân vùng |
| `co_quan_ban_hanh` | STRING | Tên cơ quan ban hành |
| `document_count` | BIGINT | Số văn bản theo cơ quan theo ngày |
| `refreshed_at` | TIMESTAMP | |

### `gold_legal_field_stats` — Thống Kê Theo Lĩnh Vực Pháp Lý

| Cột | Kiểu | Mô Tả |
|-----|------|-------|
| `ingest_date` | DATE | Khóa phân vùng |
| `linh_vuc` | STRING | Lĩnh vực pháp lý |
| `nganh` | STRING | Ngành |
| `document_count` | BIGINT | Số văn bản theo lĩnh vực theo ngày |
| `avg_quality_score` | DOUBLE | Chất lượng trung bình |
| `refreshed_at` | TIMESTAMP | |

### `gold_effect_status` — Tóm Tắt Theo Tình Trạng Hiệu Lực

| Cột | Kiểu | Mô Tả |
|-----|------|-------|
| `ingest_date` | DATE | Khóa phân vùng |
| `effect_status` | STRING | còn hiệu lực / hết hiệu lực / ... |
| `document_count` | BIGINT | Số văn bản theo tình trạng theo ngày |
| `refreshed_at` | TIMESTAMP | |

### Quy Tắc DQ (Gold)

| Bảng | Quy Tắc | Mức Độ |
|------|---------|--------|
| Tất cả | Các cột bắt buộc phải có | critical |
| Tất cả | `document_count >= 0` | critical |
| Tất cả | `ingest_date` không null | critical |
