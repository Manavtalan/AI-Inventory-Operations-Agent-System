"""
Celery application — minimal scaffold for Phase 0, Step 0.2 (Docker Environment Setup).

Full Celery configuration (queues, routing, task settings, retry policies)
happens in Phase 0, Step 0.6 — Celery Setup.
"""

import os
from celery import Celery

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_db = os.getenv("REDIS_DB", "0")

broker_url = os.getenv("CELERY_BROKER_URL", f"redis://{redis_host}:{redis_port}/{redis_db}")
result_backend = os.getenv("CELERY_RESULT_BACKEND", f"redis://{redis_host}:{redis_port}/{redis_db}")

celery_app = Celery(
    "inventory_ops",
    broker=broker_url,
    backend=result_backend,
    include=[],  # Task modules added in Step 0.6
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
