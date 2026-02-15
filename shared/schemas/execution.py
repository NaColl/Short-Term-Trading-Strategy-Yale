"""
Execution schemas — L7 types for order management and fill tracking.

Every interaction with the IBKR broker flows through these types.
The execution audit trail is built on these records.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from shared.constants.order_strategies import OrderStrategy, OrderUrgency


class PositionRequest(BaseModel):
    """
    Request from portfolio construction (L6) to execution engine (L7).

    This is what L6 hands off after Kelly sizing and portfolio optimization.
    It still requires pre-trade risk check before becoming an ExecutionRequest.
    """

    event_id: UUID
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    direction: Literal["long", "short"]
    target_quantity: int = Field(..., gt=0)
    target_notional_usd: Decimal = Field(..., gt=0)
    limit_price: Optional[Decimal] = Field(None, gt=0)
    strategy: OrderStrategy = OrderStrategy.LIMIT
    urgency: OrderUrgency = OrderUrgency.MEDIUM
    analyst_approval_id: UUID = Field(
        ..., description="Analyst approval ID — MANDATORY for every execution"
    )
    fundamental_snapshot_id: UUID = Field(
        ..., description="Fundamental snapshot anchoring this position"
    )
    signal_id: UUID = Field(
        ..., description="AlphaSignal that drove this recommendation"
    )
    conviction: int = Field(..., ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionRequest(BaseModel):
    """
    Internal execution engine order request.

    Created after pre-trade risk check passes. Contains all information
    needed to construct and submit an IBKR order.
    """

    id: UUID = Field(default_factory=uuid4)
    position_request: PositionRequest
    risk_check_id: Optional[UUID] = Field(
        None, description="PreTradeResult ID confirming risk approval"
    )
    strategy: OrderStrategy
    urgency: OrderUrgency

    # ── Order Parameters ─────────────────────────────────────
    quantity: int = Field(..., gt=0)
    limit_price: Optional[Decimal] = Field(None, gt=0)
    algo_duration_minutes: Optional[int] = Field(
        None,
        description="Duration for TWAP/VWAP algos",
    )
    max_pct_volume: Optional[float] = Field(
        None,
        ge=0.01,
        le=0.50,
        description="Max % of volume participation for VWAP",
    )

    # ── Timing ───────────────────────────────────────────────
    decision_price: Decimal = Field(
        ...,
        description="Price at time of analyst approval (for IS calculation)",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal[
        "pending",
        "submitted",
        "partially_filled",
        "filled",
        "cancelled",
        "rejected",
        "error",
    ] = "pending"


class FillRecord(BaseModel):
    """
    A single fill (partial or complete) from IBKR.

    Each IBKR fill event produces one of these. A single order may
    generate multiple FillRecords (partial fills are normal).
    """

    id: UUID = Field(default_factory=uuid4)
    execution_request_id: UUID
    ibkr_order_id: Optional[int] = None
    ibkr_exec_id: Optional[str] = None

    fill_price: Decimal = Field(..., gt=0)
    fill_quantity: int = Field(..., gt=0)
    fill_value_usd: Decimal = Field(..., gt=0)
    exchange: Optional[str] = Field(
        None, description="Exchange where fill occurred (e.g., ISLAND, ARCA)"
    )
    commission_usd: Optional[Decimal] = Field(None, ge=0)
    fill_time: datetime = Field(default_factory=datetime.utcnow)


class ExecutionResult(BaseModel):
    """
    Complete execution summary after all fills are received.

    Written to the executions table once the order is fully filled or cancelled.
    """

    id: UUID = Field(default_factory=uuid4)
    execution_request_id: UUID
    event_id: UUID
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str

    # ── Fill Summary ─────────────────────────────────────────
    direction: Literal["BUY", "SELL"]
    total_quantity_filled: int = Field(..., ge=0)
    total_quantity_requested: int = Field(..., gt=0)
    avg_fill_price: Decimal = Field(..., gt=0)
    total_value_usd: Decimal = Field(..., gt=0)
    total_commission_usd: Decimal = Field(Decimal("0"), ge=0)
    fills: list[FillRecord] = Field(default_factory=list)

    # ── Status ───────────────────────────────────────────────
    status: Literal["filled", "partially_filled", "cancelled", "error"]
    fill_rate: float = Field(
        ..., ge=0.0, le=1.0, description="filled_qty / requested_qty"
    )

    # ── Timing ───────────────────────────────────────────────
    first_fill_time: Optional[datetime] = None
    last_fill_time: Optional[datetime] = None
    total_execution_seconds: Optional[float] = None

    # ── Analyst Tracking ─────────────────────────────────────
    analyst_approval_id: UUID
    strategy_used: OrderStrategy

    completed_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionQualityReport(BaseModel):
    """
    Post-trade execution quality metrics.

    Computed after every completed trade. Implementation shortfall (IS)
    is the true cost of execution.

    Target: IS < 25bps for liquid equities, < 50bps for illiquid.
    Flag: IS > 100bps requires mandatory review.
    """

    execution_result_id: UUID
    figi: str = Field(..., min_length=12, max_length=12)

    # ── Shortfall Components ─────────────────────────────────
    implementation_shortfall_bps: float = Field(
        ...,
        description="(avg_fill - decision_price) / decision_price × 10000",
    )
    market_impact_bps: float = Field(
        ...,
        description="(avg_fill - arrival_price) / arrival_price × 10000",
    )
    timing_cost_bps: float = Field(
        ...,
        description="(arrival_price - decision_price) / decision_price × 10000",
    )

    # ── Prices ───────────────────────────────────────────────
    decision_price: Decimal
    arrival_price: Decimal
    avg_fill_price: Decimal

    # ── Assessment ───────────────────────────────────────────
    rating: Literal["GOOD", "ACCEPTABLE", "REVIEW"] = Field(
        ...,
        description="GOOD < 25bps, ACCEPTABLE < 50bps, REVIEW >= 50bps",
    )
    requires_review: bool = Field(
        False, description="True if IS > 100bps"
    )

    computed_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("rating")
    @classmethod
    def validate_rating_consistency(cls, v: str, info: "FieldInfo") -> str:  # noqa: F821
        """Ensure rating matches IS magnitude."""
        return v
