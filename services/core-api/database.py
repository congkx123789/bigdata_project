import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger("Database")

DB_PATH = os.path.join(os.path.dirname(__file__), "chat_history.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo cấu trúc bảng nếu chưa có."""
    conn = get_db()
    cursor = conn.cursor()
    
    # Bảng lưu thông tin các phiên chat (Sessions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT DEFAULT 'Tư vấn mới',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Bảng lưu nội dung tin nhắn (Messages)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON sessions(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_id ON chat_messages(session_id)")
    
    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {DB_PATH}")

def create_session(session_id: str, user_id: str, title: str = "Tư vấn mới"):
    """Tạo một phiên chat mới."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO sessions (session_id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to create session: {e}")

def update_session_title(session_id: str, title: str):
    """Cập nhật tiêu đề cho phiên chat (thường lấy từ câu hỏi đầu tiên)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title, session_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to update session title: {e}")

def save_message(session_id: str, role: str, content: str):
    """Lưu tin nhắn vào database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to save message: {e}")

def get_session_history(session_id: str, limit: int = 50):
    """Lấy lịch sử tin nhắn của một session."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch history: {e}")
        return []

def get_user_sessions(user_id: str):
    """Lấy danh sách các phiên chat của một người dùng."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch user sessions: {e}")
        return []

# Initialize on import
init_db()
