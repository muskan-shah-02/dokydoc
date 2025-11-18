# backend/app/worker.py

from celery import Celery
from app.core.config import settings

# Create the Celery app instance
celery_app = Celery(
    "dokydoc_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,  # Changed from CELERY_RESULT_BACKEND_URL
    include=["app.tasks"]  # Point to our tasks file
)

# Configure Celery from our settings object
celery_app.conf.update(
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # This ensures tasks are acknowledged only after they complete,
    # making them more resilient to worker failures.
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
)

if __name__ == "__main__":
    celery_app.start()