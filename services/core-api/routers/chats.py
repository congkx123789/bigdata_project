"""
Chat Router: Quản lý lịch sử chat và giao tiếp với AI Engine.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter(prefix="/api/chats", tags=["chats"])

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8002")

class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"

@router.get("/history")
async def get_history():
    """Lấy lịch sử chat từ PostgreSQL (phân nhóm theo ngày)."""
    # TODO: Query PostgreSQL
    return {
        "groups": [
            {"label": "Hôm nay", "chats": [{"id": 1, "title": "Phân tích tài liệu Q3"}]},
            {"label": "7 ngày trước", "chats": [{"id": 2, "title": "Debug Kafka pipeline"}]},
            {"label": "Tháng trước", "chats": [{"id": 3, "title": "Thiết lập hệ thống ban đầu"}]},
        ]
    }

@router.post("/send")
async def send_message(msg: ChatMessage):
    """
    Luồng Chat đồng bộ:
    1. Lưu tin nhắn user vào PostgreSQL.
    2. Kiểm tra Redis cache.
    3. Gọi AI RAG Engine nếu cache miss.
    4. Trả streaming response.
    """
    # TODO: Save to PostgreSQL
    # TODO: Check Redis cache first
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_ENGINE_URL}/internal/inference",
                json={"query": msg.message}
            )
            ai_response = response.json()
    except httpx.ConnectError:
        ai_response = {"answer": "[Fallback] AI Engine is offline. Please check the service."}

    # TODO: Cache result in Redis
    return {"reply": ai_response.get("answer", "No response"), "session_id": msg.session_id}
