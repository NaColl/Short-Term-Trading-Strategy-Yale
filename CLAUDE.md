# CLAUDE.md — antigravity (APEX Trading System)

> **Read this file completely before touching any code.** It is the authoritative guide to how this codebase thinks, what it values, and how every layer connects.

---

## What This Is

**antigravity** is the codebase powering **APEX** (Adaptive Position & Event eXecution System) — an event-driven, fundamentals-anchored trading system focused on special situations in industrials and natural resources. It monitors 15+ data feeds, classifies 60+ corporate event types with LLMs, anchors every opportunity in bottom-up fundamental analysis, and routes approved trades to brokers via a strict human-gated execution pipeline.

**The one-sentence mandate:** Find mispriced corporate events before the market does, verify the thesis with fundamental analysis, manage the risk precisely, and execute without emotion.

---

## Architecture at a Glance

```
L1  Data Infrastructure      → Ingest, normalize, store everything
L2  Event Detection Engine   → Find the catalyst (n8n + LangChain + Claude)
L3  Fundamental Engine       → Anchor to intrinsic value (Python + XBRL + LLM)
L4  Quant Signal Framework   → Quantify the edge (PyTorch + factor library)
L5  Risk Management          → Enforce limits relentlessly (Python + Supabase)
L6  Portfolio Construction   → Size and assemble the book (cvxpy + Kelly)
L7  Execution Management     → Route and fill cleanly (ib_insync + IBKR)
L8  Research Workflow        → Human review and approval (Streamlit dashboard)
```

No position enters L7 without an `analyst_approval_id` token from L8. This is not optional and cannot be circumvented. The human is in the loop by architecture, not by convention.

---

## Directory Structure

```
antigravity/
├── CLAUDE.md                        ← You are here
├── .claude/
│   └── skills/
│       ├── data-infrastructure/SKILL.md
│       ├── event-detection/SKILL.md
│       ├── fundamental-engine/SKILL.md
│       ├── quant-signals/SKILL.md
│       ├── risk-management/SKILL.md
│       ├── execution/SKILL.md
│       └── n8n-workflows/SKILL.md
│
├── services/
│   ├── ingest/                      ← L1: Data ingest microservices
│   │   ├── edgar/                   # SEC EDGAR pipeline
│   │   ├── polygon/                 # Market data (REST + WebSocket)
│   │   ├── commodity/               # EIA, Baker Hughes, LME
│   │   ├── sedar/                   # Canadian filings (Firecrawl)
│   │   └── options_flow/            # Polygon options + unusual activity
│   │
│   ├── detection/                   ← L2: Event detection
│   │   ├── classifiers/             # LangChain chains per event category
│   │   ├── pipelines/               # Per-source detection logic
│   │   └── dedup/                   # Cross-source deduplication
│   │
│   ├── fundamental/                 ← L3: Fundamental analysis
│   │   ├── xbrl/                    # SEC XBRL financial data parser
│   │   ├── comps/                   # Comparable company analysis
│   │   ├── nav/                     # Mining NAV model
│   │   ├── scenarios/               # Bear/base/bull scenario builder
│   │   └── filing_analysis/         # LLM document extraction chains
│   │
│   ├── signals/                     ← L4: Quant signals
│   │   ├── factors/                 # Individual factor implementations
│   │   ├── event_studies/           # Historical pattern database
│   │   ├── models/                  # PyTorch ML models
│   │   └── scoring/                 # Composite signal assembly
│   │
│   ├── risk/                        ← L5: Risk management
│   │   ├── monitors/                # Real-time exposure monitors
│   │   ├── limits/                  # Limit definitions and enforcement
│   │   └── stress/                  # Scenario stress tests
│   │
│   ├── portfolio/                   ← L6: Portfolio construction
│   │   ├── sizing/                  # Kelly + cvxpy position sizing
│   │   └── hedging/                 # Hedge recommendation engine
│   │
│   ├── execution/                   ← L7: Order routing
│   │   ├── ibkr/                    # ib_insync IBKR connector
│   │   ├── algos/                   # TWAP, VWAP implementations
│   │   └── risk_checks/             # Pre-trade risk validation
│   │
│   └── dashboard/                   ← L8: Streamlit analyst UI
│       ├── pages/
│       ├── components/
│       └── opportunity_brief/
│
├── shared/
│   ├── schemas/                     ← ALL Pydantic models live here
│   │   ├── market.py
│   │   ├── events.py
│   │   ├── fundamentals.py
│   │   ├── signals.py
│   │   ├── risk.py
│   │   └── execution.py
│   ├── db/                          ← Supabase client and helpers
│   ├── redis/                       ← Redis client and channel names
│   └── constants/                   ← EventType enum, sector maps, etc.
│
├── workflows/                       ← n8n workflow JSON exports
│   ├── edgar-realtime-monitor.json
│   ├── news-event-detector.json
│   ├── options-flow-scanner.json
│   ├── fundamental-enricher.json
│   ├── signal-generator.json
│   ├── risk-monitor.json
│   └── eod-report.json
│
├── models/                          ← Trained ML model artifacts
│   ├── deal_break_xgb_v2.pkl
│   ├── event_classifier_distilbert/
│   └── earnings_surprise_lstm/
│
├── notebooks/                       ← Research and backtesting
│   ├── event_studies/
│   ├── factor_research/
│   └── model_training/
│
├── migrations/                      ← Supabase SQL migrations
│   └── YYYYMMDD_description.sql
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
│
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

---

## Core Conventions

### 1. Pydantic Everywhere

**Every** inter-service boundary uses a Pydantic v2 model from `shared/schemas/`. Never pass raw dicts across service boundaries. Never accept unvalidated external data.

```python
# CORRECT: Always import from shared/schemas
from shared.schemas.events import CorporateEvent, EventType
from shared.schemas.signals import AlphaSignal

# WRONG: Never define schemas inline or ad hoc
def process_event(event: dict):  # ❌ No
def process_event(event: CorporateEvent):  # ✅ Yes
```

### 2. Every Write Goes Through Supabase

No service writes directly to the DB without going through `shared/db/client.py`. The client handles connection pooling, retry logic, and logging. Never instantiate a raw `psycopg2` or `asyncpg` connection outside of `shared/db/`.

```python
from shared.db.client import get_db
db = get_db()
db.table("events.corporate_events").insert(event.model_dump()).execute()
```

### 3. Redis Channels Are Constants

All Redis pub/sub channel names live in `shared/redis/channels.py`. Never hardcode a channel string. If you need a new channel, add it to the constants file first.

```python
from shared.redis.channels import CHANNELS
redis.publish(CHANNELS.NEW_EVENT, event.model_dump_json())
# CHANNELS.NEW_EVENT = "apex:events:new"
```

### 4. The EventType Enum Is The Law

All event classification must resolve to a value in `shared/constants/event_types.py:EventType`. If you encounter an event that doesn't fit an existing type, **add it to the enum** before writing classification logic. Never use raw strings for event types outside of configuration.

### 5. Risk Checks Are Never Optional

Any code path that could result in a trade being submitted to L7 **must** call `services/risk/monitors/pre_trade.py:pre_trade_check()`. This function raises `RiskLimitException` if any limit would be breached. It is tested with 100% coverage and must never be mocked in integration tests.

```python
from services.risk.monitors.pre_trade import pre_trade_check
# Always call this. Always handle RiskLimitException.
approval = pre_trade_check(position_request, portfolio_state)
```

### 6. Analyst Approval Is Required For All Executions

The `ExecutionRequest` schema has a required `analyst_approval_id: UUID` field. The execution engine will raise `MissingApprovalException` if this is `None`. Never set it programmatically — it must come from the analyst dashboard's approval flow via the Supabase `approvals` table.

### 7. Logging Standard

Use structured logging via `shared/logging/logger.py`. Always include `event_id`, `figi`, and the service name in log context. This makes debugging across async pipelines tractable.

```python
from shared.logging.logger import get_logger
logger = get_logger(__name__)
logger.info("event_classified", event_id=str(event.event_id), 
            figi=event.figi, event_type=event.event_type.value,
            confidence=event.confidence)
```

### 8. Environment Variables

Never hardcode credentials. All API keys, DB URLs, and secrets come from environment variables loaded via `python-dotenv` from `.env` (not committed). See `.env.example` for required variables. In production, secrets are injected via HashiCorp Vault.

---

## Technology Stack Quick Reference

| Purpose | Tool | Import Pattern |
|---|---|---|
| Data validation | `pydantic v2` | `from pydantic import BaseModel, Field` |
| Database | `supabase-py` | `from shared.db.client import get_db` |
| Message queue | `redis-py` | `from shared.redis.client import get_redis` |
| LLM chains | `langchain-anthropic` | `from langchain_anthropic import ChatAnthropic` |
| ML framework | `torch` | `import torch; import torch.nn as nn` |
| Data processing | `polars` (default), `pandas` (interop) | `import polars as pl` |
| Portfolio opt | `cvxpy` | `import cvxpy as cp` |
| IBKR execution | `ib_insync` | `from ib_insync import IB, Stock, LimitOrder` |
| Async HTTP | `httpx` | `import httpx` |
| Web scraping | `firecrawl-py` | `from firecrawl import FirecrawlApp` |
| Scheduling | `celery` | `from shared.celery.app import celery_app` |
| Dashboard | `streamlit` | `import streamlit as st` |

---

## Skills Quick Reference

Read the relevant skill before building in any layer:

| Task | Skill File |
|---|---|
| Adding a new data source or ingest pipeline | `.claude/skills/data-infrastructure/SKILL.md` |
| Adding a new event type or detection pipeline | `.claude/skills/event-detection/SKILL.md` |
| Adding financial modeling, valuation, or document analysis | `.claude/skills/fundamental-engine/SKILL.md` |
| Adding a new alpha factor or ML model | `.claude/skills/quant-signals/SKILL.md` |
| Modifying risk limits or adding new risk checks | `.claude/skills/risk-management/SKILL.md` |
| Working with order routing or broker integration | `.claude/skills/execution/SKILL.md` |
| Building or modifying n8n workflows | `.claude/skills/n8n-workflows/SKILL.md` |

---

## Common Tasks

### Add a New Data Source

1. Read `.claude/skills/data-infrastructure/SKILL.md`
2. Create `services/ingest/{source_name}/` with `connector.py`, `normalizer.py`, `scheduler.py`
3. Add Pydantic schema to `shared/schemas/market.py` or appropriate file
4. Add source to `shared/constants/data_sources.py:DataSource` enum
5. Create Supabase migration in `migrations/`
6. Wire into n8n workflow or Celery schedule
7. Add integration test in `tests/integration/ingest/`

### Add a New Event Type

1. Read `.claude/skills/event-detection/SKILL.md`
2. Add value to `EventType` enum in `shared/constants/event_types.py`
3. Add detection logic in `services/detection/pipelines/`
4. Add LLM classification prompt in `services/detection/classifiers/`
5. Add event-study historical data to the event_studies database (or notebook)
6. Add factor weights for the new event type in `services/signals/scoring/weights.py`
7. Update opportunity brief template in `services/dashboard/opportunity_brief/`
8. Add at least 5 unit tests covering classification edge cases

### Add a New Alpha Factor

1. Read `.claude/skills/quant-signals/SKILL.md`
2. Create `services/signals/factors/{factor_name}.py` implementing `BaseFactorCalculator`
3. Register in `services/signals/factors/__init__.py`
4. Add factor to `AlphaSignal.factors` schema if it's universally applicable
5. Run backtests in `notebooks/factor_research/` to validate IC and Sharpe
6. Add factor weights per event type in `services/signals/scoring/weights.py`
7. Document IC, coverage, and directional logic in the factor file docstring

### Modify a Risk Limit

1. Read `.claude/skills/risk-management/SKILL.md`
2. NEVER reduce a limit without a documented trade review reason
3. All limit changes must be in `services/risk/limits/config.py` — never hardcoded
4. After changing limits, run `pytest tests/risk/` before deploying
5. Update the risk snapshot schema if you're adding a new monitored metric

---

## Testing Philosophy

- **Unit tests**: Test individual functions with mocked dependencies. Located in `tests/unit/`. Required for all factor calculators, classification functions, and risk checks.
- **Integration tests**: Test a full pipeline segment against a local Supabase instance (Docker). Located in `tests/integration/`. Required for all ingest pipelines and execution flows.
- **Backtests**: Not unit tests — live in `notebooks/`. Use walk-forward validation; never look-ahead.
- **Never mock risk checks in integration tests.** If the risk check fails in a test, fix the test setup, not the check.

Run tests:
```bash
pytest tests/unit/              # Fast; run before every commit
pytest tests/integration/       # Slower; run before every PR
pytest tests/risk/ -v           # Run separately before any risk limit change
```

---

## Critical Rules (Non-Negotiable)

1. **No execution without analyst approval.** `analyst_approval_id` must be a real UUID from the approvals table.
2. **No position without fundamental anchor.** `FundamentalSnapshot` must exist in DB before `AlphaSignal` is generated.
3. **No schema changes without migration.** Add a file in `migrations/` for every DB change.
4. **No new channels without constants.** Add to `shared/redis/channels.py` first.
5. **No raw dicts across service boundaries.** Use Pydantic schemas.
6. **No secrets in code.** All credentials from environment variables.
7. **No position sizing above hard limits.** The risk system enforces this; do not fight it.
8. **All LLM calls use temperature=0 for classification tasks.** Reproducibility matters.
9. **All factor calculations must have IC > 0.03 on out-of-sample data** before being enabled in production.
10. **If a trade cannot be explained in one paragraph, it should not be taken.**

---

## Environment Setup

```bash
# Clone and set up
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_KEY, ANTHROPIC_API_KEY, POLYGON_API_KEY,
#          IBKR_HOST, IBKR_PORT, REDIS_URL, FIRECRAWL_API_KEY

# Install dependencies
pip install -e ".[dev]"

# Start local infrastructure
docker-compose up -d  # Starts: redis, supabase (local), n8n, grafana

# Run migrations
supabase db push

# Verify everything
python -c "from shared.db.client import get_db; print('DB OK')"
python -c "from shared.redis.client import get_redis; print('Redis OK')"

# Run tests
pytest tests/unit/ -q
```

---

## Deployment

Services run as Docker containers orchestrated by `docker-compose.yml` in development and Kubernetes in production. n8n runs self-hosted. Supabase is cloud-hosted (production) or local Docker (development). Never run the execution engine against a live broker without the `APEX_ENV=production` environment variable explicitly set — the engine checks this and defaults to paper trading mode.

```bash
APEX_ENV=production  # Live trading
APEX_ENV=paper       # Paper trading (default)
APEX_ENV=backtest    # Backtest mode (no external calls)
```
