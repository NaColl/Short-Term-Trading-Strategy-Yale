"""
L7 IBKR Connection Management.

One IB() instance per service. Never create multiple connections.
APEX_ENV check is mandatory — paper vs. live is the most critical
distinction in this codebase.

clientId assignments: execution_engine=1, risk_monitor=2, data_feed=3
"""

from __future__ import annotations

import os
from typing import Optional

from shared.logging.logger import get_logger

logger = get_logger(__name__)

# Global IB client — singleton pattern
_ib_client = None


async def get_ib_client():
    """
    Returns the shared IB connection. Creates and connects if not initialized.

    Environment check: If APEX_ENV != "production", connects to paper trading.
    Never connect to live broker in non-production mode.
    """
    global _ib_client

    try:
        from ib_insync import IB
    except ImportError:
        logger.error("ib_insync_not_installed")
        raise ImportError(
            "ib_insync is required for execution. "
            "Install with: pip install ib_insync"
        )

    apex_env = os.environ.get("APEX_ENV", "paper")

    if apex_env == "production":
        port = int(os.environ.get("IBKR_PORT", 4001))  # Live gateway
    else:
        port = int(os.environ.get("IBKR_PORT_PAPER", 4002))  # Paper gateway
        # Extra safety: prevent live port in non-production
        if port in (4001, 7496):
            raise ValueError(
                "Cannot connect to live broker port outside production mode. "
                f"APEX_ENV={apex_env}, port={port}"
            )

    if _ib_client is None or not _ib_client.isConnected():
        _ib_client = IB()
        host = os.environ.get("IBKR_HOST", "127.0.0.1")
        client_id = int(os.environ.get("IBKR_CLIENT_ID", 1))

        logger.info(
            "ibkr_connecting",
            host=host,
            port=port,
            client_id=client_id,
            env=apex_env,
        )

        await _ib_client.connectAsync(
            host=host,
            port=port,
            clientId=client_id,
        )

        logger.info("ibkr_connected", env=apex_env)

    return _ib_client


async def disconnect_ib() -> None:
    """Always call on service shutdown."""
    global _ib_client
    if _ib_client and _ib_client.isConnected():
        _ib_client.disconnect()
        _ib_client = None
        logger.info("ibkr_disconnected")


async def resolve_contract(figi: str, ticker: str, exchange: str = "SMART"):
    """
    Convert FIGI/ticker to a qualified IBKR Contract.

    Always uses SMART routing for best execution.
    Caches resolved contracts in Redis (1-hour TTL).
    """
    from ib_insync import Stock

    ib = await get_ib_client()

    currency = "CAD" if exchange in ("TSX", "TSXV") else "USD"
    primary_exchange = exchange if exchange not in ("SMART",) else ""

    contract = Stock(
        symbol=ticker.replace(".TO", ""),
        exchange="SMART",
        currency=currency,
        primaryExchange=primary_exchange or "",
    )

    qualified = await ib.qualifyContractsAsync(contract)
    if not qualified:
        raise ValueError(
            f"Could not qualify contract for figi={figi}, ticker={ticker}"
        )

    logger.debug("contract_resolved", figi=figi, con_id=qualified[0].conId)
    return qualified[0]
