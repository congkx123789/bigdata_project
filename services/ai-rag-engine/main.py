import logging
import os
from typing import Any, Literal

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
import torch

app = FastAPI(title="Nexus AI RAG Engine", version="1.1.0")

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


@app.post("/internal/inference")
async def run_inference(req: InferenceRequest):
    try:
        context, sources = get_context(req.query)
    except Exception as exc:
        logger.exception("Milvus retrieval failed")
        return {
            "answer": f"[Error] Milvus retrieval failed: {exc}",
            "sources": [],
            "used_context": "",
        }

    if not context:
        return {
            "answer": "Không tìm thấy ngữ cảnh phù hợp từ Milvus cho câu hỏi này.",
            "sources": [],
            "used_context": "",
        }

    if req.retrieve_only:
        num_sources = len(sources)
        return {
            "answer": f"Discovery Mode: Tìm thấy {num_sources} đoạn trích liên quan từ tài liệu của bạn.",
            "sources": sources,
            "used_context": context[:3000],
        }

    # Tạm thời vô hiệu hóa lịch sử theo yêu cầu người dùng để tránh lỗi hiển thị.
    history_text = ""

    prompt = (
        "Bạn là trợ lý AI cho kho tài liệu. "
        "Chỉ trả lời dựa trên CONTEXT đã cho. "
        "Nếu thiếu dữ liệu trong CONTEXT thì nói rõ là không đủ thông tin từ tài liệu.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {req.query}\n\n"
        "ANSWER (in Vietnamese):"
    )

    try:
        if req.provider == "google":
            if not req.google_api_key:
                return {
                    "answer": "[Error] Gemini API Key is missing. Please provide it in settings.",
                    "sources": sources,
                    "used_context": context[:3000],
                }
            answer = await get_gemini_response(prompt, req.google_api_key)
        else:
            answer = await get_ollama_response(prompt)
            
    except Exception as exc:
        logger.exception(f"{req.provider} inference failed")
        return {
            "answer": f"[Error] {req.provider} LLM inference failed: {exc}",
            "sources": sources,
            "used_context": context[:3000],
        }

    return {
        "answer": answer,
        "sources": sources,
        "used_context": context[:3000],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
