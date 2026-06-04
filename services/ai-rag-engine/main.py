import logging
import os
import asyncio
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
import torch
import sys

# Thêm root vào path để import được agentic_rag
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from agentic_rag.agent import AgenticRAG


app = FastAPI(title="Nexus AI RAG Engine", version="1.2.0")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_rag_engine")


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class InferenceRequest(BaseModel):
    query: str
    doc_id: str | None = None
    session_id: str = "default"
    history: list[HistoryMessage] = Field(default_factory=list)
    provider: Literal["local", "google"] = "local"
    google_api_key: str | None = None
    retrieve_only: bool = False


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "document_vectors")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
TOP_K = int(os.getenv("TOP_K", "5"))
EMBED_DEVICE = os.getenv("EMBED_DEVICE", "cuda")

model: SentenceTransformer | None = None
collection: Collection | None = None

# ANTI-CRASH: Limit concurrent inferences to protect GPU VRAM
# Adjust MAX_CONCURRENT based on your GPU capacity (8GB VRAM ~ 3-5 concurrent)
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
inference_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


def init_retrieval() -> None:
    global model, collection

    if model is None:
        preferred_device = EMBED_DEVICE
        if preferred_device == "cuda" and not torch.cuda.is_available():
            logger.warning("CUDA is not available, fallback to CPU for embeddings")
            preferred_device = "cpu"

        logger.info(f"Loading embedding model: {EMBEDDING_MODEL} on device={preferred_device}")
        model = SentenceTransformer(EMBEDDING_MODEL, device=preferred_device)

    if collection is None:
        logger.info(f"Connecting to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
        connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
        collection = Collection(MILVUS_COLLECTION)
        collection.load()
        logger.info(f"Milvus collection loaded: {MILVUS_COLLECTION}")


def get_context(query: str, k: int = TOP_K) -> tuple[str, list[dict[str, Any]]]:
    if model is None or collection is None:
        init_retrieval()

    query_vector = model.encode([query])[0].tolist()
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

    results = collection.search(
        data=[query_vector],
        anns_field="vector",
        param=search_params,
        limit=k,
        output_fields=["filename", "text"],
    )

    source_chunks: list[dict[str, Any]] = []
    context_parts: list[str] = []

    for hits in results:
        for hit in hits:
            filename = hit.entity.get("filename")
            text = hit.entity.get("text")
            score = float(hit.distance)

            if not text:
                continue

            source_chunks.append(
                {
                    "filename": filename,
                    "score": score,
                    "text": text,  # Return full text for audit
                    "preview": text[:300],
                }
            )
            context_parts.append(f"[Source: {filename} | score={score:.4f}]\n{text}")

    context = "\n\n".join(context_parts)
    return context, source_chunks


@app.on_event("startup")
def startup_event() -> None:
    try:
        init_retrieval()
    except Exception as exc:
        logger.warning(f"Startup retrieval init failed, will retry on first request: {exc}")


async def get_ollama_response(prompt: str) -> str:
    # ANTI-CRASH: Retry logic for local LLM
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data.get("response", "Không có câu trả lời từ AI.")
        except Exception as exc:
            if attempt == max_retries - 1:
                raise exc
            logger.warning(f"Ollama attempt {attempt+1} failed, retrying... {exc}")
            await asyncio.sleep(1)
    return "Lỗi kết nối Ollama sau nhiều lần thử."


async def get_gemini_response(prompt: str, api_key: str) -> str:
    # Google AI Studio (Gemini) REST API
    # Gemini 2.0 Flash is recommended for speed and availability
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 2048,
        }
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)
        if response.status_code != 200:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Unknown Gemini error")
            raise Exception(f"Gemini API Error: {error_msg}")
        
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return "Lỗi phân giải phản hồi từ Gemini."


# Khởi tạo Agent một lần duy nhất để tiết kiệm VRAM
agent = AgenticRAG(model_name=OLLAMA_MODEL, base_url=f"{OLLAMA_URL}/v1")

@app.post("/internal/inference")
async def run_inference(req: InferenceRequest):
    async with inference_semaphore:
        try:
            # Chạy suy luận Agentic Loop
            result = agent.run(req.query)
            
            # Phân tách kết quả
            answer = result["summary"]
            citations = result["citations"]
            
            # Ánh xạ Citations sang định dạng Frontend mong muốn
            # Frontend: Array<{ id: number; source: string; content: string }>
            formatted_sources = []
            for i, cite in enumerate(citations):
                formatted_sources.append({
                    "id": i + 1,
                    "source": cite.get("source") or cite.get("chunk_id", "Tài liệu hệ thống"),
                    "text": cite.get("content", ""), 
                    "preview": cite.get("content", "")[:300] + "...",
                    "content": cite.get("content", ""), 
                    "summary": cite.get("legal_analysis") or cite.get("summary") or "Hệ thống đang trích xuất phân tích chi tiết..."
                })

            return {
                "answer": answer,
                "sources": formatted_sources,
                "used_context": "Deep Agentic Search - Gold Standard V2 Applied.",
            }

        except Exception as exc:
            logger.exception("Agentic inference failed")
            return {
                "answer": f"[Error] Agentic Engine failed: {exc}",
                "sources": [],
                "used_context": "",
            }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
