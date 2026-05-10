from fastapi import FastAPI, Request, Response
import json
import uvicorn
import random
import asyncio
import logging
import time
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MockGoogle")

app = FastAPI()

# Simple in-memory cache
# Key: Hash(prompt + model), Value: (response_text, timestamp)
cache = {}
CACHE_TTL = 300  # 5 minutes

@app.post("/v1beta/models/{model_name}:generateContent")
async def mock_gemini(model_name: str, request: Request):
    # Get key and payload
    key = request.query_params.get("key", "no-key")
    body = await request.json()
    
    # Try to extract the user's query from the STRICT_ZONE
    try:
        prompt = body['contents'][0]['parts'][0]['text']
        if "<USER_INPUT_STRICT_ZONE>" in prompt:
            user_query = prompt.split("<USER_INPUT_STRICT_ZONE>")[1].split("</USER_INPUT_STRICT_ZONE>")[0]
            user_query = user_query.replace("Câu hỏi hiện tại của người dùng:", "").strip()
        else:
            user_query = prompt[:50].replace("\n", " ")
    except:
        prompt = ""
        user_query = "Unknown Query"

    # Check Cache
    cache_key = hashlib.md5(f"{prompt}{model_name}".encode()).hexdigest()
    if cache_key in cache:
        cached_text, timestamp = cache[cache_key]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"⚡ Cache Hit | Key: {key[:8]}... | Query: {user_query[:50]}...")
            await asyncio.sleep(0.05)
            return format_response(cached_text, key, user_query, is_cached=True)

    # Simulate AI processing time
    delay = random.uniform(0.5, 1.5)
    await asyncio.sleep(delay)
    
    logger.info(f"🟢 Received request | Key: {key[:8]}... | Query: {user_query[:50]}... | Delay: {delay:.2f}s")

    # Generate content
    response_text = f"Dựa trên quy định pháp luật, tôi xin trả lời câu hỏi '{user_query}' như sau: Đây là câu trả lời giả lập để test tải hệ thống. Dữ liệu của bạn được bảo mật và xử lý chính xác."
    
    # Store in cache
    cache[cache_key] = (response_text, time.time())

    return format_response(response_text, key, user_query)

def format_response(text: str, key: str, query: str, is_cached: bool = False):
    status = "CACHED" if is_cached else "FRESH"
    citations = [
        {"id": 1, "source": "Bộ luật Dân sự 2015", "content": "Người nào có hành vi xâm phạm tính mạng, sức khỏe của người khác thì phải bồi thường..."},
        {"id": 2, "source": "Nghị định 100/2019/NĐ-CP", "content": "Mức phạt nồng độ cồn đối với người điều khiển xe máy..."}
    ]
    return {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": f"<final_answer>{text}</final_answer>\n\n[CITATIONS_JSON]{json.dumps(citations)}[/CITATIONS_JSON]\n<!-- INTEGRITY_TAG: KEY={key} | STATUS={status} | TIME={time.time()} -->"
                }]
            },
            "finishReason": "STOP"
        }]
    }

@app.post("/v1beta/models/{model_name}:streamGenerateContent")
async def mock_gemini_stream(model_name: str, request: Request):
    key = request.query_params.get("key", "no-key")
    body = await request.json()
    
    try:
        prompt = body['contents'][0]['parts'][0]['text']
        if "<USER_INPUT_STRICT_ZONE>" in prompt:
            user_query = prompt.split("<USER_INPUT_STRICT_ZONE>")[1].split("</USER_INPUT_STRICT_ZONE>")[0]
            user_query = user_query.replace("Câu hỏi hiện tại của người dùng:", "").strip()
        else:
            user_query = prompt[:50].replace("\n", " ")
    except:
        user_query = "Unknown Query"

    logger.info(f"🌊 Starting stream | Key: {key[:8]}... | Query: {user_query[:50]}...")

    async def stream_generator():
        # Step 1: Process and delay
        await asyncio.sleep(0.5)
        
        # Step 2: Yield content in chunks
        full_text = f"Dựa trên quy định pháp luật, tôi xin trả lời câu hỏi '{user_query}' như sau: Đây là câu trả lời giả lập từ MOCK SERVER. Hệ thống đang hoạt động bình thường và dữ liệu của bạn an toàn."
        
        # Wrap in final_answer tag
        tagged_text = f"<final_answer>{full_text}</final_answer>\n\n"
        
        # Yield text chunks
        chunk_size = 20
        for i in range(0, len(tagged_text), chunk_size):
            chunk = tagged_text[i:i+chunk_size]
            data = {
                "candidates": [{
                    "content": {
                        "parts": [{"text": chunk}]
                    }
                }]
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.1)
        
        # Step 3: Yield citations (at the end as a separate chunk)
        citations = [
            {"id": 1, "source": "Bộ luật Dân sự 2015", "content": "Người nào có hành vi xâm phạm tính mạng, sức khỏe của người khác thì phải bồi thường..."},
            {"id": 2, "source": "Nghị định 100/2019/NĐ-CP", "content": "Mức phạt nồng độ cồn đối với người điều khiển xe máy..."}
        ]
        citation_chunk = f"[CITATIONS_JSON]{json.dumps(citations)}[/CITATIONS_JSON]\n<!-- INTEGRITY_TAG: KEY={key} | STATUS=STREAMED | TIME={time.time()} -->"
        data = {
            "candidates": [{
                "content": {
                    "parts": [{"text": citation_chunk}]
                }
            }]
        }
        yield f"data: {json.dumps(data)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.get("/health")
async def health():
    return {"status": "ok", "cache_size": len(cache)}

if __name__ == "__main__":
    print("🚀 Enhanced Mock Google Gemini Server is running on port 9000...")
    uvicorn.run(app, host="0.0.0.0", port=9000)
