"""
Order strategy enum for execution type selection.

Maps to IBKR algo strategies and order types. The execution engine uses this
to select the correct order builder.
"""

from enum import Enum


class OrderStrategy(str, Enum):
    """Order execution strategies available to the execution engine."""

    MARKET = "MARKET"
    """Market order. Use ONLY for hard stop losses and forced liquidations."""

    LIMIT = "LIMIT"
    """Standard limit order at specified price."""

    LIMIT_AGGRESSIVE = "LIMIT_AGGRESSIVE"
    """Limit at midpoint + tolerance. For time-sensitive but not urgent entries."""

    MARKET_ON_OPEN = "MOO"
    """Market-on-open. For M&A arb entries in liquid names."""

    MARKET_ON_CLOSE = "MOC"
    """Market-on-close. For rebalancing trades."""

    TWAP = "TWAP"
    """Time-Weighted Average Price algo. For building positions gradually."""

    VWAP = "VWAP"
    """Volume-Weighted Average Price algo. For large exits, illiquid names."""

    TENDER = "TENDER"
    """Direct tender submission via IBKR. For tender offer participation."""


class OrderUrgency(str, Enum):
    """Execution urgency levels that influence strategy selection."""

    HIGH = "HIGH"
    """Must fill today. E.g., M&A arb entry, hard stop hit."""

    MEDIUM = "MEDIUM"
    """Can wait hours. E.g., activist position entry, spinoff day-1."""

    LOW = "LOW"
    """Can wait days. E.g., building activist position, DCA entry."""


class MarketState(str, Enum):
    """Market session state for execution timing."""

    PRE_MARKET = "PRE_MARKET"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    AFTER_HOURS = "AFTER_HOURS"
    CLOSED = "CLOSED"
