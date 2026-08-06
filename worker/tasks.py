import asyncio
import time
from celery.utils.log import get_task_logger

from worker.celery_app import celery_app

logger = get_task_logger(__name__)

# ── Persistent event loop per worker process ──────────────────────────────────
# asyncio.run() sẽ đóng loop sau mỗi lần gọi → Motor (async MongoDB driver)
# bị mất loop reference và crash với "Event loop is closed".
# Giải pháp: dùng 1 loop duy nhất, sống suốt vòng đời của worker process.
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    """Trả về event loop của worker, tạo mới nếu chưa có hoặc bị đóng."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
        # Reset MongoDB client để nó bind lại vào loop mới
        try:
            from src.database.mongodb import MongoDBClient
            MongoDBClient._client = None
            MongoDBClient._db = None
        except Exception:
            pass
    return _worker_loop


def _run(coro):
    """Chạy coroutine trên persistent worker loop."""
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)


# ── Service cache (khởi tạo 1 lần per worker process) ────────────────────────
def _get_extract_service():
    """Lazy-init DocumentExtractService, cache cho toàn bộ vòng đời worker."""
    if not hasattr(_get_extract_service, "_instance"):
        from src.services.extract_service import DocumentExtractService
        _get_extract_service._instance = DocumentExtractService()
    return _get_extract_service._instance


# ── Async implementations ────────────────────────────────────────────────────
async def _process_cv_async(file_path: str, task_id: str) -> str:
    """Async implementation của CV processing task."""
    from src.services.parse_cv import parse_cv
    from src.database.mongodb import MongoDBClient
    from src.core.monitoring import get_langfuse_handler

    extract_svc = _get_extract_service()

    # 1. Extract raw text
    document = extract_svc.process_file(file_path)
    raw_text = document.page_content

    # 2. Setup Langfuse tracing
    langfuse_handler = get_langfuse_handler(session_id=task_id)
    config_dict = (
        {"callbacks": [langfuse_handler], "metadata": {"langfuse_session_id": task_id}}
        if langfuse_handler else None
    )

    # 3. Parse CV using LLM
    cv_data_obj = await parse_cv(raw_text, config=config_dict)

    if isinstance(cv_data_obj, dict) and "errors" in cv_data_obj:
        raise ValueError(f"Lỗi parse CV: {cv_data_obj['errors']}")

    cv_data = cv_data_obj.model_dump()
    cv_data["original_file_path"] = file_path
    cv_data["task_id"] = task_id

    # 4. Save to MongoDB
    return await MongoDBClient.insert_cv(cv_data)


async def _process_jd_async(file_path: str, task_id: str) -> str:
    """Async implementation của JD processing task."""
    from src.services.parse_jd import parse_jd
    from src.database.mongodb import MongoDBClient
    from src.core.monitoring import get_langfuse_handler

    extract_svc = _get_extract_service()

    # 1. Extract raw text
    document = extract_svc.process_file(file_path)
    raw_text = document.page_content

    # 2. Setup Langfuse tracing
    langfuse_handler = get_langfuse_handler(session_id=task_id)
    config_dict = (
        {"callbacks": [langfuse_handler], "metadata": {"langfuse_session_id": task_id}}
        if langfuse_handler else None
    )

    # 3. Parse JD using LLM
    jd_data_obj = await parse_jd(raw_text, config=config_dict)

    if isinstance(jd_data_obj, dict) and "errors" in jd_data_obj:
        raise ValueError(f"Lỗi parse JD: {jd_data_obj['errors']}")

    jd_data = jd_data_obj.model_dump()
    jd_data["original_file_path"] = file_path
    jd_data["task_id"] = task_id

    # 4. Save to MongoDB
    return await MongoDBClient.insert_jd(jd_data)


# ── Celery Tasks ─────────────────────────────────────────────────────────────
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
        self.update_state(state="PARSING_JSON", meta={"file_path": file_path})
        inserted_id = _run(_process_cv_async(file_path, task_id))

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
        self.update_state(state="PARSING_JSON", meta={"file_path": file_path})
        inserted_id = _run(_process_jd_async(file_path, task_id))

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
