"""
L7 Execution Management Service API.
Exposes trade submission and order status management.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from services.execution.engine import submit_trade
from shared.logging.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="APEX Execution Service")

class TradeRequest(BaseModel):
    position_request: dict
    portfolio_state: dict

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "execution"}

@app.post("/trade/submit")
async def trade_submit(request: TradeRequest):
    try:
        result = await submit_trade(
            position_request=request.position_request,
            portfolio=request.portfolio_state
        )
        return result
    except Exception as e:
        logger.error("trade_submission_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
