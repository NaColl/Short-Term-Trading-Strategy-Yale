"""
Redis pub/sub channel name constants.

Rule: Every Redis channel used in APEX is defined here. No service may
publish to or subscribe from a channel not listed in this module.

Naming convention: apex:{domain}:{action}
"""


class CHANNELS:
    """
    All Redis pub/sub channels used across APEX services.

    Usage:
        from shared.redis.channels import CHANNELS
        redis.publish(CHANNELS.EVENT_NEW, json.dumps(event_data))
    """

    # ── Event Pipeline ───────────────────────────────────────
    EVENT_NEW = "apex:events:new"
    """New event detected and classified. Published by L2 (Detection)."""

    EVENT_ENRICHED = "apex:events:enriched"
    """Event enriched with fundamentals. Published by L3 (Fundamental)."""

    EVENT_SIGNAL_READY = "apex:events:signal_ready"
    """Signal generated for event. Published by L4 (Signals)."""

    EVENT_APPROVED = "apex:events:approved"
    """Analyst approved event for execution. Published by L8 (Dashboard)."""

    EVENT_REJECTED = "apex:events:rejected"
    """Analyst rejected event. Published by L8 (Dashboard)."""

    # ── Execution Pipeline ───────────────────────────────────
    ORDER_SUBMITTED = "apex:orders:submitted"
    """Order submitted to IBKR. Published by L7 (Execution)."""

    ORDER_FILLED = "apex:orders:filled"
    """Order fully or partially filled. Published by L7 (Execution)."""

    ORDER_CANCELLED = "apex:orders:cancelled"
    """Order cancelled. Published by L7 (Execution)."""

    # ── Risk Alerts ──────────────────────────────────────────
    RISK_WARNING = "apex:risk:warning"
    """Risk limit warning (approaching threshold). Published by L5 (Risk)."""

    RISK_CRITICAL = "apex:risk:critical"
    """Risk limit breach. Published by L5 (Risk)."""

    RISK_HALT = "apex:risk:halt"
    """New position halt activated. Published by L5 (Risk)."""

    STOP_LOSS_TRIGGERED = "apex:risk:stop_loss"
    """Stop loss triggered for a position. Published by L5 (Risk)."""

    # ── Data Pipeline ────────────────────────────────────────
    MARKET_DATA_UPDATE = "apex:data:market_update"
    """New market data batch ingested. Published by L1 (Ingest)."""

    INSIDER_TRANSACTION = "apex:data:insider_transaction"
    """New insider transaction detected. Published by L1 (Ingest)."""

    OPTIONS_ANOMALY = "apex:data:options_anomaly"
    """Options flow anomaly detected. Published by L2 (Detection)."""

    # ── System ───────────────────────────────────────────────
    HEARTBEAT = "apex:system:heartbeat"
    """Service heartbeat for health monitoring."""

    SYSTEM_ALERT = "apex:system:alert"
    """System-level alert (infrastructure issues)."""
