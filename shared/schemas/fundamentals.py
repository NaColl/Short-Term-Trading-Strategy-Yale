"""
Fundamental analysis schemas — L3 output types.

These models represent the deep, fundamentals-anchored analysis that
distinguishes APEX from momentum-only systems. Every position must be
backed by a FundamentalSnapshot.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class FundamentalSnapshot(BaseModel):
    """
    Complete fundamental profile for a security at a point in time.

    Created by the Fundamental Engine (L3) after event detection triggers
    enrichment. This is the anchor that prevents APEX from taking positions
    without fundamental support.

    Rule: No position without a FundamentalSnapshot. If L3 fails to produce
    one, the event stays in 'enriching' status and is never promoted to
    'signal_generated'.

    DB table: fundamentals.snapshots
    """

    id: UUID = Field(default_factory=uuid4)
    figi: str = Field(..., min_length=12, max_length=12)
    event_id: UUID = Field(
        ..., description="The CorporateEvent that triggered this analysis"
    )
    snapshot_date: datetime = Field(default_factory=datetime.utcnow)

    # ── Financial Data (from SEC XBRL) ───────────────────────
    revenue_ttm: Optional[Decimal] = Field(None, description="Trailing 12-month revenue")
    ebitda_ttm: Optional[Decimal] = Field(None, description="Trailing 12-month EBITDA")
    net_income_ttm: Optional[Decimal] = Field(None, description="Trailing 12-month net income")
    free_cash_flow_ttm: Optional[Decimal] = Field(
        None, description="Trailing 12-month free cash flow"
    )
    total_debt: Optional[Decimal] = Field(None, description="Total debt outstanding")
    cash_and_equivalents: Optional[Decimal] = Field(None, description="Cash + short-term investments")
    net_debt: Optional[Decimal] = Field(None, description="Total debt - cash")
    shares_outstanding: Optional[int] = Field(None, description="Diluted shares outstanding")
    book_value_per_share: Optional[Decimal] = None
    tangible_book_per_share: Optional[Decimal] = None

    # ── Valuation Metrics ────────────────────────────────────
    ev_ebitda: Optional[float] = Field(None, description="EV/EBITDA multiple")
    pe_ratio: Optional[float] = Field(None, description="Price/Earnings ratio")
    pb_ratio: Optional[float] = Field(None, description="Price/Book ratio")
    fcf_yield: Optional[float] = Field(
        None, description="Free cash flow yield (FCF / market cap)"
    )
    dividend_yield: Optional[float] = None
    ev_revenue: Optional[float] = Field(None, description="EV/Revenue multiple")

    # ── Quality Metrics ──────────────────────────────────────
    roic: Optional[float] = Field(None, description="Return on invested capital")
    roe: Optional[float] = Field(None, description="Return on equity")
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    debt_to_ebitda: Optional[float] = None
    interest_coverage: Optional[float] = None
    current_ratio: Optional[float] = None

    # ── Growth ───────────────────────────────────────────────
    revenue_growth_yoy: Optional[float] = None
    ebitda_growth_yoy: Optional[float] = None
    eps_growth_yoy: Optional[float] = None

    # ── Source Tracking ──────────────────────────────────────
    xbrl_filing_accession: Optional[str] = Field(
        None, description="SEC accession number for the XBRL source filing"
    )
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CompsTableEntry(BaseModel):
    """A single comparable company in a comps table."""

    figi: str = Field(..., min_length=12, max_length=12)
    ticker: str
    name: str
    market_cap_usd: Optional[Decimal] = None
    ev_ebitda: Optional[float] = None
    pe_ratio: Optional[float] = None
    ev_revenue: Optional[float] = None
    fcf_yield: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    operating_margin: Optional[float] = None
    net_debt_ebitda: Optional[float] = None
    relevance_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="LLM-assessed relevance as a comparable (0-1)",
    )


class CompsTable(BaseModel):
    """
    Comparable company analysis table.

    The LLM selects and ranks the best comps based on business model,
    end-markets, size, and geography. Relevance score drives weighting
    in implied valuation.
    """

    subject_figi: str = Field(
        ...,
        min_length=12,
        max_length=12,
        description="FIGI of the security being valued",
    )
    event_id: UUID
    comps: list[CompsTableEntry] = Field(
        ...,
        min_length=3,
        max_length=15,
        description="Comparable companies, ordered by relevance",
    )
    implied_ev_ebitda: Optional[float] = Field(
        None,
        description="Relevance-weighted median EV/EBITDA from comps",
    )
    implied_pe: Optional[float] = Field(
        None,
        description="Relevance-weighted median P/E from comps",
    )
    implied_fair_value_per_share: Optional[Decimal] = Field(
        None,
        description="Implied fair value based on comps-derived multiples",
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("comps")
    @classmethod
    def sort_by_relevance(cls, v: list[CompsTableEntry]) -> list[CompsTableEntry]:
        """Ensure comps are ordered by relevance_score descending."""
        return sorted(v, key=lambda c: c.relevance_score, reverse=True)


class ValuationScenario(BaseModel):
    """
    A single scenario in a 3-scenario valuation framework.

    Every event-driven opportunity is valued under bull, base, and bear cases.
    """

    label: Literal["bull", "base", "bear"]
    probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Assigned probability for this scenario",
    )
    target_price: Decimal = Field(
        ..., description="Target price under this scenario"
    )
    return_pct: float = Field(
        ...,
        description="Expected return from current price (%)",
    )
    key_assumptions: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Key assumptions driving this scenario",
    )
    catalyst: Optional[str] = Field(
        None,
        description="Primary catalyst that would realize this scenario",
    )


class ValuationScenarios(BaseModel):
    """
    Three-scenario valuation output.

    Probabilities must sum to 1.0. The probability-weighted expected
    return drives sizing through the Kelly criterion.
    """

    figi: str = Field(..., min_length=12, max_length=12)
    event_id: UUID
    current_price: Decimal
    scenarios: list[ValuationScenario] = Field(
        ..., min_length=3, max_length=3
    )
    expected_return: float = Field(
        ...,
        description="Probability-weighted expected return across all scenarios",
    )
    upside_downside_ratio: float = Field(
        ...,
        description="Bull return / abs(bear return)",
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("scenarios")
    @classmethod
    def validate_probabilities_sum(cls, v: list[ValuationScenario]) -> list[ValuationScenario]:
        """Probabilities must sum to 1.0 ± 0.01 tolerance."""
        total = sum(s.probability for s in v)
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Scenario probabilities must sum to 1.0, got {total:.4f}"
            )
        return v


class MiningNAV(BaseModel):
    """
    Mining-specific Net Asset Value model.

    For resource companies: NAV = Σ(resource_value × recovery × margin)
    discounted at appropriate rate, plus net cash.
    """

    figi: str = Field(..., min_length=12, max_length=12)
    event_id: UUID

    # ── Resource Valuation ───────────────────────────────────
    total_resources_moz: Optional[float] = Field(
        None, description="Total resources in millions of ounces (gold) or equiv"
    )
    total_reserves_moz: Optional[float] = Field(
        None, description="Proven + probable reserves"
    )
    commodity_price_assumption: Optional[Decimal] = Field(
        None, description="Commodity price used in NAV calculation"
    )
    all_in_sustaining_cost: Optional[Decimal] = Field(
        None, description="AISC per ounce/unit for margin calculation"
    )

    # ── NAV Components ───────────────────────────────────────
    mine_nav_usd: Optional[Decimal] = Field(
        None, description="NPV of mine operations"
    )
    exploration_value_usd: Optional[Decimal] = Field(
        None, description="Value of exploration-stage properties"
    )
    net_cash_usd: Optional[Decimal] = Field(None, description="Cash minus debt")
    corporate_adjustment_usd: Optional[Decimal] = Field(
        None, description="Corporate G&A, hedging P&L, etc."
    )

    # ── Totals ───────────────────────────────────────────────
    total_nav_usd: Optional[Decimal] = Field(None, description="Total NAV")
    nav_per_share: Optional[Decimal] = Field(None, description="NAV per share")
    current_price: Optional[Decimal] = None
    discount_to_nav_pct: Optional[float] = Field(
        None, description="How cheap vs NAV (positive = trading at discount)"
    )
    discount_rate_pct: float = Field(
        5.0, description="Discount rate used in NPV calculation"
    )

    generated_at: datetime = Field(default_factory=datetime.utcnow)
