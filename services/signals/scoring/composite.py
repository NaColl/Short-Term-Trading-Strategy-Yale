"""
L4 Composite Signal Assembly and Factor Weights.

Combines individual factor scores into a single AlphaSignal
with event-type-specific weighting.

Composite score thresholds (from signal_thresholds.py):
> 0.70: Strong — full conviction sizing
0.50-0.70: Medium — half-size
0.30-0.50: Weak — monitor only
< 0.30: Noise — do not alert analyst
"""

from __future__ import annotations

from typing import Any

from shared.logging.logger import get_logger
from shared.schemas.signals import FactorOutput

logger = get_logger(__name__)

# ── Factor Weights by Event Type ──────────────────────────────────

FACTOR_WEIGHTS_BY_EVENT_TYPE: dict[str, dict[str, float]] = {
    "MA_ACQUISITION_TARGET": {
        "ev_discount_to_comps": 0.15,
        "short_interest_momentum": 0.10,
        "balance_sheet_quality": 0.10,
        "insider_conviction": 0.10,
        "deal_quality_score": 0.35,
        "regulatory_risk": 0.20,
    },
    "ACTIVIST_13D_NEW": {
        "ev_discount_to_comps": 0.25,
        "short_interest_momentum": 0.15,
        "balance_sheet_quality": 0.15,
        "insider_conviction": 0.15,
        "activist_filer_quality": 0.30,
    },
    "SPINOFF_ANNOUNCED": {
        "ev_discount_to_comps": 0.30,
        "short_interest_momentum": 0.10,
        "balance_sheet_quality": 0.15,
        "insider_conviction": 0.15,
        "sotp_discount": 0.30,
    },
    "EARNINGS_BEAT": {
        "ev_discount_to_comps": 0.25,
        "earnings_revision_momentum": 0.35,
        "short_interest_momentum": 0.15,
        "balance_sheet_quality": 0.10,
        "insider_conviction": 0.15,
    },
    "DEFAULT": {
        "ev_discount_to_comps": 0.30,
        "short_interest_momentum": 0.20,
        "earnings_revision_momentum": 0.20,
        "balance_sheet_quality": 0.15,
        "insider_conviction": 0.15,
    },
}


def build_composite_signal(
    event_type: str,
    factor_outputs: list[FactorOutput],
    scenarios: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Combine factor scores into a composite signal score.

    Weighting logic:
    - Each event type has custom weight dict for factors
    - Factors not in the weight dict get weight 0
    - Weights are normalized to sum to 1.0 across active factors
    - Factor confidence modulates its effective weight:
        effective_weight = weight × confidence
    """
    weights = FACTOR_WEIGHTS_BY_EVENT_TYPE.get(
        event_type,
        FACTOR_WEIGHTS_BY_EVENT_TYPE["DEFAULT"],
    )

    factor_dict = {fo.name: fo for fo in factor_outputs}

    weighted_sum = 0.0
    total_weight = 0.0
    active_factors = []

    for factor_name, base_weight in weights.items():
        if factor_name not in factor_dict:
            continue

        fo = factor_dict[factor_name]
        effective_weight = base_weight * fo.confidence
        weighted_sum += fo.score * effective_weight
        total_weight += effective_weight
        active_factors.append(factor_name)

    composite = weighted_sum / total_weight if total_weight > 0 else 0.0
    conviction = _score_to_conviction(composite)

    result = {
        "composite_score": round(composite, 4),
        "conviction": conviction,
        "conviction_label": _conviction_label(conviction),
        "active_factors": active_factors,
        "factor_scores": {fo.name: fo.score for fo in factor_outputs},
        "factor_confidences": {fo.name: fo.confidence for fo in factor_outputs},
        "event_type": event_type,
    }

    if scenarios:
        result["expected_return_base"] = scenarios.get("base_upside_pct")
        result["expected_return_bear"] = scenarios.get("bear_upside_pct")
        result["expected_return_bull"] = scenarios.get("bull_upside_pct")

    logger.info(
        "composite_signal_built",
        event_type=event_type,
        composite=round(composite, 4),
        conviction=conviction,
        factors_used=len(active_factors),
    )

    return result


def _score_to_conviction(score: float) -> int:
    """Map composite score to conviction level (1-5)."""
    if score >= 0.80:
        return 5
    elif score >= 0.65:
        return 4
    elif score >= 0.50:
        return 3
    elif score >= 0.30:
        return 2
    else:
        return 1


def _conviction_label(conviction: int) -> str:
    """Human-readable conviction label."""
    labels = {
        5: "Very Strong",
        4: "Strong",
        3: "Medium",
        2: "Weak",
        1: "Noise",
    }
    return labels.get(conviction, "Unknown")
