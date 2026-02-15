"""
L5 Pre-Trade Risk Check — Blocking and Synchronous.

No order reaches the broker without passing this function.
Raises RiskLimitException on first breach.
MUST NOT be mocked in integration tests.
"""

from __future__ import annotations

from typing import Any, Optional

from services.risk.limits.config import RISK_CONFIG
from shared.constants.event_types import EventType
from shared.logging.logger import get_logger

logger = get_logger(__name__)


class RiskLimitException(Exception):
    """Raised when a proposed trade would breach a risk limit."""

    def __init__(
        self,
        reason: str,
        limit_name: str,
        limit_value: float,
        proposed_value: float,
    ) -> None:
        self.reason = reason
        self.limit_name = limit_name
        self.limit_value = limit_value
        self.proposed_value = proposed_value
        super().__init__(f"Risk limit breached: {reason}")


async def pre_trade_check(
    request: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    """
    Run all pre-trade risk checks.

    Raises RiskLimitException on first breach.
    Returns approval dict with warnings if all checks pass.

    Checks (in order of severity):
    1. Hard limits (analyst approval, position size, gross exposure)
    2. Loss trip wires (daily/monthly loss)
    3. Liquidity checks
    4. Soft warnings (sector concentration)
    """
    nav = portfolio.get("total_nav", 0)
    if nav <= 0:
        raise RiskLimitException(
            reason="Portfolio NAV is zero or negative",
            limit_name="nav_positive",
            limit_value=1.0,
            proposed_value=nav,
        )

    notional = request.get("notional_value", 0)
    proposed_size_pct = notional / nav

    # ── HARD STOP: Analyst approval ────────────────────────────
    if not request.get("analyst_approval_id"):
        raise RiskLimitException(
            reason="Analyst approval required for all position entries",
            limit_name="analyst_approval_id",
            limit_value=1.0,
            proposed_value=0.0,
        )

    # ── HARD STOP: Position size ───────────────────────────────
    event_type = request.get("event_type")
    max_pct = _get_max_position_pct(event_type)

    if proposed_size_pct > max_pct:
        raise RiskLimitException(
            reason=f"Position size {proposed_size_pct:.1%} exceeds limit {max_pct:.1%}",
            limit_name="max_position_pct",
            limit_value=max_pct,
            proposed_value=proposed_size_pct,
        )

    # ── HARD STOP: Gross exposure ──────────────────────────────
    new_gross = portfolio.get("gross_exposure", 0) + notional
    gross_pct = new_gross / nav
    if gross_pct > RISK_CONFIG.MAX_GROSS_EXPOSURE:
        raise RiskLimitException(
            reason=f"Gross exposure {gross_pct:.1%} would exceed {RISK_CONFIG.MAX_GROSS_EXPOSURE:.1%}",
            limit_name="max_gross_exposure",
            limit_value=RISK_CONFIG.MAX_GROSS_EXPOSURE,
            proposed_value=gross_pct,
        )

    # ── HARD STOP: Daily loss trip wire ────────────────────────
    daily_pnl_pct = portfolio.get("daily_pnl", 0) / nav
    if daily_pnl_pct < -RISK_CONFIG.MAX_DAILY_LOSS_PCT:
        raise RiskLimitException(
            reason=f"Daily loss {daily_pnl_pct:.1%} exceeds limit. New positions halted.",
            limit_name="max_daily_loss",
            limit_value=RISK_CONFIG.MAX_DAILY_LOSS_PCT,
            proposed_value=abs(daily_pnl_pct),
        )

    # ── HARD STOP: Liquidity ───────────────────────────────────
    adv = request.get("adv_30d", float("inf"))
    if adv < RISK_CONFIG.MIN_ADV_USD:
        raise RiskLimitException(
            reason=f"ADV ${adv:,.0f} below minimum ${RISK_CONFIG.MIN_ADV_USD:,.0f}",
            limit_name="min_adv_usd",
            limit_value=RISK_CONFIG.MIN_ADV_USD,
            proposed_value=adv,
        )

    pct_adv = notional / adv if adv > 0 else float("inf")
    if pct_adv > RISK_CONFIG.MAX_PCT_ADV:
        raise RiskLimitException(
            reason=f"Position is {pct_adv:.0%} of ADV, exceeds {RISK_CONFIG.MAX_PCT_ADV:.0%}",
            limit_name="max_pct_adv",
            limit_value=RISK_CONFIG.MAX_PCT_ADV,
            proposed_value=pct_adv,
        )

    # ── SOFT WARNINGS ──────────────────────────────────────────
    warnings: list[str] = []

    sector_exposure = portfolio.get("sector_exposure", {})
    request_sector = request.get("sector", "Unknown")
    current_sector = sector_exposure.get(request_sector, 0)
    new_sector_pct = (current_sector + notional) / nav
    if new_sector_pct > RISK_CONFIG.MAX_SINGLE_SECTOR_PCT * 0.85:
        warnings.append(
            f"Sector concentration {new_sector_pct:.1%} approaching limit "
            f"({RISK_CONFIG.MAX_SINGLE_SECTOR_PCT:.1%})"
        )

    monthly_loss = portfolio.get("monthly_pnl", 0) / nav
    if monthly_loss < -RISK_CONFIG.MAX_MONTHLY_LOSS_PCT * 0.70:
        warnings.append(
            f"Monthly loss {monthly_loss:.1%} approaching trip wire"
        )

    logger.info(
        "pre_trade_check_passed",
        figi=request.get("figi"),
        position_size_pct=round(proposed_size_pct, 4),
        warnings=len(warnings),
    )

    return {
        "approved": True,
        "analyst_approval_id": request.get("analyst_approval_id"),
        "warnings": warnings,
        "checks_passed": [
            "analyst_approval",
            "position_size",
            "gross_exposure",
            "daily_loss",
            "liquidity",
        ],
        "proposed_size_pct": round(proposed_size_pct, 4),
        "remaining_sector_capacity": round(
            RISK_CONFIG.MAX_SINGLE_SECTOR_PCT - new_sector_pct, 4
        ),
    }


def _get_max_position_pct(event_type: Optional[str]) -> float:
    """Returns appropriate position size limit for an event type."""
    overrides = {
        "MA_ACQUISITION_TARGET": RISK_CONFIG.MAX_MA_ARB_POSITION_PCT,
        "TENDER_OFFER_TARGET": RISK_CONFIG.MAX_MA_ARB_POSITION_PCT,
        "MINE_DEVELOPMENT": RISK_CONFIG.MAX_DEVELOPMENT_MINING_PCT,
        "MINE_EXPLORATION": RISK_CONFIG.MAX_DEVELOPMENT_MINING_PCT,
    }
    return overrides.get(event_type or "", RISK_CONFIG.MAX_POSITION_PCT)
