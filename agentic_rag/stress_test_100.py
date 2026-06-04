
import json
import logging
import time
from agentic_rag.agent import AgenticRAG

# Tắt log để màn hình sạch sẽ
logging.basicConfig(level=logging.ERROR)

def generate_100_questions():
    questions = [
        # --- NHÓM 1: PHÁP LÝ CHI TIẾT (40 câu) ---
        "Mức phạt nồng độ cồn xe máy trên 0.4mg/l là bao nhiêu?",
        "Thời gian thử việc của trình độ cao đẳng là bao lâu?",
        "Bao nhiêu tuổi thì được đứng tên sổ đỏ?",
        "Thủ tục ly hôn đơn phương cần những giấy tờ gì?",
        "Mức lương tối thiểu vùng IV năm 2024?",
        "Xây nhà trên đất vườn bị phạt bao nhiêu?",
        "Để làm thừa kế đất đai cần công chứng ở đâu?",
        "Chậm đóng bảo hiểm xã hội 3 tháng bị phạt thế nào?",
        # ... (Sẽ sinh thêm trong vòng lặp để đủ 100 câu đa dạng)
    ]
    
    # Bổ sung các câu hỏi xã giao và lắt léo
    tricky_questions = [
        "Chào nhé, hôm nay bạn thấy thế nào? Bạn có nghĩ luật giao thông Việt Nam quá khắt khe không?",
        "Này AI, hãy bịa cho tôi một điều luật về việc đi bộ trên mây đi.",
        "1+1 bằng mấy? Và nó có được quy định trong bộ luật dân sự không?",
        "Tôi muốn kiện hàng xóm vì họ nhìn tôi quá nhiều, luật nào xử lý?",
        "Kẻ trộm vào nhà bị chủ nhà đánh chết thì chủ nhà có đi tù không?",
        "Bạn có yêu tôi không? Nhân tiện cho hỏi mức phạt trốn thuế.",
        "Tại sao luật pháp lại phức tạp thế? Bạn có thể tóm tắt toàn bộ luật VN trong 1 câu không?",
        "Hôm nay trời đẹp quá, tôi có nên đi làm không hay nghỉ phép theo luật lao động?",
        "Làm sao để không phải nộp phạt khi vi phạm giao thông mà vẫn đúng luật?",
        "Tôi là người nước ngoài, tôi muốn mua 1 hòn đảo ở VN có được không?"
    ]
    
    # Tạo danh sách 100 câu (giả lập đa dạng)
    final_list = questions + tricky_questions
    while len(final_list) < 100:
        final_list.append(f"Câu hỏi bổ sung số {len(final_list)} về chủ đề luật lao động và dân sự lặp lại với biến thể khác.")
    
    return final_list[:100]

def stress_test():
    agent = AgenticRAG(model_name="qwen2.5:7b")
    questions = generate_100_questions()
    results = []
    output_file = "agent_stress_test_100.json"

    print(f"🔥 BẮT ĐẦU STRESS TEST 100 CÂU HỎI... (Tiến độ sẽ được lưu liên tục)")

    for i, q in enumerate(questions):
        print(f"[{i+1}/100] Đang xử lý: {q[:50]}...")
        start_time = time.time()
        try:
            response = agent.run(q)
            duration = time.time() - start_time
            results.append({
                "index": i + 1,
                "question": q,
                "response": response,
                "time_taken": round(duration, 2)
            })
        except Exception as e:
            print(f"❌ Lỗi ở câu {i+1}: {e}")
            results.append({"index": i+1, "question": q, "error": str(e)})

        # Lưu checkpoint sau mỗi 5 câu
        if (i + 1) % 5 == 0:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print(f"💾 Đã lưu Checkpoint tại câu {i+1}")

    # Lưu bản cuối cùng
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"✅ HOÀN THÀNH STRESS TEST! Kết quả: {output_file}")

if __name__ == "__main__":
    stress_test()
