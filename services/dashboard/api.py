"""
L8 Analyst Dashboard API.

FastAPI application for the analyst-in-the-loop workflow.
Provides endpoints for event review, signal inspection,
trade approval, and portfolio monitoring.

Rule: Every trade requires analyst approval via this dashboard.
No automated position entry without analyst_approval_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from shared.logging.logger import get_logger

logger = get_logger(__name__)


# ── Event Queue ───────────────────────────────────────────────────

async def get_pending_events(
    status: str = "new",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Fetch events awaiting analyst review.

    Events are sorted by:
    1. Confidence score (desc) — highest confidence first
    2. Detection time (desc) — most recent first
    """
    try:
        from shared.db.client import fetch_many

        events = await fetch_many(
            "events.corporate_events",
            filters={"status": status},
            columns="*",
            order_by="confidence",
            descending=True,
            limit=limit,
        )
        return events
    except Exception as e:
        logger.error("fetch_pending_events_failed", error=str(e))
        return []


async def get_event_detail(event_id: str) -> dict[str, Any]:
    """
    Fetch full event detail including signal, fundamentals, and scenarios.

    Returns a comprehensive view for analyst decision-making:
    - Event metadata and classification
    - Fundamental snapshot
    - Valuation scenarios (bear/base/bull)
    - Signal breakdown by factor
    - Comparable companies
    - Recent related events
    """
    try:
        from shared.db.client import fetch_one

        event = await fetch_one("events.corporate_events", filters={"id": event_id})
        if not event:
            return {"error": "Event not found"}

        # Build the analyst view
        return {
            "event": event,
            "signal": await _get_signal_for_event(event_id),
            "fundamentals": await _get_fundamentals(event.get("figi")),
            "scenarios": await _get_scenarios(event_id),
        }
    except Exception as e:
        logger.error("event_detail_failed", error=str(e))
        return {"error": str(e)}


# ── Trade Approval ────────────────────────────────────────────────

async def approve_trade(
    event_id: str,
    analyst_id: str,
    conviction_override: Optional[int] = None,
    size_override_pct: Optional[float] = None,
    notes: str = "",
) -> dict[str, Any]:
    """
    Analyst approves a trade for a given event.

    Returns an approval record with a unique approval_id.
    This approval_id must be included in the PositionRequest
    for the execution engine to accept the order.

    Optional overrides:
    - conviction_override: Analyst can override system conviction (1-5)
    - size_override_pct: Analyst can specify custom position size
    """
    approval_id = str(uuid4())

    approval = {
        "approval_id": approval_id,
        "event_id": event_id,
        "analyst_id": analyst_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "conviction_override": conviction_override,
        "size_override_pct": size_override_pct,
        "notes": notes,
        "status": "approved",
    }

    logger.info(
        "trade_approved",
        approval_id=approval_id,
        event_id=event_id,
        analyst_id=analyst_id,
    )

    return approval


async def reject_event(
    event_id: str,
    analyst_id: str,
    reason: str,
) -> dict[str, Any]:
    """Analyst rejects an event — no trade will be generated."""
    rejection = {
        "event_id": event_id,
        "analyst_id": analyst_id,
        "rejected_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "status": "rejected",
    }

    logger.info(
        "event_rejected",
        event_id=event_id,
        reason=reason,
    )

    return rejection


# ── Portfolio Monitor ─────────────────────────────────────────────

async def get_portfolio_summary() -> dict[str, Any]:
    """
    Get current portfolio state for dashboard display.

    Returns:
    - NAV, gross/net exposure
    - Position list with P&L
    - Risk metrics (VaR, sector exposure)
    - Active events count
    - Recent fills
    """
    return {
        "nav": 0,
        "gross_exposure": 0,
        "net_exposure": 0,
        "positions": [],
        "risk_snapshot": {},
        "active_events": 0,
        "recent_fills": [],
    }


async def get_risk_dashboard() -> dict[str, Any]:
    """
    Get risk metrics for the risk monitoring panel.

    Returns current risk snapshot with breach indicators.
    """
    return {
        "var_95_1d": 0,
        "cvar_95_1d": 0,
        "gross_exposure_pct": 0,
        "net_exposure_pct": 0,
        "sector_exposure": {},
        "commodity_stress": {},
        "stop_loss_alerts": [],
        "breaches": [],
    }


# ── Internal Helpers ──────────────────────────────────────────────

async def _get_signal_for_event(event_id: str) -> dict[str, Any]:
    """Fetch the AlphaSignal associated with an event."""
    try:
        from shared.db.client import fetch_one
        return await fetch_one("signals.alpha_signals", filters={"event_id": event_id}) or {}
    except Exception:
        return {}


async def _get_fundamentals(figi: str) -> dict[str, Any]:
    """Fetch the latest FundamentalSnapshot for a security."""
    try:
        from shared.db.client import fetch_one
        return await fetch_one("fundamentals.snapshots", filters={"figi": figi}) or {}
    except Exception:
        return {}


async def _get_scenarios(event_id: str) -> list[dict[str, Any]]:
    """Fetch valuation scenarios for an event."""
    try:
        from shared.db.client import fetch_many
        return await fetch_many(
            "fundamentals.valuation_scenarios",
            filters={"event_id": event_id},
            limit=3,
        )
    except Exception:
        return []
