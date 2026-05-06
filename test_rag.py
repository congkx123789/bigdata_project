import os
import sys
import json

# Thêm thư mục gốc vào path để import
sys.path.append(os.getcwd())

from agentic_rag.agent import AgenticRAG

def test():
    # Sử dụng API Key thực tế từ env hoặc giả lập nếu chỉ test cấu trúc prompt
    api_key = os.getenv("GOOGLE_API_KEY", "")
    
    agent = AgenticRAG()
    
    query = "Điều kiện kết hôn theo Luật Hôn nhân và Gia đình 2014?"
    print(f"\n--- TESTING QUERY: {query} ---\n")
    
    response = agent.run(query, provider="google", api_key=api_key)
    
    print("\n--- AI RESPONSE ---\n")
    print(response.get("summary", "No summary"))
    
    print("\n--- CITATIONS (TREE STRUCTURE) ---\n")
    for i, cite in enumerate(response.get("citations", [])):
        print(f"{i+1}. Source: {cite.get('source', 'Unknown')}")
        print(f"   Root Title: {cite.get('root_title', 'Not found')}")
        print(f"   Analysis: {cite.get('legal_analysis', '')[:200]}...")

if __name__ == "__main__":
    test()
