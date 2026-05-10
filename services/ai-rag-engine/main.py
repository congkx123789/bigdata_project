import logging
import os
import asyncio
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
import torch
import sys

# Thêm root vào path để import được agentic_rag
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from agentic_rag.agent import AgenticRAG


app = FastAPI(title="Nexus AI RAG Engine", version="1.2.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("ai_rag_engine")


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class InferenceRequest(BaseModel):
    query: str
    doc_id: str | None = None
    session_id: str = "default"
    history: list[HistoryMessage] = Field(default_factory=list)
    provider: Literal["local", "google"] = "google"
    google_api_key: str | None = None
    google_model: str = "gemini-2.0-flash"
    retrieve_only: bool = False

GOOGLE_API_KEY = os.getenv("DEFAULT_GOOGLE_API_KEY", "")

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


# Gemini và các logic LLM đã được chuyển vào AgenticRAG
DEFAULT_GOOGLE_API_KEY = os.getenv("DEFAULT_GOOGLE_API_KEY", "")
# ANTI-CRASH: Limit concurrent inferences to protect GPU VRAM
# Adjust MAX_CONCURRENT based on your GPU capacity (Blackwell RTX 5000: 10-15 concurrent)
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "10"))
inference_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
# Khởi tạo Agent một lần duy nhất
agent = AgenticRAG()

@app.post("/internal/inference")
async def run_inference(req: InferenceRequest):
    # FAST PATH: Retrieve only (for stress testing and internal lookups)
    if req.retrieve_only:
        try:
            context, sources = get_context(req.query, k=TOP_K)
            return {
                "answer": "Retrieve only mode.",
                "sources": sources,
                "used_context": context,
                "timings": {"retrieval": 0.5} # Placeholder
            }
        except Exception as exc:
            return {"answer": f"Retrieval failed: {exc}", "sources": []}

    async with inference_semaphore:
        try:
            # Chạy suy luận Agentic Loop
            # Ưu tiên key của người dùng nếu có, nếu không dùng key hệ thống mặc định
            actual_key = req.google_api_key or DEFAULT_GOOGLE_API_KEY
            
            # Chuyển đổi HistoryMessage sang định dạng Agent cần
            history_list = [{"role": h.role, "content": h.content} for h in req.history]

            # Chạy suy luận Agentic Loop
            result = await agent.run(
                req.query, 
                api_key=actual_key,
                model_name=req.google_model,
                history=history_list
            )
            
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
                    "root_title": cite.get("root_title", "Văn bản chưa rõ tiêu đề"),
                    "text": cite.get("content", ""), 
                    "preview": cite.get("content", "")[:300] + "...",
                    "content": cite.get("content", ""), 
                    "summary": cite.get("legal_analysis") or cite.get("summary") or "Hệ thống đang trích xuất phân tích chi tiết..."
                })

            return {
                "answer": answer,
                "sources": formatted_sources,
                "used_context": "Deep Agentic Search - Gold Standard V2 Applied.",
                "timings": result.get("timings", {})
            }

        except Exception as exc:
            logger.exception("Agentic inference failed")
            return {
                "answer": f"[Error] Agentic Engine failed: {exc}",
                "sources": [],
                "used_context": "",
            }



@app.post("/internal/inference_stream")
async def run_inference_stream(req: InferenceRequest):
    """Endpoint hỗ trợ Streaming kết quả."""
    try:
        actual_key = req.google_api_key or DEFAULT_GOOGLE_API_KEY
        if not actual_key:
            raise HTTPException(status_code=400, detail="Missing API Key")

        history_list = []
        if req.history:
            for m in req.history:
                history_list.append({"role": m.role, "content": m.content})

        async def generate():
            async for chunk in agent.run_stream(
                req.query, 
                api_key=actual_key,
                model_name=req.google_model,
                history=history_list
            ):
                yield chunk

        return StreamingResponse(
            generate(), 
            media_type="text/plain", # Internal stream uses plain text to avoid SSE overhead
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as exc:
        logger.exception("Streaming inference failed")
        return StreamingResponse(iter([f"Error: {exc}"]), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
