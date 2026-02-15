---
name: quant-signals
description: Use this skill when adding a new alpha factor, building or modifying a PyTorch/ML model, running event studies, computing the composite signal score, or working with the factor library. Trigger when the task involves: BaseFactorCalculator, AlphaSignal, factor IC, event study, PyTorch model training, deal break probability, earnings surprise model, or composite scoring weights.
---

# Quant Signal Framework Skill — antigravity/APEX

The signal framework translates evidence into a numerical edge estimate. It does not make decisions — it quantifies the probability and magnitude of opportunity so the analyst can make a better decision. Every factor must have economic intuition behind it. Every model must be tested out-of-sample before deployment.

---

## Core Principle: No Black Boxes

Every factor must pass three tests before production:
1. **Economic intuition**: Can you explain in one sentence why this factor should predict returns?
2. **Statistical validity**: IC > 0.03 on out-of-sample data; win rate > 52% for direction.
3. **Decay analysis**: The factor's predictive power must decay logically (not spike and crash).

If you can't explain why a factor works, don't add it.

---

## Factor Architecture

### BaseFactorCalculator

All factors implement this interface:

`services/signals/factors/base.py`:
```python
from abc import ABC, abstractmethod
from shared.schemas.events import CorporateEvent
from shared.schemas.fundamentals import FundamentalSnapshot
from shared.schemas.signals import FactorOutput

class BaseFactorCalculator(ABC):
    """
    Base class for all alpha factors.
    
    A factor takes an event + fundamental snapshot and returns a score from -1 to +1.
    +1 = strong LONG signal for the event direction
    -1 = strong SHORT signal (or signal against the expected move)
     0 = no signal / neutral
    
    Factors are stateless. They receive all required data as inputs.
    """
    
    name: str                               # Unique identifier, snake_case
    description: str                        # One sentence economic intuition
    event_types: list[EventType] | None     # None = applies to all events
    requires_options_data: bool = False
    requires_commodity_data: bool = False
    
    @abstractmethod
    def compute(
        self,
        event: CorporateEvent,
        snapshot: FundamentalSnapshot,
        market_data: dict,                  # Current price, volume, ADV
        extra: dict = None,                 # Optional: options chain, commodity data
    ) -> FactorOutput:
        """
        Compute the factor score.
        
        Must return FactorOutput with:
        - score: float in [-1, 1]
        - confidence: float in [0, 1] (how reliable is this score?)
        - inputs_used: dict of values that went into the calculation (for explainability)
        
        Must NEVER raise. If calculation fails, return score=0.0, confidence=0.0.
        """
        ...
    
    def validate_inputs(self, event, snapshot, market_data) -> bool:
        """Returns True if all required inputs are available."""
        return (
            snapshot is not None
            and market_data.get("current_price") is not None
            and market_data.get("adv_30d") is not None
        )
```

### Adding a New Factor

`services/signals/factors/your_new_factor.py`:

```python
from services.signals.factors.base import BaseFactorCalculator
from shared.schemas.signals import FactorOutput
from shared.schemas.events import CorporateEvent
from shared.schemas.fundamentals import FundamentalSnapshot

class ShortInterestMomentumFactor(BaseFactorCalculator):
    """
    Economic intuition: High short interest + positive catalyst = 
    forced short covering amplifies the move. Low short interest on a 
    catalyst means less fuel for the fire.
    
    Score = f(short_interest_pct_float, days_to_cover)
    High SI + high DTC + positive event → score near +1.0
    """
    name = "short_interest_momentum"
    description = "High short interest amplifies catalyst-driven moves via forced covering"
    event_types = None  # Applies to all event types
    
    def compute(
        self, 
        event: CorporateEvent, 
        snapshot: FundamentalSnapshot, 
        market_data: dict,
        extra: dict = None,
    ) -> FactorOutput:
        if not self.validate_inputs(event, snapshot, market_data):
            return FactorOutput(name=self.name, score=0.0, confidence=0.0)
        
        si_pct = market_data.get("short_interest_pct_float")
        dtc = market_data.get("days_to_cover")
        
        if si_pct is None or dtc is None:
            return FactorOutput(name=self.name, score=0.0, confidence=0.2,
                               inputs_used={"missing": "short_interest_data"})
        
        # Score logic: normalized to [-1, 1] range
        # High SI (>15%) + High DTC (>5 days) = max positive score
        # Rationale: more pain for shorts = larger technical move
        si_score = min(si_pct / 20.0, 1.0)        # Caps at 20% SI = max score
        dtc_score = min(dtc / 10.0, 1.0)           # Caps at 10 DTC = max score
        raw_score = (si_score * 0.6 + dtc_score * 0.4)  # SI weighted more
        
        # This factor is directionally positive (short squeeze = upward pressure)
        # Only meaningful for LONG setups; neutral for SHORTS
        direction_adj = 1.0 if event.metadata.get("direction") != "short" else 0.0
        final_score = raw_score * direction_adj
        
        # Confidence is lower when SI data is stale
        data_age_days = market_data.get("si_data_age_days", 30)
        confidence = max(0.3, 1.0 - (data_age_days / 30.0) * 0.5)
        
        return FactorOutput(
            name=self.name,
            score=round(final_score, 4),
            confidence=round(confidence, 4),
            inputs_used={
                "short_interest_pct": si_pct,
                "days_to_cover": dtc,
                "si_data_age_days": data_age_days,
            }
        )
```

Register in `services/signals/factors/__init__.py`:
```python
from services.signals.factors.short_interest import ShortInterestMomentumFactor
from services.signals.factors.ev_discount import EVDiscountToComps
# ... all factors

ALL_FACTORS: list[BaseFactorCalculator] = [
    ShortInterestMomentumFactor(),
    EVDiscountToComps(),
    # Add new factor instance here
]

FACTOR_REGISTRY: dict[str, BaseFactorCalculator] = {
    f.name: f for f in ALL_FACTORS
}
```

---

## Composite Signal Assembly

`services/signals/scoring/composite.py`:

```python
from services.signals.scoring.weights import FACTOR_WEIGHTS_BY_EVENT_TYPE
from shared.schemas.signals import AlphaSignal

def build_composite_signal(
    event: CorporateEvent,
    snapshot: FundamentalSnapshot,
    market_data: dict,
    factor_outputs: list[FactorOutput],
) -> AlphaSignal:
    """
    Combines factor scores into a composite AlphaSignal.
    
    Weighting:
    - Each event type has a custom weight dict for factors
    - Factors not in the weight dict for this event type get weight 0
    - Weights are normalized to sum to 1.0 across active factors
    - Factor confidence modulates its effective weight:
        effective_weight = weight * confidence
    
    Composite score interpretation:
    > 0.70: Strong signal — recommend sizing at full conviction
    0.50-0.70: Medium signal — recommend half-size
    0.30-0.50: Weak signal — monitor only, no position yet
    < 0.30: Noise — do not alert analyst
    """
    weights = FACTOR_WEIGHTS_BY_EVENT_TYPE.get(
        event.event_type, 
        FACTOR_WEIGHTS_BY_EVENT_TYPE["DEFAULT"]
    )
    
    factor_dict = {fo.name: fo for fo in factor_outputs}
    
    weighted_sum = 0.0
    total_weight = 0.0
    
    for factor_name, base_weight in weights.items():
        if factor_name not in factor_dict:
            continue
        fo = factor_dict[factor_name]
        effective_weight = base_weight * fo.confidence
        weighted_sum += fo.score * effective_weight
        total_weight += effective_weight
    
    composite = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    # Map composite score to conviction level (1-5)
    conviction = _score_to_conviction(composite)
    
    return AlphaSignal(
        event_id=event.event_id,
        figi=event.figi,
        factors={fo.name: fo.score for fo in factor_outputs},
        factor_confidences={fo.name: fo.confidence for fo in factor_outputs},
        composite_score=round(composite, 4),
        conviction=conviction,
        direction=_determine_direction(event),
        # Expected returns come from scenario analysis, not the factor scores
        expected_return=snapshot_scenarios.base.upside_pct,
        expected_return_low=snapshot_scenarios.bear.upside_pct,
        expected_return_high=snapshot_scenarios.bull.upside_pct,
        time_horizon_days=EVENT_METADATA[event.event_type].typical_hold_days[1],
    )
```

`services/signals/scoring/weights.py`:
```python
# Event-type-specific factor weights
# Must sum to 1.0 per event type
# Factors not listed get weight 0.0 for this event type

FACTOR_WEIGHTS_BY_EVENT_TYPE: dict[str, dict[str, float]] = {
    "MA_ACQUISITION_TARGET": {
        "deal_quality_score": 0.35,         # Most important: will deal close?
        "ev_discount_to_comps": 0.15,        # Downside if deal breaks
        "short_interest_momentum": 0.10,
        "regulatory_risk": 0.20,
        "financing_quality": 0.20,
    },
    "ACTIVIST_13D_NEW": {
        "activist_filer_quality": 0.30,
        "ev_discount_to_comps": 0.25,
        "short_interest_momentum": 0.15,
        "insider_ownership": 0.15,
        "balance_sheet_quality": 0.15,
    },
    "SPINOFF_ANNOUNCED": {
        "ev_discount_to_comps": 0.30,
        "short_interest_momentum": 0.10,
        "index_inclusion_probability": 0.20,
        "management_incentive_score": 0.20,
        "sotp_discount": 0.20,
    },
    # Add new event types here as you add them to the system
    "DEFAULT": {                             # Fallback for event types without custom weights
        "ev_discount_to_comps": 0.30,
        "short_interest_momentum": 0.20,
        "earnings_revision_momentum": 0.20,
        "balance_sheet_quality": 0.15,
        "insider_conviction": 0.15,
    },
}
```

---

## Event Study Database

Event studies are the historical ground truth for expected returns. They live in the Supabase `signals.event_studies` table and are updated quarterly.

```python
class EventStudyResult(BaseModel):
    event_type: EventType
    subsector: Optional[str]                # None = applies to all subsectors
    n_events: int                           # Sample size
    time_horizon: int                       # Days post-event
    car_mean: float                         # Cumulative Abnormal Return, mean
    car_median: float
    car_std: float
    win_rate: float                         # % of events with positive CAR
    sharpe_event: float                     # Return / vol of event returns
    data_start: date
    data_end: date
    computed_at: datetime

def run_event_study(
    event_type: EventType,
    horizon_days: int = 30,
    subsector: str = None,
) -> EventStudyResult:
    """
    Runs a CAR event study on historical events.
    
    Methodology:
    1. Pull all historical events of this type from events table (status=closed)
    2. For each: compute stock return from T=0 to T=horizon
    3. Compute market-adjusted return (subtract SPY return in same window)
    4. Report mean, median, std, win rate of market-adjusted returns
    
    Walk-forward: Only uses data available before each event's T=0.
    No look-ahead bias.
    """
    ...
```

---

## PyTorch Models

### Model 1: Deal Break Probability

`services/signals/models/deal_break/model.py`:

```python
import torch
import torch.nn as nn
from xgboost import XGBClassifier

class DealBreakPredictor:
    """
    Predicts probability of M&A deal failing before close.
    
    Ensemble: XGBoost (tabular features) + simple NN (for non-linear interactions)
    
    Features (12 total):
    - premium_pct: Announced premium to 30-day VWAP
    - financing_type: 0=cash, 1=stock, 2=mixed (ordinal encoded)
    - acquirer_leverage: Net debt / EBITDA at announcement
    - regulatory_jurisdiction_count: Number of regulatory approvals needed
    - mac_breadth: 1=narrow, 2=standard, 3=broad (ordinal)
    - deal_size_usd_log: Log of deal value (scale invariant)
    - termination_fee_pct: Target termination fee / deal value
    - acquirer_stock_ytd: Acquirer stock return YTD (proxy for currency)
    - target_stock_premium_to_52wk_high: Premium relative to 52-week high
    - vix_at_announcement: Market volatility level at announcement
    - days_to_expected_close: Announced timeline
    - strategic_vs_financial: 1=strategic, 0=financial buyer
    
    Target: 1 = deal breaks, 0 = deal closes
    Training data: Bloomberg M&A deals, US + Canada, 2000-2024, >$50M
    
    Performance:
    - Accuracy: 83% (holdout set)
    - AUC-ROC: 0.91
    - Break precision: 74% (when model says break, correct 74% of time)
    """
    
    def __init__(self, model_path: str = "models/deal_break_xgb_v2.pkl"):
        import pickle
        with open(model_path, "rb") as f:
            self.xgb_model = pickle.load(f)
    
    def predict_proba(self, features: dict) -> float:
        """
        Returns P(deal breaks). 
        Features must match training feature set exactly.
        """
        feature_vector = self._extract_features(features)
        return float(self.xgb_model.predict_proba([feature_vector])[0][1])
    
    def _extract_features(self, raw: dict) -> list[float]:
        """Transforms raw event/market data into model features."""
        return [
            raw["premium_pct"],
            {"cash": 0, "stock": 1, "mixed": 2}.get(raw["financing_type"], 2),
            min(raw.get("acquirer_leverage", 3.0), 10.0),   # Cap at 10x
            raw.get("regulatory_jurisdiction_count", 1),
            {"narrow": 1, "standard": 2, "broad": 3}.get(raw["mac_breadth"], 2),
            np.log1p(raw["deal_size_usd"]),
            raw.get("termination_fee_pct", 0.035),
            raw.get("acquirer_stock_ytd", 0.0),
            raw.get("target_premium_to_52wk", 0.0),
            raw.get("vix_at_announcement", 18.0),
            raw.get("days_to_expected_close", 180),
            1 if raw.get("buyer_type") == "strategic" else 0,
        ]
```

### Model Training Template

All models follow this validation discipline:

```python
# notebooks/model_training/deal_break_v3.py

from sklearn.model_selection import TimeSeriesSplit

def train_with_walk_forward_cv(X, y, dates, n_splits=5):
    """
    ALWAYS use time-series cross-validation for financial models.
    NEVER use random k-fold — it introduces look-ahead bias.
    
    Walk-forward: train on [T0, T1], test on [T1, T2], 
    then train on [T0, T2], test on [T2, T3], etc.
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_aucs = []
    
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        model = XGBClassifier(...)
        model.fit(X_train, y_train)
        
        y_pred = model.predict_proba(X_test)[:, 1]
        auc = roc_auc_score(y_test, y_pred)
        fold_aucs.append(auc)
        logger.info(f"Fold {fold+1}: AUC = {auc:.3f}")
    
    logger.info(f"Mean AUC: {np.mean(fold_aucs):.3f} ± {np.std(fold_aucs):.3f}")
    
    # Minimum bar: mean AUC > 0.70 before deploying any model
    assert np.mean(fold_aucs) > 0.70, "Model does not meet minimum performance bar"
    
    return model, fold_aucs
```

---

## Factor Validation Workflow

Before adding a factor to production, run this notebook template:

```python
# notebooks/factor_research/validate_new_factor.py

def compute_information_coefficient(factor_scores: pd.Series, forward_returns: pd.Series) -> float:
    """
    IC = rank correlation between factor scores and forward returns.
    IC > 0.03: Meaningful signal
    IC > 0.05: Strong signal
    IC < 0: Inverse signal (consider flipping sign)
    """
    from scipy.stats import spearmanr
    ic, _ = spearmanr(factor_scores, forward_returns)
    return ic

# Run IC across rolling 3-month windows (not just one period)
# Rolling IC std should be low (stable factor) and mean should be > 0.03
# Plot IC over time to check for regime breaks and decay
```

---

## Critical Rules

1. **IC > 0.03 on out-of-sample data is the minimum bar for production.** Document the IC in the factor's docstring before merging.
2. **Always use walk-forward (time-series) cross-validation.** Random k-fold is not acceptable for financial ML.
3. **Every factor must return `score=0.0, confidence=0.0` on failure, never raise.** The signal assembly must be resilient to individual factor failures.
4. **Composite scores below 0.30 should not trigger analyst alerts.** This threshold is in `shared/constants/signal_thresholds.py` — do not hardcode it in the scoring service.
5. **Factor weights per event type are in `weights.py` only.** Never hardcode weights in the factor or scoring service.
6. **Retrain models quarterly, not continuously.** Continuous retraining introduces instability. Quarterly scheduled retraining with a new holdout period is the standard.
7. **Document every model's training data range, features, and out-of-sample performance in its docstring.** This is non-negotiable — undocumented models will be removed.
8. **No factor that requires look-ahead data.** If computing a factor requires knowing anything after the event date, it cannot be used live.
