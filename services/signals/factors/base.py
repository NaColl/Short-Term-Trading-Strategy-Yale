"""
L4 Alpha Factor Base Class and Registry.

All factors implement BaseFactorCalculator. Each must:
1. Have economic intuition (documented in description)
2. Return score in [-1, +1], confidence in [0, 1]
3. Never raise — return score=0.0, confidence=0.0 on failure
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from shared.constants.event_types import EventType
from shared.logging.logger import get_logger
from shared.schemas.signals import FactorOutput

logger = get_logger(__name__)


class BaseFactorCalculator(ABC):
    """
    Base class for all alpha factors.

    score: float in [-1, +1]
        +1 = strong LONG signal for the event direction
        -1 = strong SHORT signal (against expected move)
         0 = no signal / neutral

    confidence: float in [0, 1]
        1.0 = high confidence in the score
        0.0 = no confidence (data missing, stale, etc.)

    Factors are stateless. They receive all required data as inputs.
    """

    name: str
    description: str
    event_types: list[EventType] | None = None  # None = all event types
    requires_options_data: bool = False
    requires_commodity_data: bool = False

    @abstractmethod
    def compute(
        self,
        event: dict[str, Any],
        snapshot: dict[str, Any],
        market_data: dict[str, Any],
        extra: dict[str, Any] | None = None,
    ) -> FactorOutput:
        """
        Compute the factor score.

        Must return FactorOutput with score, confidence, inputs_used.
        Must NEVER raise. Return score=0.0, confidence=0.0 on failure.
        """
        ...

    def validate_inputs(
        self,
        event: dict,
        snapshot: dict,
        market_data: dict,
    ) -> bool:
        """Check that minimum data is available."""
        return (
            snapshot is not None
            and market_data.get("current_price") is not None
            and market_data.get("adv_30d") is not None
        )


# ── Built-in Factors ──────────────────────────────────────────────


class EVDiscountToComps(BaseFactorCalculator):
    """
    Economic intuition: Companies trading at a discount to sector comps
    have natural mean-reversion tailwind. Combined with a catalyst (event),
    this discount provides margin of safety and upside potential.
    """
    name = "ev_discount_to_comps"
    description = "Discount to peer group median EV/EBITDA provides margin of safety"

    def compute(self, event, snapshot, market_data, extra=None) -> FactorOutput:
        try:
            if not self.validate_inputs(event, snapshot, market_data):
                return FactorOutput(name=self.name, score=0.0, confidence=0.0)

            discount_pct = snapshot.get("ev_ebitda_discount_pct")
            if discount_pct is None:
                return FactorOutput(name=self.name, score=0.0, confidence=0.2)

            # Normalize: -50% discount → score +1.0; +50% premium → score -1.0
            score = max(-1.0, min(1.0, -discount_pct / 50.0))

            confidence = 0.7 if abs(discount_pct) > 10 else 0.5

            return FactorOutput(
                name=self.name,
                score=round(score, 4),
                confidence=round(confidence, 4),
                inputs_used={"ev_ebitda_discount_pct": discount_pct},
            )
        except Exception:
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)


class ShortInterestMomentum(BaseFactorCalculator):
    """
    Economic intuition: High short interest + positive catalyst =
    forced short covering amplifies the move.
    """
    name = "short_interest_momentum"
    description = "High short interest amplifies catalyst-driven moves via forced covering"

    def compute(self, event, snapshot, market_data, extra=None) -> FactorOutput:
        try:
            if not self.validate_inputs(event, snapshot, market_data):
                return FactorOutput(name=self.name, score=0.0, confidence=0.0)

            si_pct = market_data.get("short_interest_pct_float")
            dtc = market_data.get("days_to_cover")

            if si_pct is None or dtc is None:
                return FactorOutput(
                    name=self.name, score=0.0, confidence=0.2,
                    inputs_used={"missing": "short_interest_data"},
                )

            si_score = min(si_pct / 20.0, 1.0)
            dtc_score = min(dtc / 10.0, 1.0)
            raw_score = si_score * 0.6 + dtc_score * 0.4

            data_age = market_data.get("si_data_age_days", 30)
            confidence = max(0.3, 1.0 - (data_age / 30.0) * 0.5)

            return FactorOutput(
                name=self.name,
                score=round(raw_score, 4),
                confidence=round(confidence, 4),
                inputs_used={
                    "short_interest_pct": si_pct,
                    "days_to_cover": dtc,
                },
            )
        except Exception:
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)


class EarningsRevisionMomentum(BaseFactorCalculator):
    """
    Economic intuition: Upward earnings revisions signal improving
    fundamentals that the market has not fully priced in.
    """
    name = "earnings_revision_momentum"
    description = "Upward earnings revisions signal improving fundamentals"

    def compute(self, event, snapshot, market_data, extra=None) -> FactorOutput:
        try:
            if not self.validate_inputs(event, snapshot, market_data):
                return FactorOutput(name=self.name, score=0.0, confidence=0.0)

            revision_3m = market_data.get("eps_revision_3m_pct")
            if revision_3m is None:
                return FactorOutput(name=self.name, score=0.0, confidence=0.1)

            # Normalize: +20% revision → score +1.0; -20% → score -1.0
            score = max(-1.0, min(1.0, revision_3m / 20.0))
            confidence = 0.6 if abs(revision_3m) > 5 else 0.4

            return FactorOutput(
                name=self.name,
                score=round(score, 4),
                confidence=round(confidence, 4),
                inputs_used={"eps_revision_3m_pct": revision_3m},
            )
        except Exception:
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)


class BalanceSheetQuality(BaseFactorCalculator):
    """
    Economic intuition: Strong balance sheet reduces downside risk
    and provides runway for the event thesis to play out.
    """
    name = "balance_sheet_quality"
    description = "Strong balance sheet reduces risk and provides thesis runway"

    def compute(self, event, snapshot, market_data, extra=None) -> FactorOutput:
        try:
            if not self.validate_inputs(event, snapshot, market_data):
                return FactorOutput(name=self.name, score=0.0, confidence=0.0)

            debt_to_ebitda = snapshot.get("debt_to_ebitda")
            if debt_to_ebitda is None:
                return FactorOutput(name=self.name, score=0.0, confidence=0.2)

            # Low leverage = good: 0x → +1.0; 6x+ → -1.0
            score = max(-1.0, min(1.0, 1.0 - (debt_to_ebitda / 3.0)))
            confidence = 0.7

            return FactorOutput(
                name=self.name,
                score=round(score, 4),
                confidence=round(confidence, 4),
                inputs_used={"debt_to_ebitda": debt_to_ebitda},
            )
        except Exception:
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)


class InsiderConviction(BaseFactorCalculator):
    """
    Economic intuition: Insider buying around catalyst events signals
    that management believes the event is value-accretive.
    """
    name = "insider_conviction"
    description = "Recent insider buying signals management confidence in event outcome"

    def compute(self, event, snapshot, market_data, extra=None) -> FactorOutput:
        try:
            if not self.validate_inputs(event, snapshot, market_data):
                return FactorOutput(name=self.name, score=0.0, confidence=0.0)

            insider_net_90d = market_data.get("insider_net_shares_90d")
            if insider_net_90d is None:
                return FactorOutput(name=self.name, score=0.0, confidence=0.1)

            # Net buying → positive; net selling → negative
            shares_out = snapshot.get("shares_outstanding", 1)
            pct = insider_net_90d / shares_out * 100 if shares_out else 0

            score = max(-1.0, min(1.0, pct / 1.0))  # 1% insider buy → max score
            confidence = 0.5 if abs(pct) > 0.1 else 0.3

            return FactorOutput(
                name=self.name,
                score=round(score, 4),
                confidence=round(confidence, 4),
                inputs_used={"insider_net_pct": round(pct, 4)},
            )
        except Exception:
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)


# ── Factor Registry ──────────────────────────────────────────────

ALL_FACTORS: list[BaseFactorCalculator] = [
    EVDiscountToComps(),
    ShortInterestMomentum(),
    EarningsRevisionMomentum(),
    BalanceSheetQuality(),
    InsiderConviction(),
]

FACTOR_REGISTRY: dict[str, BaseFactorCalculator] = {
    f.name: f for f in ALL_FACTORS
}
