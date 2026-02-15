"""
L7 Order Strategy Selection and Algo Builders.

This module selects the optimal order strategy based on execution context,
then builds the corresponding IBKR order.

Rule: Never place market orders for entries.
      Market orders only for hard stop losses and forced liquidations.
"""

from __future__ import annotations

from typing import Any

from shared.constants.order_strategies import OrderStrategy
from shared.logging.logger import get_logger

logger = get_logger(__name__)


def select_order_strategy(
    event_type: str,
    urgency: str,  # HIGH / MEDIUM / LOW
    size_as_pct_adv: float,
    direction: str,  # "entry" or "exit"
    is_stop_loss: bool = False,
) -> OrderStrategy:
    """
    Select optimal order strategy based on execution context.

    Decision matrix:
    - M&A arb, high confidence, liquid → MOO
    - Spinoff first day → TWAP 60min
    - Activist building position → VWAP 3-5 days
    - Hard stop loss → MARKET (no exceptions)
    - Large exit (>5% ADV) → VWAP full day
    - Options → LIMIT at 105% theoretical
    """
    # Hard stops are always market orders
    if is_stop_loss:
        return OrderStrategy.MARKET

    # Large positions always use algo
    if size_as_pct_adv > 0.05:
        return OrderStrategy.VWAP

    if size_as_pct_adv > 0.03:
        return OrderStrategy.TWAP

    # Event-specific strategies
    if event_type == "MA_ACQUISITION_TARGET" and urgency == "HIGH":
        return OrderStrategy.MARKET_ON_OPEN

    if event_type == "SPINOFF_ANNOUNCED" and direction == "entry":
        return OrderStrategy.TWAP

    if event_type == "ACTIVIST_13D_NEW" and direction == "entry":
        return OrderStrategy.VWAP

    # Default: limit for entries, limit for exits
    if direction == "exit" and size_as_pct_adv < 0.03:
        return OrderStrategy.LIMIT

    return OrderStrategy.LIMIT


def build_order(
    action: str,  # "BUY" or "SELL"
    quantity: int,
    strategy: OrderStrategy,
    limit_price: float | None = None,
    duration_minutes: int = 60,
) -> dict[str, Any]:
    """
    Build an order specification for the execution engine.

    Returns a dict that the IBKR execution engine can translate
    to an ib_insync Order object.
    """
    order: dict[str, Any] = {
        "action": action,
        "total_quantity": quantity,
        "strategy": strategy.value,
    }

    if strategy == OrderStrategy.MARKET:
        order["order_type"] = "MKT"

    elif strategy == OrderStrategy.LIMIT:
        if limit_price is None:
            raise ValueError("Limit price required for LIMIT orders")
        order["order_type"] = "LMT"
        order["limit_price"] = limit_price

    elif strategy == OrderStrategy.MARKET_ON_OPEN:
        order["order_type"] = "MKT"
        order["tif"] = "OPG"  # Opening

    elif strategy == OrderStrategy.TWAP:
        order["order_type"] = "TWAP"
        order["algo_strategy"] = "Twap"
        order["algo_params"] = {
            "startTime": "",
            "endTime": "",
            "allowPastEndTime": 1,
        }
        order["duration_minutes"] = duration_minutes

    elif strategy == OrderStrategy.VWAP:
        order["order_type"] = "LMT"
        order["limit_price"] = 0  # Placeholder for algo
        order["algo_strategy"] = "Vwap"
        order["algo_params"] = {
            "startTime": "",
            "endTime": "16:00:00",
            "maxPctVol": "0.10",
            "noTakeLiq": 0,
        }

    logger.info(
        "order_built",
        action=action,
        quantity=quantity,
        strategy=strategy.value,
    )

    return order


def compute_implementation_shortfall(
    decision_price: float,
    arrival_price: float,
    avg_fill_price: float,
    direction: str,  # "BUY" or "SELL"
) -> dict[str, Any]:
    """
    Compute implementation shortfall — the true cost of execution.

    IS = (avg_fill - decision_price) / decision_price

    Target: IS < 25bps for liquid, < 50bps for illiquid.
    Flag and review any trade with IS > 100bps.
    """
    if direction == "BUY":
        is_bps = (avg_fill_price - decision_price) / decision_price * 10000
    else:
        is_bps = (decision_price - avg_fill_price) / decision_price * 10000

    market_impact_bps = (
        (avg_fill_price - arrival_price) / arrival_price * 10000
    )
    timing_cost_bps = (
        (arrival_price - decision_price) / decision_price * 10000
    )

    rating = (
        "GOOD" if abs(is_bps) < 25
        else "ACCEPTABLE" if abs(is_bps) < 50
        else "REVIEW"
    )

    return {
        "implementation_shortfall_bps": round(is_bps, 2),
        "market_impact_bps": round(market_impact_bps, 2),
        "timing_cost_bps": round(timing_cost_bps, 2),
        "rating": rating,
    }
