
import torch
import re
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorStore")

class VectorStore:
    def __init__(self, collection_name="vi_legal_rag", host=None, port=None):
        import os
        host = host or os.getenv("MILVUS_HOST", "localhost")
        port = port or os.getenv("MILVUS_PORT", "19530")
        # 1. Khởi tạo BGE Model trên GPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading Embedding Model (BGE-M3) on {self.device}...")
        self.model = SentenceTransformer('BAAI/bge-m3', device=self.device)
        
        # 2. Kết nối Milvus
        logger.info(f"Connecting to Milvus at {host}:{port}...")
        connections.connect("default", host=host, port=int(port))
        self.collection = Collection(collection_name)
        self.collection.load()
        logger.info(f"Collection '{collection_name}' loaded successfully.")

    def search(self, query_text: str, k: int = 6):
        # 1. Vector Search (Semantic)
        query_vector = self.model.encode(query_text).tolist()
        # Tối ưu nprobe để tìm kiếm nhanh hơn (giảm từ 128 xuống 16)
        search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
        
        vector_results = self.collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=k,
            output_fields=["filename", "text", "title"]
        )
        
        hits = {}
        for hit in vector_results[0]:
            chunk_id = f"{hit.entity.get('filename')}#chunk_id_{hit.id}"
            hits[chunk_id] = {
                "chunk_id": chunk_id,
                "title": hit.entity.get("title", "Văn bản chưa rõ tiêu đề"),
                "content": hit.entity.get("text"),
                "score": hit.distance,
                "type": "semantic"
            }
        
        # 2. Keyword Search (Chỉ chạy khi có từ khóa đặc biệt để đảm bảo tốc độ)
        if any(word in query_text.lower() for word in ["điều", "luật", "nghị định", "thông tư"]):
            keywords = re.findall(r"(Điều \d+|Luật [\w\s]+|Nghị định \d+)", query_text, re.IGNORECASE)
            for kw in keywords:
                # Milvus 2.3+ LIKE only supports prefix matching like 'word%'
                expr = f"text LIKE '{kw}%'"
                try:
                    kw_results = self.collection.query(
                        expr=expr,
                        output_fields=["id", "text", "filename", "title"],
                        limit=3
                    )
                    for res in kw_results:
                        chunk_id = f"{res.get('filename')}#chunk_id_{res.get('id')}"
                        if chunk_id not in hits:
                            hits[chunk_id] = {
                                "chunk_id": chunk_id,
                                "title": res.get("title", "Văn bản chưa rõ tiêu đề"),
                                "content": res.get("text"),
                                "score": 0.0,
                                "type": "keyword"
                            }
                except: pass

        sorted_hits = sorted(hits.values(), key=lambda x: (x['type'] != 'keyword', x['score']))
        return sorted_hits[:k]

    def get_context(self, chunk_id: str, window: int = 2):
        """
        Lấy các đoạn văn bản xung quanh một chunk_id để trích xuất sâu hơn.
        """
        try:
            # Parse chunk_id: "filename#chunk_id_123"
            parts = chunk_id.split("#chunk_id_")
            filename = parts[0]
            base_id = int(parts[1])
            
            # Tính toán dải ID (ví dụ base_id - 2 đến base_id + 2)
            id_range = [i for i in range(base_id - window, base_id + window + 1)]
            id_expr = f"id in {id_range} and filename == '{filename}'"
            
            # Truy vấn Milvus
            results = self.collection.query(
                expr=id_expr,
                output_fields=["id", "text", "filename", "title"]
            )
            
            # Sắp xếp theo ID để đảm bảo thứ tự văn bản
            results.sort(key=lambda x: x['id'])
            
            hits = []
            for res in results:
                hits.append({
                    "chunk_id": f"{res.get('filename')}#chunk_id_{res.get('id')}",
                    "title": res.get("title", "Văn bản chưa rõ tiêu đề"),
                    "content": res.get("text")
                })
            return hits
        except Exception as e:
            logger.error(f"Error in get_context: {e}")
            return []
