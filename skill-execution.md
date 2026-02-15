---
name: execution
description: Use this skill when working with order routing, broker integration (IBKR via ib_insync), algo orders (TWAP/VWAP), position management, execution quality analysis, or the execution engine service. Trigger when the task involves: ExecutionRequest, ib_insync, order types, IBKR connectivity, trade lifecycle, fill monitoring, execution cost analysis, or the executions table. NEVER touch this layer without reading this skill first.
---

# Execution Management Skill — antigravity/APEX

The execution layer is where decisions become money. A brilliant trade thesis can be destroyed by poor execution — paying too much to enter, panicking on exit, or submitting the wrong order type. This skill documents exactly how the execution engine works, what order types to use when, and how to maintain the broker connection safely.

---

## Architecture

```
PositionRequest (from Portfolio Construction)
    ↓
pre_trade_check() (Risk — MUST pass)
    ↓
analyst_approval_id (MUST be present)
    ↓
ExecutionEngine.submit_order()
    ↓
Order type selection (Market / Limit / TWAP / VWAP / MOO)
    ↓
ib_insync → IBKR SmartRouting
    ↓
Fill monitoring + confirmation
    ↓
Supabase executions table update
    ↓
Redis publish: ORDER_FILLED channel
```

---

## IBKR Connection Management

`services/execution/ibkr/connection.py`:

```python
from ib_insync import IB, util
import asyncio
import os

# Global IB client — singleton pattern
_ib_client: IB | None = None

async def get_ib_client() -> IB:
    """
    Returns the shared IB connection. Creates and connects if not initialized.
    
    Connection parameters come from environment variables:
    - IBKR_HOST: Gateway/TWS host (default: 127.0.0.1)
    - IBKR_PORT: 7497 for TWS paper, 7496 for TWS live, 4002 for Gateway paper, 4001 for Gateway live
    - IBKR_CLIENT_ID: Must be unique per connection (use different IDs for different services)
    
    Environment check: If APEX_ENV != "production", connects to paper trading port.
    Never connect to live broker in non-production mode.
    """
    global _ib_client
    
    # CRITICAL: Enforce environment check
    apex_env = os.environ.get("APEX_ENV", "paper")
    if apex_env == "production":
        port = int(os.environ.get("IBKR_PORT", 4001))  # Live gateway
    else:
        port = int(os.environ.get("IBKR_PORT_PAPER", 4002))  # Paper gateway
        if apex_env == "production" and port in (4001, 7496):
            # Extra safety check: if someone manually sets a live port in paper mode
            raise ValueError("Cannot connect to live broker port outside production mode")
    
    if _ib_client is None or not _ib_client.isConnected():
        _ib_client = IB()
        await _ib_client.connectAsync(
            host=os.environ.get("IBKR_HOST", "127.0.0.1"),
            port=port,
            clientId=int(os.environ.get("IBKR_CLIENT_ID", 1)),
        )
    
    return _ib_client

async def disconnect_ib():
    """Always call on service shutdown."""
    global _ib_client
    if _ib_client and _ib_client.isConnected():
        _ib_client.disconnect()
        _ib_client = None
```

**Connection rules:**
- One `IB()` instance per service. Never create multiple connections in the same process.
- `clientId` must be unique: execution engine = 1, risk monitor = 2, market data = 3
- Always handle disconnection/reconnection. IBKR gateways drop connections periodically.
- `APEX_ENV` check is mandatory. Paper vs. live is the most critical distinction in this codebase.

---

## Contract Resolution

All instruments must be qualified before ordering:

```python
from ib_insync import IB, Stock, Option, Contract

async def resolve_contract(figi: str, ib: IB) -> Contract:
    """
    Converts FIGI to a qualified IBKR Contract.
    Caches resolved contracts in Redis (1-hour TTL).
    
    For equities: uses ticker + exchange from securities master
    For options: uses the full options chain specification
    """
    # Check cache first
    cache_key = f"ibkr:contract:{figi}"
    cached = redis.get(cache_key)
    if cached:
        return Contract.create(**json.loads(cached))
    
    security = await get_security(figi)
    
    if security.instrument_type == "equity":
        contract = Stock(
            symbol=security.ticker,
            exchange="SMART",                   # Always SMART for best execution routing
            currency="USD" if security.exchange != "TSX" else "CAD",
            primaryExch=_map_exchange(security.exchange),  # Hint for disambiguation
        )
    
    # Qualify with IBKR (resolves conId, validates the contract)
    qualified = await ib.qualifyContractsAsync(contract)
    if not qualified:
        raise ValueError(f"Could not qualify contract for figi={figi}, ticker={security.ticker}")
    
    resolved = qualified[0]
    
    # Cache for 1 hour
    redis.setex(cache_key, 3600, json.dumps(resolved.dict()))
    
    return resolved
```

---

## Order Type Selection by Situation

This is the most important table in this skill. Wrong order type = slippage, missed fills, or adversarial market impact.

```python
from shared.constants.order_strategies import OrderStrategy

def select_order_strategy(context: ExecutionContext) -> OrderStrategy:
    """
    Selects the optimal order strategy based on execution context.
    
    Inputs:
    - urgency: HIGH (must fill today) / MEDIUM (can wait hours) / LOW (days)
    - size_as_pct_adv: Position size as % of 30-day ADV
    - event_type: Affects urgency calculation
    - direction: New position or exit?
    - market_state: PRE_MARKET / OPEN / CLOSING / AFTER_HOURS
    """
    ...
```

| Situation | Strategy | Rationale |
|---|---|---|
| M&A arb entry, high confidence, liquid (>$5M ADV) | Market-on-Open | Spread compresses within hours of announcement; need fast fill at open |
| M&A arb entry, medium confidence | Aggressive limit (midpoint + 0.25%) | Don't chase the open spike; let some of the initial reaction settle |
| Spinoff, first trading day | TWAP over first 60 minutes | Forced selling (index funds) peaks at open; let the panic subside |
| Activist 13D, building a position | VWAP over 3-5 trading days | No urgency; minimize market impact on size building |
| Liquid equity exit (<5% ADV) | Limit at midpoint | Simple limit; fills quickly without market impact |
| Illiquid equity exit (>5% ADV) | VWAP over full day | Never flash a large sell in an illiquid name |
| Hard stop loss triggered | Market order | Certainty of execution over price. Never use limit for stop losses. |
| Options purchase | Limit at 105% of theoretical | Mid-spread + 5% overpay tolerance; avoid MM fill at ask |
| Tender offer submission | Direct tender via IBKR TWS API | Deadline-sensitive; confirm receipt via IBKR position report |
| Dividend capture | Limit buy at or below ex-date price | Timing precision matters; limit protects entry economics |

---

## TWAP / VWAP Algo Orders

For sizes >3% ADV, always use algos. IBKR SmartRouting can execute these natively:

```python
from ib_insync import Order

def build_twap_order(
    action: str,            # "BUY" or "SELL"
    quantity: int,
    duration_minutes: int,  # Total algo duration
) -> Order:
    """
    IB's native TWAP implementation.
    Splits the order into equal slices over the duration.
    
    Use for: New position entry where you want to build size gradually.
    Avoid for: Stop losses (need immediate execution, not spread over time).
    """
    order = Order()
    order.action = action
    order.totalQuantity = quantity
    order.orderType = "TWAP"
    order.algoStrategy = "Twap"
    order.algoParams = [
        ("startTime", ""),              # Empty = now
        ("endTime", ""),                # Empty = market close
        ("allowPastEndTime", 1),
    ]
    return order

def build_vwap_order(
    action: str,
    quantity: int,
    start_time: str = "",               # "HH:MM:SS" format or empty for now
    end_time: str = "16:00:00",         # Default: market close
    max_pct_vol: float = 0.10,          # Max % of volume per interval
) -> Order:
    """
    IB's native VWAP algo.
    Participates at up to max_pct_vol of volume to minimize market impact.
    
    Use for: Large exits, illiquid names, or when minimizing market impact is key.
    """
    order = Order()
    order.action = action
    order.totalQuantity = quantity
    order.orderType = "LMT"
    order.lmtPrice = 0                  # Required placeholder; algo overrides
    order.algoStrategy = "Vwap"
    order.algoParams = [
        ("startTime", start_time),
        ("endTime", end_time),
        ("maxPctVol", str(max_pct_vol)),
        ("noTakeLiq", 0),              # 0 = can take liquidity; 1 = passive only
    ]
    return order
```

---

## Fill Monitoring

```python
async def monitor_fills(trade_id: str, contract: Contract, order: Order, ib: IB) -> None:
    """
    Monitors a live order until fully filled or cancelled.
    Updates Supabase executions table in real-time.
    Publishes fill notifications to Redis.
    
    Timeouts:
    - Market/Limit: 1-hour timeout (cancel if not filled; re-evaluate)
    - TWAP/VWAP: No timeout; runs for its configured duration
    - MOO: Automatically fills at open or cancels
    """
    trade = ib.placeOrder(contract, order)
    
    @trade.fillEvent
    def on_fill(trade, fill):
        # Partial fills are normal; update incrementally
        asyncio.create_task(update_execution_record(
            trade_id=trade_id,
            fill_price=fill.execution.price,
            fill_quantity=fill.execution.shares,
            exchange=fill.execution.exchange,
            fill_time=fill.execution.time,
        ))
        # Publish to Redis for position monitor
        redis.publish(CHANNELS.ORDER_FILLED, json.dumps({
            "trade_id": trade_id,
            "fill_price": fill.execution.price,
            "fill_qty": fill.execution.shares,
        }))
    
    @trade.statusEvent
    def on_status(trade):
        if trade.orderStatus.status in ("Cancelled", "Inactive"):
            asyncio.create_task(handle_cancelled_order(trade_id, trade))
```

---

## Canadian Equities (TSX/TSXV)

For Canadian-listed mining names, IBKR Canada is the broker:

```python
# For TSX-listed securities:
contract = Stock(
    symbol=ticker.replace(".TO", ""),   # IBKR uses ticker without ".TO"
    exchange="SMART",
    currency="CAD",
    primaryExch="TSX",
)

# Currency consideration:
# - Positions in CAD require USD/CAD conversion for NAV calculation
# - IBKR automatically converts via ideal FX rates
# - Always book CAD positions in CAD in Supabase; apply FX for NAV aggregation
# - FX rate source: shared/db/readers/fx.py pulls from IBKR real-time quotes
```

---

## Execution Quality Reporting

After each completed trade, compute implementation shortfall:

```python
def compute_implementation_shortfall(
    decision_price: float,          # Price at time of analyst approval
    arrival_price: float,           # Price when order first submitted
    avg_fill_price: float,
    direction: Literal["BUY", "SELL"],
) -> ExecutionQualityReport:
    """
    Implementation shortfall = (avg_fill - decision_price) / decision_price
    
    This is the true cost of execution: the difference between what you
    decided to do and what you actually achieved.
    
    Negative IS (for buys) = you paid more than decision price = execution cost
    Positive IS (for buys) = you paid less than decision price = execution alpha
    
    Target: IS < 25bps for liquid equities, < 50bps for illiquid.
    Flag and review any trade with IS > 100bps.
    """
    if direction == "BUY":
        is_bps = (avg_fill_price - decision_price) / decision_price * 10000
    else:
        is_bps = (decision_price - avg_fill_price) / decision_price * 10000
    
    return ExecutionQualityReport(
        implementation_shortfall_bps=round(is_bps, 2),
        market_impact_bps=round((avg_fill_price - arrival_price) / arrival_price * 10000, 2),
        timing_cost_bps=round((arrival_price - decision_price) / decision_price * 10000, 2),
        rating="GOOD" if abs(is_bps) < 25 else "ACCEPTABLE" if abs(is_bps) < 50 else "REVIEW",
    )
```

---

## Critical Rules

1. **`APEX_ENV` check before every broker connection.** Paper and live use different ports. Never hardcode port numbers.
2. **Never place market orders for entries.** Only for hard stop losses and forced liquidations. Market orders are a gift to market makers on entries.
3. **Qualify all contracts before ordering.** `ib.qualifyContractsAsync()` must succeed. If it fails, the instrument is not tradeable via IBKR.
4. **Log every order, fill, and cancellation to Supabase.** The executions table is the audit trail. Never skip a write.
5. **Compute implementation shortfall for every completed trade.** Track it by event type and order strategy. This is how you improve execution over time.
6. **For positions >5% ADV, always use VWAP.** Hitting the market with a block order in a thin name is charity to other market participants.
7. **For hard stops: market order, no exceptions.** Certainty of exit is always worth some slippage when the thesis is broken.
8. **One clientId per service.** Running two services with the same clientId will cause IBKR to disconnect one. `execution_engine=1`, `risk_monitor=2`, `data_feed=3`.
9. **Test in paper mode for minimum 5 days before live.** Every order type you intend to use in live trading must have been tested in paper first.
10. **CAD positions are valued at USD for NAV.** Apply live IBKR FX rate. Never use a static FX assumption.
