"""
Celery application configuration.

Phase 0, Step 0.4: All connection config sourced from app.core.config.settings.
Full Celery setup (queues, routing, task definitions) happens in Step 0.6.
"""

from celery import Celery

from app.core.config import settings

# Use explicit CELERY_BROKER_URL / CELERY_RESULT_BACKEND from env if set,
# otherwise fall back to the derived redis_url.
_broker = settings.celery_broker_url or settings.redis_url
_backend = settings.celery_result_backend or settings.redis_url

celery_app = Celery(
    "inventory_ops",
    broker=_broker,
    backend=_backend,
    include=[],  # Task modules registered in Step 0.6
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_time_limit=settings.celery_task_time_limit,
    task_max_retries=settings.celery_task_max_retries,
    result_expires=settings.celery_result_expires,
)
