import uvicorn
from fastapi import FastAPI, Request
from agentic_rag.agent import AgenticRAG
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
agent = AgenticRAG()

@app.post("/query")
async def query_nexus(request: Request):
    body = await request.json()
    message = body.get("message")
    api_key = os.getenv("GEMINI_API_KEY", "dummy_key")
    
    # Ở đây chúng ta dùng run() đồng bộ nhưng await nó
    # Hoặc nếu muốn stream thì dùng run_stream()
    # Để test concurrency tốt nhất, ta dùng run()
    result = await agent.run(message, api_key=api_key)
    return result

if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8002))
    print(f"Nexus Legal Server is running on http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
