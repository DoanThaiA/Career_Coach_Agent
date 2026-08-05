import asyncio
import time
from celery.utils.log import get_task_logger
from celery.exceptions import SoftTimeLimitExceeded

from worker.celery_app import celery_app

logger = get_task_logger(__name__)


_worker_loop = None

def get_or_create_loop():
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop

def _init_services():
    """Lazy-init các service.
    Chỉ khởi tạo 1 lần duy nhất trên mỗi worker process, tái sử dụng cho mọi task."""
    from src.services.extract_service import DocumentExtractService

    if not hasattr(_init_services, "_cache"):
        get_or_create_loop()
        extract_svc = DocumentExtractService()
        _init_services._cache = extract_svc

    return _init_services._cache

@celery_app.task(
    bind=True,
    name="worker.tasks.process_cv",
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
)
def process_cv(self, file_path: str) -> dict:
    """Task trích xuất thông tin CV và lưu vào MongoDB."""
    task_id = self.request.id
    t0 = time.perf_counter()
    logger.info(f"[{task_id}] Bắt đầu xử lý CV: {file_path}")

    try:
        extract_svc = _init_services()
        from src.services.parse_cv import parse_cv
        from src.database.mongodb import MongoDBClient

        # 1. Extract raw text
        self.update_state(state="EXTRACTING", meta={"file_path": file_path})
        document = extract_svc.process_file(file_path)
        raw_text = document.page_content

        # 2. Parse CV using LLM
        self.update_state(state="PARSING_JSON", meta={"file_path": file_path})
        from src.core.monitoring import get_langfuse_handler
        langfuse_handler = get_langfuse_handler(session_id=task_id)
        callbacks = [langfuse_handler] if langfuse_handler else None

        loop = get_or_create_loop()
        cv_data_obj = loop.run_until_complete(parse_cv(raw_text, callbacks=callbacks))
        
        if isinstance(cv_data_obj, dict) and "errors" in cv_data_obj:
            raise ValueError(f"Lỗi parse CV: {cv_data_obj['errors']}")
            
        cv_data = cv_data_obj.model_dump()
        cv_data["original_file_path"] = file_path
        cv_data["task_id"] = task_id

        # 3. Save to MongoDB
        self.update_state(state="SAVING_DB", meta={"file_path": file_path})
        inserted_id = loop.run_until_complete(MongoDBClient.insert_cv(cv_data))

        elapsed = round(time.perf_counter() - t0, 2)
        logger.info(f"[{task_id}] Hoàn thành xử lý CV trong {elapsed}s. MongoDB ID: {inserted_id}")

        return {
            "status": "success",
            "task_id": task_id,
            "type": "cv",
            "mongodb_id": inserted_id,
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Lỗi xử lý CV: {exc}", exc_info=True)
        return {
            "status": "failed",
            "task_id": task_id,
            "type": "cv",
            "error": str(exc),
        }

@celery_app.task(
    bind=True,
    name="worker.tasks.process_jd",
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
)
def process_jd(self, file_path: str) -> dict:
    """Task trích xuất thông tin JD và lưu vào MongoDB."""
    task_id = self.request.id
    t0 = time.perf_counter()
    logger.info(f"[{task_id}] Bắt đầu xử lý JD: {file_path}")

    try:
        extract_svc = _init_services()
        from src.services.parse_jd import parse_jd
        from src.database.mongodb import MongoDBClient

        # 1. Extract raw text
        self.update_state(state="EXTRACTING", meta={"file_path": file_path})
        document = extract_svc.process_file(file_path)
        raw_text = document.page_content

        # 2. Parse JD using LLM
        self.update_state(state="PARSING_JSON", meta={"file_path": file_path})
        from src.core.monitoring import get_langfuse_handler
        langfuse_handler = get_langfuse_handler(session_id=task_id)
        callbacks = [langfuse_handler] if langfuse_handler else None

        loop = get_or_create_loop()
        jd_data_obj = loop.run_until_complete(parse_jd(raw_text, callbacks=callbacks))
        
        if isinstance(jd_data_obj, dict) and "errors" in jd_data_obj:
            raise ValueError(f"Lỗi parse JD: {jd_data_obj['errors']}")
            
        jd_data = jd_data_obj.model_dump()
        jd_data["original_file_path"] = file_path
        jd_data["task_id"] = task_id

        # 3. Save to MongoDB
        self.update_state(state="SAVING_DB", meta={"file_path": file_path})
        inserted_id = loop.run_until_complete(MongoDBClient.insert_jd(jd_data))

        elapsed = round(time.perf_counter() - t0, 2)
        logger.info(f"[{task_id}] Hoàn thành xử lý JD trong {elapsed}s. MongoDB ID: {inserted_id}")

        return {
            "status": "success",
            "task_id": task_id,
            "type": "jd",
            "mongodb_id": inserted_id,
            "elapsed_seconds": elapsed,
        }

    except Exception as exc:
        logger.error(f"[{task_id}] Lỗi xử lý JD: {exc}", exc_info=True)
        return {
            "status": "failed",
            "task_id": task_id,
            "type": "jd",
            "error": str(exc),
        }

