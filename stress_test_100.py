
import requests
import json
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stress_test")

API_URL = "http://localhost:8002/internal/inference"

# 100 sample legal questions
questions = [
    "Quy hoạch sử dụng đất là gì?",
    "Thủ tục cấp sổ đỏ lần đầu như thế nào?",
    "Mức xử phạt vi phạm nồng độ cồn khi lái xe là bao nhiêu?",
    "Thế nào là hành vi chống người thi hành công vụ?",
    "Quy định về thời giờ làm việc và thời giờ nghỉ ngơi của người lao động?",
    "Điều kiện để được hưởng trợ cấp thất nghiệp?",
    "Thủ tục thành lập công ty TNHH một thành viên?",
    "Mức vốn tối thiểu để thành lập ngân hàng là bao nhiêu?",
    "Quy định về bảo hiểm y tế bắt buộc đối với học sinh, sinh viên?",
    "Thế nào là hành vi bạo lực gia đình?",
    "Quy định về tội lừa đảo chiếm đoạt tài sản?",
    "Thủ tục ly hôn đơn phương cần những giấy tờ gì?",
    "Quyền và nghĩa vụ của cha mẹ đối với con sau khi ly hôn?",
    "Quy định về thừa kế theo di chúc?",
    "Di chúc hợp pháp cần có những điều kiện gì?",
    "Mức hưởng lương hưu đối với người lao động đóng bảo hiểm xã hội bắt buộc?",
    "Thủ tục đăng ký tạm trú, tạm vắng?",
    "Quy định về bảo vệ môi trường trong hoạt động sản xuất kinh doanh?",
    "Mức phạt đối với hành vi xả thải trái phép ra môi trường?",
    "Thế nào là hành vi cạnh tranh không lành mạnh?",
    "Quy định về sở hữu trí tuệ đối với tác phẩm văn học?",
    "Thủ tục đăng ký bản quyền tác giả?",
    "Quy định về an toàn thực phẩm trong các bếp ăn tập thể?",
    "Mức phạt đối với hành vi bán hàng giả, hàng nhái?",
    "Thế nào là hành vi vi phạm trật tự an toàn giao thông?",
    "Quy định về việc sử dụng pháo hoa trong các dịp lễ tết?",
    "Thủ tục đăng ký kết hôn với người nước ngoài?",
    "Quy định về quyền sở hữu đất đai tại Việt Nam?",
    "Thế nào là tranh chấp đất đai?",
    "Thủ tục hòa giải tranh chấp đất đai tại cơ sở?",
    "Quy định về việc bồi thường khi nhà nước thu hồi đất?",
    "Mức giá đền bù đất nông nghiệp khi thu hồi là bao nhiêu?",
    "Quy định về việc chuyển đổi mục đích sử dụng đất?",
    "Thủ tục tách thửa đất cần những điều kiện gì?",
    "Quy định về việc xây dựng nhà ở trên đất nông nghiệp?",
    "Thế nào là hành vi xây dựng trái phép?",
    "Mức xử phạt đối với hành vi xây dựng không phép?",
    "Quy định về việc phòng cháy và chữa cháy tại các tòa chung cư?",
    "Trách nhiệm của chủ đầu tư trong việc quản lý vận hành chung cư?",
    "Thủ tục cấp giấy phép xây dựng nhà ở riêng lẻ?",
    "Quy định về việc ký kết hợp đồng lao động?",
    "Thế nào là đơn phương chấm dứt hợp đồng lao động trái pháp luật?",
    "Mức bồi thường khi người sử dụng lao động chấm dứt hợp đồng trái luật?",
    "Quy định về bảo hiểm xã hội tự nguyện?",
    "Thủ tục chốt sổ bảo hiểm xã hội khi nghỉ việc?",
    "Quyền lợi của lao động nữ khi nghỉ thai sản?",
    "Quy định về việc tuyển dụng người lao động dưới 15 tuổi?",
    "Thế nào là hành vi xâm phạm danh dự, nhân phẩm người khác?",
    "Quy định về mức bồi thường thiệt hại ngoài hợp đồng?",
    "Thủ tục khi khiếu nại, tố cáo đối với hành vi hành chính trái pháp luật?",
    "Thời hạn giải quyết khiếu nại lần đầu là bao lâu?",
    "Quy định về việc xử phạt hành chính đối với hành vi lấn chiếm vỉa hè?",
    "Thế nào là hành vi gây rối trật tự công cộng?",
    "Quy định về việc sử dụng lòng đường để kinh doanh trái phép?",
    "Thủ tục xin cấp giấy phép kinh doanh karaoke?",
    "Quy định về giờ giấc hoạt động của các quán bar, vũ trường?",
    "Thế nào là hành vi đánh bạc trái phép?",
    "Mức xử phạt đối với hành vi tổ chức đánh bạc?",
    "Quy định về việc quảng cáo thuốc lá và rượu bia?",
    "Thế nào là hành vi trốn thuế?",
    "Mức phạt đối với hành vi không nộp tờ khai thuế đúng hạn?",
    "Quy định về các loại thuế đối với hộ kinh doanh cá thể?",
    "Thủ tục giải thể doanh nghiệp cần những bước nào?",
    "Quy định về việc phá sản doanh nghiệp?",
    "Thế nào là hành vi vi phạm đạo đức nghề nghiệp luật sư?",
    "Quy định về việc miễn phí trợ giúp pháp lý cho người nghèo?",
    "Thủ tục xin cấp hộ chiếu phổ thông?",
    "Quy định về việc xuất cảnh, nhập cảnh đối với công dân Việt Nam?",
    "Thế nào là hành vi mua bán người?",
    "Quy định về việc xử lý tội phạm ma túy?",
    "Mức phạt đối với hành vi tàng trữ trái phép chất ma túy?",
    "Quy định về việc đi nghĩa vụ quân sự?",
    "Đối tượng nào được hoãn hoặc miễn gọi nhập ngũ?",
    "Thủ tục xin cấp giấy xác nhận tình trạng hôn nhân?",
    "Quy định về việc đặt tên cho con?",
    "Thế nào là hành vi thay đổi họ tên trái quy định?",
    "Quy định về việc đăng ký khai sinh quá hạn?",
    "Thủ tục nhận cha con theo quy định pháp luật dân sự?",
    "Quy định về việc giám hộ đối với người mất năng lực hành vi dân sự?",
    "Thế nào là giao dịch dân sự vô hiệu?",
    "Quy định về việc cầm cố, thế chấp tài sản?",
    "Sự khác nhau giữa đặt cọc và ký cược?",
    "Quy định về việc bảo lãnh trong giao dịch dân sự?",
    "Mức lãi suất tối đa trong hợp đồng vay tài sản giữa cá nhân?",
    "Thế nào là hành vi cho vay nặng lãi?",
    "Quy định về việc đòi nợ thuê trái phép?",
    "Thủ tục khởi kiện tại tòa án dân sự?",
    "Án phí dân sự được tính như thế nào?",
    "Thi hành án dân sự cần những điều kiện gì?",
    "Quy định về việc tạm đình chỉ giải quyết vụ án dân sự?",
    "Thế nào là hành vi vi phạm tố tụng?",
    "Quyền của bị can, bị cáo trong vụ án hình sự?",
    "Vai trò của luật sư bào chữa trong giai đoạn điều tra?",
    "Quy định về việc tạm giam, tạm giữ người phạm tội?",
    "Thời hạn tạm giam đối với tội phạm nghiêm trọng là bao lâu?",
    "Thế nào là tình tiết giảm nhẹ trách nhiệm hình sự?",
    "Quy định về việc xóa án tích?",
    "Điều kiện để được hưởng án treo?",
    "Quy định về việc ân xá cho phạm nhân vào ngày lễ lớn?",
    "Thủ tục xin cấp lý lịch tư pháp?"
]

def run_test():
    results = []
    print(f"Starting Stress Test with {len(questions)} questions...\n")
    
    start_time_total = time.time()
    
    for i, q in enumerate(questions):
        logger.info(f"[{i+1}/{len(questions)}] Processing: {q}")
        start_time = time.time()
        
        try:
            # We use retrieve_only=False to test full LLM response
            response = requests.post(API_URL, json={"query": q, "retrieve_only": False}, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                results.append({
                    "id": i + 1,
                    "question": q,
                    "answer": data.get("answer", ""),
                    "source_count": len(data.get("sources", [])),
                    "latency": round(elapsed, 2),
                    "status": "SUCCESS"
                })
                print(f" - Done in {round(elapsed, 2)}s, Sources: {len(data.get('sources', []))}")
            else:
                results.append({
                    "id": i + 1,
                    "question": q,
                    "status": "ERROR",
                    "error_code": response.status_code
                })
                print(f" - Failed with error {response.status_code}")
        except Exception as e:
            results.append({
                "id": i + 1,
                "question": q,
                "status": "EXCEPTION",
                "error": str(e)
            })
            print(f" - Exception: {str(e)}")
            
    total_time = time.time() - start_time_total
    
    success_count = len([r for r in results if r['status'] == "SUCCESS"])
    total_latency = sum([r.get('latency', 0) for r in results if r['status'] == "SUCCESS"])
    avg_latency = total_latency / success_count if success_count > 0 else 0
    
    summary = {
        "total_questions": len(questions),
        "success": success_count,
        "avg_latency_sec": round(avg_latency, 2),
        "total_time_sec": round(total_time, 2)
    }
    
    with open("stress_test_results.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=4)
        
    print("\n" + "="*50)
    print("STRESS TEST SUMMARY")
    print(f"Total Questions: {len(questions)}")
    print(f"Success: {success_count}")
    print(f"Avg Latency: {round(avg_latency, 2)}s/question")
    print(f"Total Time: {round(total_time/60, 2)} minutes")
    print("="*50)
    print("Results saved to stress_test_results.json")

if __name__ == "__main__":
    run_test()
