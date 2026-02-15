"""
Polygon.io Market Data Connector.

Handles EOD price data, options chain snapshots, and reference data.
Rate limits: depends on plan tier (5/min free, unlimited paid).
Auth: API key via query parameter.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Optional

import httpx

from shared.logging.logger import get_logger

logger = get_logger(__name__)

POLYGON_BASE = "https://api.polygon.io"


class PolygonConnector:
    """
    Fetches market data from Polygon.io REST API.

    Methods:
        fetch_eod_bars: OHLCV data for a ticker
        fetch_options_chain: Real-time options snapshot
        fetch_ticker_details: Reference data for a ticker
        fetch_grouped_daily: All tickers for a given date
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("POLYGON_API_KEY", "")
        if not self.api_key:
            logger.warning("polygon_api_key_missing")
        self.client = httpx.AsyncClient(
            base_url=POLYGON_BASE,
            params={"apiKey": self.api_key},
            timeout=30.0,
        )

    async def fetch_eod_bars(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Fetch daily OHLCV bars for a ticker.

        Returns list of bar dicts with: o, h, l, c, v, vw, t, n
        """
        url = f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"
        params = {"adjusted": str(adjusted).lower(), "sort": "asc", "limit": 5000}

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            logger.info(
                "polygon_eod_fetched",
                ticker=ticker,
                bars=len(results),
                range=f"{from_date} to {to_date}",
            )
            return results
        except httpx.HTTPStatusError as e:
            logger.error(
                "polygon_eod_failed", ticker=ticker, status=e.response.status_code
            )
            raise

    async def fetch_options_chain(
        self,
        underlying_ticker: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch the full options chain snapshot for an underlying.

        Returns list of option contract snapshots with greeks, IV, volume.
        """
        url = f"/v3/snapshot/options/{underlying_ticker}"
        all_results: list[dict[str, Any]] = []
        next_url: Optional[str] = url

        while next_url:
            try:
                resp = await self.client.get(
                    next_url, params={"limit": 250}
                )
                resp.raise_for_status()
                data = resp.json()
                all_results.extend(data.get("results", []))
                next_url = data.get("next_url")
            except httpx.HTTPStatusError:
                break

        logger.info(
            "polygon_options_fetched",
            ticker=underlying_ticker,
            contracts=len(all_results),
        )
        return all_results

    async def fetch_ticker_details(self, ticker: str) -> dict[str, Any]:
        """
        Fetch reference data for a ticker (name, type, SIC, market cap, etc.).
        """
        url = f"/v3/reference/tickers/{ticker}"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", {})
        except httpx.HTTPStatusError as e:
            logger.error(
                "polygon_details_failed", ticker=ticker, status=e.response.status_code
            )
            raise

    async def fetch_grouped_daily(self, target_date: date) -> list[dict[str, Any]]:
        """
        Fetch all US stock EOD data for a single date.

        Returns list of ticker bar dicts — ~10,000+ tickers per day.
        """
        url = f"/v2/aggs/grouped/locale/us/market/stocks/{target_date}"
        params = {"adjusted": "true"}

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            logger.info(
                "polygon_grouped_daily_fetched",
                date=str(target_date),
                tickers=len(results),
            )
            return results
        except httpx.HTTPStatusError as e:
            logger.error(
                "polygon_grouped_failed",
                date=str(target_date),
                status=e.response.status_code,
            )
            raise

    async def close(self) -> None:
        await self.client.aclose()
