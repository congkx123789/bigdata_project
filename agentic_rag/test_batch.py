
import json
import logging
import os
from agentic_rag.agent import AgenticRAG

# Cấu hình log
logging.basicConfig(level=logging.WARNING)

def run_agent_test():
    # Khởi tạo Agent với bộ não 7B
    agent = AgenticRAG(model_name="qwen2.5:7b")
    
    # Danh sách 5 câu hỏi test đa dạng
    queries = [
        "Mức phạt vi phạm nồng độ cồn cao nhất đối với ô tô là bao nhiêu?",
        "Người lao động có được nghỉ làm vào ngày giỗ Tổ Hùng Vương không?",
        "Trình tự thủ tục xin cấp giấy chứng nhận quyền sử dụng đất lần đầu?",
        "Hành vi bạo lực gia đình bị xử lý như thế nào theo Luật phòng chống bạo lực gia đình?",
        "Quy định về thời gian thử việc tối đa đối với vị trí quản lý doanh nghiệp?"
    ]

    all_results = []

    print(f"🚀 Bắt đầu chạy test {len(queries)} câu hỏi với Agentic RAG Qwen 7B...")
    
    for i, q in enumerate(queries):
        print(f"\n[CASE #{i+1}]: {q}")
        response = agent.run(q)
        
        result_data = {
            "id": i + 1,
            "question": q,
            "agent_response": response if response else "Error: No response",
        }
        all_results.append(result_data)

    # Xuất ra file JSON
    output_file = "agent_test_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({"results": all_results}, f, ensure_ascii=False, indent=4)
    
    print(f"\n✅ Đã hoàn thành! Kết quả được lưu tại: {output_file}")

if __name__ == "__main__":
    run_agent_test()
