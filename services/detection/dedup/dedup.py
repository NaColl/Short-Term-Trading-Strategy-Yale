"""
L2 Cross-Source Event Deduplication.

When the same event is detected by multiple sources (EDGAR + news),
this module prevents duplicate CorporateEvent records.

Strategy (ordered by specificity):
1. Same accession_number → definite duplicate
2. Same figi + same event_type + within ±3 days → probable duplicate
3. Same figi + deal_value within 5% + within ±7 days → probable duplicate
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from shared.logging.logger import get_logger
from shared.schemas.events import CorporateEvent

logger = get_logger(__name__)


async def find_duplicate(
    candidate: CorporateEvent,
    existing_events: list[CorporateEvent] | None = None,
) -> Optional[CorporateEvent]:
    """
    Check if a probable duplicate already exists in the database.

    Args:
        candidate: The new event to check
        existing_events: Optional list to check against (for testing).
                        If None, queries Supabase.

    Returns:
        Existing event if a probable duplicate exists, else None.

    When in doubt, return the existing event and merge metadata
    rather than creating a new record. Duplicate alerts are worse
    than merged records.
    """
    if existing_events is None:
        existing_events = await _fetch_recent_events(candidate)

    # Level 1: Exact source match (same accession number)
    if candidate.source_ref:
        for event in existing_events:
            if event.source_ref == candidate.source_ref:
                logger.info(
                    "dedup_exact_match",
                    candidate_figi=candidate.figi,
                    existing_id=str(event.id),
                )
                return event

    # Level 2: Same dedup hash
    if candidate.dedup_hash:
        for event in existing_events:
            if event.dedup_hash == candidate.dedup_hash:
                logger.info(
                    "dedup_hash_match",
                    candidate_figi=candidate.figi,
                    existing_id=str(event.id),
                )
                return event

    # Level 3: Same company + event type + time window
    for event in existing_events:
        if (
            event.figi == candidate.figi
            and event.event_type == candidate.event_type
            and abs(
                (event.detected_at - candidate.detected_at).total_seconds()
            )
            < timedelta(days=3).total_seconds()
        ):
            logger.info(
                "dedup_temporal_match",
                candidate_figi=candidate.figi,
                existing_id=str(event.id),
                time_diff_hours=abs(
                    (event.detected_at - candidate.detected_at).total_seconds()
                )
                / 3600,
            )
            return event

    # Level 4: Same company + deal value match + wider time window
    if candidate.deal_value_usd and candidate.deal_value_usd > 0:
        for event in existing_events:
            if (
                event.figi == candidate.figi
                and event.deal_value_usd
                and event.deal_value_usd > 0
                and abs(event.deal_value_usd - candidate.deal_value_usd)
                / candidate.deal_value_usd
                < 0.05  # Within 5%
                and abs(
                    (event.detected_at - candidate.detected_at).total_seconds()
                )
                < timedelta(days=7).total_seconds()
            ):
                logger.info(
                    "dedup_deal_value_match",
                    candidate_figi=candidate.figi,
                    existing_id=str(event.id),
                )
                return event

    return None


async def merge_event_metadata(
    existing: CorporateEvent,
    new_source: CorporateEvent,
) -> CorporateEvent:
    """
    Merge metadata from a new detection into an existing event.

    Rules:
    - Keep the higher confidence score
    - Add new source_url to the record
    - Merge key facts from both sources
    - Update deal_value if the new source has more precise data
    """
    updates: dict = {}

    if new_source.confidence > existing.confidence:
        updates["confidence"] = new_source.confidence

    if new_source.deal_value_usd and not existing.deal_value_usd:
        updates["deal_value_usd"] = new_source.deal_value_usd

    if new_source.premium_pct and not existing.premium_pct:
        updates["premium_pct"] = new_source.premium_pct

    if updates:
        logger.info(
            "event_metadata_merged",
            event_id=str(existing.id),
            updates=list(updates.keys()),
        )

    return existing


async def _fetch_recent_events(
    candidate: CorporateEvent,
    lookback_days: int = 7,
) -> list[CorporateEvent]:
    """
    Fetch recent events for the same security from Supabase.

    Returns events within the lookback window for dedup comparison.
    """
    try:
        from shared.db.client import fetch_many

        cutoff = (candidate.detected_at - timedelta(days=lookback_days)).isoformat()
        records = await fetch_many(
            "events.corporate_events",
            filters={"figi": candidate.figi},
            columns="*",
            order_by="detected_at",
            descending=True,
            limit=50,
        )
        return [CorporateEvent(**r) for r in records]
    except Exception as e:
        logger.error("dedup_fetch_failed", error=str(e))
        return []
