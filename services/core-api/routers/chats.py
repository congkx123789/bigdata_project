"""
Chat Router: Quản lý lịch sử chat và giao tiếp với AI Engine.
"""
from collections import defaultdict, deque
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from database import get_session_history, save_message, get_user_sessions, create_session, update_session_title

router = APIRouter(prefix="/api/chats", tags=["chats"])

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8002")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "12"))

class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"
    user_id: str = "anonymous"
    provider: str = "google"
    api_key: str | None = None
    google_model: str = "gemini-3.1-flash-lite-preview"
    retrieve_only: bool = False

@router.get("/list")
async def list_sessions(user_id: str = "anonymous"):
    """Lấy danh sách các phiên chat của người dùng."""
    sessions = get_user_sessions(user_id)
    # Gom nhóm theo thời gian (Today, Yesterday, etc.) cho Sidebar
    return {"sessions": sessions}

@router.get("/history")
async def get_history(session_id: str = "default"):
    """Lấy lịch sử chat theo session_id từ SQLite."""
    messages = get_session_history(session_id, limit=MAX_HISTORY_TURNS * 2)
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }

@router.post("/send")
async def send_message(msg: ChatMessage):
    """
    Chat flow có persistence:
    1. Đảm bảo session tồn tại trong DB.
    2. Lấy lịch sử hội thoại.
    3. Gọi AI Engine.
    4. Lưu vào SQLite.
    """
    # 1. Khởi tạo session nếu chưa có
    create_session(msg.session_id, msg.user_id)
    
    # 2. Lấy lịch sử từ database
    history_payload = get_session_history(msg.session_id, limit=MAX_HISTORY_TURNS * 2)

    # 3. Tự động cập nhật tiêu đề nếu là tin nhắn đầu tiên
    if not history_payload and len(msg.message) > 5:
        title = msg.message[:30] + "..." if len(msg.message) > 30 else msg.message
        update_session_title(msg.session_id, title)

    try:
        async with httpx.AsyncClient(timeout=150.0) as client:
            response = await client.post(
                f"{AI_ENGINE_URL}/internal/inference",
                json={
                    "query": msg.message,
                    "session_id": msg.session_id,
                    "history": history_payload,
                    "provider": msg.provider,
                    "google_api_key": msg.api_key,
                    "google_model": msg.google_model,
                    "retrieve_only": msg.retrieve_only,
                },
            )
            response.raise_for_status()
            ai_response = response.json()
    except Exception as exc:
        ai_response = {
            "answer": f"[Error] AI Engine communication failed: {exc}",
            "sources": [],
        }

    assistant_reply = ai_response.get("answer", "No response")

    # 4. Lưu vào database
    save_message(msg.session_id, "user", msg.message)
    save_message(msg.session_id, "assistant", assistant_reply)

    return {
        "reply": assistant_reply,
        "session_id": msg.session_id,
        "citations": ai_response.get("sources", []),
    }
