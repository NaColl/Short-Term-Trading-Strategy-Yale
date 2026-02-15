"""
L5 Risk Configuration — All limits live here.

Never hardcode limits elsewhere. Changes require:
1. Senior review sign-off
2. Documented rationale
3. Test run in paper mode for 5 trading days
4. Git commit message explaining the change reason
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskConfig:
    """
    Centralized risk limits.

    All limits expressed as fraction of NAV (0.0 to 1.0)
    unless otherwise noted.
    """

    # ── Position-level limits ──────────────────────────────────
    MAX_POSITION_PCT: float = 0.08              # 8% max single position
    MAX_MA_ARB_POSITION_PCT: float = 0.05       # 5% for deal arb (deal break risk)
    MAX_DEVELOPMENT_MINING_PCT: float = 0.03    # 3% for pre-production miners
    MAX_OPTIONS_PREMIUM_PCT: float = 0.005      # 0.5% NAV max premium per position
    MAX_SHORT_POSITION_PCT: float = 0.05        # 5% max single short

    # ── Stop losses ────────────────────────────────────────────
    STOP_LOSS_HARD: float = -0.20               # -20% on cost basis → hard stop
    STOP_LOSS_THESIS_BREAK_DAYS: int = 2        # Days to unwind after thesis-break

    # ── Portfolio-level limits ─────────────────────────────────
    MAX_GROSS_EXPOSURE: float = 1.50            # 150% NAV gross
    MAX_NET_EXPOSURE_LONG: float = 0.70         # +70% NAV net
    MAX_NET_EXPOSURE_SHORT: float = -0.30       # -30% NAV net
    MAX_SINGLE_SECTOR_PCT: float = 0.35         # 35% gross in one GICS L2 sector
    MAX_MA_ARB_BOOK_PCT: float = 0.25           # 25% NAV in all deal positions
    MAX_SINGLE_COMMODITY_EXPOSURE: float = 0.20  # 20% NAV price sensitivity

    # ── Risk metrics ───────────────────────────────────────────
    MAX_VAR_95_1D: float = 0.03                 # 3% NAV daily VaR at 95%
    MAX_CVAR_95_1D: float = 0.05                # 5% NAV CVaR at 95%
    MAX_SPX_CORRELATION: float = 0.40           # Rolling 30-day correlation to SPX

    # ── Liquidity limits ───────────────────────────────────────
    MAX_PCT_ADV: float = 0.15                   # Can't own >15% of 30-day ADV
    MIN_ADV_USD: float = 1_000_000              # $1M minimum ADV
    MAX_DAYS_TO_EXIT: int = 10                  # Must exit in 10 trading days

    # ── Loss limits (trip wires) ───────────────────────────────
    MAX_DAILY_LOSS_PCT: float = 0.03            # -3% in one day → halt new positions
    MAX_MONTHLY_LOSS_PCT: float = 0.08          # -8% in one month → drawdown review
    MAX_DRAWDOWN_FROM_PEAK: float = 0.15        # -15% from peak → risk committee


# Singleton — import this everywhere
RISK_CONFIG = RiskConfig()
