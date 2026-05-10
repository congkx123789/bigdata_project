import os
import sys
import torch
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "vi_legal_rag"
MODEL_NAME = "BAAI/bge-m3"

print("Loading model...")
model = SentenceTransformer(MODEL_NAME, device="cuda" if torch.cuda.is_available() else "cpu")

print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
collection = Collection(COLLECTION_NAME)
collection.load()

query = "Thời gian làm việc của người lao động"
print(f"Searching for: '{query}'")
query_vector = model.encode(query).tolist()
search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

results = collection.search(
    data=[query_vector],
    anns_field="vector",
    param=search_params,
    limit=3,
    output_fields=["title", "text"]
)

for hits in results:
    for hit in hits:
        print(f"\n--- Result (Score: {hit.distance:.4f}) ---")
        print(f"Title: {hit.entity.get('title')}")
        print(f"Content: {hit.entity.get('text')[:200]}...")
