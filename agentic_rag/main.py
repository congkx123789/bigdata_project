
import logging
from agentic_rag.agent import AgenticRAG

# Cấu hình log để theo dõi quá trình suy nghĩ của Agent
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # 1. Khởi tạo Agent (Bạn có thể đổi tên model qwen2.5 cho khớp với bản bạn đã tải)
    # Ví dụ: qwen2.5:7b hoặc qwen2.5:14b
    agent = AgenticRAG(model_name="qwen2.5:7b")

    # 2. Query giả lập để test luồng ReAct
    # Câu hỏi này phức tạp, Agent sẽ cần tìm kiếm vài lần để nắm đủ ý
    test_query = "Mức xử phạt nồng độ cồn đối với người điều khiển xe máy và thủ tục nộp phạt như thế nào?"

    print(f"\n🚀 Đang gửi câu hỏi tới Agent: {test_query}\n")
    
    result = agent.run(test_query)

    if result:
        print("✅ Agent đã hoàn thành nhiệm vụ.")
    else:
        print("❌ Agent thất bại trong việc đưa ra câu trả lời.")

if __name__ == "__main__":
    main()
