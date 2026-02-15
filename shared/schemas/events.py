"""
Corporate event schemas — the core L2 output types.

CorporateEvent is the single most important type in APEX. It flows from
detection → fundamental enrichment → signal generation → analyst review.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.constants.data_sources import DataSource
from shared.constants.event_types import EventCategory, EventType


class CorporateEvent(BaseModel):
    """
    A detected, classified corporate event.

    This is the central record that flows through every layer of APEX.
    Created by L2 (Event Detection), enriched by L3 (Fundamentals),
    scored by L4 (Signals), and reviewed by analyst in L8 (Dashboard).

    DB table: events.corporate_events
    """

    id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    figi: str = Field(
        ...,
        description="OpenFIGI composite identifier for the affected security",
        min_length=12,
        max_length=12,
    )
    ticker: str = Field(..., description="Ticker symbol at time of detection")
    event_type: EventType = Field(
        ..., description="Classified event type from EventType enum"
    )
    event_category: EventCategory = Field(
        ..., description="Broad category for routing and grouping"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM classification confidence score (0.0–1.0)",
    )
    headline: str = Field(
        ...,
        max_length=500,
        description="One-line event headline for analyst dashboard",
    )
    summary: str = Field(
        ...,
        max_length=5000,
        description="LLM-generated summary of the event with key details",
    )
    source: DataSource = Field(
        ..., description="Primary data source that triggered detection"
    )
    source_url: Optional[str] = Field(
        None, description="URL to the source document (EDGAR filing, news article, etc.)"
    )
    source_ref: Optional[str] = Field(
        None,
        description="Source-specific reference ID (e.g., SEC accession number)",
    )

    # ── Deal-Specific Fields ─────────────────────────────────
    deal_value_usd: Optional[Decimal] = Field(
        None, description="Total deal value in USD (for M&A, tenders)"
    )
    premium_pct: Optional[float] = Field(
        None, description="Premium to undisturbed price (%)"
    )
    consideration_type: Optional[Literal["cash", "stock", "mixed"]] = Field(
        None, description="Type of deal consideration"
    )

    # ── Timing ───────────────────────────────────────────────
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When APEX detected this event",
    )
    event_date: Optional[datetime] = Field(
        None, description="When the event actually occurred (if different from detected)"
    )
    expected_close_date: Optional[datetime] = Field(
        None, description="Expected deal close / event resolution date"
    )

    # ── Status & Workflow ────────────────────────────────────
    status: Literal[
        "new",
        "low_confidence",
        "enriching",
        "enriched",
        "signal_generated",
        "analyst_review",
        "approved",
        "rejected",
        "expired",
        "duplicate",
    ] = Field("new", description="Current workflow status")

    # ── Deduplication ────────────────────────────────────────
    dedup_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash for deduplication: hash(figi + event_type + source_ref)",
    )

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        """Round confidence to 4 decimal places."""
        return round(v, 4)

    @model_validator(mode="after")
    def set_category_from_type(self) -> "CorporateEvent":
        """Auto-set event_category based on event_type if they're inconsistent."""
        from shared.constants.event_types import EVENT_METADATA

        if self.event_type in EVENT_METADATA:
            expected_category = EVENT_METADATA[self.event_type].category
            if self.event_category != expected_category:
                self.event_category = expected_category
        return self


class OptionsAnomalyEvent(BaseModel):
    """
    An unusual options flow detection.

    Created by the options-flow scanner when z-score exceeds threshold.
    May or may not have a linked CorporateEvent (if it's pre-event positioning).
    """

    id: UUID = Field(default_factory=uuid4)
    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)

    # ── Options Data ─────────────────────────────────────────
    volume_zscore: float = Field(
        ...,
        ge=0,
        description="Standard deviations above 20-day rolling mean volume",
    )
    put_call_ratio: float = Field(..., ge=0)
    put_call_ratio_zscore: float = Field(
        ...,
        description="Z-score of P/C ratio vs 30-day average",
    )
    dominant_direction: Literal["call", "put", "balanced"] = Field(
        ..., description="Whether unusual flow is skewed call or put"
    )
    largest_trade_premium_usd: Optional[Decimal] = Field(
        None, description="Premium of the single largest unusual trade"
    )
    otm_sweep_detected: bool = Field(
        False, description="Whether OTM call/put sweep pattern detected"
    )

    # ── Classification ───────────────────────────────────────
    has_known_explanation: bool = Field(
        False,
        description="True if LLM found a known catalyst (earnings, news) explaining the flow",
    )
    explanation: Optional[str] = Field(
        None, description="LLM-generated explanation if known catalyst found"
    )
    anomaly_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Composite anomaly score (0-100)",
    )

    # ── Linked Event ─────────────────────────────────────────
    linked_event_id: Optional[UUID] = Field(
        None,
        description="If this anomaly becomes a CorporateEvent, link them",
    )
