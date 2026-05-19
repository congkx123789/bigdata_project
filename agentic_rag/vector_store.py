import os
import re
import torch
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
# from FlagEmbedding import FlagReranker

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VectorStore")

class VectorStore:
    def __init__(self, collection_name=None, host=None, port=None):
        host = host or os.getenv("MILVUS_HOST", "localhost")
        port = port or os.getenv("MILVUS_PORT", "19530")
        collection_name = collection_name or os.getenv("MILVUS_COLLECTION", "vi_legal_rag")
        
        # 1. Khởi tạo BGE Embedding Model
        self.device = "cpu"
        if torch.cuda.is_available():
            try:
                # Thử nghiệm thực tế xem GPU có tương thích với driver/pytorch hiện tại không
                test_tensor = torch.zeros(1).to("cuda")
                self.device = "cuda"
            except Exception as e:
                logger.warning(f"CUDA is available but unusable (likely sm compatibility issue): {e}. Falling back to CPU.")
                self.device = "cpu"

        embedding_model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        logger.info(f"Loading Embedding Model ({embedding_model_name}) on {self.device}...")
        self.model = SentenceTransformer(embedding_model_name, device=self.device)
        
        if self.device == "cuda":
            try:
                self.model = self.model.to(torch.bfloat16)
                logger.info("VectorStore Model optimized with bfloat16")
            except Exception as e:
                logger.warning(f"Failed to move model to bfloat16: {e}. Keeping default precision.")
        
        # 2. Khởi tạo BGE Reranker Model trên GPU
        reranker_model_name = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        logger.info(f"Loading Reranker Model ({reranker_model_name}) on {self.device}...")
        # use_fp16 helps reduce VRAM usage on 5060 Ti
        # self.reranker = FlagReranker(reranker_model_name, use_fp16=True)
        
        # 3. Kết nối Milvus
        logger.info(f"Connecting to Milvus at {host}:{port}...")
        connections.connect("default", host=host, port=int(port))
        self.collection = Collection(collection_name)
        self.collection.load()
        logger.info(f"Collection '{collection_name}' loaded successfully.")

    def search(self, query_text: str, k: int = 6, recall_k: int = 20):
        """
        Two-stage retrieval:
        1. Recall: Semantic search (BGE-M3) + Keyword search
        2. Precision: Reranking (BGE-Reranker)
        """
        # --- PHASE 1: RECALL ---
        # 1.1 Vector Search
        query_vector = self.model.encode(query_text).tolist()
        search_params = {"metric_type": "L2", "params": {"nprobe": 16}}
        
        vector_results = self.collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=recall_k,
            output_fields=["filename", "text", "title"]
        )
        
        candidates = {}
        for hit in vector_results[0]:
            entity = hit.entity
            fname = entity.get('filename')
            chunk_id = f"{fname}#chunk_id_{hit.id}"
            candidates[chunk_id] = {
                "chunk_id": chunk_id,
                "title": entity.get("title") or "Văn bản chưa rõ tiêu đề",
                "content": entity.get("text"),
                "initial_score": hit.distance,
                "type": "semantic"
            }
        
        # 1.2 Keyword Search (Hybrid)
        if any(word in query_text.lower() for word in ["điều", "luật", "nghị định", "thông tư"]):
            keywords = re.findall(r"(Điều \d+|Luật [\w\s]+|Nghị định \d+)", query_text, re.IGNORECASE)
            for kw in keywords:
                expr = f'text LIKE "{kw}%"'
                try:
                    kw_results = self.collection.query(
                        expr=expr,
                        output_fields=["id", "text", "filename", "title"],
                        limit=5
                    )
                    for res in kw_results:
                        fname = res.get('filename')
                        chunk_id = f"{fname}#chunk_id_{res.get('id')}"
                        if chunk_id not in candidates:
                            candidates[chunk_id] = {
                                "chunk_id": chunk_id,
                                "title": res.get("title") or "Văn bản chưa rõ tiêu đề",
                                "content": res.get("text"),
                                "initial_score": 0.0,
                                "type": "keyword"
                            }
                except Exception as e:
                    logger.error(f"Keyword search error: {e}")

        if not candidates:
            return []

        # --- PHASE 2: RERANKING ---
        candidate_list = list(candidates.values())
        if not candidate_list: return []
        pairs = [[query_text, c['content'][:1000]] for c in candidate_list]
        try:
            import torch
            with torch.no_grad():
                rerank_scores = self.reranker.compute_score(pairs)
            for i, score in enumerate(rerank_scores):
                candidate_list[i]['rerank_score'] = score
            sorted_candidates = sorted(candidate_list, key=lambda x: x.get('rerank_score', -99), reverse=True)
            logger.info(f"Reranked {len(candidate_list)} candidates using GPU.")
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            sorted_candidates = sorted(candidate_list, key=lambda x: x['initial_score'])
        return sorted_candidates[:k]

    def get_context(self, chunk_id: str, window: int = 2):
        """
        Lấy các đoạn văn bản xung quanh một chunk_id để trích xuất sâu hơn.
        """
        try:
            parts = chunk_id.split("#chunk_id_")
            if len(parts) < 2: return []
            filename = parts[0]
            base_id = int(parts[1])
            
            id_range = [i for i in range(base_id - window, base_id + window + 1)]
            id_expr = f"id in {id_range} and filename == '{filename}'"
            
            results = self.collection.query(
                expr=id_expr,
                output_fields=["id", "text", "filename", "title"]
            )
            
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
