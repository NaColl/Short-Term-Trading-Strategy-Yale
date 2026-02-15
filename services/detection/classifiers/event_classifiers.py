"""
L2 Event Detection — LangChain Classification Chains.

Each classifier uses Claude with temperature=0 for deterministic
classification. Returns structured Pydantic output with confidence scores.

Rule: temperature=0 ALWAYS for classification. No exceptions.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from shared.logging.logger import get_logger

logger = get_logger(__name__)


# ── Extraction Schemas ───────────────────────────────────────────

class MAEventExtraction(BaseModel):
    """Structured output for M&A event classification."""
    is_ma_event: bool = Field(description="Is this filing an M&A/acquisition event?")
    confidence: float = Field(ge=0.0, le=1.0, description="Classification confidence")
    subtype: Optional[str] = Field(
        None,
        description="Subtype: acquisition_target, acquisition_acquirer, "
        "hostile_approach, deal_break, deal_amendment",
    )
    event_date: Optional[date] = Field(None, description="Date of event if determinable")
    deal_value_usd: Optional[float] = Field(None, description="Total deal value in USD")
    premium_pct: Optional[float] = Field(None, description="Premium to undisturbed price")
    consideration_type: Optional[str] = Field(None, description="cash, stock, or mixed")
    counterparty_name: Optional[str] = Field(None, description="Other party in transaction")
    key_facts: list[str] = Field(default_factory=list, description="Top 5 important facts")
    risk_factors: list[str] = Field(default_factory=list, description="Top 3 risks")
    reasoning: str = Field(description="1-2 sentence classification explanation")


class ActivistEventExtraction(BaseModel):
    """Structured output for activist/13D classification."""
    is_activist_event: bool = Field(description="Is this an activist engagement?")
    confidence: float = Field(ge=0.0, le=1.0)
    subtype: Optional[str] = Field(
        None, description="13d_new, 13d_increase, settlement, proxy_fight, board_seats"
    )
    filer_name: Optional[str] = Field(None, description="Name of activist filer")
    ownership_pct: Optional[float] = Field(None, description="Reported ownership %")
    stated_intentions: Optional[str] = Field(None, description="Stated purpose from filing")
    key_facts: list[str] = Field(default_factory=list)
    reasoning: str = Field(description="Classification explanation")


class SpinoffEventExtraction(BaseModel):
    """Structured output for spinoff/restructuring classification."""
    is_spinoff_event: bool = Field(description="Is this a spinoff/separation event?")
    confidence: float = Field(ge=0.0, le=1.0)
    subtype: Optional[str] = Field(
        None, description="announced, completed, cancelled, asset_sale"
    )
    entity_being_separated: Optional[str] = Field(None)
    distribution_ratio: Optional[str] = Field(None, description="Share distribution ratio")
    expected_completion: Optional[date] = Field(None)
    key_facts: list[str] = Field(default_factory=list)
    reasoning: str = Field(description="Classification explanation")


class GenericEventExtraction(BaseModel):
    """Fallback extraction for events not fitting specialized classifiers."""
    event_detected: bool = Field(description="Was any significant corporate event detected?")
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_event_type: Optional[str] = Field(None, description="Best-guess EventType value")
    headline: Optional[str] = Field(None, description="One-line event headline")
    key_facts: list[str] = Field(default_factory=list)
    reasoning: str = Field(description="Classification explanation")


# ── Prompts ──────────────────────────────────────────────────────

MA_PROMPT = ChatPromptTemplate.from_template("""
You are an expert event-driven hedge fund analyst specializing in industrials
and natural resources. You are reading an SEC filing to determine if it
contains a merger, acquisition, or deal-related event.

An M&A event includes: announced acquisitions, definitive agreements,
letters of intent, hostile approaches, deal terminations, deal amendments,
tender offers, and going-private transactions.

NOT M&A events: routine business combinations, internal restructurings
without third-party involvement, joint ventures (unless they involve
majority ownership transfer).

SEC FILING:
{filing_text}

COMPANY CONTEXT:
Ticker: {ticker}
Sector: {sector}
Market Cap: {market_cap}

Extract all relevant information and classify this filing.

{format_instructions}
""")

ACTIVIST_PROMPT = ChatPromptTemplate.from_template("""
You are an expert event-driven hedge fund analyst. You are reading an SEC
filing to determine if it contains an activist engagement event.

An activist event includes: new 13D filings, 13D amendments showing
increased ownership, proxy fight announcements, board seat demands,
activist settlements, consent solicitations.

NOT activist events: routine 13G filings (passive investors), 13D filings
from insiders or founding shareholders, routine 13D amendments without
strategy changes.

SEC FILING:
{filing_text}

COMPANY CONTEXT:
Ticker: {ticker}
Sector: {sector}

{format_instructions}
""")

SPINOFF_PROMPT = ChatPromptTemplate.from_template("""
You are an expert event-driven hedge fund analyst. You are reading an SEC
filing to determine if it contains a spinoff, separation, or divestiture event.

A spinoff/separation event includes: announced spinoffs, completed separations,
asset sales to third parties, reverse Morris Trust transactions, split-offs.

NOT spinoff events: routine asset sales in the ordinary course, small
non-core dispositions, internal reorganizations.

SEC FILING:
{filing_text}

COMPANY CONTEXT:
Ticker: {ticker}
Sector: {sector}

{format_instructions}
""")


# ── Classifier Chains ────────────────────────────────────────────

def _build_llm() -> ChatAnthropic:
    """Build Claude LLM with temperature=0 for classification."""
    return ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0,  # ALWAYS 0 for classification
        max_tokens=1024,
    )


# M&A Classifier
_ma_parser = PydanticOutputParser(pydantic_object=MAEventExtraction)
_ma_chain = MA_PROMPT | _build_llm() | _ma_parser

# Activist Classifier
_activist_parser = PydanticOutputParser(pydantic_object=ActivistEventExtraction)
_activist_chain = ACTIVIST_PROMPT | _build_llm() | _activist_parser

# Spinoff Classifier
_spinoff_parser = PydanticOutputParser(pydantic_object=SpinoffEventExtraction)
_spinoff_chain = SPINOFF_PROMPT | _build_llm() | _spinoff_parser


async def classify_ma_event(
    filing_text: str, figi: str, context: dict | None = None
) -> MAEventExtraction:
    """Classify whether a filing contains an M&A event."""
    context = context or {}
    return await _ma_chain.ainvoke({
        "filing_text": filing_text[:12000],
        "ticker": context.get("ticker", "UNKNOWN"),
        "sector": context.get("sector", "UNKNOWN"),
        "market_cap": context.get("market_cap", "UNKNOWN"),
        "format_instructions": _ma_parser.get_format_instructions(),
    })


async def classify_activist_event(
    filing_text: str, figi: str, context: dict | None = None
) -> ActivistEventExtraction:
    """Classify whether a filing contains an activist event."""
    context = context or {}
    return await _activist_chain.ainvoke({
        "filing_text": filing_text[:12000],
        "ticker": context.get("ticker", "UNKNOWN"),
        "sector": context.get("sector", "UNKNOWN"),
        "format_instructions": _activist_parser.get_format_instructions(),
    })


async def classify_spinoff_event(
    filing_text: str, figi: str, context: dict | None = None
) -> SpinoffEventExtraction:
    """Classify whether a filing contains a spinoff event."""
    context = context or {}
    return await _spinoff_chain.ainvoke({
        "filing_text": filing_text[:12000],
        "ticker": context.get("ticker", "UNKNOWN"),
        "sector": context.get("sector", "UNKNOWN"),
        "format_instructions": _spinoff_parser.get_format_instructions(),
    })
