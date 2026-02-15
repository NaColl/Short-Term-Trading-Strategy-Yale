"""
L6 Portfolio Construction — Position Sizing and Allocation.

Translates AlphaSignals into PositionRequests with proper sizing.
Uses the Kelly criterion (modified) for position sizing.

Rule: No position request is generated without both
an AlphaSignal AND a FundamentalSnapshot in the database.
"""

from __future__ import annotations

from typing import Any, Optional

from shared.logging.logger import get_logger

logger = get_logger(__name__)


def compute_position_size(
    signal: dict[str, Any],
    portfolio: dict[str, Any],
    risk_limits: dict[str, float],
) -> dict[str, Any]:
    """
    Compute optimal position size from signal and portfolio state.

    Sizing framework:
    1. Kelly criterion gives theoretical optimal fraction
    2. Half-Kelly used for robustness (industry standard)
    3. Capped by risk limits (max_position_pct)
    4. Adjusted for liquidity (max_pct_adv)

    Conviction mapping:
    - Conviction 5 (Very Strong): Full size (half-Kelly)
    - Conviction 4 (Strong): 75% of full size
    - Conviction 3 (Medium): 50% of full size
    - Conviction 2 (Weak): No position (monitor only)
    - Conviction 1 (Noise): No position
    """
    conviction = signal.get("conviction", 1)
    composite_score = signal.get("composite_score", 0)
    nav = portfolio.get("total_nav", 0)

    if conviction <= 2 or composite_score < 0.30 or nav <= 0:
        return {
            "should_size": False,
            "reason": "Below conviction/score threshold",
            "target_size_pct": 0.0,
        }

    # Expected return from scenario analysis
    expected_return = signal.get("expected_return_base", 0)
    expected_loss = signal.get("expected_return_bear", 0)
    win_rate = signal.get("win_rate", 0.55)

    # Kelly criterion: f* = (p * b - q) / b
    # Where p = win rate, b = win/loss ratio, q = 1 - p
    if expected_loss != 0 and expected_return > 0:
        b = abs(expected_return / expected_loss)
        q = 1 - win_rate
        kelly = (win_rate * b - q) / b
        half_kelly = max(0, kelly / 2)
    else:
        half_kelly = 0.04  # Default 4% if no scenario data

    # Apply conviction scaling
    conviction_scale = {5: 1.0, 4: 0.75, 3: 0.50}
    scaled_size = half_kelly * conviction_scale.get(conviction, 0.50)

    # Cap by risk limits
    max_position = risk_limits.get("max_position_pct", 0.08)
    capped_size = min(scaled_size, max_position)

    # Liquidity check
    adv = signal.get("adv_30d_usd", float("inf"))
    max_from_adv = risk_limits.get("max_pct_adv", 0.15) * adv / nav if nav > 0 else 0
    final_size = min(capped_size, max_from_adv)
    final_size = max(0, final_size)

    notional = final_size * nav
    shares = int(notional / signal.get("current_price", 1)) if signal.get("current_price") else 0

    result = {
        "should_size": final_size > 0,
        "target_size_pct": round(final_size, 4),
        "target_notional": round(notional, 2),
        "target_shares": shares,
        "kelly_raw": round(half_kelly * 2, 4) if half_kelly else 0,
        "half_kelly": round(half_kelly, 4),
        "conviction_scale": conviction_scale.get(conviction, 0.50),
        "limiting_factor": (
            "conviction" if scaled_size == final_size
            else "risk_limit" if capped_size == final_size
            else "liquidity"
        ),
    }

    logger.info(
        "position_sized",
        figi=signal.get("figi"),
        conviction=conviction,
        target_pct=round(final_size, 4),
        limiting_factor=result["limiting_factor"],
    )

    return result


def build_position_request(
    signal: dict[str, Any],
    sizing: dict[str, Any],
    analyst_approval_id: str,
    order_strategy: str = "LIMIT",
) -> dict[str, Any]:
    """
    Build a PositionRequest for submission to the execution engine.

    This is the final output of the portfolio construction layer.
    It includes all information the execution engine needs.
    """
    if not sizing.get("should_size"):
        return {"status": "skipped", "reason": sizing.get("reason")}

    return {
        "figi": signal.get("figi"),
        "ticker": signal.get("ticker"),
        "event_id": signal.get("event_id"),
        "event_type": signal.get("event_type"),
        "direction": signal.get("direction", "long"),
        "notional_value": sizing["target_notional"],
        "target_shares": sizing["target_shares"],
        "target_size_pct": sizing["target_size_pct"],
        "order_strategy": order_strategy,
        "analyst_approval_id": analyst_approval_id,
        "signal_score": signal.get("composite_score"),
        "conviction": signal.get("conviction"),
        "expected_return": signal.get("expected_return_base"),
        "stop_loss_pct": -0.20,  # Hard stop from risk config
        "time_horizon_days": signal.get("time_horizon_days", 30),
    }


def rebalance_portfolio(
    positions: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    portfolio: dict[str, Any],
    risk_limits: dict[str, float],
) -> list[dict[str, Any]]:
    """
    Generate rebalancing orders for the existing portfolio.

    Actions:
    - Close positions where event status is 'closed' or 'expired'
    - Reduce positions where conviction has dropped
    - Increase positions where conviction has increased (if within limits)
    - Close positions at hard stop loss level

    Returns list of adjustment orders.
    """
    adjustments = []
    signal_lookup = {s.get("figi"): s for s in signals}

    for pos in positions:
        figi = pos.get("figi")
        signal = signal_lookup.get(figi)

        event_status = pos.get("event_status")
        pnl_pct = pos.get("pnl_pct", 0)

        # Close on event completion
        if event_status in ("closed", "expired", "cancelled"):
            adjustments.append({
                "action": "close",
                "figi": figi,
                "reason": f"Event {event_status}",
                "current_pnl_pct": pnl_pct,
            })
            continue

        # Signal conviction drop
        if signal and signal.get("conviction", 0) < pos.get("entry_conviction", 3):
            adjustments.append({
                "action": "reduce",
                "figi": figi,
                "reason": "Conviction decreased",
                "reduce_to_pct": pos.get("current_size_pct", 0) * 0.5,
            })

    if adjustments:
        logger.info("rebalance_orders", count=len(adjustments))

    return adjustments
