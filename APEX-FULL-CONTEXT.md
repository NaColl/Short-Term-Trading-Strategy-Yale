# APEX TRADING SYSTEM — FULL CONTEXT
> Drop this file into your IDE as the single source of truth for the antigravity codebase.

---

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

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: data-infrastructure -->
<!-- ════════════════════════════════════════════════════════ -->

---
name: data-infrastructure
description: Use this skill when adding a new data source, modifying an ingest pipeline, adding a new table to the database schema, or working with any raw data ingestion in the antigravity/APEX system. Covers connector patterns, Pydantic normalization, Supabase writes, TimescaleDB hypertables, Redis publishing, and data source enumeration. Trigger on any task involving: new API integration, scraping, data normalization, DB migration, time-series table design.
---

# Data Infrastructure Skill — antigravity/APEX

Every trade in APEX depends on data arriving correctly, reliably, and fast. This skill documents exactly how to add data sources, normalize feeds, persist to Supabase, and publish to downstream layers without introducing silent failures.

---

## The Data Lifecycle

```
External Source (API/WebSocket/Scraper)
    ↓
Connector (services/ingest/{source}/connector.py)
    ↓  raw response
Normalizer (services/ingest/{source}/normalizer.py)
    ↓  Pydantic model
Supabase Writer (shared/db/writers/{domain}.py)
    ↓  persisted
Redis Publisher (shared/redis/publishers.py)
    ↓  channel message
Downstream layer (L2 Detection, L3 Fundamental, etc.)
```

Never skip the normalizer step. Never write to Supabase before Pydantic validation passes.

---

## Adding a New Data Source: Step-by-Step

### Step 1: Register the Source

Add to `shared/constants/data_sources.py`:
```python
class DataSource(str, Enum):
    EDGAR = "EDGAR"
    POLYGON = "POLYGON"
    EIA = "EIA"
    BAKER_HUGHES = "BAKER_HUGHES"
    YOUR_NEW_SOURCE = "YOUR_NEW_SOURCE"  # Add here first
```

### Step 2: Create the Connector

`services/ingest/{source_name}/connector.py`

```python
import httpx
from shared.logging.logger import get_logger
from shared.constants.data_sources import DataSource

logger = get_logger(__name__)

class YourSourceConnector:
    """
    Fetches raw data from YourSource API.
    
    Rate limits: 100 req/min. Handles 429 with exponential backoff.
    Auth: Bearer token from env var YOUR_SOURCE_API_KEY.
    """
    BASE_URL = "https://api.yoursource.com/v1"
    
    def __init__(self):
        self.api_key = os.environ["YOUR_SOURCE_API_KEY"]
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )
    
    async def fetch_latest(self, ticker: str) -> dict:
        """Returns raw API response dict. Raises on non-200."""
        try:
            resp = await self.client.get(f"/data/{ticker}")
            resp.raise_for_status()
            logger.debug("fetched", source=DataSource.YOUR_NEW_SOURCE, ticker=ticker)
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("fetch_failed", source=DataSource.YOUR_NEW_SOURCE, 
                        ticker=ticker, status=e.response.status_code)
            raise
```

**Connector rules:**
- One method per logical API endpoint
- Returns raw response only — no business logic
- Logs every request at DEBUG, every failure at ERROR
- Raises on HTTP errors; let the caller handle retry logic
- Always set `timeout` — external APIs will hang

### Step 3: Create the Normalizer

`services/ingest/{source_name}/normalizer.py`

```python
from datetime import datetime
from shared.schemas.market import YourDataSchema  # Pydantic model
from shared.constants.data_sources import DataSource

def normalize_your_source(raw: dict, figi: str) -> YourDataSchema:
    """
    Converts raw API response to validated Pydantic model.
    
    Raises ValidationError if required fields are missing or malformed.
    This is intentional — bad data should never reach Supabase.
    """
    return YourDataSchema(
        figi=figi,
        source=DataSource.YOUR_NEW_SOURCE,
        as_of=datetime.fromisoformat(raw["timestamp"]),
        value=float(raw["value"]),           # Explicit casting — never trust API types
        unit=raw.get("unit", "USD"),         # Defensive default only when semantically safe
        raw_json=raw,                        # Always store raw for debugging/reprocessing
    )
```

**Normalizer rules:**
- Returns a Pydantic model or raises `ValidationError` — never returns `None`
- Always store `raw_json` for debuggability and reprocessing
- Use explicit type casting (`float(raw["value"])`) — never assume API types
- Never apply business logic here — just map fields
- One normalizer function per data type/endpoint

### Step 4: Add the Pydantic Schema

`shared/schemas/market.py` (or appropriate domain file):

```python
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any

class YourDataSchema(BaseModel):
    figi: str
    source: DataSource
    as_of: datetime
    value: float = Field(gt=0, description="Must be positive")
    unit: str
    raw_json: dict[str, Any]
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator("figi")
    @classmethod
    def figi_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("figi cannot be empty")
        return v.strip().upper()
    
    model_config = {"frozen": True}  # Immutable after creation
```

### Step 5: Write to Supabase

Use a writer function, never raw SQL in the ingest service:

`shared/db/writers/market.py`:
```python
from shared.db.client import get_db
from shared.schemas.market import YourDataSchema

async def write_your_data(record: YourDataSchema) -> None:
    db = get_db()
    result = (
        db.table("market.your_data_table")
        .upsert(
            record.model_dump(mode="json"),
            on_conflict="figi,as_of"   # Prevent duplicates on reprocessing
        )
        .execute()
    )
    if not result.data:
        raise RuntimeError(f"Write failed for figi={record.figi}")
```

### Step 6: Write the DB Migration

`migrations/YYYYMMDD_add_your_data_table.sql`:
```sql
-- Always include: schema, table, indexes, and TimescaleDB if time-series

CREATE TABLE market.your_data_table (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    figi        TEXT NOT NULL REFERENCES market.securities(figi),
    source      TEXT NOT NULL,
    as_of       TIMESTAMPTZ NOT NULL,
    value       NUMERIC(18, 6) NOT NULL,
    unit        TEXT NOT NULL,
    raw_json    JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- For time-series data, always use TimescaleDB:
SELECT create_hypertable('market.your_data_table', 'as_of',
    chunk_time_interval => INTERVAL '1 month');

-- Index for the most common query patterns:
CREATE INDEX idx_your_data_figi_as_of 
    ON market.your_data_table(figi, as_of DESC);

-- Never query without figi filter; this is the hot path index.
```

**Migration rules:**
- One file per logical change
- Always include `ROLLBACK` scenario comments if irreversible
- TimescaleDB hypertable for any table queried by time range
- Always add index on `(figi, timestamp DESC)` — every table gets queried this way
- Use `NUMERIC(18,6)` for prices/values, never `FLOAT` (precision matters in finance)

### Step 7: Publish to Redis (if downstream layers need to react)

```python
from shared.redis.client import get_redis
from shared.redis.channels import CHANNELS
import json

async def publish_new_data(record: YourDataSchema) -> None:
    redis = get_redis()
    # Only publish if downstream layers care about this data in real-time
    # Not every data type needs pub/sub — daily batch data doesn't
    redis.publish(
        CHANNELS.NEW_COMMODITY_DATA,
        record.model_dump_json()
    )
```

---

## Supabase Client Patterns

```python
from shared.db.client import get_db

db = get_db()

# Read
result = db.table("market.securities").select("*").eq("figi", figi).single().execute()
security = result.data  # dict or None

# Write
db.table("events.corporate_events").insert(event.model_dump(mode="json")).execute()

# Upsert (idempotent writes — use this for ingest pipelines)
db.table("market.market_data_eod").upsert(
    row.model_dump(mode="json"), 
    on_conflict="figi,date"
).execute()

# Batch insert (use for historical backfill)
db.table("market.your_data").insert([r.model_dump(mode="json") for r in records]).execute()

# Real-time subscription (triggers from DB changes)
def handle_new_event(payload):
    event = CorporateEvent(**payload["new"])
    # trigger downstream logic

db.table("events.corporate_events").on("INSERT", handle_new_event).subscribe()
```

---

## TimescaleDB Patterns

```sql
-- Querying recent data (fast — hits one chunk)
SELECT * FROM market.market_data_eod
WHERE figi = 'BBG000B9XRY4'
  AND date >= NOW() - INTERVAL '30 days'
ORDER BY date DESC;

-- Continuous aggregate (pre-compute expensive aggregations)
CREATE MATERIALIZED VIEW market.daily_volume_summary
WITH (timescaledb.continuous) AS
SELECT figi,
       time_bucket('1 day', ingested_at) AS bucket,
       SUM(volume) AS total_volume,
       AVG(close) AS avg_close
FROM market.market_data_eod
GROUP BY figi, bucket;
```

---

## Scheduler Patterns

For periodic ingest (vs. real-time WebSocket):

```python
# services/ingest/{source}/scheduler.py
from shared.celery.app import celery_app

@celery_app.task(
    name="ingest.your_source.fetch_daily",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 60 second retry delay
)
def fetch_daily_task(self, date_str: str = None):
    """Runs daily at 6:30 AM EST via Celery beat schedule."""
    try:
        connector = YourSourceConnector()
        raw = connector.fetch_all()
        records = [normalize_your_source(r) for r in raw]
        for record in records:
            write_your_data(record)
    except Exception as exc:
        raise self.retry(exc=exc)
```

Register in `shared/celery/schedule.py`:
```python
CELERYBEAT_SCHEDULE = {
    "your-source-daily": {
        "task": "ingest.your_source.fetch_daily",
        "schedule": crontab(hour=6, minute=30),  # 6:30 AM EST daily
    },
}
```

---

## Firecrawl Patterns (for scraping)

Use for: SEDAR+ filings, IR pages, regulatory sites that don't have APIs.

```python
from firecrawl import FirecrawlApp

app = FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])

# Scrape a page — returns clean Markdown for LLM ingestion
result = app.scrape_url(
    "https://www.sedarplus.ca/csa-party/records/document.html?id=XXXXX",
    params={"formats": ["markdown"], "onlyMainContent": True}
)
content = result["markdown"]  # Pass directly to LLM classification chain

# Crawl a site (IR page with multiple documents)
result = app.crawl_url(
    "https://www.company.com/investors",
    params={
        "limit": 20,
        "scrapeOptions": {"formats": ["markdown"]},
        "includePaths": ["/investors/*", "/press-releases/*"],
    }
)
pages = result["data"]  # List of {url, markdown} dicts
```

**Firecrawl rules:**
- Always use `onlyMainContent: True` to strip nav/footer noise before LLM
- Cache results in Supabase `filings.scraped_pages` table with URL + hash — avoid re-scraping
- Never scrape in a tight loop — add 2-5 second delays between pages
- Use `crawl_url` for IR pages, `scrape_url` for specific known documents

---

## Critical Rules

1. **Validate before writing.** Pydantic validation must pass before any Supabase write. If validation fails, log the raw data and the error, then skip the record. Do not crash the pipeline.
2. **Use `upsert` with conflict resolution for all ingest writes.** Pipelines run repeatedly; writes must be idempotent.
3. **Store `raw_json` always.** You will need it for debugging, reprocessing, and LLM re-analysis.
4. **Never use `FLOAT` in Supabase for financial values.** Use `NUMERIC(18,6)`.
5. **TimescaleDB for every time-series table.** Any table with a timestamp column that gets range queries needs to be a hypertable.
6. **One connector per external source.** Never multiplex multiple APIs through a single connector file.
7. **Test your normalizer with real API responses.** Save a sample response in `tests/fixtures/` and write a unit test that runs the normalizer on it.

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: event-detection -->
<!-- ════════════════════════════════════════════════════════ -->

---
name: event-detection
description: Use this skill when adding a new event type to the taxonomy, building a new detection pipeline (EDGAR, news, options flow, commodity data), writing LangChain classification chains, tuning confidence thresholds, or working with the deduplication system. Trigger when the task involves: EventType enum, LangChain chains, EDGAR parsing, event classification, confidence scoring, or the corporate_events table.
---

# Event Detection Skill — antigravity/APEX

The Event Detection Engine is APEX's competitive clock. Every millisecond between a filing hitting EDGAR and a signal landing on the analyst's desk is a millisecond the market has to reprice before we can act. This skill documents how to build detection pipelines that are fast, accurate, and resilient.

---

## The Three Detection Pillars

### Pillar 1: Source Coverage
Every relevant event must have a detection path. If an event type can be identified from a filing, it must have an EDGAR pipeline. If it can be identified from news first, it must have a news pipeline. The two pipelines for the same event must deduplicate cleanly.

### Pillar 2: Classification Quality
A confident wrong answer is worse than an uncertain right one. All classification outputs include confidence scores. Anything below `CONFIDENCE_THRESHOLD` (default: `0.65`) goes into the database as `LOW_CONFIDENCE` status and does not trigger analyst alerts.

### Pillar 3: Speed
Target: analyst alert within 90 seconds of EDGAR filing timestamp. Current bottlenecks: LLM API latency (5-15s), filing download (1-5s), Supabase write (200ms). Monitor via Prometheus `event_detection_latency_seconds`.

---

## Adding a New Event Type

### Step 1: Define the Enum Value

`shared/constants/event_types.py`:
```python
class EventType(str, Enum):
    # M&A
    MA_ACQUISITION_TARGET = "MA_ACQUISITION_TARGET"
    MA_ACQUISITION_ACQUIRER = "MA_ACQUISITION_ACQUIRER"
    MA_HOSTILE_APPROACH = "MA_HOSTILE_APPROACH"
    MA_DEAL_BREAK = "MA_DEAL_BREAK"
    # Spinoffs
    SPINOFF_ANNOUNCED = "SPINOFF_ANNOUNCED"
    SPINOFF_COMPLETED = "SPINOFF_COMPLETED"
    # Activist
    ACTIVIST_13D_NEW = "ACTIVIST_13D_NEW"
    ACTIVIST_SETTLEMENT = "ACTIVIST_SETTLEMENT"
    # Your new type — add here
    YOUR_NEW_EVENT = "YOUR_NEW_EVENT"
```

Also add it to the event metadata map in `shared/constants/event_metadata.py`:
```python
EVENT_METADATA: dict[EventType, EventMeta] = {
    EventType.YOUR_NEW_EVENT: EventMeta(
        display_name="Your New Event",
        category=EventCategory.CORPORATE_STRUCTURE,
        typical_hold_days=(30, 90),
        base_win_rate=0.60,            # From event study or conservative estimate
        primary_sec_forms=["8-K"],     # What forms trigger this event
        requires_fundamental=True,     # Must L3 run before signal generation?
        analyst_alert_threshold=0.65,  # Confidence needed to alert analyst
    ),
}
```

### Step 2: Write the Detection Logic

**For EDGAR-triggered events:**

`services/detection/pipelines/edgar_pipeline.py` — add to the form router:
```python
FORM_TO_PIPELINE: dict[str, list[str]] = {
    "8-K": ["ma_pipeline", "spinoff_pipeline", "your_new_pipeline"],
    "13D": ["activist_pipeline"],
    "SC TO": ["tender_offer_pipeline"],
    # Add your form → pipeline mapping here
}
```

Create `services/detection/pipelines/your_new_pipeline.py`:
```python
from services.detection.classifiers.your_new_classifier import classify_your_event
from shared.schemas.events import CorporateEvent, EventType
from shared.constants.data_sources import DataSource

async def run_your_new_pipeline(
    filing_text: str,
    form_type: str,
    figi: str,
    accession_no: str,
) -> CorporateEvent | None:
    """
    Returns CorporateEvent if a YOUR_NEW_EVENT is detected, else None.
    Never raises — log and return None on any classification failure.
    """
    # Quick pre-filter: is this even plausible?
    if not _quick_keyword_check(filing_text):
        return None
    
    try:
        classification = await classify_your_event(filing_text, figi)
    except Exception as e:
        logger.error("classification_failed", figi=figi, accession=accession_no, error=str(e))
        return None
    
    if classification.confidence < 0.40:  # Hard floor — don't even log below this
        return None
    
    return CorporateEvent(
        figi=figi,
        event_type=EventType.YOUR_NEW_EVENT,
        event_subtype=classification.subtype,
        source=DataSource.EDGAR,
        source_url=f"https://www.sec.gov/Archives/edgar/{accession_no}",
        raw_content=filing_text[:5000],    # First 5k chars; full text in S3/storage
        confidence=classification.confidence,
        status="new" if classification.confidence >= 0.65 else "low_confidence",
        catalyst_date=classification.event_date,
        metadata=classification.extracted_facts.model_dump(),
    )

def _quick_keyword_check(text: str) -> bool:
    """Fast string scan before expensive LLM call. Tune keywords to this event type."""
    keywords = ["merger", "acquisition", "proposed transaction", "definitive agreement"]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)
```

**The quick keyword check is critical.** EDGAR receives 500+ filings per day. Most are irrelevant to any given pipeline. The keyword pre-filter eliminates 90%+ of LLM calls before they happen, keeping latency and cost under control.

### Step 3: Write the LangChain Classifier

`services/detection/classifiers/your_new_classifier.py`:

```python
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class YourEventExtraction(BaseModel):
    """Structured output for YOUR_NEW_EVENT classification."""
    is_your_event: bool = Field(description="Is this filing definitely a YOUR_NEW_EVENT?")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    subtype: Optional[str] = Field(description="Specific subtype within this event category")
    event_date: Optional[date] = Field(description="Date of the event, if determinable from text")
    # Event-specific fields — add what matters for this event type:
    deal_value_usd: Optional[int] = Field(description="Total deal value in USD, if applicable")
    counterparty_name: Optional[str] = Field(description="Other party in the transaction")
    key_facts: list[str] = Field(description="Top 5 most important facts from the filing")
    risk_factors: list[str] = Field(description="Top 3 risks to this situation resolving favorably")
    reasoning: str = Field(description="1-2 sentence explanation of the classification decision")

YOUR_EVENT_PROMPT = ChatPromptTemplate.from_template("""
You are an expert event-driven hedge fund analyst specializing in industrial and 
natural resource companies. You are reading an SEC filing to determine if it 
contains a YOUR_NEW_EVENT.

A YOUR_NEW_EVENT is defined as: [CLEAR DEFINITION OF WHAT THIS EVENT IS AND IS NOT]

Examples of YES (is a YOUR_NEW_EVENT):
- [Concrete example 1]
- [Concrete example 2]

Examples of NO (is NOT a YOUR_NEW_EVENT):
- [What to exclude and why]

SEC FILING:
{filing_text}

COMPANY CONTEXT:
Ticker: {ticker}
Sector: {sector}
Market Cap: {market_cap}

Extract all relevant information and classify this filing.

{format_instructions}
""")

_llm = ChatAnthropic(
    model="claude-sonnet-4-5-20250929",
    temperature=0,          # ALWAYS 0 for classification tasks
    max_tokens=1024,
)
_parser = PydanticOutputParser(pydantic_object=YourEventExtraction)
_chain = YOUR_EVENT_PROMPT | _llm | _parser

async def classify_your_event(
    filing_text: str, 
    figi: str,
    context: dict = None,
) -> YourEventExtraction:
    """
    Classifies whether a filing contains a YOUR_NEW_EVENT.
    Returns structured extraction. Raises on LLM failure.
    """
    context = context or {}
    result = await _chain.ainvoke({
        "filing_text": filing_text[:12000],   # ~3000 tokens; enough context
        "ticker": context.get("ticker", "UNKNOWN"),
        "sector": context.get("sector", "UNKNOWN"),
        "market_cap": context.get("market_cap", "UNKNOWN"),
        "format_instructions": _parser.get_format_instructions(),
    })
    return result
```

**Prompt engineering rules for classification chains:**
- Always include concrete YES and NO examples in the prompt — this is the highest-leverage improvement
- Always include company context (sector, market cap) — it dramatically improves classification for ambiguous filings
- Truncate filing text to ~12,000 chars — beyond this, signal-to-noise drops for classification
- `temperature=0` always — we need reproducibility, not creativity
- The reasoning field is required — it enables human review of misclassifications

### Step 4: Test the Classifier

Save a real filing as a fixture and write unit tests:

```python
# tests/unit/detection/test_your_new_classifier.py

import pytest
from pathlib import Path
from services.detection.classifiers.your_new_classifier import classify_your_event

FIXTURES = Path("tests/fixtures/filings")

@pytest.mark.asyncio
async def test_positive_case():
    """Should correctly identify a real YOUR_NEW_EVENT filing."""
    text = (FIXTURES / "your_event_positive_example.txt").read_text()
    result = await classify_your_event(text, "BBG000B9XRY4")
    assert result.is_your_event is True
    assert result.confidence >= 0.80
    assert result.counterparty_name is not None

@pytest.mark.asyncio
async def test_negative_case_similar_filing():
    """Should NOT fire on a similar-looking but non-qualifying filing."""
    text = (FIXTURES / "your_event_false_positive_risk.txt").read_text()
    result = await classify_your_event(text, "BBG000B9XRY4")
    assert result.is_your_event is False or result.confidence < 0.50

@pytest.mark.asyncio  
async def test_low_confidence_on_ambiguous():
    """Ambiguous cases should produce low confidence, not confident wrong answers."""
    text = (FIXTURES / "your_event_ambiguous.txt").read_text()
    result = await classify_your_event(text, "BBG000B9XRY4")
    # Either correct classification or appropriately uncertain
    assert result.confidence < 0.70 or result.is_your_event == True
```

---

## Deduplication System

When the same underlying event is detected by both EDGAR and news pipelines, the deduplication system prevents two separate `CorporateEvent` records from being created and alerting the analyst twice.

`services/detection/dedup/dedup.py`:

```python
async def find_duplicate(candidate: CorporateEvent) -> CorporateEvent | None:
    """
    Returns existing event if a probable duplicate exists, else None.
    
    Duplicate detection strategy (ordered by specificity):
    1. Same accession_number (exact EDGAR match) → definite duplicate
    2. Same figi + same event_type + event within ±3 days → probable duplicate
    3. Same figi + deal_value within 5% + within ±7 days → probable duplicate
    
    When in doubt, return the existing event and merge metadata rather than
    creating a new record. Duplicate alerts are worse than merged records.
    """
    db = get_db()
    
    # Level 1: Exact source match
    if candidate.source_url:
        existing = db.table("events.corporate_events")\
            .select("*").eq("source_url", candidate.source_url).execute()
        if existing.data:
            return CorporateEvent(**existing.data[0])
    
    # Level 2: Same company + event type + time window
    cutoff = (candidate.detected_at - timedelta(days=3)).isoformat()
    similar = db.table("events.corporate_events")\
        .select("*")\
        .eq("figi", candidate.figi)\
        .eq("event_type", candidate.event_type.value)\
        .gte("detected_at", cutoff)\
        .execute()
    
    return CorporateEvent(**similar.data[0]) if similar.data else None
```

---

## Confidence Thresholds Reference

| Confidence | Status | Action |
|---|---|---|
| < 0.40 | Discarded | Not written to DB at all |
| 0.40 – 0.64 | `low_confidence` | Written to DB; no analyst alert |
| 0.65 – 0.79 | `new` | Written to DB; analyst alert (priority 2-3) |
| 0.80 – 0.89 | `new` | Written to DB; analyst alert (priority 4) |
| ≥ 0.90 | `new` | Written to DB; analyst alert (priority 5 — immediate) |

---

## Options Flow Anomaly Detection

This pipeline differs from EDGAR/news — it doesn't detect a single event but a statistical anomaly that suggests a forthcoming event.

```python
# services/detection/pipelines/options_flow_pipeline.py

def compute_volume_zscore(ticker: str, current_volume: int, lookback_days: int = 20) -> float:
    """Z-score of today's options volume vs. 20-day rolling history."""
    historical = get_historical_options_volume(ticker, lookback_days)
    mu, sigma = historical.mean(), historical.std()
    return (current_volume - mu) / sigma if sigma > 0 else 0.0

def score_options_anomaly(ticker: str, chain: OptionsChainSnapshot) -> OptionsAnomalyScore:
    """
    Composite anomaly score across multiple dimensions:
    - Volume z-score (call volume vs. 20d avg)
    - Put/call ratio deviation
    - OTM call concentration
    - IV term structure shape change
    - Large single-order sweeps
    
    Returns score 0-100. Score >= 75 triggers event detection review.
    """
    ...
```

---

## Critical Rules

1. **Every pipeline must have a keyword pre-filter.** LLM calls are expensive and slow. Pre-filter 90%+ of irrelevant filings before invoking the LLM.
2. **`temperature=0` for all classification chains.** Never deviate. Reproducibility is essential for debugging misclassifications.
3. **Store `raw_content` always.** First 5,000 chars minimum. You will need it to debug misclassifications and retrain models.
4. **Never create a `CorporateEvent` without checking deduplication first.** Run `find_duplicate()` before every insert.
5. **Classify uncertainty honestly.** A `confidence=0.45` that's correct is better than a `confidence=0.95` that's wrong. The model should express genuine uncertainty on ambiguous filings.
6. **Include concrete examples in every classification prompt.** This is the highest-leverage improvement you can make to classification accuracy.
7. **Save real filing fixtures for every event type.** Tests against synthetic data are nearly worthless — tests against real filings catch real failures.
8. **Add new event types to `EVENT_METADATA` immediately.** Downstream layers (signal generation, opportunity brief) read from this map. Missing metadata causes silent failures.

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: fundamental-engine -->
<!-- ════════════════════════════════════════════════════════ -->

---
name: fundamental-engine
description: Use this skill when building or modifying fundamental analysis components: financial model pulls, XBRL parsing, comparable company analysis, DCF/EV/NAV valuation scenarios, LLM-powered document analysis (earnings transcripts, M&A filings, technical reports), or mining/resource NAV models. Trigger when the task involves: FundamentalSnapshot, valuation scenarios, XBRL, comps tables, NAV, earnings transcripts, or filing document extraction.
---

# Fundamental Engine Skill — antigravity/APEX

The fundamental engine is what separates APEX from a pure pattern-matching signal system. Every event-driven opportunity must have a valuation anchor before a signal is generated. This skill documents how to build and extend fundamental analysis components that are accurate, automated, and event-aware.

---

## Core Principle

**Every `CorporateEvent` that reaches "under_review" status must have an associated `FundamentalSnapshot` in the database before `AlphaSignal` generation is triggered.** The signal generator checks for this. If the snapshot is missing, it logs an error and waits (up to 5 minutes with retries) before proceeding. This prevents signals being generated on events without fundamental grounding.

---

## The FundamentalSnapshot

This is the central output of the fundamental engine. Every valuation-related component writes to or reads from this schema.

`shared/schemas/fundamentals.py`:
```python
class FundamentalSnapshot(BaseModel):
    figi: str
    as_of: date
    period_type: Literal["Q", "A"]          # Quarterly or Annual
    
    # Income Statement (TTM)
    revenue_ttm: float
    gross_profit_ttm: float
    ebitda_ttm: float
    ebit_ttm: float
    net_income_ttm: float
    
    # Cash Flow (TTM)
    cfo_ttm: float
    capex_ttm: float
    fcf_ttm: float                          # = cfo_ttm - capex_ttm
    
    # Balance Sheet (most recent quarter)
    cash: float
    total_debt: float
    net_debt: float                         # = total_debt - cash
    book_value: float
    shares_diluted: int
    
    # Computed market metrics (updated daily with price)
    market_cap: float
    ev: float                               # = market_cap + net_debt
    ev_ebitda: Optional[float]              # None if ebitda <= 0
    ev_ebit: Optional[float]
    p_e: Optional[float]
    p_fcf: Optional[float]
    p_book: Optional[float]
    fcf_yield: Optional[float]
    
    # Forward estimates (from guidance or consensus)
    guidance_revenue_low: Optional[float]
    guidance_revenue_high: Optional[float]
    guidance_ebitda_low: Optional[float]
    guidance_ebitda_high: Optional[float]
    consensus_eps_next_year: Optional[float]
    
    # Resource-specific (null for non-resource companies)
    nav_per_share: Optional[float]          # Mining/resource NAV
    p_nav: Optional[float]                  # Price / NAV
    aisc_per_oz: Optional[float]            # All-in sustaining cost (gold/silver)
    reserve_life_years: Optional[float]
    primary_commodity: Optional[str]
    
    data_sources: list[str]                 # Which sources contributed
    computed_at: datetime
```

---

## XBRL Financial Data Pull

SEC XBRL data is the primary source for all public company financials. It's machine-readable and avoids the errors of LLM-parsing financial statements.

`services/fundamental/xbrl/xbrl_client.py`:
```python
import httpx
from shared.schemas.fundamentals import RawXBRLData

BASE_URL = "https://data.sec.gov/api/xbrl"

async def fetch_company_facts(cik: str) -> dict:
    """
    Fetches all XBRL-tagged financial facts for a company.
    Returns the raw SEC API response — normalization happens in xbrl_normalizer.py.
    
    CIK: 10-digit SEC identifier (zero-padded). Obtain from securities.cik column.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BASE_URL}/companyfacts/CIK{cik.zfill(10)}.json",
            headers={"User-Agent": "APEX Trading research@apexcapital.com"},  # Required by SEC
        )
        resp.raise_for_status()
        return resp.json()

def extract_ttm_metric(
    facts: dict,
    concept: str,                           # e.g., "us-gaap/Revenues"
    units: str = "USD",
) -> float | None:
    """
    Extracts trailing-twelve-month value for an XBRL concept.
    
    Handles: mixed quarterly/annual, restatements (takes most recent),
    fiscal year vs. calendar year, multiple share classes.
    
    Returns None if fewer than 4 quarters of data exist.
    """
    try:
        data = facts["facts"]["us-gaap"][concept]["units"][units]
    except KeyError:
        return None
    
    # Get quarterly filings (form 10-Q), sorted by end date
    quarterly = sorted(
        [d for d in data if d["form"] in ("10-Q", "10-K") and d["accn"]],
        key=lambda x: x["end"],
        reverse=True
    )
    
    # Find 4 most recent non-overlapping quarters
    ttm_quarters = _select_ttm_quarters(quarterly)
    if len(ttm_quarters) < 4:
        return None
    
    return sum(q["val"] for q in ttm_quarters)
```

**Common XBRL concept mappings:**
```python
XBRL_CONCEPTS = {
    "revenue": "us-gaap/Revenues",                          # or RevenueFromContractWithCustomer
    "cost_of_revenue": "us-gaap/CostOfRevenue",
    "gross_profit": "us-gaap/GrossProfit",
    "operating_income": "us-gaap/OperatingIncomeLoss",
    "net_income": "us-gaap/NetIncomeLoss",
    "ebitda": None,                                          # Not directly reported; compute
    "capex": "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment",
    "cfo": "us-gaap/NetCashProvidedByUsedInOperatingActivities",
    "total_debt": "us-gaap/LongTermDebt",                   # May need + ShortTermDebt
    "cash": "us-gaap/CashAndCashEquivalentsAtCarryingValue",
    "shares_diluted": "us-gaap/CommonStockSharesOutstanding",
    "book_value": "us-gaap/StockholdersEquity",
}
# Note: Revenue concept varies by industry. E&P uses "OilAndGasSalesRevenue".
# Always check for alternative concepts when primary is missing.
```

---

## Comparable Company Analysis

`services/fundamental/comps/comps_engine.py`:

```python
def build_comps_table(
    figi: str,
    subsector: str,
    market_cap_usd: float,
    exclude_figis: list[str] = None,
) -> CompsTable:
    """
    Builds a comparable company multiples table for a given security.
    
    Peer selection criteria:
    - Same GICS subsector
    - Market cap 0.2x to 5.0x the subject company
    - Has positive EBITDA (negative EBITDA companies distort multiples)
    - Has reported in last 6 months
    - Not the subject company itself
    
    Returns median and quartile multiples for EV/EBITDA, EV/EBIT, P/FCF, P/E.
    """
    db = get_db()
    
    peers_query = db.table("market.fundamentals")\
        .select("figi, ev_ebitda, ev_ebit, p_fcf, p_e, market_cap_usd, ev")\
        .eq("s.subsector", subsector)\
        .gte("market_cap_usd", market_cap_usd * 0.20)\
        .lte("market_cap_usd", market_cap_usd * 5.0)\
        .gt("ebitda_ttm", 0)\
        .execute()
    
    peers = [p for p in peers_query.data if p["figi"] != figi]
    if exclude_figis:
        peers = [p for p in peers if p["figi"] not in exclude_figis]
    
    if len(peers) < 3:
        # Not enough peers in subsector; widen to sector
        logger.warning("insufficient_peers", subsector=subsector, count=len(peers))
        # ... recursive call with sector instead of subsector
    
    ev_ebitda_vals = [p["ev_ebitda"] for p in peers if p["ev_ebitda"]]
    
    return CompsTable(
        peer_figis=[p["figi"] for p in peers],
        peer_count=len(peers),
        ev_ebitda_p25=np.percentile(ev_ebitda_vals, 25),
        ev_ebitda_median=np.median(ev_ebitda_vals),
        ev_ebitda_p75=np.percentile(ev_ebitda_vals, 75),
        # ... repeat for other multiples
        subject_ev_ebitda_discount=(
            subject_snapshot.ev_ebitda / np.median(ev_ebitda_vals) - 1
        ),  # Negative = trading at discount to peers
    )
```

---

## Valuation Scenarios

Every fundamental snapshot feeds a three-scenario analysis. Scenarios are what the analyst reviews, not the snapshot itself.

```python
class ValuationScenario(BaseModel):
    label: Literal["bear", "base", "bull"]
    probability: float = Field(ge=0, le=1)
    ebitda_assumption: float
    multiple_assumption: float
    implied_ev: float
    implied_equity_value: float
    implied_price: float
    upside_pct: float                           # vs. current market price

def build_scenarios(
    snapshot: FundamentalSnapshot,
    comps: CompsTable,
    event: CorporateEvent,
    current_price: float,
) -> list[ValuationScenario]:
    """
    Generates bear/base/bull scenarios using comps multiples and EBITDA ranges.
    
    Multiple selection by scenario:
    - Bear: 25th percentile comps multiple
    - Base: Median comps multiple (or target multiple if event implies re-rating)
    - Bull: 75th percentile comps multiple (or takeout multiple for M&A targets)
    
    EBITDA selection by scenario:
    - Bear: Low end of guidance (or TTM * 0.85 if no guidance)
    - Base: Midpoint of guidance (or TTM * 1.00)
    - Bull: High end of guidance (or TTM * 1.15)
    
    Event-specific overrides:
    - M&A target: Bull multiple = deal price; bear = pre-announcement price
    - Spinoff: Apply sum-of-parts logic separately
    - Activist: Bull includes premium for strategic action resolution
    """
    ...
```

---

## Mining NAV Model

For mining and natural resource developers, NAV is the primary valuation anchor.

`services/fundamental/nav/mining_nav.py`:

```python
class MiningNAV(BaseModel):
    figi: str
    as_of: date
    
    # Asset NAVs (after-tax, discounted)
    producing_assets_nav: float         # Mines currently in production
    development_assets_nav: float       # Projects with completed studies
    exploration_assets_nav: float       # Early-stage resources
    total_asset_nav: float              # Sum of above
    
    # Corporate adjustments
    net_debt: float                     # Balance sheet debt - cash
    corporate_adjustments: float        # G&A NPV, exploration spend, etc.
    
    # Per-share
    total_nav: float                    # = total_asset_nav - net_debt + adj
    shares_fully_diluted: int
    nav_per_share: float                # = total_nav / shares_fully_diluted
    
    # Market comparison
    current_price: float
    p_nav: float                        # = current_price / nav_per_share
    
    # Key assumptions
    commodity_price_deck: dict[str, float]  # {"gold_usd_oz": 2100, ...}
    discount_rate: float                    # WACC used
    computed_at: datetime

def compute_producing_asset_nav(
    resource_tonnes: float,
    grade_gpt: float,                   # grams per tonne (gold)
    recovery_pct: float,
    aisc_per_oz: float,                 # All-in sustaining cost
    commodity_price: float,             # Gold price assumption
    mine_life_years: int,
    annual_production_oz: float,
    discount_rate: float = 0.05,
    tax_rate: float = 0.25,
) -> float:
    """
    DCF-based NAV for a producing mine.
    
    FCF per year = Annual production * (commodity price - AISC) * (1 - tax rate)
    NAV = PV of FCF over mine life
    """
    annual_fcf = annual_production_oz * (commodity_price - aisc_per_oz) * (1 - tax_rate)
    nav = sum(
        annual_fcf / (1 + discount_rate) ** year
        for year in range(1, mine_life_years + 1)
    )
    return max(nav, 0)  # NAV cannot be negative for producing assets
```

**Commodity price deck:** Always use a blend of: spot price (weight 40%), 1-year forward (30%), analyst consensus long-term (30%). Never use only spot — this makes NAV too volatile and whipsaw-prone.

---

## LLM Document Analysis

### Earnings Transcript Extraction

```python
class TranscriptAnalysis(BaseModel):
    """Structured output from earnings call transcript analysis."""
    guidance_raised: bool
    guidance_lowered: bool
    guidance_maintained: bool
    revenue_guidance_low: Optional[float]
    revenue_guidance_high: Optional[float]
    ebitda_guidance_low: Optional[float]
    ebitda_guidance_high: Optional[float]
    management_tone: Literal["very_positive", "positive", "neutral", "cautious", "negative"]
    key_positive_developments: list[str]    # Max 5
    key_risks_mentioned: list[str]          # Max 5
    backlog_change: Optional[Literal["increased", "decreased", "stable", "not_mentioned"]]
    ma_language: Optional[str]             # Any M&A/strategic language
    commodity_sensitivity: Optional[str]   # Commodity exposure language
    capex_outlook: Optional[str]
    reasoning: str

TRANSCRIPT_PROMPT = ChatPromptTemplate.from_template("""
You are an expert analyst for an event-driven hedge fund focused on industrials 
and natural resources. Analyze this earnings call transcript and extract 
structured information.

Pay particular attention to:
1. Exact guidance figures (use None if not stated)
2. Changes vs. prior guidance (raised/lowered/maintained)
3. Management confidence and hedging language
4. Backlog and order trends (critical for industrials)
5. Any strategic/M&A language
6. Commodity price sensitivity commentary

TRANSCRIPT:
{transcript_text}

PRIOR GUIDANCE:
Revenue: {prior_revenue_guidance}
EBITDA: {prior_ebitda_guidance}

{format_instructions}
""")
```

### M&A Filing Analysis (S-4, DEFM14A, SC TO)

Key extractions for deal analysis:
```python
class MAFilingAnalysis(BaseModel):
    deal_consideration: str             # "cash", "stock", "mixed", "cvr"
    cash_per_share: Optional[float]
    stock_exchange_ratio: Optional[float]
    total_consideration_usd: Optional[int]
    termination_fee_target: Optional[float]    # Target pays if walks
    termination_fee_acquirer: Optional[float]  # Acquirer pays if walks
    financing_committed: bool
    financing_type: Optional[str]       # "committed_debt", "equity", "balance_sheet"
    regulatory_approvals_needed: list[str]   # ["HSR", "CFIUS", "EU Phase I"]
    mac_clause_breadth: Literal["standard", "broad", "narrow"]
    expected_close_date: Optional[date]
    synergy_estimate_low: Optional[float]
    synergy_estimate_high: Optional[float]
    synergy_type: Optional[str]         # "cost", "revenue", "both"
    shareholder_vote_required_target: bool
    shareholder_vote_required_acquirer: bool
    go_shop_period_days: Optional[int]  # Days target can solicit other bids
    key_conditions: list[str]           # Other closing conditions
```

---

## Critical Rules

1. **FundamentalSnapshot must exist before AlphaSignal generation.** The signal generator enforces this. Don't work around it.
2. **Use XBRL API for all financial data.** Never parse 10-K/Q text for numbers with an LLM — XBRL is more accurate and cheaper.
3. **Store `guidance_revenue_low/high` and `guidance_ebitda_low/high` as soon as guidance is given.** Guidance changes are the most reliable event signal in industrials.
4. **NAV models must store the commodity price deck used.** A NAV without documented price assumptions is useless for back-comparison.
5. **Always compute scenarios in units the analyst can verify.** Show implied price per share, not just EV — analysts think in stock price terms.
6. **Resource companies require the mining NAV model, not just EV/EBITDA comps.** Applying an industrial multiple to a mining developer is the #1 valuation error in this sector.
7. **All LLM extraction outputs require manual spot-checks weekly.** LLMs hallucinate specific numbers. Build a verification workflow that flags extractions where the LLM-extracted number differs significantly from XBRL data.
8. **EBITDA is computed, never extracted directly.** `EBITDA = Operating Income + D&A`. Always compute from components — never take EBITDA reported in press releases at face value (adjustments vary).

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: quant-signals -->
<!-- ════════════════════════════════════════════════════════ -->

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

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: risk-management -->
<!-- ════════════════════════════════════════════════════════ -->

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

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: execution -->
<!-- ════════════════════════════════════════════════════════ -->

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

---

<!-- ════════════════════════════════════════════════════════ -->
<!-- SKILL: n8n-workflows -->
<!-- ════════════════════════════════════════════════════════ -->

---
name: n8n-workflows
description: Use this skill when building, modifying, or debugging n8n workflows in the antigravity/APEX system. Covers APEX-specific workflow patterns, node configurations, error handling, environment variable usage, webhook design, inter-service communication, and workflow export/import conventions. Trigger when the task involves any n8n workflow JSON, n8n node configuration, cron scheduling, webhook triggers, or the workflows/ directory.
---

# n8n Workflows Skill — antigravity/APEX

n8n is the nervous system that connects APEX's data sources, processing services, and alerting. It handles timing, retries, error isolation, and the complex conditional routing that would otherwise require brittle Python scheduling code. This skill documents APEX's specific workflow patterns.

---

## Core Principles for APEX Workflows

1. **Workflows are glue, not logic.** Heavy computation (LLM calls, factor calculations, risk checks) happens in Python microservices called via HTTP. n8n handles the "when, what, and if it fails."
2. **Every workflow logs to Supabase.** The `workflow_runs` table tracks every execution with status, duration, and error details.
3. **No secrets in workflows.** All API keys and credentials come from n8n environment variables (Settings → Variables), never hardcoded in node configurations.
4. **Workflows are version-controlled.** Every workflow is exported to `workflows/` as JSON and committed to git. Name convention: `{workflow-name}.json`.

---

## Standard Workflow Template

Every new workflow follows this structure:

```
[Trigger Node]
    ↓
[Workflow Logger: START]      ← Always first after trigger
    ↓
[Core Processing Nodes]
    ↓
[Workflow Logger: SUCCESS]    ← On happy path
[Error Handler]               ← On any node failure
    ↓
[Alert: Slack #ops-alerts]    ← Only for critical failures
```

### Workflow Logger Node (Code Node)

Add this Code node immediately after every trigger and before every terminal state:

```javascript
// Workflow Logger — paste this into every "log start" Code node

const workflowName = $workflow.name;
const runId = $execution.id;
const status = $input.first().json.log_status || 'RUNNING';  // Passed via parameter

const logEntry = {
  workflow_name: workflowName,
  run_id: runId,
  status: status,
  started_at: new Date().toISOString(),
  trigger_data: JSON.stringify($input.first().json).substring(0, 1000),  // First 1KB
};

// Write to Supabase
const response = await $http.request({
  method: 'POST',
  url: `${$env.SUPABASE_URL}/rest/v1/system.workflow_runs`,
  headers: {
    'apikey': $env.SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${$env.SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
  },
  body: JSON.stringify(logEntry),
});

return [{ json: { ...logEntry, logged: true } }];
```

---

## Workflow: edgar-realtime-monitor

**Trigger:** Schedule — every 60 seconds, 24/7 (filings happen outside US market hours)

**Purpose:** Detect new SEC filings for securities in our universe

```
[Schedule: every 60s]
    ↓
[HTTP: GET EDGAR EFTS API]
    URL: https://efts.sec.gov/LATEST/search-index
    Params: 
      q: ""
      forms: "8-K,13D,13G,SC+TO,DEFM14A,S-4,Form+4"
      dateRange: "custom"
      startdt: {{ $vars.EDGAR_LAST_POLL_TS }}  ← stored as n8n variable, updated each run
      enddt: {{ $now.toISO() }}
    
    ↓
[Code: Filter & Deduplicate]
    - Filter hits by form whitelist
    - Remove accession numbers already in Supabase (batch check)
    - Return only new, unprocessed filings
    
    ↓
[IF: any new filings?]
    NO → [Update EDGAR_LAST_POLL_TS] → [End]
    YES ↓
    
[Split in Batches: 5 per batch]    ← Prevent overwhelming the LLM API
    ↓
[HTTP: POST /classify-event]       ← Python FastAPI service
    URL: {{ $env.CLASSIFICATION_SERVICE_URL }}/classify
    Body: { accession_no, form_type, cik, filing_url }
    Timeout: 30 seconds
    
    ↓
[IF: confidence >= 0.65?]
    NO → [HTTP: POST Supabase events (status=low_confidence)] → next item
    YES ↓
    
[HTTP: POST Supabase events (status=new)]
    ↓
[HTTP: POST Redis publish new_event]
    URL: {{ $env.REDIS_REST_URL }}/publish
    Body: { channel: "apex:events:new", message: {{ event_json }} }
    
    ↓
[IF: event.confidence >= 0.80?]
    YES → [Slack: #event-alerts] with event summary
    
[Update EDGAR_LAST_POLL_TS]        ← Always update, even if no new filings
```

**Key configuration:**
```
EDGAR_LAST_POLL_TS: n8n workflow variable (persists between runs)
Initial value: "2024-01-01T00:00:00"
Update frequency: After each successful poll, set to current timestamp minus 5 minutes (overlap buffer)
```

**Error handling:**
- EDGAR API 429 (rate limit): Wait node (30 seconds) → retry once → if still fails, continue without updating timestamp (will retry same window next poll)
- EDGAR API 500: Log error, send Slack alert to #ops-critical, continue (don't update timestamp)
- Classification service timeout: Log, skip this filing, continue with others

---

## Workflow: fundamental-enricher

**Trigger:** Redis Subscribe on `apex:events:new` channel (via Webhook trigger listening to a Redis-to-HTTP bridge)

**Purpose:** Automatically trigger fundamental analysis for every new high-confidence event

```
[Webhook: POST /n8n/new-event]     ← Redis bridge calls this on new_event channel message
    Body: CorporateEvent JSON
    ↓
[Code: Parse & validate event]
    - Parse JSON to CorporateEvent schema
    - Check event type is in REQUIRES_FUNDAMENTAL list
    - If not requires_fundamental → End (no-op)
    
    ↓
[HTTP: POST /fundamental/enrich]   ← Python FastAPI fundamental service
    URL: {{ $env.FUNDAMENTAL_SERVICE_URL }}/enrich
    Body: { event_id, figi, event_type }
    Timeout: 60 seconds            ← XBRL pull + comps can take 30-60s
    
    ↓
[IF: enrichment successful?]
    NO → [Retry once after 30s] → [Log failure to Supabase] → [Alert #ops]
    YES ↓
    
[HTTP: POST /signals/generate]     ← Trigger signal generation
    URL: {{ $env.SIGNAL_SERVICE_URL }}/generate
    Body: { event_id }
    
    ↓
[HTTP: POST /dashboard/notify]     ← Tell analyst dashboard to refresh
    Body: { event_id, figi, priority }
```

---

## Workflow: options-flow-scanner

**Trigger:** Schedule — every 5 minutes, 9:30 AM – 4:00 PM EST weekdays only

```
[Schedule: every 5min, market hours]
    ↓
[HTTP: GET Polygon options volume]
    For each figi in active universe (paginated)
    
    ↓
[Code: Compute z-scores]
    For each ticker:
    - Current options volume vs. 20-day rolling average
    - Put/call ratio vs. 30-day average
    - OTM call sweep detection
    
    ↓
[IF: any z-score > 4.0?]          ← 4 sigma is the alert threshold
    YES ↓
    
[HTTP: POST Supabase options_anomalies table]
    ↓
[HTTP: POST /classify-options-anomaly]    ← LLM context check
    Check if known event explains the flow (earnings, known news)
    If no known explanation: this is pre-event positioning
    
    ↓
[IF: unexplained and z-score > 5.0?]
    YES → [Slack: #options-flow alert with details]
    YES → [HTTP: POST Supabase events (type=OPTIONS_ANOMALY)]
```

---

## Workflow: risk-monitor

**Trigger:** Schedule — every 30 seconds, 9:25 AM – 4:30 PM EST weekdays

```
[Schedule: every 30s]
    ↓
[HTTP: GET /risk/snapshot]         ← Python risk service computes live snapshot
    URL: {{ $env.RISK_SERVICE_URL }}/snapshot
    Timeout: 5 seconds             ← Must be fast; this runs constantly
    
    ↓
[HTTP: POST Supabase risk_snapshots]    ← Write to TimescaleDB hypertable
    ↓
[Code: Check limits]
    - gross_exposure > 1.45 * nav → WARNING
    - gross_exposure > 1.50 * nav → CRITICAL
    - single_sector_pct > 0.30 → WARNING
    - single_sector_pct > 0.35 → CRITICAL
    - daily_loss_pct < -0.025 → WARNING
    - daily_loss_pct < -0.030 → CRITICAL + HALT NEW POSITIONS
    
    ↓
[IF: any CRITICAL?]
    YES → [Slack: #risk-critical @risk-team] + [HTTP: POST /risk/halt-new-positions]
    
[IF: any WARNING?]
    YES → [Slack: #risk-warnings] (no halt)
```

**Important:** The 30-second risk snapshot is how Grafana's risk dashboard stays real-time. Never increase this interval without understanding the impact on dashboard freshness.

---

## Workflow: eod-report

**Trigger:** Schedule — 5:30 PM EST, weekdays only (after options expiry data is complete)

```
[Schedule: 5:30 PM EST weekdays]
    ↓
[HTTP: POST /reporting/generate-eod]
    URL: {{ $env.REPORTING_SERVICE_URL }}/eod
    Timeout: 300 seconds           ← Report generation can take 2-5 minutes
    Returns: { report_url, summary_json }
    
    ↓
[Code: Format summary message]
    Extract: daily P&L, top movers, active events count, risk metrics
    
    ↓
[Slack: #daily-pnl]
    Message: Formatted daily summary with key stats
    Include: Link to full PDF report
    
    ↓
[HTTP: POST Supabase reports table]
    Store report URL for dashboard access
```

---

## Environment Variables Used in Workflows

All n8n environment variables (Settings → Variables in n8n UI):

```
# Service URLs (all internal; no external exposure)
CLASSIFICATION_SERVICE_URL  http://classification:8001
FUNDAMENTAL_SERVICE_URL     http://fundamental:8002
SIGNAL_SERVICE_URL          http://signals:8003
RISK_SERVICE_URL            http://risk:8004
REPORTING_SERVICE_URL       http://reporting:8005

# Supabase
SUPABASE_URL                https://your-project.supabase.co
SUPABASE_ANON_KEY           eyJ...  (read-only key for n8n; write via service role in Python services)

# Redis REST Bridge
REDIS_REST_URL              http://redis-rest:8080  (Upstash Redis REST or custom bridge)

# Alerting
SLACK_BOT_TOKEN             xoxb-...
SLACK_OPS_CHANNEL           #ops-alerts
SLACK_RISK_CHANNEL          #risk-critical
SLACK_EVENTS_CHANNEL        #event-alerts

# APEX control
APEX_ENV                    paper  (or production)

# n8n workflow state (workflow variables, not environment)
EDGAR_LAST_POLL_TS          2024-01-01T00:00:00  (updated by edgar-realtime-monitor)
```

---

## Error Handling Patterns

### Pattern 1: Retry with Backoff
For transient errors (rate limits, timeouts):
```
[HTTP Node with error]
    ↓ (on error output)
[Wait: 30 seconds]
    ↓
[HTTP Node: retry once]
    ↓ (on error output)
[Log error to Supabase] + [Slack alert if critical]
    ↓
[End: continue processing remaining items]
```

### Pattern 2: Partial Batch Failure
For batch operations where some items fail:
```javascript
// Code node after batch HTTP call
const results = $input.all();
const successes = results.filter(r => !r.json.error);
const failures = results.filter(r => r.json.error);

if (failures.length > 0) {
  // Log failures but don't block the successes
  for (const fail of failures) {
    console.error(`Failed: ${JSON.stringify(fail.json)}`);
  }
}

// Continue with successes only
return successes;
```

### Pattern 3: Alert Deduplication
Prevent Slack spam from repeated failures:
```javascript
// Before sending Slack alert, check if we sent one in the last 15 minutes
const alertKey = `n8n:alert:${$workflow.name}:${errorType}`;
const lastAlert = await $http.request({
  url: `${$env.REDIS_REST_URL}/get/${alertKey}`,
});

if (!lastAlert.data.result) {
  // No recent alert — send it and set a 15-minute cooldown
  // ... send Slack message ...
  await $http.request({
    method: 'POST',
    url: `${$env.REDIS_REST_URL}/set/${alertKey}/1/EX/900`,  // 900s = 15 min TTL
  });
}
```

---

## Exporting and Versioning Workflows

```bash
# Export a workflow after modifying in n8n UI
# Settings → Workflows → Export → JSON
# Save to: workflows/{workflow-name}.json

# Git commit convention:
git add workflows/edgar-realtime-monitor.json
git commit -m "chore(n8n): add 13G form to EDGAR monitor filter list"

# Import workflow to a new n8n instance:
# Settings → Workflows → Import from File
```

---

## Critical Rules

1. **No business logic in n8n Code nodes.** Route, filter, transform data shape. Compute in Python services.
2. **Always log workflow start and end to Supabase `system.workflow_runs`.** This is your operational audit trail.
3. **Every n8n variable with a secret goes through Settings → Variables, never in node configs.** Credentials in node configs are visible in workflow exports.
4. **Test every new workflow with the "Test Workflow" button before activating.** Check every output path including error branches.
5. **Market hours scheduling:** Use the Schedule trigger with `Timezone: America/New_York` and cron expressions that respect 9:30 AM – 4:00 PM. Never use UTC for market-hours workflows.
6. **Export the workflow JSON to `workflows/` after every non-trivial change.** Treat the JSON file as the source of truth; the n8n database as the running instance.
7. **Use `Split in Batches` for any loop over multiple items.** Never use a JavaScript for-loop to make sequential HTTP calls inside a Code node — it blocks the node and creates timeout risk.
8. **EDGAR poll interval is 60 seconds minimum.** SEC EDGAR has rate limits. Faster polling results in 429 responses and gaps in coverage.
