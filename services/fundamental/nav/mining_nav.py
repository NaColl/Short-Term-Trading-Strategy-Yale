"""
L3 Mining NAV Model.

For mining and natural resource companies, NAV is the primary valuation anchor.
Computes DCF-based NAV for producing mines and risk-adjusts development assets.

Rule: Resource companies require the mining NAV model, not just EV/EBITDA comps.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel

from shared.logging.logger import get_logger

logger = get_logger(__name__)


class MiningNAV(BaseModel):
    """Net Asset Value breakdown for a mining company."""
    figi: str
    as_of: date

    # Individual asset NAVs (after-tax, discounted)
    producing_assets_nav: float
    development_assets_nav: float
    exploration_assets_nav: float
    total_asset_nav: float

    # Corporate adjustments
    net_debt: float
    corporate_adjustments: float  # G&A NPV, exploration spend

    # Per-share values
    total_nav: float
    shares_fully_diluted: int
    nav_per_share: float

    # Market comparison
    current_price: float
    p_nav: float  # = current_price / nav_per_share

    # Assumptions
    commodity_price_deck: dict[str, float]
    discount_rate: float
    computed_at: datetime


def compute_producing_asset_nav(
    annual_production_oz: float,
    commodity_price: float,
    aisc_per_oz: float,
    mine_life_years: int,
    discount_rate: float = 0.05,
    tax_rate: float = 0.25,
) -> float:
    """
    DCF-based NAV for a producing mine.

    FCF per year = annual_production × (commodity_price - AISC) × (1 - tax_rate)
    NAV = PV of FCF over mine life

    Rule: NAV cannot be negative for producing assets.
    """
    annual_fcf = annual_production_oz * (commodity_price - aisc_per_oz) * (1 - tax_rate)
    nav = sum(
        annual_fcf / (1 + discount_rate) ** year
        for year in range(1, mine_life_years + 1)
    )
    return max(nav, 0.0)


def compute_development_asset_nav(
    total_resource_oz: float,
    commodity_price: float,
    estimated_aisc: float,
    capex_to_build: float,
    years_to_production: int,
    discount_rate: float = 0.08,
    tax_rate: float = 0.25,
    risk_factor: float = 0.50,  # Development uncertainty
) -> float:
    """
    Risk-adjusted NAV for a development-stage mine.

    Applied risk factor (0.5 = 50% probability of reaching production).
    Higher discount rate than producing assets.
    """
    if years_to_production <= 0:
        return 0.0

    annual_production = total_resource_oz / max(years_to_production * 3, 1)
    once_producing_nav = compute_producing_asset_nav(
        annual_production_oz=annual_production,
        commodity_price=commodity_price,
        aisc_per_oz=estimated_aisc,
        mine_life_years=years_to_production * 3,
        discount_rate=discount_rate,
        tax_rate=tax_rate,
    )

    # Discount back to present and apply risk factor
    pv = once_producing_nav / (1 + discount_rate) ** years_to_production
    nav = (pv - capex_to_build) * risk_factor
    return max(nav, 0.0)


def build_commodity_price_deck(
    spot_prices: dict[str, float],
    forward_prices: dict[str, float] | None = None,
    consensus_lt: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Build blended commodity price deck.

    Blend: spot (40%) + 1-year forward (30%) + analyst consensus LT (30%).
    Rule: Never use only spot — this makes NAV too volatile.
    """
    forward = forward_prices or {}
    consensus = consensus_lt or {}
    blended = {}

    for commodity, spot in spot_prices.items():
        fwd = forward.get(commodity, spot)
        lt = consensus.get(commodity, spot)
        blended[commodity] = spot * 0.40 + fwd * 0.30 + lt * 0.30

    logger.info("price_deck_built", commodities=list(blended.keys()))
    return blended


def build_mining_nav(
    figi: str,
    producing_assets: list[dict[str, Any]],
    development_assets: list[dict[str, Any]],
    exploration_value: float,
    net_debt: float,
    corporate_adj: float,
    shares_diluted: int,
    current_price: float,
    price_deck: dict[str, float],
    discount_rate: float = 0.05,
) -> MiningNAV:
    """Build complete MiningNAV model from asset data."""
    producing_nav = sum(
        compute_producing_asset_nav(
            annual_production_oz=asset["annual_production_oz"],
            commodity_price=price_deck.get(asset["commodity"], 0),
            aisc_per_oz=asset["aisc_per_oz"],
            mine_life_years=asset["mine_life_years"],
            discount_rate=discount_rate,
        )
        for asset in producing_assets
    )

    development_nav = sum(
        compute_development_asset_nav(
            total_resource_oz=asset["total_resource_oz"],
            commodity_price=price_deck.get(asset["commodity"], 0),
            estimated_aisc=asset["estimated_aisc"],
            capex_to_build=asset["capex_to_build"],
            years_to_production=asset["years_to_production"],
        )
        for asset in development_assets
    )

    total_asset = producing_nav + development_nav + exploration_value
    total_nav = total_asset - net_debt + corporate_adj
    nav_ps = total_nav / shares_diluted if shares_diluted > 0 else 0

    return MiningNAV(
        figi=figi,
        as_of=date.today(),
        producing_assets_nav=round(producing_nav, 2),
        development_assets_nav=round(development_nav, 2),
        exploration_assets_nav=round(exploration_value, 2),
        total_asset_nav=round(total_asset, 2),
        net_debt=round(net_debt, 2),
        corporate_adjustments=round(corporate_adj, 2),
        total_nav=round(total_nav, 2),
        shares_fully_diluted=shares_diluted,
        nav_per_share=round(nav_ps, 2),
        current_price=current_price,
        p_nav=round(current_price / nav_ps, 3) if nav_ps > 0 else 0,
        commodity_price_deck=price_deck,
        discount_rate=discount_rate,
        computed_at=datetime.utcnow(),
    )
