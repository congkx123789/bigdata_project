import os
from pymilvus import connections, Collection, utility

MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")

def check():
    print(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}...")
    try:
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        print("✅ Connected to Milvus.")
        
        collections = utility.list_collections()
        print(f"Collections found: {collections}")
        
        for name in collections:
            col = Collection(name)
            # col.num_entities is an estimate if not flushed, but it's usually fine
            print(f"Collection: {name}")
            print(f" - Entities (approx): {col.num_entities}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check()
