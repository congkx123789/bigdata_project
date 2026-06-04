import json
import re
import logging
from openai import OpenAI
from typing import Dict, List, Any
from agentic_rag.vector_store import VectorStore
from agentic_rag.tools import TOOLS

logger = logging.getLogger("AgentCore")

class AgenticRAG:
    def __init__(self, model_name="legal-rag-finetuned", base_url="http://localhost:11434/v1"):
        self.client = OpenAI(base_url=base_url, api_key="ollama")
        self.model = model_name
        self.vector_store = VectorStore()
        
        self.system_prompt = """# SYSTEM PROMPT V15: TRỢ LÝ PHÁP LÝ THÔNG MINH (CONSULTATIVE MODE)
Bạn là Chuyên gia Pháp lý Việt Nam cao cấp. Nhiệm vụ của bạn là tra cứu và tư vấn các vấn đề pháp luật một cách tận tâm, dễ hiểu và chuyên nghiệp.

# NGUYÊN TẮC HOẠT ĐỘNG:
1. **LUÔN LUÔN HỖ TRỢ**: Tuyệt đối không trả lời ngắn gọn "không biết" hoặc "không có thông tin". Nếu không tìm thấy Điều luật cụ thể, hãy cung cấp nguyên tắc chung, hướng dẫn quy trình hoặc các bước cần thực hiện.
2. **TRUY VẤN ĐA CHIỀU**: Sử dụng các từ khóa đồng nghĩa, thuật ngữ tương đương để tìm kiếm (ví dụ: "đánh người" -> "cố ý gây thương tích").
3. **PHONG CÁCH TƯ VẤN**: Trả lời dưới dạng một bài tư vấn pháp lý hoàn chỉnh, có đầu có đuôi, ngôn ngữ nhuần nhuyễn, gần gũi nhưng vẫn đảm bảo tính pháp lý.
4. **CĂN CỨ PHÁP LÝ**: Luôn trích dẫn chính xác Tên văn bản, Điều, Khoản. Sử dụng tool `cite_and_answer` hoặc trích dẫn trực tiếp trong Summary.

# ĐỊNH DẠNG PHẢN HỒI:
- Bố cục mạch lạc: Tóm tắt giải đáp -> Phân tích chi tiết -> Mức xử phạt/Hệ quả -> Lời khuyên & Kết luận.
- Sử dụng Markdown để làm nổi bật các con số (tiền phạt, số năm tù)."""
        self.chat_history = [{"role": "system", "content": self.system_prompt}]

    def _clean_text(self, text: str) -> str:
        """Loại bỏ tiếng Trung và làm sạch văn bản."""
        text = re.sub(r'[\u4e00-\u9fff]+', '', text)
        return text.strip()

    def _parse_fallback_content(self, text: str) -> Dict:
        """Bóc tách text thô cực kỳ mạnh mẽ."""
        text = self._clean_text(text)
        citations = []
        
        json_blocks = re.findall(r'\{.*?"citations":.*?\}.*?\}', text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data.get("citations"), list):
                    citations.extend(data["citations"])
            except: continue

        if not citations:
            lines = text.split("\n")
            for i, line in enumerate(lines):
                if re.search(r'(Điều \d+|Luật|Nghị định|Thông tư)', line, re.IGNORECASE):
                    if len(line.strip()) > 30:
                        citations.append({
                            "chunk_id": f"auto-{i}",
                            "source": re.search(r'(Điều \d+|Luật \w+|Nghị định \d+|Thông tư \d+)', line, re.IGNORECASE).group(0) if re.search(r'(Điều \d+|Luật \w+|Nghị định \d+|Thông tư \d+)', line, re.IGNORECASE) else "Căn cứ pháp lý",
                            "legal_analysis": "Trích dẫn tự động từ câu trả lời.",
                            "content": line.strip()
                        })

        summary = re.sub(r'(?s)```json.*?```', '', text)
        summary = re.sub(r'(?s)\{.*?"citations":.*?\}.*?\}', '', summary)
        summary = re.sub(r'(?s)cite_and_answer\(.*?\)', '', summary)
        
        return {
            "summary": summary if len(summary) > 20 else "Dưới đây là các căn cứ pháp lý chi tiết:",
            "citations": citations
        }

    def _force_verbatim_content(self, citations: List[Dict]) -> List[Dict]:
        """Khôi phục nội dung BẢN GỐC từ lịch sử Tool calls."""
        db_text = ""
        for msg in self.chat_history:
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", "")
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if role == "tool" and "Dữ liệu database:" in str(content):
                db_text += str(content) + "\n"

        for c in citations:
            chunk_id = c.get("chunk_id", "")
            if chunk_id and not c.get("content"):
                match = re.search(rf"- ID: {re.escape(chunk_id)}\s*\n\s*NỘI DUNG: (.*?)(?=\n- ID: |$)", db_text, re.DOTALL)
                if match:
                    c["content"] = match.group(1).strip()
        return citations

    def _force_verbatim_content_direct(self, citations: List[Dict], results: List[Dict]) -> List[Dict]:
        """Khôi phục nội dung BẢN GỐC trực tiếp từ kết quả search."""
        for c in citations:
            chunk_id = c.get("chunk_id", "")
            if chunk_id:
                for r in results:
                    if r["chunk_id"] == chunk_id:
                        c["content"] = r["content"]
                        break
        return citations

    def run(self, user_query: str) -> Dict:
        self.chat_history = [{"role": "system", "content": self.system_prompt}]
        
        # --- CHIẾN LƯỢC 1: ZERO-SHOT RAG CHO MODEL FINE-TUNED ---
        if "finetuned" in self.model:
            logger.info(f"Using Zero-shot RAG for finetuned model: {user_query}")
            results = self.vector_store.search(user_query, k=3)
            formatted_context = "Dữ liệu tra cứu được:\n" + "\n".join([f"- ID: {r['chunk_id']}\n  NỘI DUNG: {r['content']}" for r in results])
            
            full_user_content = f"{formatted_context}\n\nCâu hỏi: {user_query}"
            self.chat_history.append({"role": "user", "content": full_user_content})
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.chat_history,
                    temperature=0.1
                )
                content = response.choices[0].message.content or ""
                logger.info(f"RAW LLM RESPONSE (Finetuned Mode): {content}")
                
                # --- TRÍCH XUẤT THÔNG MINH ---
                # 1. Tìm JSON để lấy citations
                citations = []
                json_match = re.search(r"```json\n(.*?)\n```", content, re.DOTALL)
                if not json_match:
                    json_match = re.search(r"(\{.*\})", content, re.DOTALL)
                
                if json_match:
                    try:
                        json_str = json_match.group(1).strip()
                        json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                        tool_data = json.loads(json_str)
                        # Nếu là format Tool Call
                        if "arguments" in tool_data:
                            citations = tool_data["arguments"].get("citations", [])
                        # Nếu là format Direct JSON
                        elif "citations" in tool_data:
                            citations = tool_data["citations"]
                    except: pass

                # 2. Toàn bộ text (sau khi loại bỏ JSON) là Summary
                summary = re.sub(r'```json.*?```', '', content, flags=re.DOTALL)
                summary = re.sub(r'\{.*?"citations":.*?\}.*?\}', '', summary, flags=re.DOTALL)
                summary = summary.strip()
                
                # 3. Hợp nhất nội dung
                if not summary or len(summary) < 20:
                    summary = "Dưới đây là các căn cứ pháp lý tôi tìm thấy:"
                
                if citations:
                    citations = self._force_verbatim_content_direct(citations, results)
                
                # Tự động tạo citations từ text nếu model không trả về JSON (nhưng có nhắc tới Điều/Luật)
                if not citations:
                    fallback_res = self._parse_fallback_content(content)
                    citations = fallback_res["citations"]

                return {"summary": summary, "citations": citations}
                
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                return {"summary": f"Lỗi kết nối LLM: {e}", "citations": []}

        # --- CHIẾN LƯỢC 2: REACT LOOP CHO MODEL STANDARD ---
        self.chat_history.append({"role": "user", "content": user_query})
        max_iterations = 5
        logger.info(f"Starting ReAct loop for: {user_query}")

        for i in range(max_iterations):
            logger.info(f"Iteration {i+1}...")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.chat_history,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.1
                )
            except Exception as e:
                logger.error(f"LLM Error: {e}")
                return {"summary": f"Lỗi kết nối LLM: {e}", "citations": []}

            response_message = response.choices[0].message
            self.chat_history.append(response_message)
            content = response_message.content or ""

            if response_message.tool_calls:
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        args = json.loads(tool_call.function.arguments)
                    except: continue

                    if function_name == "search_database":
                        query = args.get("query", str(user_query))
                        results = self.vector_store.search(str(query), k=6)
                        formatted = "Dữ liệu database:\n" + "\n".join([f"- ID: {r['chunk_id']}\n  NỘI DUNG: {r['content']}" for r in results])
                        self.chat_history.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": formatted})
                    
                    elif function_name == "fetch_context":
                        chunk_id = args.get("chunk_id", "")
                        results = self.vector_store.get_context(chunk_id)
                        formatted = f"Bối cảnh mở rộng cho {chunk_id}:\n" + "\n".join([f"- ID: {r['chunk_id']}\n  NỘI DUNG: {r['content']}" for r in results])
                        self.chat_history.append({"tool_call_id": tool_call.id, "role": "tool", "name": function_name, "content": formatted})

                    elif function_name == "cite_and_answer":
                        summary = self._clean_text(args.get("summary", ""))
                        citations = args.get("citations", [])
                        for c in citations:
                            if c.get("content"): c["content"] = self._clean_text(c["content"])
                            if c.get("legal_analysis"): c["legal_analysis"] = self._clean_text(c["legal_analysis"])
                        
                        citations = self._force_verbatim_content(citations)
                        return {"summary": summary, "citations": citations}

            elif content:
                res = self._parse_fallback_content(content)
                if res["citations"] or i == max_iterations - 1:
                    res["citations"] = self._force_verbatim_content(res["citations"])
                    return res

        return {"summary": "Không tìm thấy câu trả lời phù hợp.", "citations": []}
