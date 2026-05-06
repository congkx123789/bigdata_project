
import logging
from agentic_rag.agent import AgenticRAG

# Tắt log hệ thống để tập trung vào câu trả lời
logging.basicConfig(level=logging.ERROR)

def retest_failed_cases():
    agent = AgenticRAG()
    questions = [
        "Mức phạt nồng độ cồn xe máy trên 0.4mg/l là bao nhiêu?",
        "Để làm thừa kế đất đai cần công chứng ở đâu?",
        "Chậm đóng bảo hiểm xã hội 3 tháng bị phạt thế nào?",
        "Tôi muốn kiện hàng xóm vì họ nhìn tôi quá nhiều, luật nào xử lý?",
        "Tôi lỡ trốn thuế thì mức phạt tiền là bao nhiêu?"
    ]
    
    print("🚀 BẮT ĐẦU RE-TEST 5 CÂU HỎI TỪNG LỖI 🚀")
    
    for i, q in enumerate(questions):
        print(f"\n" + "="*50)
        print(f"CASE {i+1}: {q}")
        print("="*50)
        agent.run(q)
        print("-" * 50)

if __name__ == "__main__":
    retest_failed_cases()
