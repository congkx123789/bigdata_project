import time

def start_ocr_worker():
    """
    Data Worker: Lắng nghe Kafka topic 'document-uploaded'
    Sử dụng PaddleOCR để bóc tách chữ từ ảnh.
    Đẩy text result vào topic 'text-extracted'.
    """
    print("[OCR WORKER] Listening to Kafka topic: document-uploaded...")
    while True:
        # Mock looping
        time.sleep(10)
        print("[OCR WORKER] Waiting for documents to extract using RTX 5060 Ti...")

if __name__ == "__main__":
    start_ocr_worker()
