"""
Celery Beat schedule — cron definitions for all periodic tasks.

All scheduled tasks are defined here. This is the canonical source
of truth for APEX's time-based automation.
"""

from celery.schedules import crontab

# ── Schedule configuration applied to celery_app.conf.beat_schedule ──

BEAT_SCHEDULE = {
    # ── Data Ingest ──────────────────────────────────────────
    "edgar-poll": {
        "task": "services.ingest.tasks.poll_edgar",
        "schedule": 60.0,  # Every 60 seconds, 24/7
        "options": {"queue": "ingest"},
    },
    "polygon-eod": {
        "task": "services.ingest.tasks.ingest_polygon_eod",
        "schedule": crontab(hour=18, minute=0, day_of_week="1-5"),  # 6 PM ET weekdays
        "options": {"queue": "ingest"},
    },
    "polygon-options-flow": {
        "task": "services.ingest.tasks.scan_options_flow",
        "schedule": 300.0,  # Every 5 minutes (filtered to market hours in task)
        "options": {"queue": "ingest"},
    },
    "commodity-eia-weekly": {
        "task": "services.ingest.tasks.ingest_eia_data",
        "schedule": crontab(hour=11, minute=0, day_of_week="3"),  # Wed 11 AM ET (after EIA release)
        "options": {"queue": "ingest"},
    },
    "commodity-baker-hughes": {
        "task": "services.ingest.tasks.ingest_baker_hughes",
        "schedule": crontab(hour=13, minute=30, day_of_week="5"),  # Fri 1:30 PM ET (after release)
        "options": {"queue": "ingest"},
    },
    "insider-transactions": {
        "task": "services.ingest.tasks.poll_insider_transactions",
        "schedule": 3600.0,  # Every hour during market hours (filtered in task)
        "options": {"queue": "ingest"},
    },

    # ── Risk Monitoring ──────────────────────────────────────
    "risk-snapshot": {
        "task": "services.risk.tasks.compute_risk_snapshot",
        "schedule": 30.0,  # Every 30 seconds (filtered to market hours in task)
        "options": {"queue": "risk"},
    },
    "stop-loss-monitor": {
        "task": "services.risk.tasks.check_stop_losses",
        "schedule": 15.0,  # Every 15 seconds during market hours
        "options": {"queue": "risk"},
    },

    # ── EOD Processes ────────────────────────────────────────
    "eod-report": {
        "task": "services.risk.tasks.generate_eod_report",
        "schedule": crontab(hour=17, minute=30, day_of_week="1-5"),  # 5:30 PM ET weekdays
        "options": {"queue": "risk"},
    },
    "nightly-stress-test": {
        "task": "services.risk.tasks.run_stress_tests",
        "schedule": crontab(hour=20, minute=0, day_of_week="1-5"),  # 8 PM ET weekdays
        "options": {"queue": "risk"},
    },
    "signal-refresh": {
        "task": "services.signals.tasks.refresh_stale_signals",
        "schedule": crontab(hour=6, minute=0, day_of_week="1-5"),  # 6 AM ET pre-market
        "options": {"queue": "signals"},
    },
}
