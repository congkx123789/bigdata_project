"""
Unstructured Worker: Xử lý PDF text, DOCX, TXT
Lắng nghe Kafka topic 'document-uploaded', phân loại file type,
nếu là text-based thì extract trực tiếp bằng unstructured.io
rồi push text vào topic 'text-extracted'.
"""
import time
import json

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF using unstructured library."""
    # TODO: from unstructured.partition.pdf import partition_pdf
    return f"Extracted text from {file_path}"

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from Word documents."""
    # TODO: from unstructured.partition.docx import partition_docx
    return f"Extracted text from {file_path}"

def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list:
    """Chia text thành các đoạn nhỏ (chunks) để embedding."""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunks.append(text[i:i + chunk_size])
    return chunks

def start_unstructured_worker():
    print("[UNSTRUCTURED WORKER] Listening to Kafka topic: document-uploaded...")
    while True:
        time.sleep(10)
        print("[UNSTRUCTURED WORKER] Waiting for text-based documents...")

if __name__ == "__main__":
    start_unstructured_worker()
