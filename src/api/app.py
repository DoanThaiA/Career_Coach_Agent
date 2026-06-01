from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.document import router as document_router
from src.api.schemas import HealthResponse
from src.core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("API server starting up...")
    yield
    logger.info("API server shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Document Processing API",
        description="API xử lý tài liệu: Extract → Chunk → Vector DB (Qdrant)",
        version="1.0.0",
        lifespan=lifespan,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ──
    app.include_router(document_router, prefix="/api/v1")

    # ── Health check ──
    @app.get("/health", response_model=HealthResponse, tags=["Health"])
    async def health_check():
        celery_status = "unknown"
        try:
            from worker.celery_app import celery_app
            inspect = celery_app.control.inspect()
            ping_result = inspect.ping()
            celery_status = "connected" if ping_result else "no_workers"
        except Exception:
            celery_status = "disconnected"

        return HealthResponse(
            status="healthy",
            celery_status=celery_status,
            timestamp=datetime.now(timezone.utc),
        )

    return app


app = create_app()
