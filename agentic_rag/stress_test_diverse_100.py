
import json
import time
import logging
from agentic_rag.agent import AgenticRAG

# Cấu hình log
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("StressTest")

def run_diverse_stress_test():
    agent = AgenticRAG()
    
    # 100 câu hỏi đa dạng các lĩnh vực
    questions = [
        "Ngoại tình có bị đi tù không?",
        "Thủ tục cấp sổ đỏ lần đầu cần bao nhiêu tiền?",
        "Bị sếp nợ lương 2 tháng thì kiện ở đâu?",
        "Đâm người để tự vệ có bị đi tù không?",
        "Mức phạt cao nhất khi lạng lách đánh võng xe máy?",
        "Lừa đảo qua mạng 2 triệu đồng có bị khởi tố hình sự?",
        "Chồng có quyền đòi lại quà sau khi ly hôn không?",
        "Đất không có giấy tờ có được đền bù khi nhà nước thu hồi?",
        "Mang hộ hàng cấm trong sân bay bị xử lý thế nào?",
        "Xúc phạm danh dự người khác trên Facebook phạt bao nhiêu?",
        "Bao nhiêu tuổi được phép làm di chúc?",
        "Đặt cọc mua đất bằng giấy viết tay có hợp pháp không?",
        "Người lao động tự ý nghỉ việc 5 ngày liên tục có bị sa thải?",
        "Lương 15 triệu/tháng phải nộp bao nhiêu thuế TNCN?",
        "Bị CSGT thu bằng lái 12 tháng có được lái xe không?",
        "Cha mẹ có quyền xem tin nhắn điện thoại của con không?",
        "Mượn tiền không trả giá trị bao nhiêu thì bị khởi tố?",
        "Xây dựng ban công lấn ra lề đường bị phạt thế nào?",
        "Công ty không đóng bảo hiểm cho nhân viên đòi quyền lợi ở đâu?",
        "Chống người thi hành công vụ bị phạt bao nhiêu năm tù?",
        "Kẻ trộm bị chó nhà cắn chết thì chủ nhà có bồi thường không?",
        "Mua hàng online bị lừa thì báo công an phường hay quận?",
        "Trình độ đại học được hoãn nghĩa vụ quân sự đến bao nhiêu tuổi?",
        "Tiền phúng viếng đám tang là tài sản chung hay riêng của vợ chồng?",
        "Mức phạt nồng độ cồn xe đạp là bao nhiêu?",
        "Sử dụng bằng lái xe giả bị phạt bao nhiêu tiền?",
        "Công ty bắt nhân viên làm thêm 100 giờ/tháng có đúng luật?",
        "Thủ tục đổi tên trong giấy khai sinh cho người trên 18 tuổi?",
        "Tự ý mở cổng sang đất nhà hàng xóm có vi phạm?",
        "Hành vi nhìn lén phụ nữ tắm bị xử lý thế nào?",
        "Mức phạt khi không mang theo căn cước công dân?",
        "Kinh doanh karaoke quá 12h đêm bị phạt thế nào?",
        "Cho vay nặng lãi bao nhiêu % thì bị coi là tội phạm?",
        "Hành vi tạt axit người khác bị xử bao nhiêu năm tù?",
        "Di chúc bằng miệng có giá trị pháp lý không?",
        "Vợ tự ý bán đất cấp cho hộ gia đình có được không?",
        "Mức phạt khi đi ngược chiều trên đường cao tốc?",
        "Trốn thuế bao nhiêu tiền thì bị đi tù?",
        "Nhặt được tiền tỷ không trả lại có bị đi tù?",
        "Chủ nhà trọ tự ý vào phòng người thuê có vi phạm?",
        "Nuôi chó dữ cắn người lòi xương bị xử lý thế nào?",
        "Mức lương tối thiểu vùng I năm 2024 là bao nhiêu?",
        "Người bị tâm thần giết người có bị đi tù không?",
        "Hành vi đánh ghen lột đồ giữa đường phạm tội gì?",
        "Bố mẹ có được quyền đánh con để giáo dục không?",
        "Bán hàng giả nhãn hiệu nổi tiếng phạt bao nhiêu?",
        "Hành vi rải đinh trên đường có bị khởi tố?",
        "Thủ tục mua súng săn hợp pháp tại Việt Nam?",
        "Đi làm ngày lễ quốc khánh lương tính thế nào?",
        "Hợp đồng thuê nhà 1 năm không công chứng có giá trị?",
        "Gây tai nạn giao thông rồi bỏ chạy bị phạt thế nào?",
        "Uống rượu bia lái xe điện có bị phạt nồng độ cồn?",
        "Công nhân đình công tự phát có bị sa thải không?",
        "Mức phạt khi đăng thông tin sai sự thật về dịch bệnh?",
        "Ly hôn khi vợ đang mang thai chồng có quyền yêu cầu?",
        "Cây nhà hàng xóm đổ vào nhà mình gây hư hỏng ai đền?",
        "Sản xuất rượu thủ công tại nhà mang bán có phải xin phép?",
        "Quay phim CSGT đang làm nhiệm vụ có bị cấm?",
        "Bị công an giữ xe quá hạn tạm giữ làm thế nào lấy lại?",
        "Hành vi 'boom' hàng online có bị phạt hành chính?",
        "Chủ nợ tự ý vào nhà con nợ lấy tài sản là đúng hay sai?",
        "Mức phạt nộp chậm thuế môn bài?",
        "Xăm hình lên mặt có được đi nghĩa vụ quân sự?",
        "Dùng kích điện bắt cá có bị đi tù?",
        "Thay đổi màu sơn xe máy khác cà vẹt phạt bao nhiêu?",
        "Nhân viên văn phòng đi làm muộn 30 phút bị trừ 500k lương có đúng?",
        "Hành vi rủ rê người khác chơi cờ bạc ăn tiền xử lý thế nào?",
        "Thủ tục mở văn phòng luật sư cần những gì?",
        "Uống rượu ở quán bar rồi bị bảo vệ đánh bồi thường thế nào?",
        "Đăng ảnh người khác lên mạng làm ảnh chế (meme) có vi phạm?",
        "Bán đất đang tranh chấp bị xử lý thế nào?",
        "Mức phạt khi chở quá số người quy định trên xe ô tô 5 chỗ?",
        "Tự ý phá rào chắn đường sắt bị phạt bao nhiêu?",
        "Dùng tiền giả mệnh giá 500k để mua hàng xử lý thế nào?",
        "Vợ chồng đã ly thân có được tự ý mua nhà riêng?",
        "Cố tình không cứu người đang trong tình trạng nguy hiểm?",
        "Hành vi treo cờ nước ngoài tại nhà riêng có phải xin phép?",
        "Mức phạt khi gây tiếng ồn lớn sau 10 giờ đêm?",
        "Thủ tục đăng ký kết hôn với người nước ngoài tại Việt Nam?",
        "Hành vi bạo lực ngôn ngữ với vợ/chồng có bị phạt?",
        "Trẻ em bao nhiêu tuổi có thể tự đi làm thêm?",
        "Mua xe cũ không sang tên đổi chủ bị phạt bao nhiêu?",
        "Lấn chiếm vỉa hè để kinh doanh trà đá phạt bao nhiêu?",
        "Hành vi tàng trữ pháo nổ ngày Tết bị xử lý ra sao?",
        "Tự ý chặt cây xanh trước cửa nhà mình có bị phạt?",
        "Phạt bao nhiêu tiền nếu không đeo khẩu trang nơi công cộng?",
        "Tham gia biểu tình trái phép bị xử lý thế nào?",
        "Hành vi gửi tin nhắn đe dọa người khác phạm tội gì?",
        "Quyền của người lao động khi công ty bị giải thể?",
        "Thủ tục xin cấp lại bằng lái xe bị mất?",
        "Mức phạt khi bỏ rác không đúng nơi quy định?",
        "Hành vi ngược đãi, hành hạ ông bà cha mẹ xử lý thế nào?",
        "Mức phạt khi không thắt dây an toàn trên xe ô tô?",
        "Sử dụng loa kẹo kéo hát karaoke gây ồn ào xử lý thế nào?",
        "Công ty bắt nhân viên nữ cam kết 2 năm không sinh con?",
        "Lương tháng 13 có phải là bắt buộc theo luật không?",
        "Hành vi bỏ trốn sau khi gây tai nạn đường thủy?",
        "Mức phạt khi sử dụng chất cấm tại quán bar?",
        "Cha mẹ có được định đoạt tiền lì xì của con?",
        "Hành vi đốt rác gây khói bụi mù mịt sang nhà hàng xóm?"
    ]

    results = []
    checkpoint_file = "agent_legal_gold_standard_v2.json"
    
    # Load checkpoint if exists
    try:
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
            start_index = len(results)
            print(f"🔄 Tiếp tục từ câu {start_index + 1}")
    except:
        start_index = 0

    for i in range(start_index, len(questions)):
        q = questions[i]
        print(f"[{i+1}/100] Đang xử lý: {q[:50]}...")
        
        start_time = time.time()
        try:
            res = agent.run(q)
            elapsed = time.time() - start_time
            
            results.append({
                "index": i + 1,
                "question": q,
                "response": res,
                "time_taken": round(elapsed, 2)
            })
            
            # Lưu mỗi 5 câu để an toàn
            if (i + 1) % 5 == 0:
                with open(checkpoint_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)
                print(f"💾 Đã lưu Checkpoint tại câu {i+1}")
                
        except Exception as e:
            logger.error(f"Lỗi tại câu {i+1}: {e}")
            continue

    # Lưu kết quả cuối cùng
    with open(checkpoint_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"✅ HOÀN THÀNH STRESS TEST ĐA DẠNG! Kết quả: {checkpoint_file}")

if __name__ == "__main__":
    run_diverse_stress_test()
