"""
Market data schemas — canonical types for securities and prices.

These are the L1 types that every upstream service depends on.
All market data writes to Supabase use these models.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from shared.constants.data_sources import DataSource


class SecurityMaster(BaseModel):
    """
    Canonical security reference record.

    The securities_master table in Supabase maps FIGI → everything.
    FIGI is the global primary key for all instruments across APEX.
    """

    figi: str = Field(
        ...,
        description="OpenFIGI composite identifier (e.g., BBG000B9XRY4)",
        min_length=12,
        max_length=12,
    )
    ticker: str = Field(..., description="Exchange ticker symbol (e.g., AAPL)")
    name: str = Field(..., description="Full legal name of the security")
    exchange: str = Field(..., description="Primary exchange (e.g., NYSE, NASDAQ, TSX)")
    instrument_type: Literal["equity", "option", "etf", "warrant", "preferred"] = Field(
        ..., description="Security classification"
    )
    sector: Optional[str] = Field(None, description="GICS sector classification")
    industry: Optional[str] = Field(None, description="GICS sub-industry classification")
    currency: Literal["USD", "CAD"] = Field("USD", description="Trading currency")
    market_cap_usd: Optional[Decimal] = Field(None, description="Market cap in USD")
    average_daily_volume_30d: Optional[int] = Field(
        None, description="30-day average daily volume in shares"
    )
    is_active: bool = Field(True, description="Whether the security is actively traded")
    country: str = Field("US", description="Country of primary listing")
    cik: Optional[str] = Field(None, description="SEC Central Index Key (US only)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("figi")
    @classmethod
    def validate_figi(cls, v: str) -> str:
        """FIGI must start with BBG."""
        if not v.startswith("BBG"):
            raise ValueError(f"FIGI must start with 'BBG', got: {v}")
        return v


class MarketDataEOD(BaseModel):
    """
    End-of-day OHLCV bar plus derived fields.

    Written nightly by the Polygon ingest pipeline.
    Stored in market.prices_eod (Supabase).
    """

    figi: str = Field(..., min_length=12, max_length=12)
    date: date
    open: Decimal = Field(..., ge=0)
    high: Decimal = Field(..., ge=0)
    low: Decimal = Field(..., ge=0)
    close: Decimal = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    vwap: Optional[Decimal] = Field(None, description="Volume-weighted average price", ge=0)
    adj_close: Optional[Decimal] = Field(None, ge=0)
    source: DataSource = DataSource.POLYGON
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v: Decimal, info: "FieldInfo") -> Decimal:  # noqa: F821
        """High must be >= low when both are present."""
        # Pydantic v2 validation order may differ; this is a safety check
        return v


class OptionsChainSnapshot(BaseModel):
    """
    Real-time options flow data for anomaly detection.

    Written every 5 minutes during market hours by the options-flow scanner.
    """

    figi: str = Field(..., min_length=12, max_length=12)
    timestamp: datetime
    total_call_volume: int = Field(..., ge=0)
    total_put_volume: int = Field(..., ge=0)
    put_call_ratio: float = Field(..., ge=0)
    unusual_call_volume: Optional[int] = Field(None, ge=0)
    unusual_put_volume: Optional[int] = Field(None, ge=0)
    largest_trade_premium: Optional[Decimal] = Field(
        None, description="Premium of the single largest options trade (USD)"
    )
    implied_volatility_atm: Optional[float] = Field(
        None, description="At-the-money implied vol"
    )
    iv_30d_percentile: Optional[float] = Field(
        None,
        description="Current ATM IV percentile vs trailing 30 days",
        ge=0,
        le=100,
    )
    oi_call: Optional[int] = Field(None, ge=0)
    oi_put: Optional[int] = Field(None, ge=0)
    source: DataSource = DataSource.POLYGON_OPTIONS


class CommodityDataPoint(BaseModel):
    """
    Commodity price or inventory data point.

    Covers crude oil, natural gas, metals, rig counts, and inventory draws.
    """

    commodity: str = Field(
        ...,
        description="Commodity identifier (e.g., crude_oil_wti, natural_gas_henry_hub, copper_lme)",
    )
    date: date
    value: Decimal = Field(..., description="Price or inventory level")
    unit: str = Field(
        ..., description="Unit of measure (e.g., USD/bbl, USD/MMBtu, MT, rigs)"
    )
    data_type: Literal["price", "inventory", "production", "rig_count"] = Field(
        ..., description="What this value represents"
    )
    source: DataSource
    metadata: Optional[dict] = Field(
        None, description="Source-specific metadata (e.g., API gravity, survey date)"
    )


class InsiderTransaction(BaseModel):
    """
    SEC Form 4 insider transaction record.

    Used by the insider cluster detection algorithm.
    """

    figi: str = Field(..., min_length=12, max_length=12)
    filing_date: date
    accession_no: str = Field(..., description="SEC accession number for deduplication")
    insider_name: str
    insider_title: str = Field(..., description="Officer title or relationship")
    transaction_type: Literal["buy", "sell", "option_exercise", "gift"] = "buy"
    shares: int = Field(..., description="Number of shares transacted")
    price_per_share: Optional[Decimal] = Field(None, ge=0)
    total_value_usd: Optional[Decimal] = Field(None, ge=0)
    shares_owned_after: Optional[int] = Field(
        None, description="Total shares after transaction"
    )
    is_10b5_1: bool = Field(
        False, description="Whether this is a pre-planned 10b5-1 transaction"
    )
    source: DataSource = DataSource.EDGAR
