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
