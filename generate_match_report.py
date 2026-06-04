
import json
import requests
import time
import os

URL = 'http://127.0.0.1:8002/internal/inference'

def wait_for_server():
    print("Waiting for RAG Engine to load BGE-M3 model (this can take 1-2 mins)...")
    for i in range(60):
        try:
            r = requests.post(URL, json={'query': 'ping', 'retrieve_only': True}, timeout=2)
            if r.status_code == 200:
                print("RAG Engine is ONLINE!")
                return True
        except:
            pass
        time.sleep(5)
    return False

if not wait_for_server():
    print("Error: RAG Engine failed to start.")
    exit(1)

with open('stress_test_results.json', 'r') as f:
    data = json.load(f)

report = "# BGE-M3 RETRIEVAL DIRECTION REPORT (FINAL)\n\n"
print("Generating report for 100 cases...")

for item in data['results']:
    q = item['question']
    try:
        r = requests.post(URL, json={'query': q, 'retrieve_only': True}, timeout=10)
        sources = r.json().get('sources', [])
        report += f"### {item['id']}. Câu hỏi: {q}\n"
        if sources:
            s = sources[0]
            report += f"- **Đoạn văn khớp nhất**: {s['preview']}...\n"
            report += f"- **Nguồn file**: {s['filename']}\n"
            report += f"- **Độ lệch (Distance)**: {s['score']:.4f}\n\n"
        else:
            report += "- *Không tìm thấy match.*\n\n"
    except Exception as e:
        report += f"### {item['id']}. Câu hỏi: {q} - [LỖI: {str(e)[:50]}]\n\n"

with open('BGE_CHUNK_MATCH_REPORT.md', 'w') as f:
    f.write(report)

print("SUCCESS: Report generated in BGE_CHUNK_MATCH_REPORT.md")
