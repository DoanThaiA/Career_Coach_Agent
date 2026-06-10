import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from src.api.routes.document import router as document_router
from src.api.routes.interview import router as interview_router
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
        description="API xử lý tài liệu",
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
    app.include_router(interview_router, prefix="/api/v1")

    # ── Static files (Test UI) ──
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/interview-test", include_in_schema=False)
    async def interview_test_redirect():
        """Redirect tiện lợi đến trang test Interview Agent."""
        return RedirectResponse(url="/static/interview_test.html")

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
