import sys
import os
import json

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agentic_rag.vector_store import VectorStore

def test_bge():
    try:
        # Initialize VectorStore (will connect to Milvus at milvus-standalone:19530)
        vs = VectorStore(host="milvus-standalone", port="19530")
        
        query = "Mức lương tối thiểu vùng năm 2024"
        print(f"--- TESTING BGE-M3 RETRIEVAL ---")
        print(f"Query: {query}\n")
        
        results = vs.search(query, k=5)
        
        for i, res in enumerate(results):
            print(f"Result #{i+1}:")
            print(f"  - Title: {res['title']}")
            print(f"  - Type: {res['type']}")
            print(f"  - Score: {res['score']:.4f}")
            print(f"  - Content Preview: {res['content'][:200]}...")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_bge()
