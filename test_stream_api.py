import httpx
import asyncio
import json
import time

async def test_stream():
    url = "http://localhost:8003/api/chats/send_stream"
    payload = {
        "message": "Chào bạn, hãy cho tôi biết về luật lao động",
        "session_id": "test-session-123",
        "provider": "google",
        "api_key": "",
        "google_model": "gemini-2.0-flash"
    }
    
    print(f"--- BẮT ĐẦU TEST STREAMING TỪ: {url} ---")
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                print(f"Status Code: {response.status_code}")
                print(f"Headers: {response.headers.get('Content-Type')}")
                
                async for chunk in response.aiter_text():
                    elapsed = time.time() - start_time
                    # Loại bỏ phần padding để dễ nhìn log
                    clean_chunk = chunk.replace(" ", "").replace(":", "") if len(chunk) > 1000 else chunk
                    if clean_chunk.strip():
                        print(f"[{elapsed:.2f}s] Nhận dữ liệu: {clean_chunk.strip()}")
    except Exception as e:
        print(f"LỖI: {e}")

if __name__ == "__main__":
    asyncio.run(test_stream())
