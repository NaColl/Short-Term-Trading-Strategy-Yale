"""
SEC EDGAR Real-Time Filing Connector.

Polls the EDGAR full-text search RSS feed every 60 seconds for new filings.
Returns raw filing metadata + text. Never applies business logic.

Rate limits: SEC requires ≤10 req/sec. We operate at 1 req/60sec.
Auth: User-Agent header with contact email (SEC requirement).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from shared.logging.logger import get_logger

logger = get_logger(__name__)

EDGAR_BASE = "https://efts.sec.gov/LATEST"
EDGAR_FILINGS = "https://www.sec.gov/cgi-bin/browse-edgar"
COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts"
SUBMISSIONS = "https://data.sec.gov/submissions"

# SEC requires a descriptive User-Agent
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "APEX Trading research@apextrading.com"
)


class EdgarConnector:
    """
    Fetches filings from SEC EDGAR.

    Methods:
        poll_recent_filings: Get latest filings from full-text search
        fetch_filing_text: Download full filing text by accession number
        fetch_company_facts: Get XBRL financial facts for a CIK
    """

    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30.0,
        )
        self._last_poll_ts: Optional[datetime] = None

    async def poll_recent_filings(
        self,
        form_types: list[str] | None = None,
        since_minutes: int = 2,
    ) -> list[dict[str, Any]]:
        """
        Poll EDGAR EFTS for recently filed documents.

        Args:
            form_types: Filter by form type (e.g., ["8-K", "SC 13D", "S-4"])
            since_minutes: Look back this many minutes

        Returns:
            List of raw filing metadata dicts
        """
        params: dict[str, Any] = {
            "dateRange": "custom",
            "startdt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "enddt": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        if form_types:
            params["forms"] = ",".join(form_types)

        try:
            resp = await self.client.get(
                f"{EDGAR_BASE}/search-index",
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            filings = data.get("hits", {}).get("hits", [])
            logger.info(
                "edgar_poll_complete",
                filing_count=len(filings),
                form_types=form_types,
            )
            self._last_poll_ts = datetime.now(timezone.utc)
            return filings

        except httpx.HTTPStatusError as e:
            logger.error("edgar_poll_failed", status=e.response.status_code)
            raise

    async def fetch_filing_document(self, accession_no: str, cik: str) -> str:
        """
        Download the primary document text for a filing.

        Args:
            accession_no: SEC accession number (e.g., "0001193125-24-123456")
            cik: Company CIK (zero-padded to 10 digits)

        Returns:
            Filing text content (HTML or plain text)
        """
        accession_clean = accession_no.replace("-", "")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik.lstrip('0')}/{accession_clean}/{accession_no}.txt"
        )

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            logger.debug(
                "filing_fetched",
                accession_no=accession_no,
                size_bytes=len(resp.text),
            )
            return resp.text

        except httpx.HTTPStatusError as e:
            logger.error(
                "filing_fetch_failed",
                accession_no=accession_no,
                status=e.response.status_code,
            )
            raise

    async def fetch_company_facts(self, cik: str) -> dict[str, Any]:
        """
        Fetch all XBRL-tagged financial facts for a company.

        Used by the Fundamental Engine (L3) for automated financial
        statement extraction. Returns the raw SEC CompanyFacts JSON.
        """
        padded_cik = cik.zfill(10)
        url = f"{COMPANY_FACTS}/CIK{padded_cik}.json"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("xbrl_fetch_failed", cik=cik, status=e.response.status_code)
            raise

    async def fetch_recent_submissions(self, cik: str) -> dict[str, Any]:
        """
        Fetch recent submission history for a company.

        Returns filing metadata including form types, dates, accession numbers.
        """
        padded_cik = cik.zfill(10)
        url = f"{SUBMISSIONS}/CIK{padded_cik}.json"

        try:
            resp = await self.client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                "submissions_fetch_failed", cik=cik, status=e.response.status_code
            )
            raise

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
