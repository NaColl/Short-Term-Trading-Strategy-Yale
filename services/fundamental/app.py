"""
L3 Fundamental Engine Service API.
Exposes XBRL extraction, Comps building, and NAV modeling.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List

from services.fundamental.xbrl.xbrl_client import fetch_company_xbrl
from services.fundamental.comps.comps_engine import build_comps_table
from services.fundamental.nav.mining_nav import build_mining_nav
from shared.logging.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="APEX Fundamental Service")

class CompsRequest(BaseModel):
    figi: str
    sector: str
    industry: str
    market_cap: float
    subject_multiples: dict

class NavRequest(BaseModel):
    figi: str
    producing_assets: List[dict]
    development_assets: List[dict]
    exploration_value: float
    net_debt: float
    corporate_adj: float
    shares_diluted: int
    current_price: float
    price_deck: dict

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "fundamental"}

@app.get("/xbrl/{cik}")
async def get_xbrl(cik: str):
    try:
        facts = await fetch_company_xbrl(cik)
        return facts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/comps")
async def get_comps(request: CompsRequest):
    try:
        table = await build_comps_table(
            figi=request.figi,
            sector=request.sector,
            industry=request.industry,
            market_cap_usd=request.market_cap,
            subject_multiples=request.subject_multiples
        )
        return table
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/nav/mining")
async def get_mining_nav(request: NavRequest):
    try:
        nav_model = build_mining_nav(
            figi=request.figi,
            producing_assets=request.producing_assets,
            development_assets=request.development_assets,
            exploration_value=request.exploration_value,
            net_debt=request.net_debt,
            corporate_adj=request.corporate_adj,
            shares_diluted=request.shares_diluted,
            current_price=request.current_price,
            price_deck=request.price_deck
        )
        return nav_model
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
