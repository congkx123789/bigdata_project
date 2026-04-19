"""
Chat Router: Quản lý lịch sử chat và giao tiếp với AI Engine.
"""
from collections import defaultdict, deque
import os

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/chats", tags=["chats"])

AI_ENGINE_URL = os.getenv("AI_ENGINE_URL", "http://localhost:8002")
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "12"))

# In-memory conversation store: {session_id: deque([{role, content}, ...])}
# NOTE: đủ tốt cho local/dev. Có thể thay bằng Redis/Postgres sau.
SESSION_MESSAGES: dict[str, deque[dict[str, str]]] = defaultdict(
    lambda: deque(maxlen=MAX_HISTORY_TURNS * 2)
)


class ChatMessage(BaseModel):
    message: str
    session_id: str = "default"
    provider: str = "local"
    api_key: str | None = None
    retrieve_only: bool = False

@router.get("/history")
async def get_history(session_id: str = "default"):
    """Lấy lịch sử chat theo session_id (in-memory)."""
    messages = list(SESSION_MESSAGES.get(session_id, deque()))
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }

@router.post("/send")
async def send_message(msg: ChatMessage):
    """
    Chat flow có memory theo session_id:
    1. Lấy lịch sử hội thoại gần nhất.
    2. Gọi AI Engine với query + history + provider settings.
    3. Lưu user/assistant vào memory.
    """
    session_history = SESSION_MESSAGES[msg.session_id]
    history_payload = list(session_history)

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

    session_history.append({"role": "user", "content": msg.message})
    session_history.append({"role": "assistant", "content": assistant_reply})

    return {
        "reply": assistant_reply,
        "session_id": msg.session_id,
        "sources": ai_response.get("sources", []),
    }
