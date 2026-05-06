
import torch
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection
import logging

# Tối ưu cho Blackwell
torch.backends.cuda.matmul.allow_tf32 = True
os_environ = __import__('os').environ
os_environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_search")

def test_query(query_text, top_k=3):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"🚀 Loading model on {device}...")
    
    # Load model với BF16 cho Blackwell
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    if device == "cuda":
        model = model.to(dtype=torch.bfloat16)
    
    # Kết nối Milvus
    connections.connect("default", host="milvus-standalone", port="19530")
    collection = Collection("vi_legal_rag")
    collection.load()
    
    # Encode query
    logger.info(f"🔍 Querying: '{query_text}'")
    query_vector = model.encode([query_text], normalize_embeddings=True).tolist()
    
    # Tìm kiếm
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
    results = collection.search(
        data=query_vector,
        anns_field="vector",
        param=search_params,
        limit=top_k,
        output_fields=["title", "text"]
    )
    
    print("\n" + "="*80)
    print(f"KẾT QUẢ TRUY VẤN CHO: '{query_text}'")
    print("="*80)
    
    for i, hit in enumerate(results[0]):
        print(f"\n[{i+1}] Score: {hit.score:.4f}")
        print(f"Tiêu đề: {hit.entity.get('title')}")
        content = hit.entity.get('text')
        # Hiển thị 500 ký tự đầu của nội dung
        print(f"Nội dung: {content[:500]}...")
        print("-" * 40)

if __name__ == "__main__":
    test_query("Quy định về thời giờ làm việc, thời giờ nghỉ ngơi")
