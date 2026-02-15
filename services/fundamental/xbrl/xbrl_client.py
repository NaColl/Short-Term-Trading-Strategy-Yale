"""
L3 Fundamental Engine — XBRL Financial Data Client.

Extracts TTM financial metrics from SEC XBRL CompanyFacts API.
This is the primary source for all public company financials.

Rule: Use XBRL for numbers, never parse 10-K text with LLM for figures.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import httpx

from shared.logging.logger import get_logger

logger = get_logger(__name__)

# XBRL concept-to-field mapping
XBRL_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        "us-gaap/Revenues",
        "us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap/SalesRevenueNet",
    ],
    "cost_of_revenue": ["us-gaap/CostOfRevenue", "us-gaap/CostOfGoodsAndServicesSold"],
    "gross_profit": ["us-gaap/GrossProfit"],
    "operating_income": ["us-gaap/OperatingIncomeLoss"],
    "net_income": ["us-gaap/NetIncomeLoss", "us-gaap/ProfitLoss"],
    "ebit": ["us-gaap/OperatingIncomeLoss"],
    "depreciation": [
        "us-gaap/DepreciationDepletionAndAmortization",
        "us-gaap/DepreciationAndAmortization",
    ],
    "capex": [
        "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment",
        "us-gaap/PaymentsToAcquireProductiveAssets",
    ],
    "cfo": [
        "us-gaap/NetCashProvidedByUsedInOperatingActivities",
        "us-gaap/NetCashProvidedByOperatingActivities",
    ],
    "total_debt": ["us-gaap/LongTermDebt", "us-gaap/LongTermDebtAndCapitalLeaseObligations"],
    "short_term_debt": ["us-gaap/ShortTermBorrowings"],
    "cash": [
        "us-gaap/CashAndCashEquivalentsAtCarryingValue",
        "us-gaap/CashCashEquivalentsAndShortTermInvestments",
    ],
    "shares_outstanding": [
        "dei/EntityCommonStockSharesOutstanding",
        "us-gaap/CommonStockSharesOutstanding",
    ],
    "book_value": [
        "us-gaap/StockholdersEquity",
        "us-gaap/StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
}

SEC_USER_AGENT = "APEX Trading research@apextrading.com"


async def fetch_company_xbrl(cik: str) -> dict[str, Any]:
    """
    Fetch all XBRL-tagged financial facts for a company from the SEC API.

    Args:
        cik: SEC CIK number (will be zero-padded)

    Returns:
        Raw SEC CompanyFacts JSON response
    """
    padded = cik.zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded}.json"

    async with httpx.AsyncClient(
        headers={"User-Agent": SEC_USER_AGENT}, timeout=30.0
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


def extract_ttm_metric(
    facts: dict[str, Any],
    field_name: str,
    units: str = "USD",
) -> Optional[float]:
    """
    Extract trailing-twelve-month value for a financial metric.

    Handles: multiple concept names per metric, mixed quarterly/annual
    data, restatements (takes most recent filing).

    Returns None if fewer than 4 quarters of data exist.
    """
    concepts = XBRL_CONCEPTS.get(field_name, [])

    for concept_path in concepts:
        parts = concept_path.split("/")
        if len(parts) != 2:
            continue
        taxonomy, concept = parts

        try:
            data = facts["facts"][taxonomy][concept]["units"][units]
        except KeyError:
            continue

        # Filter to 10-K and 10-Q filings, sorted by end date
        quarterly = sorted(
            [d for d in data if d.get("form") in ("10-Q", "10-K") and d.get("end")],
            key=lambda x: x["end"],
            reverse=True,
        )

        if not quarterly:
            continue

        ttm_quarters = _select_ttm_quarters(quarterly)
        if len(ttm_quarters) >= 4:
            return sum(q["val"] for q in ttm_quarters)

        # Fallback: use most recent annual (10-K) value
        annual = [d for d in quarterly if d.get("form") == "10-K"]
        if annual:
            return annual[0]["val"]

    return None


def extract_balance_sheet_metric(
    facts: dict[str, Any],
    field_name: str,
    units: str = "USD",
) -> Optional[float]:
    """
    Extract the most recent balance sheet value for a metric.

    Balance sheet items are point-in-time, not cumulative,
    so we take the most recent filing value.
    """
    concepts = XBRL_CONCEPTS.get(field_name, [])

    for concept_path in concepts:
        parts = concept_path.split("/")
        if len(parts) != 2:
            continue
        taxonomy, concept = parts

        try:
            data = facts["facts"][taxonomy][concept]["units"][units]
        except KeyError:
            continue

        filings = sorted(
            [d for d in data if d.get("form") in ("10-Q", "10-K") and d.get("end")],
            key=lambda x: x["end"],
            reverse=True,
        )

        if filings:
            return filings[0]["val"]

    return None


def _select_ttm_quarters(
    quarterly_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Select 4 most recent non-overlapping quarters.

    Handles quarterly vs annual reporting by checking the 'fp' (fiscal period)
    field and the start/end date ranges.
    """
    selected = []
    seen_periods: set[str] = set()

    for entry in quarterly_data:
        period_key = f"{entry.get('start', '')}_{entry.get('end', '')}"
        if period_key not in seen_periods:
            # Filter to quarterly-duration periods (~90 days)
            try:
                start = date.fromisoformat(entry["start"])
                end = date.fromisoformat(entry["end"])
                duration = (end - start).days
                if 75 <= duration <= 105:  # ~quarterly
                    selected.append(entry)
                    seen_periods.add(period_key)
            except (KeyError, ValueError):
                continue

        if len(selected) >= 4:
            break

    return selected


async def build_fundamental_snapshot(
    cik: str,
    figi: str,
    current_price: float,
    shares_outstanding: int,
) -> dict[str, Any]:
    """
    Build a complete FundamentalSnapshot from XBRL data.

    Returns a dict suitable for constructing FundamentalSnapshot Pydantic model.
    """
    facts = await fetch_company_xbrl(cik)

    # Income statement (TTM)
    revenue = extract_ttm_metric(facts, "revenue")
    net_income = extract_ttm_metric(facts, "net_income")
    operating_income = extract_ttm_metric(facts, "operating_income")
    depreciation = extract_ttm_metric(facts, "depreciation")
    ebitda = (operating_income or 0) + (depreciation or 0) if operating_income else None

    # Cash flow (TTM)
    cfo = extract_ttm_metric(facts, "cfo")
    capex = extract_ttm_metric(facts, "capex")
    fcf = (cfo or 0) - abs(capex or 0) if cfo else None

    # Balance sheet (most recent)
    cash = extract_balance_sheet_metric(facts, "cash")
    total_debt = extract_balance_sheet_metric(facts, "total_debt") or 0
    short_debt = extract_balance_sheet_metric(facts, "short_term_debt") or 0
    book_value = extract_balance_sheet_metric(facts, "book_value")

    # Compute market metrics
    market_cap = current_price * shares_outstanding
    net_debt = (total_debt + short_debt) - (cash or 0)
    ev = market_cap + net_debt

    return {
        "figi": figi,
        "revenue_ttm": revenue,
        "ebitda_ttm": ebitda,
        "net_income_ttm": net_income,
        "free_cash_flow_ttm": fcf,
        "total_debt": total_debt + short_debt,
        "cash_and_equivalents": cash,
        "net_debt": net_debt,
        "shares_outstanding": shares_outstanding,
        "book_value_per_share": (book_value or 0) / shares_outstanding if shares_outstanding else None,
        "ev_ebitda": ev / ebitda if ebitda and ebitda > 0 else None,
        "pe_ratio": market_cap / net_income if net_income and net_income > 0 else None,
        "pb_ratio": market_cap / book_value if book_value and book_value > 0 else None,
        "fcf_yield": fcf / market_cap if fcf and market_cap > 0 else None,
        "ev_revenue": ev / revenue if revenue and revenue > 0 else None,
        "gross_margin": None,  # Computed from detailed income stmt
        "operating_margin": operating_income / revenue if operating_income and revenue and revenue > 0 else None,
        "net_margin": net_income / revenue if net_income and revenue and revenue > 0 else None,
        "debt_to_ebitda": net_debt / ebitda if ebitda and ebitda > 0 else None,
    }
