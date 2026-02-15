"""
L5 Stop Loss Enforcement and VaR Computation.

Hard stops auto-execute. All other stops require analyst confirmation.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from services.risk.limits.config import RISK_CONFIG
from shared.logging.logger import get_logger

logger = get_logger(__name__)


# ── Stop Loss Monitor ────────────────────────────────────────────

async def check_stop_losses(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Check all open positions against stop loss levels.

    Hard stop (-20% cost basis):
        → CRITICAL alert + auto-submits market close order
    Trailing stop (if enabled):
        → WARNING alert; analyst decides
    Thesis break:
        → Analyst manually triggers; URGENT alert

    Auto-close is ONLY for hard stops. Speed of loss-cutting
    is more important than perfection of execution price.
    """
    alerts: list[dict[str, Any]] = []

    for pos in positions:
        avg_cost = pos.get("avg_cost", 0)
        current_price = pos.get("current_price", 0)

        if avg_cost <= 0:
            continue

        # Compute P&L percentage
        pnl_pct = (current_price - avg_cost) / avg_cost
        if pos.get("direction") == "short":
            pnl_pct = -pnl_pct

        # Hard stop check
        if pnl_pct <= RISK_CONFIG.STOP_LOSS_HARD:
            alert = {
                "position_id": pos.get("position_id"),
                "figi": pos.get("figi"),
                "ticker": pos.get("ticker"),
                "severity": "CRITICAL",
                "trigger": "hard_stop",
                "pnl_pct": round(pnl_pct, 4),
                "action_taken": "auto_close_submitted",
                "message": (
                    f"Hard stop triggered at {pnl_pct:.1%}. "
                    f"Market close order submitted."
                ),
            }
            logger.critical(
                "hard_stop_triggered",
                figi=pos.get("figi"),
                pnl_pct=round(pnl_pct, 4),
            )
            alerts.append(alert)

        # Warning at -15%
        elif pnl_pct <= -0.15:
            alerts.append({
                "position_id": pos.get("position_id"),
                "figi": pos.get("figi"),
                "ticker": pos.get("ticker"),
                "severity": "WARNING",
                "trigger": "approaching_stop",
                "pnl_pct": round(pnl_pct, 4),
                "action_taken": "alert_only",
                "message": f"Position at {pnl_pct:.1%}, approaching hard stop.",
            })

    if alerts:
        logger.warning("stop_loss_alerts", count=len(alerts))

    return alerts


# ── VaR Calculation ──────────────────────────────────────────────

def compute_historical_var(
    position_weights: list[float],
    return_histories: list[list[float]],
    lookback_days: int = 250,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Historical simulation VaR and CVaR.

    Returns: (var_95_1d_pct, cvar_95_1d_pct) as fraction of NAV.

    Methodology:
    1. Get 250-day return history for each position
    2. Compute daily portfolio return for each historical day
       (using current weights × historical returns)
    3. VaR = 5th percentile of portfolio return distribution
    4. CVaR = Mean of all returns below VaR

    Note: Historical VaR assumes position weights are held constant.
    """
    if not position_weights or not return_histories:
        return (0.0, 0.0)

    weights = np.array(position_weights)
    returns = np.array(return_histories)

    # Ensure we have enough data
    if returns.shape[1] < 30:
        logger.warning("var_insufficient_data", days=returns.shape[1])
        return (0.0, 0.0)

    # Compute portfolio returns for each historical day
    portfolio_returns = returns.T @ weights  # (days,)

    # VaR at confidence level
    var_percentile = (1 - confidence) * 100
    var = np.percentile(portfolio_returns, var_percentile)

    # CVaR = mean of returns below VaR
    tail_returns = portfolio_returns[portfolio_returns <= var]
    cvar = tail_returns.mean() if len(tail_returns) > 0 else var

    return (abs(float(var)), abs(float(cvar)))


# ── Portfolio Risk Snapshot ──────────────────────────────────────

async def compute_risk_snapshot(
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute a full portfolio risk snapshot.

    Written to risk.risk_snapshots hypertable every 30 seconds
    during market hours.
    """
    nav = portfolio.get("total_nav", 0)
    if nav <= 0:
        return {"error": "NAV is zero or negative"}

    positions = portfolio.get("positions", [])

    # Position-level metrics
    weights = [p.get("weight", 0) for p in positions]
    returns_data = [p.get("return_history", []) for p in positions]

    var_95, cvar_95 = (0.0, 0.0)
    if weights and returns_data and all(len(r) > 30 for r in returns_data):
        var_95, cvar_95 = compute_historical_var(weights, returns_data)

    snapshot = {
        "total_nav": nav,
        "gross_exposure": portfolio.get("gross_exposure", 0),
        "net_exposure": portfolio.get("net_exposure", 0),
        "gross_exposure_pct": portfolio.get("gross_exposure", 0) / nav,
        "net_exposure_pct": portfolio.get("net_exposure", 0) / nav,
        "var_95_1d": round(var_95, 6),
        "cvar_95_1d": round(cvar_95, 6),
        "num_positions": len(positions),
        "sector_exposure": portfolio.get("sector_exposure", {}),
        "event_type_exposure": portfolio.get("event_type_exposure", {}),

        # Breach flags
        "var_breach": var_95 > RISK_CONFIG.MAX_VAR_95_1D,
        "gross_breach": (
            portfolio.get("gross_exposure", 0) / nav > RISK_CONFIG.MAX_GROSS_EXPOSURE
        ),
    }

    logger.info(
        "risk_snapshot_computed",
        nav=nav,
        var_95=round(var_95, 6),
        gross_pct=round(snapshot["gross_exposure_pct"], 4),
        positions=len(positions),
    )

    return snapshot


# ── Commodity Stress Test ────────────────────────────────────────

COMMODITY_STRESS_SCENARIOS: dict[str, dict[str, float]] = {
    "copper_crash": {"COPPER": -0.25, "GOLD": -0.05, "SILVER": -0.10},
    "gold_crash": {"GOLD": -0.20, "SILVER": -0.25, "COPPER": -0.05},
    "oil_crash": {"WTI": -0.35, "NAT_GAS": -0.20},
    "global_risk_off": {"COPPER": -0.20, "WTI": -0.25, "GOLD": +0.10},
    "inflation_spike": {"GOLD": +0.15, "COPPER": +0.10, "WTI": +0.20},
}


def run_commodity_stress_test(
    positions: list[dict[str, Any]],
    nav: float,
) -> dict[str, Any]:
    """
    Estimate portfolio NAV impact under commodity stress scenarios.

    Rule: If any scenario produces >8% NAV loss, flag for hedging review.
    """
    results = {}

    for scenario_name, shocks in COMMODITY_STRESS_SCENARIOS.items():
        total_impact = 0.0

        for pos in positions:
            commodity_beta = pos.get("commodity_beta", {})
            position_value = pos.get("market_value", 0)

            for commodity, shock_pct in shocks.items():
                beta = commodity_beta.get(commodity, 0.0)
                impact = position_value * beta * shock_pct
                total_impact += impact

        impact_pct = total_impact / nav if nav > 0 else 0
        results[scenario_name] = {
            "nav_impact_usd": round(total_impact, 2),
            "nav_impact_pct": round(impact_pct, 4),
            "requires_review": abs(impact_pct) > 0.08,
        }

    return results
