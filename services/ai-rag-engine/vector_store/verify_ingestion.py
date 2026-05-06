import os
from pymilvus import connections, Collection
import json

def verify_data():
    connections.connect("default", host="milvus-standalone", port="19530")
    collection = Collection("vi_legal_rag")
    collection.load()
    
    # Lấy ngẫu nhiên 20 records để kiểm tra
    results = collection.query(
        expr="id > 0",
        output_fields=["filename", "title", "text"],
        limit=20
    )
    
    output = []
    for res in results:
        output.append({
            "chunk_id": res.get("filename"),
            "extracted_title": res.get("title"),
            "content_preview": res.get("text")[:500] + "..."
        })
        
    with open("/app/verify_1200_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
    
    print(f"✅ Đã kiểm định xong 20 mẫu ngẫu nhiên từ 1200 đoạn. Kết quả lưu tại verify_1200_results.json")

if __name__ == "__main__":
    verify_data()
