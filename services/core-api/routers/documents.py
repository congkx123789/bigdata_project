"""
Documents Router: Xử lý upload file và theo dõi trạng thái pipeline.
"""
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/api/documents", tags=["documents"])

class DocumentStatus(BaseModel):
    doc_id: str
    filename: str
    status: str  # Pending | Extracting | Vectorizing | Completed | Error
    uploader: str = "Guest"

# Mock in-memory store
_documents = []

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload luồng bất đồng bộ:
    1. Lưu file gốc vào MinIO.
    2. Ghi record trạng thái 'Pending' vào PostgreSQL.
    3. Push event 'document-uploaded' vào Kafka.
    4. Trả về ngay cho Client mà không chờ xử lý xong.
    """
    doc_id = str(uuid.uuid4())[:8]
    doc = DocumentStatus(doc_id=doc_id, filename=file.filename, status="Pending")
    _documents.append(doc)
    
    # TODO: MinIO upload
    # TODO: PostgreSQL insert
    # TODO: Kafka producer push
    
    return {"message": "Upload thành công, đang xử lý.", "doc_id": doc_id, "status": "Pending"}

@router.get("/pipeline")
async def get_pipeline_status():
    """Lấy danh sách tài liệu và trạng thái pipeline cho Admin Dashboard."""
    if not _documents:
        return {"documents": [
            {"doc_id": "DOC_001", "filename": "BaoCao_Q3.pdf", "status": "Completed", "uploader": "Nguyen Van A"},
            {"doc_id": "DOC_002", "filename": "HopDong.docx", "status": "Vectorizing", "uploader": "Tran Thi B"},
            {"doc_id": "DOC_003", "filename": "VanBan_Co.png", "status": "Extracting", "uploader": "Le Van C"},
            {"doc_id": "DOC_004", "filename": "HuongDan.txt", "status": "Pending", "uploader": "Pham D"},
        ]}
    return {"documents": [d.dict() for d in _documents]}
