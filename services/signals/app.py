"""
L4 Quant Signal Library API.
Exposes factor computation and composite scoring.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List

from services.signals.scoring.composite import build_composite_signal
from services.signals.factors.base import FACTOR_REGISTRY
from shared.schemas.signals import FactorOutput
from shared.logging.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="APEX Signal Service")

class SignalRequest(BaseModel):
    event_type: str
    factor_outputs: List[FactorOutput]
    scenarios: Optional[dict] = None

class FactorRequest(BaseModel):
    factor_name: str
    event: dict
    snapshot: dict
    market_data: dict

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "signals"}

@app.post("/signals/composite")
async def get_composite_signal(request: SignalRequest):
    try:
        signal = build_composite_signal(
            event_type=request.event_type,
            factor_outputs=request.factor_outputs,
            scenarios=request.scenarios
        )
        return signal
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/factors/compute")
async def compute_single_factor(request: FactorRequest):
    factor = FACTOR_REGISTRY.get(request.factor_name)
    if not factor:
        raise HTTPException(status_code=404, detail="Factor not found")
    
    try:
        output = factor.compute(
            event=request.event,
            snapshot=request.snapshot,
            market_data=request.market_data
        )
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
