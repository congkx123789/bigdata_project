
from agentic_rag.agent import AgenticRAG
import logging

logging.basicConfig(level=logging.INFO)

def test_hallucination():
    agent = AgenticRAG()
    test_queries = [
        "Hành vi bỏ trốn sau khi gây tai nạn đường thủy xử lý thế nào?",
        "Mức phạt khi sử dụng chất cấm tại quán bar?",
        "Công ty bắt nhân viên nữ cam kết 2 năm không sinh con xử lý thế nào?"
    ]
    
    for q in test_queries:
        print(f"\n❓ CÂU HỎI: {q}")
        res = agent.run(q)
        print(f"✅ TRẢ LỜI: {res['summary']}")
        print("-" * 50)

if __name__ == "__main__":
    test_hallucination()
