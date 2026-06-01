import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, status

from src.api.schemas import (
    ProcessDocumentRequest,
    TaskResponse,
    TaskResultResponse,
    TaskStatus,
)
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def _validate_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng '{ext}' không được hỗ trợ. Chấp nhận: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return ext


# ── POST /documents/upload ──

@router.post(
    "/upload",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload file và gửi vào hàng đợi xử lý",
)
async def upload_document(file: UploadFile = File(...)):
    """Upload file tài liệu, lưu vào disk, gửi task xử lý vào Celery queue.

    - Giới hạn kích thước: {MAX_FILE_SIZE_MB} MB
    - Định dạng hỗ trợ: .pdf, .docx, .txt, .png, .jpg, .jpeg
    """
    # Validate extension
    ext = _validate_extension(file.filename)

    # Validate file size (đọc nhanh content_type header trước, đọc thực tế sau)
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File vượt quá giới hạn {settings.MAX_FILE_SIZE_MB}MB",
        )

    # Lưu file
    upload_dir = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_dir, exist_ok=True)

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"File uploaded: {file.filename} -> {file_path} ({len(content)} bytes)")

    # Gửi task vào Celery
    from worker.tasks import process_document
    task = process_document.delay(file_path)

    return TaskResponse(
        task_id=task.id,
        status=TaskStatus.PENDING,
        message=f"File '{file.filename}' đã được nhận và đang chờ xử lý",
    )


# ── POST /documents/process ──

@router.post(
    "/process",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Gửi file_path có sẵn trên server vào hàng đợi xử lý",
)
async def process_document_by_path(request: ProcessDocumentRequest):
    """Gửi task xử lý cho file đã tồn tại trên server (không cần upload)."""
    file_path = os.path.abspath(request.file_path)

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File không tồn tại: {request.file_path}",
        )

    _validate_extension(file_path)

    from worker.tasks import process_document
    task = process_document.delay(file_path)

    return TaskResponse(
        task_id=task.id,
        status=TaskStatus.PENDING,
        message=f"Task đã được tạo cho file: {request.file_path}",
    )


# ── GET /documents/tasks/{task_id} ──

@router.get(
    "/tasks/{task_id}",
    response_model=TaskResultResponse,
    summary="Kiểm tra trạng thái và kết quả task",
)
async def get_task_status(task_id: str):
    """Lấy trạng thái hiện tại và kết quả (nếu đã xong) của một task."""
    from worker.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)

    response = TaskResultResponse(
        task_id=task_id,
        status=result.state,
    )

    if result.state == "SUCCESS":
        response.result = result.result
    elif result.state == "FAILURE":
        response.error = str(result.result)
    elif result.state in ("EXTRACTING", "CHUNKING", "UPSERTING"):
        response.result = result.info  # meta dict từ update_state

    return response


# ── DELETE /documents/tasks/{task_id} ──

@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Hủy một task đang chờ hoặc đang chạy",
)
async def revoke_task(task_id: str):
    """Hủy task. Nếu task đang chạy, sẽ gửi signal terminate."""
    from worker.celery_app import celery_app
    celery_app.control.revoke(task_id, terminate=True, signal="SIGTERM")

    logger.info(f"Task {task_id} đã được yêu cầu hủy")
    return {"task_id": task_id, "status": "REVOKED", "message": "Task đã được gửi lệnh hủy"}
