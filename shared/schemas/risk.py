"""
Risk management schemas — L5 types.

These models enforce the hard risk limits that protect capital.
PreTradeResult is a blocking gate: no trade passes without it.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class PositionRecord(BaseModel):
    """
    Current state of a single position.

    Maintained in the positions table by the risk monitor.
    Updated on every fill event from the execution engine.
    """

    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    direction: Literal["long", "short"]
    quantity: int = Field(..., description="Shares held (negative for short)")
    avg_entry_price: Decimal
    current_price: Decimal
    market_value_usd: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_pct: float
    weight_pct: float = Field(
        ..., description="Position as % of portfolio NAV"
    )
    sector: Optional[str] = None
    event_id: Optional[UUID] = None
    event_type: Optional[str] = None
    entry_date: datetime
    days_held: int = 0
    stop_loss_price: Optional[Decimal] = None
    target_price: Optional[Decimal] = None


class PortfolioState(BaseModel):
    """
    Complete portfolio snapshot at a point in time.

    Written to the risk_snapshots table every 30 seconds during market hours.
    """

    snapshot_time: datetime = Field(default_factory=datetime.utcnow)
    nav: Decimal = Field(..., description="Net asset value in USD")
    cash: Decimal = Field(..., description="Available cash in USD")
    positions: list[PositionRecord] = Field(default_factory=list)

    # ── Exposure Metrics ─────────────────────────────────────
    gross_exposure: Decimal = Field(
        ..., description="Sum of |position market values|"
    )
    net_exposure: Decimal = Field(
        ..., description="Sum of signed position market values"
    )
    long_exposure: Decimal = Field(..., ge=0)
    short_exposure: Decimal = Field(..., ge=0)
    gross_leverage: float = Field(
        ..., description="Gross exposure / NAV"
    )
    net_leverage: float = Field(
        ..., description="Net exposure / NAV"
    )

    # ── Concentration ────────────────────────────────────────
    largest_position_pct: float = Field(
        ..., description="Largest single position as % of NAV"
    )
    top5_concentration_pct: float = Field(
        ..., description="Top 5 positions as % of NAV"
    )
    sector_exposures: dict[str, float] = Field(
        default_factory=dict,
        description="Sector name → % of NAV",
    )

    # ── P&L ──────────────────────────────────────────────────
    daily_pnl_usd: Decimal = Field(
        Decimal("0"), description="Today's P&L"
    )
    daily_pnl_pct: float = Field(0.0, description="Today's P&L as % of NAV")
    mtd_pnl_pct: float = Field(0.0, description="Month-to-date P&L %")
    ytd_pnl_pct: float = Field(0.0, description="Year-to-date P&L %")

    # ── Risk Metrics ─────────────────────────────────────────
    portfolio_var_1d_95: Optional[Decimal] = Field(
        None, description="1-day 95% Value at Risk"
    )
    portfolio_beta: Optional[float] = Field(
        None, description="Portfolio beta to SPY"
    )
    active_positions_count: int = 0


class RiskSnapshot(BaseModel):
    """
    Lightweight risk summary for real-time monitoring.

    This is what the risk-monitor n8n workflow checks every 30 seconds.
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    nav: Decimal
    gross_leverage: float
    net_leverage: float
    largest_position_pct: float
    largest_sector_pct: float
    daily_pnl_pct: float
    active_positions: int
    breaches: list[str] = Field(
        default_factory=list,
        description="List of limit breaches (e.g., 'GROSS_LEVERAGE_WARNING')",
    )
    status: Literal["OK", "WARNING", "CRITICAL", "HALT"] = "OK"


class PreTradeRequest(BaseModel):
    """
    Input to the pre-trade risk check.

    This is sent BEFORE every order is submitted to the execution engine.
    """

    event_id: UUID
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    direction: Literal["long", "short"]
    quantity: int = Field(..., gt=0)
    limit_price: Decimal = Field(..., gt=0)
    notional_usd: Decimal = Field(
        ..., gt=0, description="quantity × limit_price"
    )
    event_type: str
    sector: Optional[str] = None
    analyst_approval_id: UUID = Field(
        ..., description="Analyst approval record — MANDATORY"
    )


class PreTradeResult(BaseModel):
    """
    Output of the pre-trade risk check.

    If approved=False, the execution engine MUST NOT submit the order.
    There are NO exceptions to this rule.
    """

    approved: bool = Field(
        ..., description="Whether the trade passes all risk checks"
    )
    request: PreTradeRequest
    checks_passed: list[str] = Field(
        default_factory=list,
        description="List of checks that passed",
    )
    checks_failed: list[str] = Field(
        default_factory=list,
        description="List of checks that failed (if any)",
    )
    rejection_reason: Optional[str] = Field(
        None,
        description="Human-readable rejection explanation (if not approved)",
    )
    risk_metrics_at_check: Optional[dict] = Field(
        None,
        description="Portfolio risk state at time of check (for audit)",
    )
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class StopLossAlert(BaseModel):
    """
    Alert generated when a position hits its stop-loss level.

    Stop losses are hard limits — when triggered, the risk engine
    sends a MARKET order (not limit) for certainty of execution.
    """

    id: UUID = Field(default_factory=uuid4)
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    event_id: Optional[UUID] = None
    direction: Literal["long", "short"]
    trigger_price: Decimal
    current_price: Decimal
    stop_type: Literal["initial", "trailing", "time_based", "thesis_break"] = "initial"
    loss_pct: float = Field(
        ..., description="Current loss % from entry"
    )
    recommended_action: Literal["close_full", "reduce_half", "alert_only"] = "close_full"
    triggered_at: datetime = Field(default_factory=datetime.utcnow)


class StressTestScenario(BaseModel):
    """A single stress test scenario definition."""

    name: str = Field(
        ..., description="Scenario name (e.g., '2008_financial_crisis')"
    )
    description: str
    market_shock_pct: float = Field(
        ..., description="Broad market shock to apply (%)"
    )
    sector_shocks: dict[str, float] = Field(
        default_factory=dict,
        description="Sector-specific shocks (sector → %)",
    )
    spread_widening_bps: float = Field(
        0.0, description="Credit spread widening in bps"
    )
    vol_multiplier: float = Field(
        1.0, description="Multiplier for implied vol (e.g., 2.0 = double vol)"
    )


class StressTestReport(BaseModel):
    """
    Results of running stress tests on the current portfolio.

    Run nightly as part of EOD processing. Surface scenarios where
    portfolio loss exceeds defined thresholds.
    """

    id: UUID = Field(default_factory=uuid4)
    portfolio_state: PortfolioState
    scenarios: list[StressTestScenario]
    results: dict[str, float] = Field(
        ...,
        description="Scenario name → estimated portfolio loss %",
    )
    worst_case_loss_pct: float
    worst_case_scenario: str
    passes_stress_test: bool = Field(
        ...,
        description="True if worst case < max drawdown limit",
    )
    run_at: datetime = Field(default_factory=datetime.utcnow)
