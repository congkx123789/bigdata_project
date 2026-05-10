import json
import os
import torch
import time
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, utility

def evaluate_accuracy(sample_size=20):
    # Load gold standard
    with open("agent_legal_gold_standard_v2.json", "r") as f:
        gold_data = json.load(f)
    
    # Filter only samples with citations
    test_samples = [s for s in gold_data if s.get("response", {}).get("citations")]
    test_samples = test_samples[:sample_size]
    
    # Setup model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    if device == "cuda" and torch.cuda.is_bf16_supported():
        model = model.to(dtype=torch.bfloat16)
    
    # Connect Milvus
    connections.connect("default", host="localhost", port="19530")
    collection = Collection("vi_legal_rag")
    collection.load()
    
    hits = 0
    total = len(test_samples)
    
    print(f"📊 Evaluating BGE-M3 Accuracy on {total} samples...")
    
    for i, sample in enumerate(test_samples):
        query = sample["question"]
        # Extract document IDs from expected citations (e.g., "vi-legal:6157")
        expected_doc_ids = set()
        for c in sample["response"]["citations"]:
            cid = c["chunk_id"]
            if ":" in cid and "#" in cid:
                doc_id = cid.split("#")[0] # Gets "vi-legal:6157"
                expected_doc_ids.add(doc_id)
        
        # Search Top 10
        query_vec = model.encode([query], normalize_embeddings=True).tolist()
        results = collection.search(
            data=query_vec,
            anns_field="vector",
            param={"metric_type": "L2", "params": {"nprobe": 10}},
            limit=10,
            output_fields=["filename"]
        )
        
        # Extract document IDs from retrieved filenames (e.g., "vi-legal:4260")
        retrieved_doc_ids = set()
        for hit in results[0]:
            fname = hit.entity.get("filename")
            if fname and "#" in fname:
                doc_id = fname.split("#")[0]
                retrieved_doc_ids.add(doc_id)
        
        # Check if any expected Doc ID is in retrieved Doc IDs
        found = any(did in retrieved_doc_ids for did in expected_doc_ids)
        if found:
            hits += 1
            status = "✅ MATCH"
        else:
            status = "❌ MISS"
            
        print(f"[{i+1}/{total}] Query: {query[:50]}... -> {status}")
        if not found:
            print(f"   Expected Doc IDs: {list(expected_doc_ids)}")
            print(f"   Top Retrieved: {list(retrieved_doc_ids)[:3]}")

    accuracy = (hits / total) * 100
    print("\n" + "="*30)
    print(f"🎯 FINAL RECALL@10: {accuracy:.2f}%")
    print("="*30)

if __name__ == "__main__":
    evaluate_accuracy(20)
