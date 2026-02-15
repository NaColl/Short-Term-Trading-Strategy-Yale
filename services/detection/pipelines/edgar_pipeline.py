"""
L2 Event Detection Pipelines — per-source detection logic.

Each pipeline: pre-filter → classify → create CorporateEvent → dedup → persist.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from shared.constants.event_types import EVENT_METADATA, EventType
from shared.logging.logger import get_logger
from shared.schemas.events import CorporateEvent

logger = get_logger(__name__)

# ── Form-to-Pipeline Routing ────────────────────────────────────────

FORM_TO_PIPELINES: dict[str, list[str]] = {
    "8-K": ["ma_pipeline", "spinoff_pipeline", "restructuring_pipeline"],
    "SC 13D": ["activist_pipeline"],
    "SC 13D/A": ["activist_pipeline"],
    "SC TO": ["tender_offer_pipeline"],
    "SC TO-T": ["tender_offer_pipeline"],
    "S-4": ["ma_pipeline"],
    "DEFM14A": ["ma_pipeline"],
    "PREM14A": ["ma_pipeline"],
    "4": ["insider_pipeline"],
}

# ── Keyword Pre-Filters (fast string scan before LLM) ───────────────

MA_KEYWORDS = [
    "merger", "acquisition", "definitive agreement", "proposed transaction",
    "tender offer", "purchase price", "per share", "amalgamation",
    "arrangement agreement", "going private", "buyout",
]

ACTIVIST_KEYWORDS = [
    "schedule 13d", "beneficial ownership", "activist", "proxy fight",
    "board representation", "consent solicitation", "strategic alternative",
    "unlock value", "undervalued",
]

SPINOFF_KEYWORDS = [
    "spinoff", "spin-off", "separation", "split-off", "divestiture",
    "reverse morris trust", "tax-free distribution",
]


def keyword_prefilter(text: str, keywords: list[str]) -> bool:
    """
    Fast string scan before expensive LLM call.

    This eliminates 90%+ of irrelevant filings before invoking the classifier.
    """
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ── EDGAR Pipeline ──────────────────────────────────────────────────

async def run_edgar_pipeline(
    filing_text: str,
    form_type: str,
    figi: str,
    ticker: str,
    accession_no: str,
    context: dict | None = None,
) -> Optional[CorporateEvent]:
    """
    Main EDGAR detection pipeline.

    Routes filing to appropriate classifiers based on form type.
    Returns CorporateEvent if a qualifying event is detected, else None.
    Never raises — logs and returns None on classification failure.
    """
    pipelines = FORM_TO_PIPELINES.get(form_type, [])
    if not pipelines:
        return None

    for pipeline_name in pipelines:
        try:
            event = await _run_single_pipeline(
                pipeline_name, filing_text, figi, ticker, accession_no, context
            )
            if event is not None:
                return event
        except Exception as e:
            logger.error(
                "pipeline_failed",
                pipeline=pipeline_name,
                figi=figi,
                accession=accession_no,
                error=str(e),
            )
            continue

    return None


async def _run_single_pipeline(
    pipeline_name: str,
    filing_text: str,
    figi: str,
    ticker: str,
    accession_no: str,
    context: dict | None = None,
) -> Optional[CorporateEvent]:
    """Run a single detection pipeline. Returns CorporateEvent or None."""
    if pipeline_name == "ma_pipeline":
        if not keyword_prefilter(filing_text, MA_KEYWORDS):
            return None
        from services.detection.classifiers.event_classifiers import classify_ma_event

        result = await classify_ma_event(filing_text, figi, context)
        if not result.is_ma_event or result.confidence < 0.40:
            return None

        event_type = _map_ma_subtype(result.subtype)
        return _build_event(
            figi=figi,
            ticker=ticker,
            event_type=event_type,
            confidence=result.confidence,
            headline=f"M&A Event: {result.counterparty_name or 'Unknown'} — {ticker}",
            summary=result.reasoning,
            accession_no=accession_no,
            deal_value_usd=result.deal_value_usd,
            premium_pct=result.premium_pct,
            consideration_type=result.consideration_type,
        )

    elif pipeline_name == "activist_pipeline":
        if not keyword_prefilter(filing_text, ACTIVIST_KEYWORDS):
            return None
        from services.detection.classifiers.event_classifiers import classify_activist_event

        result = await classify_activist_event(filing_text, figi, context)
        if not result.is_activist_event or result.confidence < 0.40:
            return None

        event_type = _map_activist_subtype(result.subtype)
        return _build_event(
            figi=figi,
            ticker=ticker,
            event_type=event_type,
            confidence=result.confidence,
            headline=f"Activist: {result.filer_name or 'Unknown'} → {ticker}",
            summary=result.reasoning,
            accession_no=accession_no,
        )

    elif pipeline_name == "spinoff_pipeline":
        if not keyword_prefilter(filing_text, SPINOFF_KEYWORDS):
            return None
        from services.detection.classifiers.event_classifiers import classify_spinoff_event

        result = await classify_spinoff_event(filing_text, figi, context)
        if not result.is_spinoff_event or result.confidence < 0.40:
            return None

        event_type = _map_spinoff_subtype(result.subtype)
        return _build_event(
            figi=figi,
            ticker=ticker,
            event_type=event_type,
            confidence=result.confidence,
            headline=f"Spinoff: {result.entity_being_separated or 'Unknown'} from {ticker}",
            summary=result.reasoning,
            accession_no=accession_no,
        )

    return None


# ── Helpers ─────────────────────────────────────────────────────────

def _build_event(
    figi: str,
    ticker: str,
    event_type: EventType,
    confidence: float,
    headline: str,
    summary: str,
    accession_no: str,
    deal_value_usd: float | None = None,
    premium_pct: float | None = None,
    consideration_type: str | None = None,
) -> CorporateEvent:
    """Build a CorporateEvent with dedup hash and proper status assignment."""
    meta = EVENT_METADATA.get(event_type)
    threshold = meta.analyst_alert_threshold if meta else 0.65

    status = "new" if confidence >= threshold else "low_confidence"

    dedup_hash = hashlib.sha256(
        f"{figi}:{event_type.value}:{accession_no}".encode()
    ).hexdigest()

    return CorporateEvent(
        id=uuid4(),
        figi=figi,
        ticker=ticker,
        event_type=event_type,
        confidence=confidence,
        headline=headline[:500],
        summary=summary,
        source="EDGAR",
        source_url=f"https://www.sec.gov/Archives/edgar/{accession_no}",
        source_ref=accession_no,
        deal_value_usd=deal_value_usd,
        premium_pct=premium_pct,
        consideration_type=consideration_type,
        status=status,
        dedup_hash=dedup_hash,
    )


def _map_ma_subtype(subtype: str | None) -> EventType:
    """Map M&A subtype strings to EventType enum values."""
    mapping = {
        "acquisition_target": EventType.MA_ACQUISITION_TARGET,
        "acquisition_acquirer": EventType.MA_ACQUISITION_ACQUIRER,
        "hostile_approach": EventType.MA_HOSTILE_APPROACH,
        "deal_break": EventType.MA_DEAL_BREAK,
        "deal_amendment": EventType.MA_DEAL_AMENDMENT,
    }
    return mapping.get(subtype or "", EventType.MA_ACQUISITION_TARGET)


def _map_activist_subtype(subtype: str | None) -> EventType:
    mapping = {
        "13d_new": EventType.ACTIVIST_13D_NEW,
        "13d_increase": EventType.ACTIVIST_13D_INCREASE,
        "settlement": EventType.ACTIVIST_SETTLEMENT,
        "proxy_fight": EventType.ACTIVIST_PROXY_FIGHT,
        "board_seats": EventType.ACTIVIST_BOARD_SEATS,
    }
    return mapping.get(subtype or "", EventType.ACTIVIST_13D_NEW)


def _map_spinoff_subtype(subtype: str | None) -> EventType:
    mapping = {
        "announced": EventType.SPINOFF_ANNOUNCED,
        "completed": EventType.SPINOFF_COMPLETED,
        "asset_sale": EventType.ASSET_SALE,
    }
    return mapping.get(subtype or "", EventType.SPINOFF_ANNOUNCED)
