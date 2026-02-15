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
