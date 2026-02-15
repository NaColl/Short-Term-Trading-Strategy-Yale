"""
Signal and confidence thresholds — named constants, no magic numbers.

Every threshold referenced in the codebase must be defined here.
"""

# ── Classification Confidence ────────────────────────────────
CONFIDENCE_DISCARD: float = 0.40
"""Below this: event is not written to DB at all."""

CONFIDENCE_LOW: float = 0.65
"""Below this but above DISCARD: written to DB as 'low_confidence', no alert."""

CONFIDENCE_ALERT_PRIORITY_HIGH: float = 0.80
"""At or above: analyst alert with priority 4."""

CONFIDENCE_ALERT_PRIORITY_IMMEDIATE: float = 0.90
"""At or above: analyst alert with priority 5 (immediate)."""

# ── Composite Signal Score ───────────────────────────────────
SIGNAL_NOISE_FLOOR: float = 0.30
"""Below this: considered noise, do not alert analyst."""

SIGNAL_WEAK: float = 0.50
"""Below this but above NOISE_FLOOR: monitor only, no position."""

SIGNAL_MEDIUM: float = 0.70
"""Below this but above WEAK: recommend half-size position."""

SIGNAL_STRONG: float = 0.70
"""At or above: recommend full conviction sizing."""

# ── Conviction Levels ────────────────────────────────────────
CONVICTION_MIN: int = 1
CONVICTION_MAX: int = 5

CONVICTION_THRESHOLDS: dict[int, float] = {
    1: 0.00,   # score >= 0.00 → 1 star
    2: 0.30,   # score >= 0.30 → 2 stars
    3: 0.50,   # score >= 0.50 → 3 stars
    4: 0.70,   # score >= 0.70 → 4 stars
    5: 0.85,   # score >= 0.85 → 5 stars
}

# ── Factor IC Thresholds ─────────────────────────────────────
FACTOR_IC_MINIMUM: float = 0.03
"""Minimum information coefficient for production deployment."""

FACTOR_IC_STRONG: float = 0.05
"""IC above this is considered a strong signal."""

# ── Options Anomaly ──────────────────────────────────────────
OPTIONS_ANOMALY_SCORE_THRESHOLD: int = 75
"""Composite options anomaly score >= this triggers alert (0-100 scale)."""

OPTIONS_VOLUME_ZSCORE_ALERT: float = 4.0
"""Z-score threshold for options volume anomaly alert."""

OPTIONS_VOLUME_ZSCORE_EVENT: float = 5.0
"""Z-score threshold for creating OPTIONS_ANOMALY event."""

# ── Model Performance Gates ──────────────────────────────────
MODEL_MINIMUM_AUC: float = 0.70
"""Minimum AUC-ROC on walk-forward validation before model deployment."""

MODEL_MINIMUM_WIN_RATE: float = 0.52
"""Minimum directional win rate for any production factor."""

# ── Execution Quality ───────────────────────────────────────
IS_GOOD_BPS: float = 25.0
"""Implementation shortfall below this is 'GOOD'."""

IS_ACCEPTABLE_BPS: float = 50.0
"""Implementation shortfall below this is 'ACCEPTABLE', above is 'REVIEW'."""

IS_FLAG_BPS: float = 100.0
"""Implementation shortfall above this requires mandatory review."""

# ── Keyword Pre-filter Floor ─────────────────────────────────
KEYWORD_PREFILTER_CONFIDENCE_FLOOR: float = 0.40
"""Events below this confidence after keyword pre-filter are discarded entirely."""
