import requests
import json
import time
import random

def run_stress_test(num_tests=20):
    url = "http://localhost:8003/api/chats/send"
    
    # Load Gold Standard Questions
    try:
        with open("agent_legal_gold_standard_v2.json", "r", encoding="utf-8") as f:
            gold_data = json.load(f)
    except Exception as e:
        print(f"Error loading gold standard: {e}")
        return

    # Extract all questions from the dataset
    all_questions = []
    if isinstance(gold_data, list):
        for item in gold_data:
            if "question" in item:
                all_questions.append(item["question"])
            elif "queries" in item:
                all_questions.extend(item["queries"])
    
    if not all_questions:
        # Fallback common questions if dataset is empty/invalid
        all_questions = [
            "Quy định về thu hồi đất đai?",
            "Mức phạt ngoại tình là bao nhiêu?",
            "Phòng vệ chính đáng là gì?",
            "Lệ phí cấp sổ đỏ lần đầu?",
            "Điều 147 Bộ luật Hình sự 2015?",
            "Tranh chấp đất đai giải quyết ở đâu?",
            "Điều kiện tách thửa đất?",
            "Mức bồi thường khi thu hồi đất nông nghiệp?",
            "Tội giết người do vượt quá giới hạn phòng vệ chính đáng?",
            "Quy trình cấp giấy chứng nhận quyền sử dụng đất?"
        ]

    # Select random questions
    test_questions = random.sample(all_questions, min(num_tests, len(all_questions)))
    
    results = []
    print(f"Starting Stress Test: {len(test_questions)} Questions")
    print("=" * 60)

    report_md = "# BÁO CÁO CHI TIẾT KẾT QUẢ TEST AI\n\n"
    
    for i, q in enumerate(test_questions):
        print(f"[{i+1}/{len(test_questions)}] Query: {q[:50]}...")
        start_time = time.time()
        try:
            payload = {
                "message": q,
                "session_id": f"stress-test-{i}",
                "provider": "local"
            }
            response = requests.post(url, json=payload, timeout=300)
            duration = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                reply = data.get("reply", "")
                citations = data.get("citations", [])
                
                report_md += f"## {i+1}. Câu hỏi: {q}\n"
                report_md += f"**Thời gian phản hồi:** {duration:.2f}s\n\n"
                report_md += f"### Trả lời của AI:\n{reply}\n\n"
                
                if citations:
                    report_md += "### Căn cứ pháp lý (Thẻ nguồn):\n"
                    for c in citations:
                        report_md += f"- **Nguồn:** {c.get('source')}\n"
                        report_md += f"  - **Phân tích:** {c.get('summary') or c.get('legal_analysis')}\n"
                        report_md += f"  - **Nguyên văn:** {c.get('content')[:300]}...\n\n"
                else:
                    report_md += "> *Không tìm thấy trích dẫn trực tiếp từ database cho câu hỏi này.*\n\n"
                
                report_md += "---\n\n"
                
                results.append({
                    "query": q,
                    "status": "PASS",
                    "duration": f"{duration:.2f}s",
                    "citations": len(citations)
                })
                print(f"   Done: {duration:.2f}s")
            else:
                print(f"   Failed: HTTP {response.status_code}")
        except Exception as e:
            print(f"   Error: {str(e)}")

    # Save detailed report
    with open("detailed_test_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    print("\nDetailed report saved to detailed_test_report.md")

    # Final Summary
    print("\n" + "=" * 60)
    print("STRESS TEST SUMMARY")
    print("=" * 60)
    passed = len([r for r in results if r["status"] == "PASS"])
    print(f"Total: {len(results)} | Passed: {passed} | Failed: {len(results) - passed}")
    
    # Save results to artifact
    with open("stress_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nFull results saved to stress_test_results.json")

if __name__ == "__main__":
    run_stress_test(20)
