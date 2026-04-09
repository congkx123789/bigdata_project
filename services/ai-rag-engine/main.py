from fastapi import FastAPI
from pydantic import BaseModel
import httpx
import os

app = FastAPI(title="Nexus AI RAG Engine", version="1.0.0")

class InferenceRequest(BaseModel):
    query: str
    doc_id: str = None

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

@app.post("/internal/inference")
async def run_inference(req: InferenceRequest):
    """
    AI RAG Engine: Xử lý chat sinh văn bản đồng bộ.
    1. Gọi Vector Store (Milvus) để lấy Context.
    2. Gửi Context + Query vào LLM (Llama-3).
    3. Trả về kết quả dưới dạng Streaming.
    """
    # 1. Similarity Search in Milvus
    # context = milvus_client.search(req.query)
    context = "Giả định đây là nội dung bóc tách từ tài liệu liên quan..." 
    
    # 2. Prompt Engineering
    prompt = f"Context: {context}\n\nQuestion: {req.query}"
    
    # 3. Ollama Llama-3 Inference
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Trong thực tế sẽ dùng streaming (Iterate over lines)
        response = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": prompt,
                "stream": False
            }
        )
        data = response.json()
    
    return {"answer": data.get("response", "Không có câu trả lời từ AI.")}

# TODO: Kafka Consumer listener loop for text-extracted -> Embedding (BAAI/bge-m3)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
