"""
Commodity Data Connectors — EIA, Baker Hughes, and Quandl.

Each connector is a separate class following the single-source-per-connector rule.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import httpx

from shared.logging.logger import get_logger

logger = get_logger(__name__)


class EIAConnector:
    """
    EIA (U.S. Energy Information Administration) API v2.

    Primary data: crude oil inventories, natural gas storage,
    petroleum production/consumption, refinery utilization.
    Release schedule: Weekly (Wed 10:30 AM ET for petroleum, Thu for NG).
    """

    BASE_URL = "https://api.eia.gov/v2"

    def __init__(self) -> None:
        self.api_key = os.environ.get("EIA_API_KEY", "")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_petroleum_inventories(
        self, product: str = "crude_oil", frequency: str = "weekly"
    ) -> list[dict[str, Any]]:
        """Fetch petroleum inventory data (e.g., crude oil stocks)."""
        url = f"{self.BASE_URL}/petroleum/stoc/wstk/data/"
        params = {
            "api_key": self.api_key,
            "frequency": frequency,
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 52,
        }

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("response", {}).get("data", [])
            logger.info("eia_inventories_fetched", product=product, rows=len(results))
            return results
        except httpx.HTTPStatusError as e:
            logger.error("eia_fetch_failed", status=e.response.status_code)
            raise

    async def fetch_natural_gas_storage(self) -> list[dict[str, Any]]:
        """Fetch weekly natural gas storage report data."""
        url = f"{self.BASE_URL}/natural-gas/stor/wkly/data/"
        params = {
            "api_key": self.api_key,
            "frequency": "weekly",
            "data[0]": "value",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 52,
        }

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("response", {}).get("data", [])
            logger.info("eia_ng_storage_fetched", rows=len(results))
            return results
        except httpx.HTTPStatusError as e:
            logger.error("eia_ng_fetch_failed", status=e.response.status_code)
            raise

    async def close(self) -> None:
        await self.client.aclose()


class BakerHughesConnector:
    """
    Baker Hughes Rig Count Data.

    Release schedule: Weekly (Fri 1:00 PM ET).
    Source: scraped from Baker Hughes public dataset (CSV).
    """

    RIG_COUNT_URL = (
        "https://rigcount.bakerhughes.com/static-files/8af696c1-"
        "7780-4e11-8127-25cf5aa01108"  # Current CSV endpoint
    )

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_rig_count(self) -> list[dict[str, Any]]:
        """
        Fetch the latest North America rig count data.

        Returns parsed rows with region, type (oil/gas), count, and date.
        """
        try:
            resp = await self.client.get(self.RIG_COUNT_URL)
            resp.raise_for_status()
            # Parse CSV content
            lines = resp.text.strip().split("\n")
            headers = [h.strip() for h in lines[0].split(",")]
            results = []
            for line in lines[1:50]:  # Latest 50 weeks
                values = [v.strip() for v in line.split(",")]
                if len(values) == len(headers):
                    results.append(dict(zip(headers, values)))
            logger.info("baker_hughes_fetched", rows=len(results))
            return results
        except httpx.HTTPStatusError as e:
            logger.error("baker_hughes_failed", status=e.response.status_code)
            raise

    async def close(self) -> None:
        await self.client.aclose()


class QuandlConnector:
    """
    Quandl/Nasdaq Data Link — metals, commodities, macro data.

    Primary data: LME metals prices (copper, aluminum, zinc, nickel),
    gold/silver spot prices, uranium spot.
    """

    BASE_URL = "https://data.nasdaq.com/api/v3"

    def __init__(self) -> None:
        self.api_key = os.environ.get("QUANDL_API_KEY", "")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def fetch_dataset(
        self,
        database_code: str,
        dataset_code: str,
        start_date: date | None = None,
        rows: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch a Quandl/Nasdaq Data Link time series dataset.

        Common datasets:
            LBMA/GOLD — London gold fixing
            LBMA/SILVER — London silver fixing
            LME/PR_CU — London Metal Exchange copper
            ODA/PURAN_USD — Uranium spot price
        """
        url = f"{self.BASE_URL}/datasets/{database_code}/{dataset_code}.json"
        params: dict[str, Any] = {
            "api_key": self.api_key,
            "rows": rows,
            "order": "desc",
        }
        if start_date:
            params["start_date"] = str(start_date)

        try:
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            dataset = data.get("dataset", {})
            columns = dataset.get("column_names", [])
            rows_data = dataset.get("data", [])
            results = [dict(zip(columns, row)) for row in rows_data]
            logger.info(
                "quandl_fetched",
                dataset=f"{database_code}/{dataset_code}",
                rows=len(results),
            )
            return results
        except httpx.HTTPStatusError as e:
            logger.error(
                "quandl_failed",
                dataset=f"{database_code}/{dataset_code}",
                status=e.response.status_code,
            )
            raise

    async def close(self) -> None:
        await self.client.aclose()
