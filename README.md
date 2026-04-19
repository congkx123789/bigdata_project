# Hệ thống Xử lý Tài liệu Thông minh (Bigdata AI Document Processing)

Hệ thống cung cấp nền tảng phân tích và truy vấn tài liệu quy mô lớn, kết hợp sức mạnh của Generative AI (RAG) và kiến trúc microservices hiện đại. Dự án được thiết kế để xử lý hàng triệu tài liệu với độ trễ thấp và khả năng mở rộng cao.

---

## 🚀 Công nghệ sử dụng

### 🎨 Frontend
- **Framework**: [Next.js 16](https://nextjs.org/) (React 19)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Components**: Shadcn UI, Framer Motion (cho micro-animations)
- **Features**: Streaming response, Markdown & LaTeX support, Responsive Design.

### 🧠 AI & RAG Engine
- **LLM**: [Google Gemini 2.0 Flash](https://ai.google.dev/) (Primary) & [Ollama](https://ollama.com/) (Local fallback).
- **Embedding Model**: [BAAI/BGE-M3](https://huggingface.co/BAAI/bge-m3) (Độ chính xác cao, hỗ trợ đa ngôn ngữ).
- **Orchestration**: LangChain & FastAPI.
- **Vector Database**: [Milvus](https://milvus.io/) (Standalone) - Lưu trữ và tìm kiếm vector hiệu năng cao.

### 🏗️ Infrastructure & Backend
- **Message Broker**: [Apache Kafka](https://kafka.apache.org/) - Xử lý luồng dữ liệu thời gian thực.
- **Object Storage**: [MinIO](https://min.io/) - Lưu trữ tài liệu thô và đã xử lý.
- **Database**: PostgreSQL 15 (Metadata) & Redis 7 (Caching).
- **Inference**: Ollama (chạy Llama 3.2:1b tại local).
- **IAM**: Keycloak (Quản lý định danh và quyền truy cập).

### 📊 Monitoring & Data Engineering
- **Monitoring**: Prometheus, Grafana, ELK Stack (Elasticsearch, Logstash, Kibana).
- **Data Processing**: Apache Spark (Ingestion pipelines).
- **Workflow**: Airflow (tuần tự hóa các task xử lý dữ liệu).

---

## ✨ Những thứ đã làm được

- [x] **Hạ tầng Docker hóa**: Triển khai toàn bộ stack hạ tầng (Milvus, Kafka, MinIO, v.v.) chỉ với 1 câu lệnh.
- [x] **Pipeline RAG hoàn chỉnh**: Tích hợp thành công BGE-M3 cho embedding và Gemini 2.0 cho sinh văn bản.
- [x] **Giao diện Chat hiện đại**: Hỗ trợ streaming, hiển thị nguồn trích dẫn (sources), và giao diện Sidebar linh hoạt.
- [x] **Hệ thống Ingestion**: Tự động nạp tài liệu từ MinIO, trích xuất text và đẩy vào Milvus qua Spark.
- [x] **Quản lý GPU**: Script tự động giới hạn công suất GPU (Nvidia Power Limit) để bảo vệ phần cứng (RTX 5060 Ti Blackwell).
- [x] **Giám sát hệ thống**: Dashboard Grafana theo dõi sức khỏe container và lưu lượng Kafka.

---

## 🛠️ Hướng dẫn cài đặt (Setup)

### 1. Yêu cầu hệ thống
- **OS**: Linux (Ubuntu 22.04+ khuyến nghị).
- **Hardware**: Nvidia GPU (8GB+ VRAM), 16GB+ RAM.
- **Tools**: Docker, Docker Compose, Python 3.10+, Node.js 20+.

### 2. Các bước triển khai

**Bước 1: Cấu hình phần cứng**
Đảm bảo bạn đã cài đặt Nvidia Container Toolkit. Hệ thống sẽ tự động giới hạn công suất GPU ở mức 150W.

**Bước 2: Khởi chạy hạ tầng và cài đặt dependency**
```bash
chmod +x setup.sh
./setup.sh
```
Script này sẽ:
1. Áp dụng giới hạn công suất GPU.
2. Khởi chạy toàn bộ container trong `infra/` và `monitoring/`.
3. Cài đặt các thư viện Python cần thiết cho backend.

**Bước 3: Cài đặt Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Bước 4: Cấu hình biến môi trường**
Tạo file `.env` trong các thư mục tương ứng (`services/ai-rag-engine`, `frontend`) dựa trên các file `.env.example`. 
Quan trọng: Cần có `GOOGLE_API_KEY` để sử dụng Gemini.

---

## 🌍 Triển khai đa máy (Portable Deployment)

Hệ thống được thiết kế để có thể dễ dàng thiết lập trên một máy tính mới bằng cách đồng bộ mã nguồn qua GitHub và dữ liệu qua Hugging Face.

### 1. Đồng bộ dữ liệu lên Hugging Face (Trên máy gốc)
Nếu bạn có thay đổi về dữ liệu hoặc vector indexed, hãy chạy script sau để upload snapshot lên Hugging Face:
```bash
export HF_TOKEN="your_huggingface_token_here"
python3 sync_to_hf.py
```
*Dữ liệu sẽ được đẩy lên repository: [Cong123779/bigdata-assets](https://huggingface.co/datasets/Cong123779/bigdata-assets)*

### 2. Thiết lập trên máy mới
1. Clone mã nguồn từ GitHub:
   ```bash
   git clone https://github.com/congkx123789/bigdata_project.git
   cd bigdata_project
   ```
2. Cài đặt biến môi trường và chạy script setup:
   ```bash
   export HF_TOKEN="your_huggingface_token_here"
   ./setup.sh
   ```
3. Khi được hỏi: `Do you want to restore data from Hugging Face?`, chọn `y`. Hệ thống sẽ tự động tải các bản sao lưu từ Hugging Face và khôi phục vào các Docker Volume tương ứng.

---

## 📂 Cấu trúc dự án

- `frontend/`: Ứng dụng Web Next.js.
- `infra/`: Cấu hình Docker Compose cho các dịch vụ nền tảng (Database, Broker).
- `services/`: Các microservices xử lý (Core API, RAG Engine, Ingestor).
- `monitoring/`: Cấu hình cho stack giám sát (Grafana/Prometheus).
- `dags/`: Các quy trình xử lý dữ liệu tự động hóa bằng Airflow.
- `infrastructure/`: Các script setup bổ sung và cấu hình môi trường.

---

## 🤝 Liên hệ
Dự án được phát triển và duy trì bởi **congkx123789**.
