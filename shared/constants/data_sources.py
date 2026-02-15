"""
Data source registry for all external feeds.

Every ingest pipeline must register its source here before writing to Supabase.
"""

from enum import Enum


class DataSource(str, Enum):
    """All external data sources APEX ingests from."""

    # ── SEC / Regulatory ─────────────────────────────────────
    EDGAR = "EDGAR"
    SEDAR = "SEDAR"

    # ── Market Data ──────────────────────────────────────────
    POLYGON = "POLYGON"
    POLYGON_WS = "POLYGON_WS"
    POLYGON_OPTIONS = "POLYGON_OPTIONS"

    # ── Commodity Data ───────────────────────────────────────
    EIA = "EIA"
    BAKER_HUGHES = "BAKER_HUGHES"
    LME = "LME"
    QUANDL = "QUANDL"

    # ── News & Sentiment ─────────────────────────────────────
    BENZINGA = "BENZINGA"
    NEWS_API = "NEWS_API"

    # ── Reference Data ───────────────────────────────────────
    OPEN_FIGI = "OPEN_FIGI"

    # ── Internal / Derived ───────────────────────────────────
    LLM_EXTRACTION = "LLM_EXTRACTION"
    XBRL = "XBRL"
    COMPUTED = "COMPUTED"
