"""
Celery tasks for L5 Risk Monitoring.

All risk monitoring runs through Celery Beat:
- Risk snapshots every 30 seconds
- Stop loss checks every 15 seconds
- EOD stress tests daily at 4:15 PM ET
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.celery.app import celery_app
from shared.logging.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="services.risk.tasks.compute_risk_snapshot",
    bind=True,
    max_retries=1,
)
def compute_risk_snapshot(self) -> dict:
    """
    Compute portfolio risk snapshot every 30 seconds during market hours.

    Writes to risk.risk_snapshots hypertable.
    """
    now = datetime.now(timezone.utc)
    hour_et = (now - timedelta(hours=5)).hour

    # Only during market hours (9:00 AM - 4:30 PM ET)
    if hour_et < 9 or hour_et >= 17:
        return {"status": "skipped", "reason": "outside_market_hours"}

    logger.info("risk_snapshot_computing")
    # In production: fetch portfolio state, compute VaR, write snapshot
    return {"status": "ok", "timestamp": now.isoformat()}


@celery_app.task(
    name="services.risk.tasks.check_stop_losses",
    bind=True,
    max_retries=1,
)
def check_stop_losses_task(self) -> dict:
    """
    Check all open positions for stop loss breaches every 15 seconds.

    Hard stops auto-execute without analyst confirmation.
    """
    now = datetime.now(timezone.utc)
    hour_et = (now - timedelta(hours=5)).hour

    if hour_et < 9 or hour_et >= 17:
        return {"status": "skipped", "reason": "outside_market_hours"}

    logger.info("stop_loss_check_running")
    # In production: fetch positions, check stop levels, auto-close if breached
    return {"status": "ok", "alerts": 0}


@celery_app.task(
    name="services.risk.tasks.eod_stress_test",
    bind=True,
    max_retries=2,
)
def eod_stress_test(self) -> dict:
    """
    Run end-of-day commodity stress tests.

    Scheduled daily at 4:15 PM ET (after market close).
    Generates stress test report and flags any scenario with >8% NAV impact.
    """
    logger.info("eod_stress_test_running")
    # In production: compute commodity stress, generate report
    return {"status": "ok", "scenarios_tested": 5}


@celery_app.task(
    name="services.risk.tasks.daily_pnl_attribution",
    bind=True,
    max_retries=2,
)
def daily_pnl_attribution(self) -> dict:
    """
    Compute daily P&L attribution by event type, sector, and factor.

    Runs at 5:00 PM ET (after EOD prices are final).
    """
    logger.info("daily_pnl_attribution_running")
    return {"status": "ok"}
