
# Schema cho các Tool của Agent (OpenAI Format)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Tìm kiếm tài liệu pháp lý. Nếu tìm kiếm lần đầu không thấy, hãy thử lại với các từ khóa đồng nghĩa hoặc thuật ngữ chuyên môn khác (ví dụ: 'đánh người' -> 'cố ý gây thương tích'). Bạn có thể gọi tool này nhiều lần.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Câu truy vấn cụ thể để tìm thông tin.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cite_and_answer",
            "description": "Trả lời câu hỏi dựa trên các đoạn trích dẫn từ database và cung cấp nguyên văn trích dẫn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Câu trả lời chi tiết, mạch lạc, đầy đủ các phần: Giải đáp, Quy định, Mức phạt và Lời khuyên. Sử dụng Markdown để trình bày đẹp mắt."
                    },
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "chunk_id": {"type": "string"},
                                "legal_analysis": {"type": "string", "description": "Phân tích pháp lý chuyên sâu về đoạn trích này: Giải thích tại sao đoạn này lại liên quan đến câu hỏi của người dùng, các quy định cụ thể trong này áp dụng thế nào cho trường hợp của họ. Phải viết dài và chi tiết (ít nhất 3-5 câu)."},
                                "content": {"type": "string", "description": "Nguyên văn đoạn văn bản trích dẫn từ database."},
                                "source": {"type": "string", "description": "Tên văn bản hoặc nguồn của đoạn trích dẫn (ví dụ: 'Điều 202 Bộ luật Hình sự 2015')."}
                            }
                        },
                        "description": "Danh sách các đoạn trích dẫn nguyên văn dùng để trả lời."
                    }
                },
                "required": ["summary", "citations"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_context",
            "description": "Lấy thêm nội dung xung quanh một đoạn trích dẫn (Deep Extraction). Dùng khi bạn thấy một Điều luật nhưng nó bị cắt ngang hoặc bạn muốn xem các Khoản/Điểm tiếp theo của Điều đó.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {
                        "type": "string",
                        "description": "ID của đoạn trích dẫn cần mở rộng (lấy từ kết quả search_database)."
                    },
                    "window": {
                        "type": "integer",
                        "description": "Số lượng đoạn văn bản muốn lấy thêm phía trước và phía sau (mặc định là 2).",
                        "default": 2
                    }
                },
                "required": ["chunk_id"]
            }
        }
    }
]
