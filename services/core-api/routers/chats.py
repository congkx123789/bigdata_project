"""
Chat Router: Quản lý lịch sử chat và giao tiếp với AI Engine.
"""
from collections import defaultdict, deque
import os

import httpx
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from database import get_session_history, save_message, get_user_sessions, create_session, update_session_title

router = APIRouter(prefix="/api/chats", tags=["chats"])

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8002")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "50"))

class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"
    user_id: str = "anonymous"
    provider: str = "google"
    api_key: str | None = None
    google_model: str = "gemini-2.0-flash"
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
    
    # 2. Lưu tin nhắn của USER vào database NGAY LẬP TỨC
    save_message(msg.session_id, "user", msg.message)
    
    # 3. Lấy lịch sử từ database (bao gồm cả tin nhắn vừa lưu)
    history_payload = get_session_history(msg.session_id, limit=MAX_HISTORY_TURNS * 2)

    # 4. Tự động cập nhật tiêu đề nếu là tin nhắn đầu tiên
    if len(history_payload) <= 1 and len(msg.message) > 5:
        title = msg.message[:30] + "..." if len(msg.message) > 30 else msg.message
        update_session_title(msg.session_id, title)

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{AI_ENGINE_URL}/internal/inference",
                json={
                    "query": msg.message,
                    "session_id": msg.session_id,
                    "history": history_payload[:-1], # Gửi lịch sử trước đó, không gửi chính nó
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
            "answer": f"[Error] Hệ thống đang bận hoặc quá tải. Vui lòng thử lại sau giây lát. (Chi tiết: {exc})",
            "sources": [],
        }

    assistant_reply = ai_response.get("answer", "Hệ thống không phản hồi.")

    # 5. Lưu câu trả lời của AI vào database kèm trích dẫn
    import json
    sources_json = json.dumps(ai_response.get("sources", []))
    save_message(msg.session_id, "assistant", assistant_reply, metadata=sources_json)

    return {
        "reply": assistant_reply,
        "session_id": msg.session_id,
        "citations": ai_response.get("sources", []),
        "timings": ai_response.get("timings", {})
    }

@router.post("/send_stream")
async def send_message_stream(msg: ChatMessage):
    """
    Endpoint hỗ trợ Streaming cho Frontend.
    """
    create_session(msg.session_id, msg.user_id)
    save_message(msg.session_id, "user", msg.message)
    history_payload = get_session_history(msg.session_id, limit=MAX_HISTORY_TURNS * 2)

    async def stream_generator():
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{AI_ENGINE_URL}/internal/inference_stream",
                json={
                    "query": msg.message,
                    "session_id": msg.session_id,
                    "history": history_payload[:-1],
                    "provider": msg.provider,
                    "google_api_key": msg.api_key,
                    "google_model": msg.google_model,
                }
            ) as response:
                # Gửi ngay dòng đầu tiên để kích hoạt UI
                first_chunk = "### 🛡️ Nexus Legal AI - Tiến trình xử lý:\n"
                yield first_chunk
                print(f"DEBUG: Khởi động stream với chunk đầu tiên: {first_chunk}", flush=True)
                
                full_reply = ""
                # Sử dụng aiter_text() để httpx tự động xử lý decoding UTF-8 chuẩn xác (đặc biệt quan trọng cho tiếng Việt)
                async for chunk in response.aiter_text():
                    full_reply += chunk
                    yield chunk
                
                # Lưu vào DB sau khi kết thúc stream
                if full_reply:
                    save_message(msg.session_id, "assistant", full_reply)

    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream", # Quay lại event-stream để Proxy nhận diện luồng
        headers={
            "X-Accel-Buffering": "no", # Quan trọng nhất cho Nginx
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )
