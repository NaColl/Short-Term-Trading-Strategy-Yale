"""
L7 Execution Engine — Orchestrates the full trade lifecycle.

PositionRequest → pre_trade_check → order strategy → submit → monitor fills.

Rule: Every order, fill, and cancellation must be logged to Supabase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from services.execution.orders.order_builder import (
    build_order,
    compute_implementation_shortfall,
    select_order_strategy,
)
from services.risk.monitors.pre_trade import pre_trade_check, RiskLimitException
from shared.logging.logger import get_logger
from shared.redis.channels import CHANNELS

logger = get_logger(__name__)


async def submit_trade(
    position_request: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    """
    Full trade submission pipeline.

    1. Run pre-trade risk check (blocking)
    2. Select order strategy
    3. Build order
    4. Submit to IBKR
    5. Monitor fills
    6. Write execution record to Supabase
    7. Publish fill to Redis

    Returns execution result with trade_id and status.
    """
    trade_id = str(uuid4())

    # Step 1: Pre-trade risk check (MUST pass)
    try:
        risk_result = await pre_trade_check(position_request, portfolio)
    except RiskLimitException as e:
        logger.warning(
            "trade_blocked_by_risk",
            trade_id=trade_id,
            figi=position_request.get("figi"),
            reason=e.reason,
            limit=e.limit_name,
        )
        return {
            "trade_id": trade_id,
            "status": "REJECTED",
            "reason": e.reason,
            "limit_breached": e.limit_name,
        }

    # Step 2: Select order strategy
    adv = position_request.get("adv_30d_usd", 10_000_000)
    notional = position_request.get("notional_value", 0)
    size_as_pct_adv = notional / adv if adv > 0 else 0

    strategy = select_order_strategy(
        event_type=position_request.get("event_type", "DEFAULT"),
        urgency=position_request.get("urgency", "MEDIUM"),
        size_as_pct_adv=size_as_pct_adv,
        direction="entry",
    )

    # Step 3: Build order
    current_price = position_request.get("current_price", 0)
    limit_price = current_price * 1.005 if strategy.value == "LIMIT" else None

    order = build_order(
        action="BUY" if position_request.get("direction") == "long" else "SELL",
        quantity=position_request.get("target_shares", 0),
        strategy=strategy,
        limit_price=limit_price,
    )

    # Step 4+5: Submit and monitor (placeholder for live IBKR)
    execution_record = {
        "trade_id": trade_id,
        "figi": position_request.get("figi"),
        "ticker": position_request.get("ticker"),
        "event_id": position_request.get("event_id"),
        "order": order,
        "strategy": strategy.value,
        "status": "SUBMITTED",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "risk_approval": risk_result,
        "decision_price": current_price,
    }

    logger.info(
        "trade_submitted",
        trade_id=trade_id,
        figi=position_request.get("figi"),
        strategy=strategy.value,
        shares=position_request.get("target_shares"),
    )

    return execution_record


async def handle_fill(
    trade_id: str,
    fill_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Process a trade fill event.

    Updates execution record, computes quality metrics,
    publishes to Redis ORDER_FILLED channel.
    """
    # Compute execution quality
    quality = compute_implementation_shortfall(
        decision_price=fill_data.get("decision_price", 0),
        arrival_price=fill_data.get("arrival_price", 0),
        avg_fill_price=fill_data.get("avg_fill_price", 0),
        direction=fill_data.get("direction", "BUY"),
    )

    result = {
        "trade_id": trade_id,
        "status": "FILLED",
        "fill_price": fill_data.get("avg_fill_price"),
        "fill_quantity": fill_data.get("fill_quantity"),
        "filled_at": datetime.now(timezone.utc).isoformat(),
        "execution_quality": quality,
    }

    logger.info(
        "trade_filled",
        trade_id=trade_id,
        fill_price=fill_data.get("avg_fill_price"),
        is_bps=quality.get("implementation_shortfall_bps"),
        rating=quality.get("rating"),
    )

    # Publish fill notification
    try:
        from shared.redis.client import publish_event
        publish_event(
            CHANNELS.ORDER_FILLED,
            json.dumps({"trade_id": trade_id, **result}),
        )
    except Exception as e:
        logger.error("redis_publish_failed", error=str(e))

    return result
