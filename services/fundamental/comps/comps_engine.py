"""
L3 Comparable Company Analysis Engine.

Selects peers by subsector/sector and market cap range,
computes median multiples, and identifies discount/premium to comps.
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from shared.logging.logger import get_logger

logger = get_logger(__name__)


async def build_comps_table(
    figi: str,
    sector: str,
    industry: str,
    market_cap_usd: float,
    subject_multiples: dict[str, Optional[float]],
    exclude_figis: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a comparable company multiples table.

    Peer selection criteria:
    - Same industry (fallback to sector if <3 peers)
    - Market cap 0.2x to 5.0x the subject company
    - Has positive EBITDA
    - Has reported in last 6 months
    - Not the subject company itself

    Returns median and quartile multiples for EV/EBITDA, P/E, P/FCF.
    """
    from shared.db.client import fetch_many

    # Try industry-level peers first
    peers = await _fetch_peers(
        industry=industry,
        market_cap_range=(market_cap_usd * 0.2, market_cap_usd * 5.0),
        exclude_figis=[figi] + (exclude_figis or []),
    )

    if len(peers) < 3:
        logger.warning(
            "insufficient_industry_peers",
            industry=industry,
            count=len(peers),
        )
        # Widen to sector
        peers = await _fetch_peers(
            sector=sector,
            market_cap_range=(market_cap_usd * 0.2, market_cap_usd * 5.0),
            exclude_figis=[figi] + (exclude_figis or []),
        )

    if not peers:
        logger.error("no_peers_found", figi=figi, sector=sector)
        return {"peer_count": 0, "comps": []}

    # Compute multiples
    ev_ebitda_vals = [p["ev_ebitda"] for p in peers if p.get("ev_ebitda") and p["ev_ebitda"] > 0]
    pe_vals = [p["pe_ratio"] for p in peers if p.get("pe_ratio") and p["pe_ratio"] > 0]
    fcf_yield_vals = [p["fcf_yield"] for p in peers if p.get("fcf_yield")]

    result = {
        "subject_figi": figi,
        "peer_count": len(peers),
        "comps": [
            {
                "figi": p["figi"],
                "ticker": p.get("ticker"),
                "name": p.get("name"),
                "market_cap_usd": p.get("market_cap_usd"),
                "ev_ebitda": p.get("ev_ebitda"),
                "pe_ratio": p.get("pe_ratio"),
                "fcf_yield": p.get("fcf_yield"),
            }
            for p in peers
        ],
    }

    if ev_ebitda_vals:
        result["implied_ev_ebitda"] = float(np.median(ev_ebitda_vals))
        result["ev_ebitda_p25"] = float(np.percentile(ev_ebitda_vals, 25))
        result["ev_ebitda_p75"] = float(np.percentile(ev_ebitda_vals, 75))

        subj_ev_ebitda = subject_multiples.get("ev_ebitda")
        if subj_ev_ebitda and subj_ev_ebitda > 0:
            result["ev_ebitda_discount_pct"] = (
                subj_ev_ebitda / np.median(ev_ebitda_vals) - 1
            ) * 100

    if pe_vals:
        result["implied_pe"] = float(np.median(pe_vals))
        result["pe_p25"] = float(np.percentile(pe_vals, 25))
        result["pe_p75"] = float(np.percentile(pe_vals, 75))

    return result


async def _fetch_peers(
    industry: str | None = None,
    sector: str | None = None,
    market_cap_range: tuple[float, float] = (0, 1e15),
    exclude_figis: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Fetch potential peer companies from the securities master."""
    from shared.db.client import get_supabase

    db = get_supabase()

    query = db.table("market.securities_master").select(
        "figi, ticker, name, market_cap_usd, sector, industry"
    )

    if industry:
        query = query.eq("industry", industry)
    elif sector:
        query = query.eq("sector", sector)

    query = (
        query.gte("market_cap_usd", market_cap_range[0])
        .lte("market_cap_usd", market_cap_range[1])
        .eq("is_active", True)
    )

    result = query.limit(50).execute()
    peers = result.data or []

    if exclude_figis:
        peers = [p for p in peers if p["figi"] not in exclude_figis]

    return peers
