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

    history_text = ""
    if req.history:
        last_turns = req.history[-12:]
        history_lines = [f"{m.role.upper()}: {m.content}" for m in last_turns]
        history_text = "\n".join(history_lines)

    prompt = (
        "Bạn là trợ lý AI cho kho tài liệu. "
        "Giữ ngữ cảnh xuyên suốt theo lịch sử hội thoại. "
        "Nếu câu hỏi hiện tại tham chiếu câu trước (ví dụ: 'còn gì nữa', 'nói kỹ hơn', 'ý trên'), "
        "hãy dùng HISTORY để suy luận đúng chủ đề đang nói. "
        "Chỉ trả lời dựa trên CONTEXT đã cho; nếu thiếu dữ liệu thì nói rõ là không đủ thông tin từ tài liệu.\n\n"
        f"HISTORY:\n{history_text or '[No history]'}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"CURRENT_QUESTION: {req.query}\n\n"
        "ANSWER (in Vietnamese):"
    )

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
    except Exception as exc:
        logger.exception("Ollama inference failed")
        return {
            "answer": f"[Error] LLM inference failed: {exc}",
            "sources": sources,
            "used_context": context[:3000],
        }

    return {
        "answer": data.get("response", "Không có câu trả lời từ AI."),
        "sources": sources,
        "used_context": context[:3000],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
