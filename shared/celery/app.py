"""
Celery application instance.

All async task processing in APEX runs through this Celery app.
Workers process tasks from named queues (ingest, detection, signals, etc.).
"""

from __future__ import annotations

import os

from celery import Celery

# Broker URL defaults to local Redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "apex",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    # ── Serialization ────────────────────────────────────────
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # ── Time & Timezone ──────────────────────────────────────
    timezone="America/New_York",
    enable_utc=True,

    # ── Task Behavior ────────────────────────────────────────
    task_acks_late=True,              # ACK after completion (not on receive)
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes
    worker_prefetch_multiplier=1,     # One task at a time per worker

    # ── Results ──────────────────────────────────────────────
    result_expires=86400,             # Results expire after 24 hours

    # ── Routing ──────────────────────────────────────────────
    task_routes={
        "services.ingest.*": {"queue": "ingest"},
        "services.detection.*": {"queue": "detection"},
        "services.fundamental.*": {"queue": "fundamental"},
        "services.signals.*": {"queue": "signals"},
        "services.risk.*": {"queue": "risk"},
        "services.execution.*": {"queue": "execution"},
    },

    # ── Beat Schedule (imported from schedule.py) ────────────
    beat_schedule={},  # Populated by schedule.py
)

# Auto-discover tasks in all service modules
celery_app.autodiscover_tasks([
    "services.ingest",
    "services.detection",
    "services.fundamental",
    "services.signals",
    "services.risk",
    "services.execution",
])
