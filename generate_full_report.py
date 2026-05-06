
import json
import requests
import time
import os

URL = 'http://127.0.0.1:8002/internal/inference'

def wait_for_server():
    print("Waiting for RAG Engine...")
    for i in range(30):
        try:
            r = requests.post(URL, json={'query': 'ping', 'retrieve_only': True}, timeout=2)
            if r.status_code == 200:
                print("RAG Engine is ONLINE!")
                return True
        except:
            pass
        time.sleep(2)
    return False

if not wait_for_server():
    print("Error: RAG Engine failed to start.")
    exit(1)

with open('stress_test_results.json', 'r') as f:
    data = json.load(f)

report = "# BGE-M3 FULL CHUNK RETRIEVAL REPORT (100 CASES)\n\n"
report += "Báo cáo này hiển thị TOÀN BỘ nội dung đoạn văn bản khớp cho 100 câu hỏi.\n\n"

print("Generating FULL report for 100 cases...")
for item in data['results']:
    q = item['question']
    try:
        r = requests.post(URL, json={'query': q, 'retrieve_only': True}, timeout=15)
        sources = r.json().get('sources', [])
        report += f"### {item['id']}. Câu hỏi: {q}\n"
        if sources:
            s = sources[0]
            # USING FULL 'text' FIELD INSTEAD OF PREVIEW
            full_text = s.get('text', s.get('preview', 'No text found'))
            report += f"- **Nội dung đầy đủ (Full Chunk)**:\n\n{full_text}\n\n"
            report += f"- **Nguồn file**: {s['filename']}\n"
            report += f"- **Độ khớp (Score)**: {s['score']:.4f}\n"
            report += f"\n" + "-"*30 + "\n\n"
        else:
            report += "- *Không tìm thấy đoạn văn nào khớp.*\n\n"
    except Exception as e:
        report += f"### {item['id']}. Câu hỏi: {q} - [LỖI: {str(e)[:50]}]\n\n"

with open('BGE_FULL_CHUNK_AUDIT.md', 'w') as f:
    f.write(report)

print("SUCCESS: Full report written to BGE_FULL_CHUNK_AUDIT.md")
