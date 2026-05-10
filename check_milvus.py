import os
import sys
from pymilvus import connections, Collection, utility

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
COLLECTION_NAME = "vi_legal_rag"

print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
try:
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
    print("✅ Connected to Milvus.")
    
    if utility.has_collection(COLLECTION_NAME):
        collection = Collection(COLLECTION_NAME)
        collection.load()
        print(f"✅ Collection '{COLLECTION_NAME}' exists and is loaded.")
        print(f"   Entities count: {collection.num_entities}")
    else:
        print(f"❌ Collection '{COLLECTION_NAME}' NOT found.")
except Exception as e:
    print(f"❌ Error: {e}")
