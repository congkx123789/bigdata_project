import requests
import json
import time

def test_inference(query):
    url = "http://localhost:8003/api/chats/send"
    payload = {
        "message": query,
        "session_id": "test-session",
        "provider": "local"
    }
    headers = {"Content-Type": "application/json"}
    
    print(f"Testing Query: {query}")
    print("-" * 50)
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=180)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"Status: SUCCESS ({duration:.2f}s)")
            print(f"Reply: {result.get('reply', 'N/A')}")
            print(f"Citations Found: {len(result.get('citations', []))}")
            for i, source in enumerate(result.get('citations', [])):
                print(f"  [{i+1}] {source.get('source')}")
                print(f"      Summary: {source.get('summary')[:100]}...")
        else:
            print(f"Status: FAILED (HTTP {response.status_code})")
            print(response.text)
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_inference("Trích xuất cho tôi nội dung Điều 147 Bộ luật Hình sự 2015 về ngoại tình")
