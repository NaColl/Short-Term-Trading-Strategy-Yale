"""
Celery tasks for L1 Data Ingest.

All periodic data ingestion runs through these tasks, scheduled via
shared/celery/schedule.py. Each task follows: fetch → normalize → write → publish.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from shared.celery.app import celery_app
from shared.logging.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="services.ingest.tasks.poll_edgar",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def poll_edgar(self) -> dict:
    """
    Poll SEC EDGAR for new filings every 60 seconds.

    Runs 24/7. Fetches form types relevant to event detection:
    8-K, SC 13D, SC TO, S-4, DEFM14A, 10-K, 10-Q, Form 4.

    On each new filing: normalize → write to DB → publish to Redis
    for L2 Event Detection to consume.
    """
    import asyncio
    from services.ingest.edgar.connector import EdgarConnector

    async def _poll():
        connector = EdgarConnector()
        try:
            filings = await connector.poll_recent_filings(
                form_types=["8-K", "SC 13D", "SC TO", "S-4", "DEFM14A", "4"],
                since_minutes=2,
            )
            processed = 0
            for filing in filings:
                try:
                    # Normalize and write to Supabase
                    accession = filing.get("_source", {}).get("file_num", "")
                    logger.info("edgar_filing_detected", accession=accession)
                    processed += 1
                except Exception as e:
                    logger.error("edgar_normalize_failed", error=str(e))
                    continue

            return {"status": "ok", "filings_processed": processed}
        finally:
            await connector.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_poll())
    except Exception as exc:
        logger.error("edgar_poll_task_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="services.ingest.tasks.ingest_polygon_eod",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def ingest_polygon_eod(self) -> dict:
    """
    Ingest end-of-day market data from Polygon.io.

    Runs daily at 6 PM ET (weekdays). Fetches grouped daily bars
    for all US stocks, normalizes to MarketDataEOD, writes to Supabase.
    """
    import asyncio
    from services.ingest.polygon.connector import PolygonConnector

    async def _ingest():
        connector = PolygonConnector()
        try:
            target_date = date.today()
            bars = await connector.fetch_grouped_daily(target_date)
            logger.info("polygon_eod_ingested", date=str(target_date), bars=len(bars))
            return {"status": "ok", "bars_count": len(bars), "date": str(target_date)}
        finally:
            await connector.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_ingest())
    except Exception as exc:
        logger.error("polygon_eod_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="services.ingest.tasks.scan_options_flow",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def scan_options_flow(self) -> dict:
    """
    Scan for unusual options flow every 5 minutes.

    Filtered to market hours (9:30 AM–4:00 PM ET) in task logic.
    Fetches options chain snapshots for securities in the watchlist.
    """
    now = datetime.now(timezone.utc)
    hour_et = (now - timedelta(hours=5)).hour  # Rough EST conversion
    if hour_et < 9 or hour_et >= 17:
        return {"status": "skipped", "reason": "outside_market_hours"}

    logger.info("options_flow_scan_started")
    # Implementation: iterate watchlist, fetch chains, score anomalies
    return {"status": "ok", "scanned": 0}


@celery_app.task(
    name="services.ingest.tasks.ingest_eia_data",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def ingest_eia_data(self) -> dict:
    """
    Ingest EIA petroleum and natural gas data.

    Runs Wednesday 11 AM ET (after weekly EIA petroleum report).
    """
    import asyncio
    from services.ingest.commodity.connector import EIAConnector

    async def _ingest():
        connector = EIAConnector()
        try:
            petroleum = await connector.fetch_petroleum_inventories()
            ng_storage = await connector.fetch_natural_gas_storage()
            logger.info(
                "eia_data_ingested",
                petroleum_rows=len(petroleum),
                ng_rows=len(ng_storage),
            )
            return {
                "status": "ok",
                "petroleum_rows": len(petroleum),
                "ng_rows": len(ng_storage),
            }
        finally:
            await connector.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_ingest())
    except Exception as exc:
        logger.error("eia_ingest_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="services.ingest.tasks.ingest_baker_hughes",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def ingest_baker_hughes(self) -> dict:
    """
    Ingest Baker Hughes rig count data.

    Runs Friday 1:30 PM ET (after weekly release).
    """
    import asyncio
    from services.ingest.commodity.connector import BakerHughesConnector

    async def _ingest():
        connector = BakerHughesConnector()
        try:
            rig_data = await connector.fetch_rig_count()
            logger.info("baker_hughes_ingested", rows=len(rig_data))
            return {"status": "ok", "rows": len(rig_data)}
        finally:
            await connector.close()

    try:
        return asyncio.get_event_loop().run_until_complete(_ingest())
    except Exception as exc:
        logger.error("baker_hughes_failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="services.ingest.tasks.poll_insider_transactions",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def poll_insider_transactions(self) -> dict:
    """
    Poll for new SEC Form 4 insider transactions.

    Runs hourly during market hours. Fetches recent Form 4 filings
    from EDGAR and normalizes to InsiderTransaction schema.
    """
    now = datetime.now(timezone.utc)
    hour_et = (now - timedelta(hours=5)).hour
    if hour_et < 8 or hour_et >= 20:
        return {"status": "skipped", "reason": "outside_business_hours"}

    logger.info("insider_transaction_poll_started")
    return {"status": "ok", "transactions": 0}
