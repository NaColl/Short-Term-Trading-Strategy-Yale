"""
L2 Event Detection Service API.
Exposes the EDGAR detection pipeline and classification endpoints.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from services.detection.pipelines.edgar_pipeline import run_edgar_pipeline
from shared.logging.logger import get_logger

logger = get_logger(__name__)
app = FastAPI(title="APEX Detection Service")

class DetectionRequest(BaseModel):
    filing_text: str
    form_type: str
    ticker: str
    figi: str
    accession_no: str
    context: Optional[dict] = None

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "detection"}

@app.post("/detect/edgar")
async def detect_edgar_event(request: DetectionRequest):
    """Run detection pipeline on a single EDGAR filing."""
    try:
        event = await run_edgar_pipeline(
            filing_text=request.filing_text,
            form_type=request.form_type,
            ticker=request.ticker,
            figi=request.figi,
            accession_no=request.accession_no,
            context=request.context
        )
        if not event:
            return {"detected": False, "message": "No significant event detected"}
        
        return {"detected": True, "event": event}
    except Exception as e:
        logger.error("detection_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
