import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

class LegalParser:
    def __init__(self, html_content: str):
        self.html = html_content
        # Làm sạch HTML cơ bản trước khi đưa vào BeautifulSoup
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.title = self._extract_main_title()

    def _extract_main_title(self) -> str:
        """Trích xuất tiêu đề gốc chuẩn xác nhất."""
        # 1. Tìm trong các thẻ Header hoặc Paragraph căn giữa đậm
        candidates = []
        for p in self.soup.find_all(['p', 'div'], align="CENTER"):
            b = p.find('b')
            if b: candidates.append(b.get_text().strip())
        
        for h in self.soup.find_all(['h1', 'h2', 'h3']):
            candidates.append(h.get_text().strip())

        for c in candidates:
            if any(kw in c.upper() for kw in ["LUẬT", "NGHỊ ĐỊNH", "THÔNG TƯ", "QUYẾT ĐỊNH", "HIẾN PHÁP"]):
                if len(c) > 10: return c

        # 2. Dự phòng: Tìm số hiệu văn bản
        text_content = self.soup.get_text()
        doc_no_match = re.search(r'(Số|Số hiệu):\s*([\w\d\/\-]+)', text_content, re.IGNORECASE)
        
        # 3. Dự phòng cuối: Tìm dòng IN HOA đầu tiên
        lines = [l.strip() for l in text_content.split("\n") if l.strip()]
        for l in lines[:10]:
            if l.isupper() and len(l) > 15: return l

        if doc_no_match:
            return f"Văn bản số {doc_no_match.group(2)}"

        return lines[0][:250] if lines else "Văn bản Pháp luật"

    def parse_to_tree_chunks(self) -> List[Dict[str, str]]:
        """
        Phân tích văn bản thành các Chunk có cấu trúc Cây.
        Làm sạch 100% HTML và nối tiêu đề chuẩn.
        """
        chunks = []
        # Loại bỏ các thẻ rác trước khi lấy text
        for tag in self.soup(["script", "style", "meta", "link"]):
            tag.decompose()
            
        text_content = self.soup.get_text(separator="\n")
        lines = [l.strip() for l in text_content.split("\n") if l.strip()]
        
        current_chapter = ""
        current_section = ""
        current_article = ""
        buffer = []
        
        # Pattern nhận diện các cấp bậc
        chapter_pattern = re.compile(r'^(Chương [IVXLCDM\d]+[:.]?.*)', re.IGNORECASE)
        section_pattern = re.compile(r'^(Mục \d+[:.]?.*)', re.IGNORECASE)
        article_pattern = re.compile(r'^(Điều \d+[:.]?.*)', re.IGNORECASE)
        
        for line in lines:
            # Nhận diện Chương
            if chapter_pattern.match(line):
                if buffer and current_article:
                    chunks.append(self._create_chunk(current_chapter, current_section, current_article, buffer))
                    buffer = []
                current_chapter = line
                current_section = ""
                current_article = ""
                continue
            
            # Nhận diện Mục
            if section_pattern.match(line):
                if buffer and current_article:
                    chunks.append(self._create_chunk(current_chapter, current_section, current_article, buffer))
                    buffer = []
                current_section = line
                current_article = ""
                continue
                
            # Nhận diện Điều
            if article_pattern.match(line):
                if buffer and current_article:
                    chunks.append(self._create_chunk(current_chapter, current_section, current_article, buffer))
                current_article = line
                buffer = [line]
                continue
                
            if current_article:
                buffer.append(line)

        # Lưu chunk cuối cùng
        if buffer and current_article:
            chunks.append(self._create_chunk(current_chapter, current_section, current_article, buffer))

        return chunks

    def _create_chunk(self, chapter, section, article, buffer) -> Dict[str, str]:
        # Chuẩn hóa Hierarchy
        path_parts = [self.title]
        if chapter: path_parts.append(chapter)
        if section: path_parts.append(section)
        if article: path_parts.append(article)
        
        full_path = " > ".join(path_parts)
        content_text = "\n".join(buffer)
        
        # Định dạng nội dung sạch (Markdown-like)
        formatted_content = f"NGUỒN TRÍCH DẪN: [{full_path}]\n\nNỘI DUNG CHI TIẾT:\n{content_text}"
        
        return {
            "title": self.title,
            "path": full_path,
            "content": formatted_content,
            "article": article
        }
