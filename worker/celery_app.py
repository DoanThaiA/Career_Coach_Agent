import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from celery import Celery
from src.core.config import settings

celery_app = Celery(
    "document_worker",
    broker = settings.RABBITMQ_URL,
    backend = settings.REDIS_URL,
    include = ["worker.tasks"]
)

celery_app.conf.update(
    task_serializer = "json",
    result_serializer = "json",
    accept_content = ["json"],
    timezone = "Asia/Ho_Chi_Minh",
    enable_utc = False,
    worker_prefetch_multiplier = 1,
    task_acks_late = True,
    task_reject_on_worker_lost = True,
    task_track_started = True,
    result_persistent = True,
    result_expires = 3600,
)