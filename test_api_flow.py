
import requests
import json

services = {
    'Core API': 'http://localhost:8001/',
    'RAG Engine': 'http://localhost:8002/internal/inference',
    'Milvus': 'http://localhost:9091/api/v1/health',
    'MinIO': 'http://localhost:9000/minio/health/live',
    'Ollama': 'http://localhost:11434/api/tags'
}

results = {}

print("--- API CONNECTIVITY TEST ---")
for name, url in services.items():
    try:
        if name == 'RAG Engine':
            r = requests.post(url, json={'query': 'ping', 'retrieve_only': True}, timeout=10)
        else:
            r = requests.get(url, timeout=10)
        
        status = "ONLINE" if r.status_code in [200, 204] else f"HTTP {r.status_code}"
        results[name] = status
        print(f"[+] {name:15}: {status}")
    except Exception as e:
        results[name] = "OFFLINE"
        print(f"[-] {name:15}: OFFLINE")

print("\n--- DETAILED FLOW TEST ---")
# Test Full RAG Flow (Embedding + Search)
try:
    r = requests.post(services['RAG Engine'], json={'query': 'Luật đất đai mới nhất là gì?', 'retrieve_only': False}, timeout=30)
    if r.status_code == 200:
        data = r.json()
        print(f"[OK] RAG Engine -> Milvus Search successful.")
        print(f"     Retrieved {len(data.get('sources', []))} legal sources.")
        print(f"     AI response length: {len(data.get('answer', ''))} chars.")
    else:
        print(f"[FAIL] RAG Engine returned {r.status_code}")
except Exception as e:
    print(f"[FAIL] RAG Flow Error: {str(e)[:100]}")
