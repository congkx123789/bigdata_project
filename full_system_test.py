
import requests
import time
import json

BASE_URL = "http://localhost:8001"
RAG_URL = "http://localhost:8002/internal/inference"

def test_section(name):
    print(f"\n{'='*20} TESTING: {name} {'='*20}")

def run_all_tests():
    # 1. Basic Health
    test_section("Infrastructure Connectivity")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"[OK] Core API: {r.json()['status']}")
    except: print("[FAIL] Core API unreachable")

    # 2. AI Retrieval & Knowledge Quality
    test_section("RAG Knowledge Retrieval")
    query = "Mức xử phạt tội trốn thuế là bao nhiêu?"
    r = requests.post(RAG_URL, json={"query": query, "retrieve_only": True})
    if r.status_code == 200:
        sources = r.json().get("sources", [])
        print(f"[OK] Found {len(sources)} sources for trốn thuế.")
        for i, s in enumerate(sources[:2]):
            print(f"     Source {i+1}: {s['filename']} (Score: {s['score']:.4f})")
    else: print("[FAIL] RAG Retrieval failed")

    # 3. Heavy Inference (LLM + GPU)
    test_section("Full AI Inference (LLM Synthesis)")
    print("Asking AI a complex legal question (this tests GPU/VRAM)...")
    start = time.time()
    try:
        r = requests.post(RAG_URL, json={"query": "Tóm tắt các quy định về xử lý tội phạm ma túy", "retrieve_only": False}, timeout=60)
        elapsed = time.time() - start
        if r.status_code == 200:
            print(f"[OK] AI responded in {elapsed:.2f}s")
            print(f"     Answer Snippet: {r.json().get('answer', '')[:150]}...")
        else: print(f"[FAIL] LLM inference error {r.status_code}")
    except Exception as e: print(f"[FAIL] LLM Timeout or Crash: {e}")

    # 4. Anti-Crash Semaphore Check
    test_section("Anti-Crash / High Load Simulation")
    print("Testing 5 parallel heavy requests (Semaphore check)...")
    import threading
    def worker(i):
        r = requests.post(RAG_URL, json={"query": f"Q{i}", "retrieve_only": False}, timeout=30)
        print(f"     Worker {i} finished: {r.status_code}")
    
    threads = []
    for i in range(5):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    for t in threads: t.join()
    print("[OK] Concurrency test finished safely.")

if __name__ == "__main__":
    run_all_tests()
