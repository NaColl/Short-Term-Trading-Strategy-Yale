---
name: risk-management
description: Use this skill when modifying risk limits, adding new risk checks, building stress tests, working with portfolio exposure monitoring, or debugging risk-related exceptions. Trigger when the task involves: RiskLimitException, pre_trade_check, position limits, VaR, sector exposure, portfolio stress testing, stop losses, or the risk_snapshots table. ALWAYS read this skill before touching any risk configuration.
---

# Risk Management Skill — antigravity/APEX

Risk management is the system that ensures APEX is still running in 10 years. Every position we don't take because of a risk limit is a cost. Every position we exit early because of a stop loss is a cost. These costs are insurance premiums — they protect the fund from the tail events that end trading operations. Never optimize for eliminating these costs. Optimize for keeping them appropriate to the actual risk.

---

## Architecture

```
Pre-Trade Check (synchronous, blocking)
    ↓ RiskLimitException if any limit breached
Position Monitor (async, continuous)
    ↓ Alerts and auto-closes on breach
Portfolio Monitor (async, every 30s during market hours)
    ↓ Snapshots to risk_snapshots hypertable
EOD Stress Test (batch, nightly)
    ↓ Scenario analysis report
```

The pre-trade check is **blocking and synchronous**. No order reaches the broker without passing it. The position and portfolio monitors are advisory — they generate alerts but do not automatically close positions except for hard stop-loss triggers.

---

## Risk Limits Configuration

All limits live in `services/risk/limits/config.py`. Never hardcode limits elsewhere.

```python
from dataclasses import dataclass
from shared.constants.event_types import EventType

@dataclass(frozen=True)
class RiskConfig:
    """
    All limits are expressed as fraction of NAV (0.0 to 1.0)
    unless otherwise noted.
    
    Changing these values requires:
    1. Senior review sign-off
    2. Documented rationale
    3. Test run in paper mode for 5 trading days
    4. Git commit message explaining the change reason
    """
    
    # Position-level limits
    MAX_POSITION_PCT: float = 0.08              # 8% max single position
    MAX_MA_ARB_POSITION_PCT: float = 0.05       # 5% for deal arb (deal break risk)
    MAX_DEVELOPMENT_MINING_PCT: float = 0.03    # 3% for pre-production miners (binary risk)
    MAX_OPTIONS_PREMIUM_PCT: float = 0.005      # 0.5% of NAV max premium per position
    MAX_SHORT_POSITION_PCT: float = 0.05        # 5% max single short
    
    # Stop losses
    STOP_LOSS_HARD: float = -0.20               # -20% on cost basis → hard stop
    STOP_LOSS_THESIS_BREAK_DAYS: int = 2        # Days to unwind after thesis-break event
    
    # Portfolio-level limits
    MAX_GROSS_EXPOSURE: float = 1.50            # 150% NAV gross
    MAX_NET_EXPOSURE_LONG: float = 0.70         # +70% NAV net
    MAX_NET_EXPOSURE_SHORT: float = -0.30       # -30% NAV net
    MAX_SINGLE_SECTOR_PCT: float = 0.35         # 35% gross in one GICS L2 sector
    MAX_MA_ARB_BOOK_PCT: float = 0.25           # 25% NAV in all deal positions combined
    MAX_SINGLE_COMMODITY_EXPOSURE: float = 0.20 # 20% NAV price sensitivity to one commodity
    
    # Risk metrics
    MAX_VAR_95_1D: float = 0.03                 # 3% of NAV daily VaR at 95%
    MAX_CVAR_95_1D: float = 0.05                # 5% of NAV CVaR at 95%
    MAX_SPX_CORRELATION: float = 0.40           # Rolling 30-day correlation to SPX
    
    # Liquidity limits
    MAX_PCT_ADV: float = 0.15                   # Can't own > 15% of 30-day avg daily volume
    MIN_ADV_USD: float = 1_000_000              # $1M minimum ADV to enter new position
    MAX_DAYS_TO_EXIT: int = 10                  # Must be able to exit in 10 trading days
    
    # Loss limits (trip wires)
    MAX_DAILY_LOSS_PCT: float = 0.03            # -3% in one day → halt new positions, review
    MAX_MONTHLY_LOSS_PCT: float = 0.08          # -8% in one month → drawdown review meeting
    MAX_DRAWDOWN_FROM_PEAK: float = 0.15        # -15% from peak → risk committee escalation

RISK_CONFIG = RiskConfig()                      # Singleton — import this everywhere
```

---

## Pre-Trade Check

`services/risk/monitors/pre_trade.py`:

```python
from services.risk.limits.config import RISK_CONFIG
from shared.schemas.risk import PreTradeRequest, PreTradeResult
from shared.schemas.execution import PositionRequest
from shared.db.client import get_db
import asyncio

class RiskLimitException(Exception):
    """Raised when a proposed trade would breach a risk limit."""
    def __init__(self, reason: str, limit_name: str, limit_value: float, proposed_value: float):
        self.reason = reason
        self.limit_name = limit_name
        self.limit_value = limit_value
        self.proposed_value = proposed_value
        super().__init__(f"Risk limit breached: {reason}")

async def pre_trade_check(
    request: PositionRequest,
    portfolio: PortfolioState,
) -> PreTradeResult:
    """
    Runs all pre-trade risk checks synchronously.
    
    Raises RiskLimitException on first breach.
    Returns PreTradeResult with approval details if all checks pass.
    
    Checks run in order of severity:
    1. Hard limits (position size, gross exposure)
    2. Soft limits with warnings (sector concentration, correlation)
    3. Liquidity checks
    
    This function MUST be called before every order submission.
    MUST NOT be mocked in integration tests.
    """
    nav = portfolio.total_nav
    proposed_size_pct = request.notional_value / nav
    
    # ── HARD STOP: Analyst approval required ─────────────────────────────────
    if not request.analyst_approval_id:
        raise RiskLimitException(
            reason="Analyst approval required for all position entries",
            limit_name="analyst_approval_id",
            limit_value=1.0,
            proposed_value=0.0,
        )
    
    # ── HARD STOP: Position size limits ──────────────────────────────────────
    event = await get_event(request.event_id)
    max_pct = _get_max_position_pct(event.event_type)
    
    if proposed_size_pct > max_pct:
        raise RiskLimitException(
            reason=f"Position size {proposed_size_pct:.1%} exceeds limit {max_pct:.1%} for {event.event_type}",
            limit_name="max_position_pct",
            limit_value=max_pct,
            proposed_value=proposed_size_pct,
        )
    
    # ── HARD STOP: Gross exposure ─────────────────────────────────────────────
    new_gross = portfolio.gross_exposure + request.notional_value
    if new_gross / nav > RISK_CONFIG.MAX_GROSS_EXPOSURE:
        raise RiskLimitException(
            reason=f"Gross exposure {new_gross/nav:.1%} would exceed {RISK_CONFIG.MAX_GROSS_EXPOSURE:.1%} limit",
            limit_name="max_gross_exposure",
            limit_value=RISK_CONFIG.MAX_GROSS_EXPOSURE,
            proposed_value=new_gross / nav,
        )
    
    # ── HARD STOP: Liquidity check ────────────────────────────────────────────
    adv = await get_adv_30d(request.figi)
    if adv < RISK_CONFIG.MIN_ADV_USD:
        raise RiskLimitException(
            reason=f"ADV ${adv:,.0f} below minimum ${RISK_CONFIG.MIN_ADV_USD:,.0f}",
            limit_name="min_adv_usd",
            limit_value=RISK_CONFIG.MIN_ADV_USD,
            proposed_value=adv,
        )
    
    position_as_pct_adv = request.notional_value / adv
    if position_as_pct_adv > RISK_CONFIG.MAX_PCT_ADV:
        raise RiskLimitException(
            reason=f"Position is {position_as_pct_adv:.0%} of ADV, exceeds {RISK_CONFIG.MAX_PCT_ADV:.0%} limit",
            limit_name="max_pct_adv",
            limit_value=RISK_CONFIG.MAX_PCT_ADV,
            proposed_value=position_as_pct_adv,
        )
    
    # ── HARD STOP: Daily loss trip wire ──────────────────────────────────────
    daily_pnl_pct = portfolio.daily_pnl / nav
    if daily_pnl_pct < -RISK_CONFIG.MAX_DAILY_LOSS_PCT:
        raise RiskLimitException(
            reason=f"Daily loss {daily_pnl_pct:.1%} exceeds {-RISK_CONFIG.MAX_DAILY_LOSS_PCT:.1%} limit. New positions halted.",
            limit_name="max_daily_loss",
            limit_value=RISK_CONFIG.MAX_DAILY_LOSS_PCT,
            proposed_value=abs(daily_pnl_pct),
        )
    
    # ── SOFT WARNINGS (logged but do not block) ───────────────────────────────
    warnings = []
    new_sector_pct = _compute_sector_exposure(portfolio, request)
    if new_sector_pct > RISK_CONFIG.MAX_SINGLE_SECTOR_PCT * 0.85:  # Warning at 85% of limit
        warnings.append(f"Sector concentration {new_sector_pct:.1%} approaching limit")
    
    return PreTradeResult(
        approved=True,
        analyst_approval_id=request.analyst_approval_id,
        warnings=warnings,
        checks_passed=["position_size", "gross_exposure", "liquidity", "daily_loss"],
        proposed_size_pct=proposed_size_pct,
        remaining_capacity_this_sector=RISK_CONFIG.MAX_SINGLE_SECTOR_PCT - new_sector_pct,
    )

def _get_max_position_pct(event_type: EventType) -> float:
    """Returns the appropriate position size limit for a given event type."""
    overrides = {
        EventType.MA_ACQUISITION_TARGET: RISK_CONFIG.MAX_MA_ARB_POSITION_PCT,
        EventType.TENDER_OFFER_TARGET: RISK_CONFIG.MAX_MA_ARB_POSITION_PCT,
        EventType.MINE_DEVELOPMENT: RISK_CONFIG.MAX_DEVELOPMENT_MINING_PCT,
        EventType.MINE_EXPLORATION: RISK_CONFIG.MAX_DEVELOPMENT_MINING_PCT,
    }
    return overrides.get(event_type, RISK_CONFIG.MAX_POSITION_PCT)
```

---

## Stop Loss Enforcement

`services/risk/monitors/stop_loss.py`:

```python
async def check_stop_losses(positions: list[PositionSnapshot]) -> list[StopLossAlert]:
    """
    Checks all open positions against stop loss levels.
    
    Hard stop (-20% cost basis): Generates CRITICAL alert + auto-submits market close order.
    Trailing stop (if enabled): Generates WARNING alert; analyst decides.
    Thesis break: Analyst must manually trigger; generates URGENT alert.
    
    Auto-close is only for hard stops. All other stops require analyst confirmation.
    """
    alerts = []
    for pos in positions:
        pnl_pct = (pos.current_price - pos.avg_cost) / pos.avg_cost
        if pos.direction == "short":
            pnl_pct = -pnl_pct
        
        if pnl_pct <= RISK_CONFIG.STOP_LOSS_HARD:
            # Auto-close: submit market order immediately
            await submit_emergency_close(pos)
            alerts.append(StopLossAlert(
                position_id=pos.position_id,
                figi=pos.figi,
                severity="CRITICAL",
                trigger="hard_stop",
                pnl_pct=pnl_pct,
                action_taken="auto_close_submitted",
                message=f"Hard stop triggered at {pnl_pct:.1%}. Market close order submitted.",
            ))
    
    return alerts
```

---

## VaR Calculation

`services/risk/monitors/var.py`:

```python
def compute_historical_var(
    portfolio: PortfolioState,
    lookback_days: int = 250,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """
    Historical simulation VaR and CVaR.
    
    Returns: (var_95_1d_pct, cvar_95_1d_pct) as fraction of NAV.
    
    Methodology:
    1. Get 250-day return history for each position's figi
    2. Compute daily portfolio return for each historical day
       (using current weights × historical returns)
    3. VaR = 5th percentile of portfolio return distribution
    4. CVaR = Mean of all returns below VaR
    
    Note: Historical VaR assumes position weights are held constant.
    This is correct for risk monitoring; wrong for backtesting P&L.
    """
    ...
    var = np.percentile(portfolio_returns, (1 - confidence) * 100)
    cvar = portfolio_returns[portfolio_returns <= var].mean()
    return abs(var), abs(cvar)
```

---

## Portfolio Snapshot

Every 30 seconds during market hours, the risk monitor writes a snapshot:

```python
async def write_risk_snapshot(portfolio: PortfolioState) -> None:
    snapshot = RiskSnapshot(
        snapshot_ts=datetime.utcnow(),
        total_nav=portfolio.total_nav,
        gross_exposure=portfolio.gross_exposure,
        net_exposure=portfolio.net_exposure,
        var_95_1d=portfolio.var_95,
        cvar_95_1d=portfolio.cvar_95,
        spx_correlation=portfolio.spx_correlation_30d,
        industrials_pct=portfolio.sector_exposure.get("Industrials", 0),
        materials_pct=portfolio.sector_exposure.get("Materials", 0),
        energy_pct=portfolio.sector_exposure.get("Energy", 0),
        ma_arb_pct=portfolio.event_type_exposure.get("MA_ARB", 0),
        num_positions=len(portfolio.positions),
        active_events=portfolio.active_events_count,
    )
    db = get_db()
    db.table("portfolio.risk_snapshots").insert(snapshot.model_dump(mode="json")).execute()
```

---

## Commodity Stress Tests

`services/risk/stress/commodity_stress.py`:

```python
COMMODITY_STRESS_SCENARIOS = {
    "copper_crash": {"COPPER": -0.25, "GOLD": -0.05, "SILVER": -0.10},
    "gold_crash": {"GOLD": -0.20, "SILVER": -0.25, "COPPER": -0.05},
    "oil_crash": {"WTI": -0.35, "NAT_GAS": -0.20},
    "global_risk_off": {"COPPER": -0.20, "OIL": -0.25, "GOLD": +0.10},
    "inflation_spike": {"GOLD": +0.15, "COPPER": +0.10, "WTI": +0.20},
}

def run_commodity_stress_test(portfolio: PortfolioState) -> StressTestReport:
    """
    For each scenario, estimates portfolio NAV impact.
    
    Method: Each position's sector + commodity sensitivity
    (from FundamentalSnapshot.commodity_sensitivity_map) is multiplied
    by the commodity price change to estimate equity price impact.
    
    Rule: If any scenario produces portfolio loss > 8% NAV,
    flag for hedging review.
    """
    ...
```

---

## Critical Rules

1. **NEVER reduce a limit without documented rationale.** Every limit exists because a historical failure mode justified it. Before lowering a limit, find three examples of why the old limit was correct.
2. **NEVER mock `pre_trade_check` in integration tests.** If a test fails because the risk check triggers, fix the test data, not the check.
3. **Hard stops are auto-executed without analyst confirmation.** This is intentional and non-negotiable. Speed of loss-cutting is more important than perfection of execution price.
4. **All limit changes must be in `config.py` only.** Never hardcode limits in pipelines, services, or notebooks.
5. **The daily loss trip wire halts new positions but does not close existing ones.** Closing existing positions under stress often makes things worse. Halting new positions is the correct response.
6. **Run `pytest tests/risk/ -v` before deploying any risk change.** 100% test coverage is required on `pre_trade.py`.
7. **VaR is a risk measurement, not a stop loss.** VaR tells you what losses look like in normal conditions. Tail scenarios are handled by CVaR and commodity stress tests.
8. **Document every RiskLimitException in the trade log.** If a check blocks a trade and the trade would have been profitable, that's important data for limit calibration.
