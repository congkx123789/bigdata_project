import os
import logging
from pathlib import Path
import importlib.util
from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from minio import Minio
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chatbot_backend")

app = Flask(__name__)
CORS(app)

# Database Configuration (Host port is 5433 as remapped)
DB_CONFIG = {
    "host": "localhost",
    "port": "5433",
    "database": "document_db",
    "user": "admin",
    "password": "password123"
}

# MinIO Configuration
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "password123"

minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

# Lazy-load RAG pipeline from services/rag/rag_pipeline.py
_RAG_ASK = None
_RAG_LOAD_ERROR = None

def get_rag_ask():
    global _RAG_ASK, _RAG_LOAD_ERROR
    if _RAG_ASK is not None:
        return _RAG_ASK
    if _RAG_LOAD_ERROR is not None:
        raise RuntimeError(_RAG_LOAD_ERROR)

    rag_file = Path(__file__).resolve().parent.parent / "rag" / "rag_pipeline.py"
    if not rag_file.exists():
        _RAG_LOAD_ERROR = f"RAG file not found: {rag_file}"
        raise RuntimeError(_RAG_LOAD_ERROR)

    try:
        spec = importlib.util.spec_from_file_location("rag_pipeline", str(rag_file))
        rag_module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(rag_module)
        _RAG_ASK = rag_module.ask_question
        logger.info("RAG pipeline loaded successfully")
        return _RAG_ASK
    except Exception as e:
        _RAG_LOAD_ERROR = str(e)
        logger.exception("Failed to load RAG pipeline")
        raise

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "Chatbot Backend is running"})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_query = data.get("message", "").lower()
    
    if not user_query:
        return jsonify({"error": "No message provided"}), 400

    logger.info(f"Received query: {user_query}")

    # Logic 1: Tra cứu thống kê đơn giản từ Postgres
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        if "thống kê" in user_query or "bao nhiêu" in user_query:
            cur.execute("SELECT count(*) FROM documents")
            count = cur.fetchone()[0]
            response = f"Hiện tại hệ thống đã nạp được {count:,} tài liệu vào kho lưu trữ."
        elif "trạng thái" in user_query:
            cur.execute("SELECT status, count(*) FROM documents GROUP BY status")
            stats = cur.fetchall()
            response = "Trạng thái hệ thống: " + ", ".join([f"{s[0]}: {s[1]:,}" for s in stats])
        else:
            # Real RAG response for generic queries
            try:
                ask = get_rag_ask()
                answer, context = ask(user_query)
                if not answer or not str(answer).strip():
                    response = "Mình chưa tìm được câu trả lời rõ ràng từ dữ liệu."
                else:
                    response = str(answer)
            except Exception as rag_error:
                logger.error(f"RAG error: {str(rag_error)}")
                response = "Mình chưa truy xuất được RAG cục bộ, hiện đang trả lời ở chế độ cơ bản."
            
        cur.close()
        conn.close()
        
        return jsonify({
            "response": response,
            "sender": "bot",
            "timestamp": "now"
        })
        
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        return jsonify({"response": "Xin lỗi, tôi đang gặp trục trặc khi kết nối với kho dữ liệu.", "sender": "bot"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)
