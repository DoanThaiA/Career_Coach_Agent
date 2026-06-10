from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    GENERAL = "general"
    CV = "cv"
    JD = "jd"


class ProcessDocumentRequest(BaseModel):
    """Request body khi gọi API bằng JSON (truyền file_path trực tiếp)."""
    file_path: str = Field(..., description="Đường dẫn tuyệt đối tới file cần xử lý")



class TaskStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    UPSERTING = "UPSERTING"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"
    RETRY = "RETRY"
    REVOKED = "REVOKED"


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    message: str


class TaskResultResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    status: str
    celery_status: str
    timestamp: datetime
