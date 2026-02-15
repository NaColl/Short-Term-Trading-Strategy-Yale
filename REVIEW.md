# APEX Trading System — Honest Technical Review

**Date:** 2026-02-15
**Reviewer:** Claude (automated code review)
**Verdict: This is not a 10/10 system. It is not generating alpha. It cannot trade.**

---

## Executive Summary

This codebase is an **architectural blueprint with partial implementation**. It describes
an ambitious 8-layer event-driven trading system, but the code cannot execute a single
trade end-to-end. The documentation (CLAUDE.md) describes a system that does not yet
exist. What exists is roughly **40% of a scaffold** — some layers are well-built, others
are stubs, and critical integration points are broken.

---

## Quantitative Assessment

| Metric | Value |
|---|---|
| Total Python files | 68 |
| Total lines of code | ~7,300 (including 922-line enum) |
| Actual logic lines (excl. imports, blanks, `__init__.py`) | ~3,500 |
| Test files | **0** |
| Test coverage | **0%** |
| Git commits | **1** ("Initial commit") |
| n8n workflow JSON files | **0** (documented as 7) |
| ML model artifacts (.pkl, .pt) | **0** (documented as 3) |
| Research notebooks | **0** (documented as multiple) |
| Working end-to-end pipelines | **0** |

---

## Layer-by-Layer Reality Check

### L1 — Data Ingest: 30% complete

**What works:** Three API connectors (EDGAR, Polygon, Commodity) are properly implemented
with httpx async clients, error handling, and rate limiting. They can fetch data from
external APIs.

**What doesn't work:** The Celery tasks that orchestrate these connectors are scaffolds.
They call the connectors but **never write to the database**. There are no
`insert_record()` calls. `scan_options_flow()` returns `{"status": "ok", "scanned": 0}`
unconditionally. `poll_insider_transactions()` is a time-gated stub returning zero
transactions. Data enters the system but goes nowhere.

### L2 — Event Detection: 85% complete (best layer)

**What works:** LangChain classifiers with well-written prompts, keyword pre-filters, EDGAR
pipeline with form-to-pipeline routing, SHA-256 deduplication with 4-level merge strategy.

**What doesn't work:** A typo in `_map_activist_subtype()` references
`EventType.ACTIVIST_BOARD_SEATS` — the correct enum value is `ACTIVIST_BOARD_SEAT`. This
will crash with `KeyError` on activist events with "board_seats" subtype.

### L3 — Fundamental Analysis: 85% complete

**What works:** XBRL client with proper TTM extraction (4-quarter non-overlapping), comps
engine with peer filtering (0.2x-5.0x market cap), bear/base/bull scenario builder with
probability weighting, mining NAV model with producing/development/exploration breakdown
and commodity price blending (40% spot, 30% forward, 30% consensus).

**What doesn't work:** The FastAPI app.py is a thin wrapper with no orchestration logic
connecting these components into a pipeline.

### L4 — Quant Signals: BROKEN

**Critical bug:** The factor calculators construct `FactorOutput(name=..., score=...,
confidence=..., inputs_used=...)` but the actual Pydantic schema `FactorOutput` requires
completely different fields: `factor_name`, `figi`, `event_id`, `raw_value`, `z_score`,
`percentile`, `signal_direction`. **Every factor computation will crash with
`ValidationError`.** The schemas and the code that uses them were written independently
and never integrated.

The composite scorer (`composite.py`) accesses `fo.name`, `fo.score`, `fo.confidence` —
none of these attributes exist on the `FactorOutput` model. This entire layer is
non-functional.

### L5 — Risk Management: 90% complete (strongest layer)

**What works:** Pre-trade risk checks are properly implemented and tested. The blocking
gate correctly rejects: missing analyst approval, oversized positions (with event-type
overrides), gross exposure breaches, daily loss halts, liquidity violations. Risk limits
are centralized in a frozen dataclass. The `RiskLimitException` class carries structured
metadata.

**What doesn't work:** `stop_loss_var.py` was not fully verified. No real-time portfolio
state feed exists to drive the monitors.

### L6 — Portfolio Construction: 75% complete

**What works:** Kelly criterion position sizing with half-Kelly robustness, conviction
scaling (5-star = 100%, 4-star = 75%, 3-star = 50%), liquidity-constrained sizing,
rebalancing logic for event completion/conviction changes.

**What doesn't work:** No integration with actual signal or portfolio data. All inputs are
raw dicts, not Pydantic models (contradicting CLAUDE.md's "Pydantic everywhere" rule).

### L7 — Execution: 40% complete

**What works:** Order strategy selection decision tree (MARKET for hard stops, VWAP for
large orders, TWAP for medium, LIMIT default), IBKR connection manager with live/paper
safety check, implementation shortfall computation.

**What doesn't work:** `submit_trade()` builds an order dict but never submits it to IBKR
(comment: "placeholder for live IBKR"). `handle_fill()` never persists fills to Supabase.
No async fill monitoring loop exists. The system literally cannot place a trade.

### L8 — Dashboard: 40% complete

**What works:** Streamlit landing page layout with KPI metrics, approval API with proper
UUID generation and audit logging.

**What doesn't work:** Dashboard shows hardcoded dummy data (BHP, XOM, PLTR). Not
connected to the database. Thesis detail page does not exist.

---

## Critical Bugs Found

1. **Build system broken:** `pyproject.toml` specifies `setuptools.backends._legacy:_Backend`
   which doesn't exist. Correct value is `setuptools.build_meta`. `pip install` fails
   immediately.

2. **FactorOutput schema mismatch:** Factors construct objects with fields (`name`, `score`,
   `confidence`, `inputs_used`) that don't exist on the Pydantic model. Every factor
   computation crashes with `ValidationError`. This means L4 is completely non-functional.

3. **Composite scorer field mismatch:** `composite.py` accesses `fo.name`, `fo.score`,
   `fo.confidence` on `FactorOutput` objects — none of these fields exist.

4. **EventType enum typo:** `ACTIVIST_BOARD_SEATS` should be `ACTIVIST_BOARD_SEAT`. Will
   crash on activist board-seat events.

5. **Signal threshold typo:** `SIGNAL_STRONG = 0.70` and `SIGNAL_MEDIUM = 0.70` are
   identical (copy-paste error).

6. **CorporateEvent requires event_category:** The `set_category_from_type` model_validator
   runs `after` init, but `event_category` is a required field with no default. You must
   always provide it manually, defeating the purpose of the auto-setter.

---

## What's Missing Entirely

| Documented Component | Exists? |
|---|---|
| `tests/` directory (unit, integration, fixtures) | No |
| `workflows/` n8n JSON exports (7 workflows) | No |
| `models/` ML artifacts (deal_break_xgb, distilbert, LSTM) | No |
| `notebooks/` research notebooks | No |
| `services/ingest/sedar/` (Canadian filings) | No |
| `services/ingest/options_flow/` | No |
| `services/detection/classifiers/` per-category chains | Partial (3 of ~13 categories) |
| `services/fundamental/filing_analysis/` LLM extraction | No |
| `services/signals/event_studies/` historical patterns | No |
| `services/signals/models/` PyTorch ML models | No |
| `services/risk/stress/` scenario stress tests | No |
| `services/portfolio/sizing/` Kelly + cvxpy module | Partial (in risk/portfolio/) |
| `services/portfolio/hedging/` hedge engine | No |
| `services/execution/algos/` TWAP/VWAP implementations | No (referenced, not implemented) |
| `services/dashboard/pages/` multi-page Streamlit | No |
| `services/dashboard/components/` reusable widgets | No |
| `services/dashboard/opportunity_brief/` template | No |

---

## Is This Generating Alpha?

**No.** This system cannot:

1. Ingest data into a database (connectors exist, persistence doesn't)
2. Compute a single factor score (schema mismatch crashes it)
3. Build a composite signal (depends on broken factors)
4. Size a position from real data (no signal pipeline to feed it)
5. Submit an order to any broker (IBKR submission is a placeholder)
6. Monitor fills or compute P&L (no fill loop exists)
7. Display real data to an analyst (dashboard uses hardcoded dummies)

The system has **zero evidence of ever having been run end-to-end**, even once. There is
one git commit, zero tests, and multiple integration points where schemas and code are
incompatible.

---

## What IS Good

To be fair, several components show genuine domain expertise:

- **Risk limits configuration** is thoughtful and realistic for a small event-driven fund
- **Pre-trade risk checks** are properly implemented with correct blocking behavior
- **XBRL financial extraction** handles TTM aggregation, balance sheet snapshots, and
  multiple GAAP concept names correctly
- **Mining NAV model** is a real DCF with proper price deck blending
- **Event taxonomy** (79 types, 14 categories) with historical win rates and hold periods
  shows real special-situations research knowledge
- **Deduplication strategy** (4-level: exact, hash, temporal, value-proximity) is
  well-designed
- **Order strategy selection** decision tree reflects real institutional execution thinking
- **Kelly criterion sizing** with half-Kelly, conviction scaling, and liquidity caps is
  textbook correct

---

## Honest Rating

| Dimension | Score | Notes |
|---|---|---|
| Architecture & Design | 7/10 | Well-thought-out 8-layer design, good separation of concerns |
| Documentation | 8/10 | CLAUDE.md is comprehensive (but describes a system that doesn't exist) |
| Code Quality (where it exists) | 6/10 | Clean Python, proper async, but schemas don't match code |
| Completeness | 2/10 | ~40% scaffolded, critical integration points broken |
| Test Coverage | 0/10 | Zero tests exist |
| Runability | 1/10 | Can't install (`pyproject.toml` broken), can't run end-to-end |
| Alpha Generation | 0/10 | Cannot execute any trade, process any data, or generate any signal |
| Production Readiness | 0/10 | Not close to deployable |
| **Overall** | **2/10** | Architecture with promise, but not a functioning system |

This is a **design document masquerading as a codebase**. The CLAUDE.md reads like a pitch
deck for a system that should exist but doesn't yet. The gap between documentation claims
and code reality is substantial.

To reach "alpha-generating investment system" status, this project needs:
1. Fix the build system so it installs
2. Fix the FactorOutput schema mismatch so signals can compute
3. Wire ingest tasks to actually persist data
4. Implement IBKR order submission
5. Connect the dashboard to real data
6. Write tests (the CLAUDE.md claims 100% coverage on risk checks — actual coverage is 0%)
7. Build the ML models, notebooks, and n8n workflows that are documented but don't exist
8. Run it end-to-end at least once
