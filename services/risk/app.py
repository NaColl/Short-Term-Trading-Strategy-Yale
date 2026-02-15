"""
L5 Risk Management Service API.
Exposes pre-trade checks and risk snapshots.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from services.risk.monitors.pre_trade import pre_trade_check, RiskLimitException
from services.risk.monitors.stop_loss_var import compute_risk_snapshot
from shared.logging.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="APEX Risk Service")

class PreTradeRequest(BaseModel):
    request_data: dict
    portfolio_state: dict

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "risk"}

@app.post("/check/pre-trade")
async def run_pre_trade_check(request: PreTradeRequest):
    try:
        result = await pre_trade_check(
            request=request.request_data,
            portfolio=request.portfolio_state
        )
        return result
    except RiskLimitException as e:
        return {"approved": False, "reason": str(e), "limit": e.limit_name}
    except Exception as e:
        logger.error("pre_trade_check_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/snapshot")
async def get_risk_snapshot(portfolio: dict):
    try:
        snapshot = await compute_risk_snapshot(portfolio)
        return snapshot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
