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
    """Lazy-init các service nặng (OCR model, embedding model, tokenizer, qdrant client).
    Chỉ khởi tạo 1 lần duy nhất trên mỗi worker process, tái sử dụng cho mọi task."""

    from src.services.extract_service import DocumentExtractService
    from src.services.chunking_service import ChunkingService
    from src.services.embedding_service import EmbeddingService
    from src.database.qdrant import QdrantDocumentStore, QdrantConfig

    if not hasattr(_init_services, "_cache"):
        # Make sure the loop is created before initializing services
        # that might bind to the current event loop.
        get_or_create_loop()
        
        extract_svc = DocumentExtractService()
        chunking_svc = ChunkingService()
        embedding_svc = EmbeddingService()
        qdrant_store = QdrantDocumentStore(
            config=QdrantConfig(),
            embedding_service=embedding_svc,
        )
        _init_services._cache = (extract_svc, chunking_svc, qdrant_store)

    return _init_services._cache


@celery_app.task(
    bind=True,
    name="worker.tasks.process_document",
    max_retries=3,
    soft_time_limit=600,
    time_limit=660,
    acks_late=True,
)
def process_document(self, file_path: str) -> dict:
    """Pipeline xử lý tài liệu: Extract → Chunk → Upsert vào Qdrant.

    Args:
        file_path: Đường dẫn tuyệt đối tới file cần xử lý.

    Returns:
        dict chứa kết quả xử lý (status, thống kê, thời gian).
    """
    task_id = self.request.id
    t0 = time.perf_counter()
    logger.info(f"[{task_id}] Bắt đầu xử lý: {file_path}")

    try:
        extract_svc, chunking_svc, qdrant_store = _init_services()

        # ── 1. Extract: file → Document ──
        self.update_state(state="EXTRACTING", meta={"file_path": file_path})
        document = extract_svc.process_file(file_path)
        logger.info(
            f"[{task_id}] Extract xong — {document.metadata.get('total_length', 0)} ký tự"
        )

        # ── 2. Chunk: Document → List[Document] ──
        self.update_state(state="CHUNKING", meta={"file_path": file_path})
        chunks = chunking_svc.process_document(document)
        logger.info(f"[{task_id}] Chunking xong — {len(chunks)} chunks")

        if not chunks:
            logger.warning(f"[{task_id}] Không có chunk nào được tạo, bỏ qua upsert.")
            return {
                "status": "success",
                "task_id": task_id,
                "file_path": file_path,
                "total_chunks": 0,
                "message": "Không trích xuất được nội dung từ tài liệu",
                "elapsed_seconds": round(time.perf_counter() - t0, 2),
            }

        # ── 3. Upsert: List[Document] → Qdrant ──
        self.update_state(
            state="UPSERTING",
            meta={"file_path": file_path, "total_chunks": len(chunks)},
        )
        loop = get_or_create_loop()
        loop.run_until_complete(qdrant_store.upsert_documents(chunks))
        logger.info(f"[{task_id}] Upsert xong — {len(chunks)} chunks vào Qdrant")

        elapsed = round(time.perf_counter() - t0, 2)
        logger.info(f"[{task_id}] Hoàn thành pipeline trong {elapsed}s")

        return {
            "status": "success",
            "task_id": task_id,
            "file_path": file_path,
            "total_chunks": len(chunks),
            "total_length": document.metadata.get("total_length", 0),
            "elapsed_seconds": elapsed,
        }

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_id}] Task bị timeout (soft_time_limit=600s)")
        return {
            "status": "timeout",
            "task_id": task_id,
            "file_path": file_path,
            "error": "Task vượt quá thời gian cho phép (600s)",
        }

    except (FileNotFoundError, ValueError) as exc:
        logger.error(f"[{task_id}] Lỗi input: {exc}")
        return {
            "status": "error",
            "task_id": task_id,
            "file_path": file_path,
            "error": str(exc),
        }

    except Exception as exc:
        elapsed = round(time.perf_counter() - t0, 2)
        logger.error(f"[{task_id}] Lỗi không mong đợi sau {elapsed}s: {exc}", exc_info=True)

        retry_count = self.request.retries
        if retry_count < self.max_retries:
            countdown = 2 ** retry_count * 30  # 30s, 60s, 120s
            logger.info(f"[{task_id}] Retry lần {retry_count + 1}/{self.max_retries} sau {countdown}s")
            raise self.retry(exc=exc, countdown=countdown)

        return {
            "status": "failed",
            "task_id": task_id,
            "file_path": file_path,
            "error": str(exc),
            "retries_exhausted": True,
        }
