"""
Signal and alpha schemas — L4 output types.

These models represent quantized trading signals derived from
fundamental snapshots, event studies, and ML models. The composite
AlphaSignal drives conviction scoring and position sizing.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from shared.constants.event_types import EventType


class FactorOutput(BaseModel):
    """
    Output of a single alpha factor computation.

    Every factor in the factor library produces one of these.
    Factors with IC < 0.03 on out-of-sample data must not be
    used in production composite scores.
    """

    factor_name: str = Field(
        ..., description="Factor identifier (e.g., 'merger_arb_spread')"
    )
    figi: str = Field(..., min_length=12, max_length=12)
    event_id: UUID
    raw_value: float = Field(
        ..., description="Raw factor value before normalization"
    )
    z_score: float = Field(
        ..., description="Cross-sectional z-score vs. universe"
    )
    percentile: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentile rank in current universe (0-100)",
    )
    signal_direction: Literal["long", "short", "neutral"] = Field(
        ..., description="Implied directional view"
    )
    information_coefficient: Optional[float] = Field(
        None,
        description="Rolling 63-day IC for this factor",
    )
    computed_at: datetime = Field(default_factory=datetime.utcnow)


class AlphaSignal(BaseModel):
    """
    Composite alpha signal that aggregates all factor outputs for an event.

    This is the primary input to the analyst dashboard and position sizing.
    """

    id: UUID = Field(default_factory=uuid4)
    event_id: UUID = Field(
        ..., description="The CorporateEvent this signal is for"
    )
    figi: str = Field(..., min_length=12, max_length=12)
    event_type: EventType

    # ── Composite Score ──────────────────────────────────────
    composite_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Final weighted alpha score (0.0 = no edge, 1.0 = max conviction)",
    )
    conviction: int = Field(
        ...,
        ge=1,
        le=5,
        description="Star rating for analyst display (1-5)",
    )
    direction: Literal["long", "short"] = Field(
        ..., description="Recommended position direction"
    )
    expected_return_annualized: Optional[float] = Field(
        None,
        description="Annualized expected return from scenario analysis",
    )
    win_probability: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Estimated probability of profitable outcome",
    )

    # ── Component Factors ────────────────────────────────────
    factor_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Individual factor z-scores that compose the signal",
    )
    factor_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Weights applied to each factor in the composite",
    )

    # ── ML Model Outputs ─────────────────────────────────────
    ml_deal_break_prob: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="XGBoost deal-break probability (for M&A events)",
    )
    ml_earnings_surprise: Optional[float] = Field(
        None,
        description="LSTM earnings surprise estimate (for earnings events)",
    )

    # ── Metadata ─────────────────────────────────────────────
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(
        "v1.0.0", description="Version of the signal generation model"
    )
    is_stale: bool = Field(
        False, description="True if signal is > 24h old and needs refresh"
    )


class EventStudyResult(BaseModel):
    """
    Historical event study output for a specific event type.

    Used to calibrate expected returns and holding periods.
    """

    event_type: EventType
    sample_size: int = Field(
        ..., ge=10, description="Number of historical events in the study"
    )
    avg_return_1d: float
    avg_return_5d: float
    avg_return_20d: float
    avg_return_60d: float
    median_return_20d: float
    win_rate_20d: float = Field(
        ..., ge=0.0, le=1.0, description="% of events with positive 20-day return"
    )
    volatility_20d: float = Field(
        ..., ge=0, description="Standard deviation of 20-day returns"
    )
    sharpe_20d: Optional[float] = None
    optimal_hold_days: int = Field(
        ..., ge=1, description="Holding period that maximizes Sharpe"
    )
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class OpportunityBrief(BaseModel):
    """
    Complete analyst brief combining event, fundamentals, and signal.

    This is what the analyst sees in the dashboard before approving a trade.
    Must be explainable in one paragraph.
    """

    event_id: UUID
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    event_type: EventType
    headline: str

    # ── Signal Summary ───────────────────────────────────────
    composite_score: float = Field(..., ge=0.0, le=1.0)
    conviction: int = Field(..., ge=1, le=5)
    direction: Literal["long", "short"]
    expected_return_pct: Optional[float] = None
    win_probability: Optional[float] = Field(None, ge=0.0, le=1.0)

    # ── Position Recommendation ──────────────────────────────
    recommended_size_pct: Optional[float] = Field(
        None,
        description="Recommended position size as % of NAV",
    )
    recommended_entry_strategy: Optional[str] = Field(
        None,
        description="Suggested order strategy (e.g., 'VWAP over 2 hours')",
    )

    # ── Fundamental Backing ──────────────────────────────────
    valuation_summary: Optional[str] = Field(
        None,
        max_length=2000,
        description="One-paragraph valuation thesis",
    )
    upside_downside_ratio: Optional[float] = None
    comps_implied_fair_value: Optional[Decimal] = None
    current_price: Optional[Decimal] = None

    # ── Risk Flags ───────────────────────────────────────────
    risk_flags: list[str] = Field(
        default_factory=list,
        description="Risk warnings for analyst attention",
    )

    # ── Key Dates ────────────────────────────────────────────
    key_dates: dict[str, str] = Field(
        default_factory=dict,
        description="Key upcoming dates (e.g., 'tender_deadline': '2024-06-15')",
    )

    generated_at: datetime = Field(default_factory=datetime.utcnow)
