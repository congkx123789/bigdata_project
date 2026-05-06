
import json
import logging
from agentic_rag.agent import AgenticRAG
import re

logging.basicConfig(level=logging.INFO)

def is_bad_response(resp):
    if not resp or not resp.get('summary'):
        return True
    content = resp['summary'].lower()
    # Kiểm tra tiếng nước ngoài hoặc rác
    vietnamese_chars = len(re.findall(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', content))
    if len(content) > 10 and (vietnamese_chars / len(content)) < 0.05:
        return True
    if any(word in content for word in ['xin lỗi', 'sự cố', 'call tool', 'callcheck', 'thought:', 'hỏi:']):
        return True
    if 'lorsqu' in content: # Chốt chặn tiếng Pháp
        return True
    return False

def patch():
    file_path = 'agent_stress_test_diverse_100.json'
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    agent = AgenticRAG()
    patched_count = 0
    
    for item in data:
        idx = item['index']
        if is_bad_response(item.get('response')):
            print(f"🛠️ Đang vá câu {idx}: {item['question']}")
            new_res = agent.run(item['question'])
            item['response'] = new_res
            patched_count += 1
            # Lưu ngay sau mỗi câu để tránh mất dữ liệu
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
    
    print(f"✅ Đã vá xong {patched_count} câu lỗi!")

if __name__ == "__main__":
    patch()
