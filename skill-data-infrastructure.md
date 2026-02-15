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
