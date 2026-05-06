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
        
        self.system_prompt = """# SYSTEM PROMPT V16: TRỢ LÝ PHÁP LÝ THÔNG MINH (CONSULTATIVE MODE)
Bạn là Chuyên gia Pháp lý Việt Nam cao cấp. Nhiệm vụ của bạn là tra cứu và tư vấn các vấn đề pháp luật một cách tận tâm, dễ hiểu và chuyên nghiệp.

# NGUYÊN TẮC HOẠT ĐỘNG (BẮT BUỘC):
1. **DỮ LIỆU THỰC TẾ**: Chỉ trích dẫn những gì CÓ TRONG kết quả tra cứu được cung cấp. KHÔNG tự bịa ra điều luật.
2. **TRÍCH DẪN ĐA TẦNG (GỐC -> CÀNH -> LÁ)**: Với mỗi căn cứ pháp lý, bạn phải nêu rõ lộ trình trích dẫn: **[Tên văn bản] > [Chương/Mục] > [Điều luật]**. Ví dụ: "Theo Điều 8, thuộc Chương II của Luật Hôn nhân và Gia đình 2014...".
3. **ĐỊNH DẠNG JSON TRÍCH DẪN**: Cuối mỗi câu trả lời, bạn PHẢI liệt kê trích dẫn dưới dạng JSON khối ```json { "citations": [ { "id": [Số thứ tự kết quả], "source": "Tên văn bản + Điều luật", "legal_analysis": "Phân tích 3-5 câu của bạn" } ] } ```
4. **PHONG CÁCH TƯ VẤN**: Trả lời chuyên nghiệp như một luật sư, ngôn ngữ chuẩn xác, tận tâm.
5. **KHÔNG TRẢ LỜI NGẮN GỌN**: Phân tích kỹ từng khía cạnh của vấn đề dựa trên luật định.
"""
        self.chat_history = [{"role": "system", "content": self.system_prompt}]

    def _clean_text(self, text: str) -> str:
        """Làm sạch HTML và rác văn bản tại chỗ."""
        if not text: return ""
        # 1. Loại bỏ các thẻ HTML rác nếu còn tồn tại trong DB
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, 'html.parser')
            text = soup.get_text(separator=" ")
        except: pass
        
        # 2. Loại bỏ tiếng Trung và làm sạch khoảng trắng
        text = re.sub(r'[\u4e00-\u9fff]+', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_fallback_content(self, text: str) -> Dict:
        """Bóc tách text thô nếu LLM không nhả ra JSON chuẩn."""
        citations = []
        # Tìm các khối JSON
        json_blocks = re.findall(r'(\{.*?"citations":.*?\})', text, re.DOTALL)
        for block in json_blocks:
            try:
                data = json.loads(block)
                if isinstance(data.get("citations"), list):
                    citations.extend(data["citations"])
            except: continue

        # Regex cứu hộ nếu JSON hỏng hẳn
        if not citations:
            lines = text.split("\n")
            for line in lines:
                if re.search(r'(Điều \d+)', line, re.IGNORECASE) and len(line.strip()) > 50:
                    citations.append({
                        "id": None,
                        "source": "Căn cứ tìm thấy",
                        "content": line.strip()
                    })

        summary = re.sub(r'(?s)\{.*?"citations":.*?\}.*?\}', '', text)
        return {
            "summary": summary.strip() if len(summary.strip()) > 20 else "Kết quả tra cứu:",
            "citations": citations
        }

    def _get_parent_title(self, chunk_id: str) -> str:
        """Truy vết ngược để lấy tiêu đề gốc từ Chunk 0 của văn bản."""
        try:
            # Format chunk_id thường là "vi-legal:123#chunk-4"
            if "#chunk-" in chunk_id:
                parent_base = chunk_id.split("#chunk-")[0]
                root_chunk_id = f"{parent_base}#chunk-0"
                
                # Truy vấn nhanh Milvus để lấy tiêu đề từ đoạn đầu tiên
                res = self.vector_store.collection.query(
                    expr=f'filename == "{root_chunk_id}"',
                    output_fields=["title", "text"],
                    limit=1
                )
                if res:
                    # Nếu chunk 0 có tiêu đề chuẩn, lấy luôn
                    title = res[0].get("title")
                    if title and len(title) > 10 and not title.startswith("Điều"):
                        return title
                    # Nếu không, lấy dòng đầu tiên của text trong chunk 0
                    first_line = res[0].get("text", "").split("\n")[0].strip()
                    if len(first_line) > 10: return first_line
        except Exception as e:
            logger.warning(f"Parent lookup failed: {e}")
        return ""

    def _shorten_title(self, title: str) -> str:
        """Rút gọn tiêu đề văn bản thông minh, lọc bỏ các tiêu đề rác."""
        if not title or any(x in title.lower() for x in ["không rõ", "chưa xác định", "văn bản hệ thống", "văn bản pháp luật"]):
            return ""
            
        # Nếu tiêu đề chỉ có mỗi chữ "Nghị định" hoặc "Điều..." thì coi là rác
        if title.strip().upper() in ["NGHỊ ĐỊNH", "QUYẾT ĐỊNH", "THÔNG TƯ", "LUẬT", "HIẾN PHÁP"]:
            return ""
            
        if title.startswith("Điều ") or ":" in title:
            parts = title.split(":")
            if any(kw in parts[0].upper() for kw in ["LUẬT", "NGHỊ ĐỊNH", "THÔNG TƯ"]):
                title = parts[0]
            else:
                return ""

        doc_no = re.search(r'([Ss]ố\s*[\w\d\/\-]+)', title)
        doc_type = re.search(r'(Luật|Nghị định|Quyết định|Thông tư|Hiến pháp|Sắc lệnh)', title, re.IGNORECASE)
        
        if doc_type and doc_no:
            return f"{doc_type.group(0).capitalize()} {doc_no.group(1)}"
        elif doc_type:
            words = title.split()
            for i, w in enumerate(words):
                if doc_type.group(0).lower() in w.lower():
                    return " ".join(words[i:i+8]).strip(",. ")
        
        return title[:60].strip() + "..." if len(title) > 65 else title

    def _force_verbatim_content_direct(self, citations: List[Dict], results: List[Dict]) -> List[Dict]:
        """Khôi phục nội dung BẢN GỐC và tự động sửa tiêu đề thông qua truy vết ngược."""
        final_citations = []
        seen_ids = set()

        for c in citations:
            idx = c.get("id")
            found_res = None
            
            if isinstance(idx, (int, str)) and str(idx).isdigit():
                val = int(idx)
                if 1 <= val <= len(results):
                    found_res = results[val - 1]
            
            if not found_res and c.get("source"):
                for r in results:
                    if any(word.lower() in r['content'].lower() for word in c['source'].split() if len(word) > 3):
                        found_res = r
                        break
            
            if found_res:
                cid = found_res['chunk_id']
                if cid not in seen_ids:
                    # 1. Làm sạch nội dung tại chỗ
                    c["content"] = self._clean_text(found_res["content"])
                    
                    # 2. Truy vết tiêu đề chuẩn (Logic mới)
                    raw_title = found_res.get("title", "")
                    short_title = self._shorten_title(raw_title)
                    
                    if not short_title:
                        # Nếu tiêu đề trong DB bị "nông" hoặc rác, đi tìm tiêu đề ở Parent
                        parent_title = self._get_parent_title(cid)
                        short_title = self._shorten_title(parent_title) or "Văn bản Pháp luật"
                    
                    c["root_title"] = short_title
                    
                    if not c.get("source") or "Căn cứ" in c["source"]:
                        c["source"] = short_title
                    
                    final_citations.append(c)
                    seen_ids.add(cid)
            elif c.get("content") and len(c["content"]) > 50:
                final_citations.append(c)

        return final_citations

    def run(self, user_query: str, provider: str = "local", api_key: str | None = None, model_name: str = "gemini-3.1-flash-lite-preview") -> Dict:
        # --- CHIẾN LƯỢC 0: GOOGLE GEMINI (NẾU ĐƯỢC YÊU CẦU) ---
        if provider == "google" and api_key:
            return self._run_gemini(user_query, api_key, model_name)

        # Mặc định lấy kết quả search trước để đưa vào Prompt
        search_results = self.vector_store.search(user_query, k=6)
        context_str = "\n".join([f"KẾT QUẢ {i+1}:\n{r['content']}" for i, r in enumerate(search_results)])

        # --- CHIẾN LƯỢC 1: ZERO-SHOT RAG (CẢI TIẾN) ---
        prompt_with_context = f"""{self.system_prompt}
        
DỮ LIỆU TRA CỨU TỪ DATABASE (DÙNG ĐỂ TRÍCH DẪN):
{context_str}

CÂU HỎI: {user_query}
"""
        self.chat_history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_with_context}
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.chat_history,
                temperature=0.1
            )
            content = response.choices[0].message.content or ""
            
            # Parse và khôi phục nội dung gốc
            res = self._parse_fallback_content(content)
            res["citations"] = self._force_verbatim_content_direct(res["citations"], search_results)
            
            return res
            
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return {"summary": f"Lỗi kết nối AI: {e}", "citations": []}

    def _run_gemini(self, user_query: str, api_key: str, model_name: str = "gemini-3.1-flash-lite-preview") -> Dict:
        """Sử dụng Google Gemini với dữ liệu retrieval từ local Milvus."""
        results = self.vector_store.search(user_query, k=6)
        context = "\n".join([f"KẾT QUẢ {i+1}:\n{r['content']}" for i, r in enumerate(results)])
        
        prompt = f"""{self.system_prompt}

DỮ LIỆU PHÁP LUẬT TÌM THẤY (Hãy dùng số thứ tự KẾT QUẢ X để trích dẫn):
{context}

CÂU HỎI CỦA NGƯỜI DÙNG:
{user_query}

YÊU CẦU: Bạn phải trả lời chi tiết và xuất JSON citations ở cuối bài.
"""

        
        # 3. Call Gemini API (REST) with Safety Settings & Retries
        import requests
        import time
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=60)
                
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        logger.warning(f"Gemini Rate Limit (429). Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                
                response.raise_for_status()
                data = response.json()
                
                # Check for safety blocks in response
                if not data.get("candidates") or not data["candidates"][0].get("content"):
                    finish_reason = data.get("candidates", [{}])[0].get("finishReason")
                    if finish_reason == "SAFETY":
                        return {"summary": "⚠️ Câu hỏi của bạn bị hệ thống an toàn của Google chặn. Vui lòng điều chỉnh lại cách đặt câu hỏi.", "citations": []}
                    return {"summary": f"Lỗi phản hồi Gemini: {finish_reason or 'Không có nội dung'}", "citations": []}

                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                # 4. Parse response
                res = self._parse_fallback_content(content)
                
                # 5. Restore verbatim content from local results if IDs match
                res["citations"] = self._force_verbatim_content_direct(res["citations"], results)
                
                return res
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Gemini attempt {attempt+1} failed: {e}. Retrying...")
                    time.sleep(2)
                    continue
                logger.error(f"Gemini API Error after {max_retries} attempts: {e}")
                return {"summary": f"Lỗi kết nối Gemini ({model_name}): {str(e)}", "citations": []}
