"""
Supabase database client — the single gateway for all DB writes.

Rule: ALL database writes go through this module. No service writes
directly to Supabase. This ensures consistent error handling, logging,
and audit trail.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from supabase import Client, create_client

from shared.logging.logger import get_logger

logger = get_logger(__name__)

_supabase_client: Optional[Client] = None


def get_supabase() -> Client:
    """
    Get or create a singleton Supabase client.

    Environment variables:
        SUPABASE_URL: Project URL (e.g., https://xxx.supabase.co)
        SUPABASE_KEY: Service role key (NOT anon key — we need write access)

    Returns:
        Supabase Client instance

    Raises:
        ValueError: If required environment variables are missing
    """
    global _supabase_client

    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be set. "
                "See .env.example for required variables."
            )

        _supabase_client = create_client(url, key)
        logger.info("supabase_client_initialized", url=url[:30] + "...")

    return _supabase_client


async def insert_record(
    table: str,
    data: dict[str, Any],
    *,
    on_conflict: Optional[str] = None,
) -> dict[str, Any]:
    """
    Insert a single record into a Supabase table.

    Args:
        table: Table name (schema-qualified, e.g., 'events.corporate_events')
        data: Record data as a dict (typically from model.model_dump())
        on_conflict: Column(s) for upsert conflict resolution

    Returns:
        The inserted record from Supabase

    Raises:
        Exception: On insert failure (logged and re-raised)
    """
    client = get_supabase()

    try:
        query = client.table(table).insert(data)
        if on_conflict:
            query = client.table(table).upsert(data, on_conflict=on_conflict)
        result = query.execute()

        logger.info(
            "db_insert_success",
            table=table,
            record_id=data.get("id", "N/A"),
        )
        return result.data[0] if result.data else {}

    except Exception as e:
        logger.error(
            "db_insert_failed",
            table=table,
            error=str(e),
            record_id=data.get("id", "N/A"),
        )
        raise


async def insert_batch(
    table: str,
    records: list[dict[str, Any]],
    *,
    on_conflict: Optional[str] = None,
    batch_size: int = 100,
) -> list[dict[str, Any]]:
    """
    Insert multiple records in batches.

    Args:
        table: Table name
        records: List of record dicts
        on_conflict: Column(s) for upsert
        batch_size: Max records per insert call

    Returns:
        List of inserted records
    """
    client = get_supabase()
    results: list[dict[str, Any]] = []

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]

        try:
            if on_conflict:
                result = client.table(table).upsert(batch, on_conflict=on_conflict).execute()
            else:
                result = client.table(table).insert(batch).execute()

            if result.data:
                results.extend(result.data)

            logger.info(
                "db_batch_insert_success",
                table=table,
                batch_index=i // batch_size,
                count=len(batch),
            )

        except Exception as e:
            logger.error(
                "db_batch_insert_failed",
                table=table,
                batch_index=i // batch_size,
                count=len(batch),
                error=str(e),
            )
            raise

    return results


async def fetch_one(
    table: str,
    *,
    filters: dict[str, Any],
    columns: str = "*",
) -> Optional[dict[str, Any]]:
    """
    Fetch a single record from a table.

    Args:
        table: Table name
        filters: Column equality filters
        columns: Comma-separated column selection

    Returns:
        Record dict or None
    """
    client = get_supabase()

    query = client.table(table).select(columns)
    for col, val in filters.items():
        query = query.eq(col, val)

    result = query.limit(1).execute()
    return result.data[0] if result.data else None


async def fetch_many(
    table: str,
    *,
    filters: Optional[dict[str, Any]] = None,
    columns: str = "*",
    order_by: Optional[str] = None,
    descending: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    Fetch multiple records from a table.

    Args:
        table: Table name
        filters: Column equality filters
        columns: Comma-separated column selection
        order_by: Column to sort by
        descending: Sort descending?
        limit: Max records to return

    Returns:
        List of record dicts
    """
    client = get_supabase()

    query = client.table(table).select(columns)

    if filters:
        for col, val in filters.items():
            query = query.eq(col, val)

    if order_by:
        query = query.order(order_by, desc=descending)

    result = query.limit(limit).execute()
    return result.data if result.data else []
