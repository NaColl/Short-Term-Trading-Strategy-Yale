"""
L3 Valuation Scenario Builder.

Generates bear/base/bull valuation scenarios from comps multiples
and fundamental data. Scenarios are what the analyst reviews.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.logging.logger import get_logger

logger = get_logger(__name__)


class ValuationScenario(BaseModel):
    """Single valuation scenario with implied price and upside."""
    label: str = Field(description="bear, base, or bull")
    probability: float = Field(ge=0.0, le=1.0)
    ebitda_assumption: float
    multiple_assumption: float
    implied_ev: float
    implied_equity_value: float
    implied_price: float
    upside_pct: float  # vs. current market price


def build_scenarios(
    ebitda_ttm: float,
    net_debt: float,
    shares_outstanding: int,
    current_price: float,
    comps: dict[str, Any],
    guidance: dict[str, Optional[float]] | None = None,
    event_type: str | None = None,
) -> list[ValuationScenario]:
    """
    Generate bear/base/bull valuation scenarios.

    Multiple selection by scenario:
    - Bear: 25th percentile comps multiple
    - Base: Median comps multiple
    - Bull: 75th percentile comps multiple

    EBITDA selection by scenario:
    - Bear: Low guidance or TTM × 0.85
    - Base: Midpoint guidance or TTM × 1.00
    - Bull: High guidance or TTM × 1.15

    Event-specific overrides for M&A targets, spinoffs, etc.
    """
    guidance = guidance or {}

    # EBITDA assumptions
    bear_ebitda = guidance.get("ebitda_low", ebitda_ttm * 0.85)
    base_ebitda = guidance.get("ebitda_mid", ebitda_ttm * 1.00)
    bull_ebitda = guidance.get("ebitda_high", ebitda_ttm * 1.15)

    # Multiple assumptions from comps
    bear_multiple = comps.get("ev_ebitda_p25", 6.0)
    base_multiple = comps.get("implied_ev_ebitda", 8.0)
    bull_multiple = comps.get("ev_ebitda_p75", 10.0)

    # Event-specific adjustments
    if event_type == "MA_ACQUISITION_TARGET":
        bull_multiple = base_multiple * 1.30  # Control premium
    elif event_type == "ACTIVIST_13D_NEW":
        bull_multiple = base_multiple * 1.15  # Strategic value premium

    scenarios = []
    for label, prob, ebitda, multiple in [
        ("bear", 0.25, bear_ebitda, bear_multiple),
        ("base", 0.50, base_ebitda, base_multiple),
        ("bull", 0.25, bull_ebitda, bull_multiple),
    ]:
        implied_ev = ebitda * multiple
        implied_equity = implied_ev - net_debt
        implied_price = implied_equity / shares_outstanding if shares_outstanding else 0
        upside = (implied_price / current_price - 1) * 100 if current_price > 0 else 0

        scenarios.append(
            ValuationScenario(
                label=label,
                probability=prob,
                ebitda_assumption=round(ebitda, 2),
                multiple_assumption=round(multiple, 2),
                implied_ev=round(implied_ev, 2),
                implied_equity_value=round(implied_equity, 2),
                implied_price=round(implied_price, 2),
                upside_pct=round(upside, 2),
            )
        )

    logger.info(
        "scenarios_built",
        bear_price=scenarios[0].implied_price,
        base_price=scenarios[1].implied_price,
        bull_price=scenarios[2].implied_price,
    )

    return scenarios


def expected_value_price(scenarios: list[ValuationScenario]) -> float:
    """Compute probability-weighted expected price from scenarios."""
    return sum(s.probability * s.implied_price for s in scenarios)
