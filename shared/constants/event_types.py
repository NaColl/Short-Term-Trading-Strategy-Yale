"""
EventType enum, EventCategory enum, and EVENT_METADATA mapping.

This is the canonical taxonomy of all corporate events APEX can detect and trade.
Every event classification must resolve to a value in EventType.
Adding a new event type? Add the enum value here FIRST, then add metadata below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventCategory(str, Enum):
    """High-level grouping for event types."""

    MERGERS_AND_ACQUISITIONS = "MERGERS_AND_ACQUISITIONS"
    ACTIVIST_ENGAGEMENT = "ACTIVIST_ENGAGEMENT"
    SPINOFFS_AND_RESTRUCTURING = "SPINOFFS_AND_RESTRUCTURING"
    CAPITAL_ALLOCATION = "CAPITAL_ALLOCATION"
    OPERATIONAL = "OPERATIONAL"
    MANAGEMENT_AND_GOVERNANCE = "MANAGEMENT_AND_GOVERNANCE"
    REGULATORY_AND_LEGAL = "REGULATORY_AND_LEGAL"
    RESOURCE_AND_MINING = "RESOURCE_AND_MINING"
    COMMODITY = "COMMODITY"
    EARNINGS_AND_GUIDANCE = "EARNINGS_AND_GUIDANCE"
    OPTIONS_AND_MARKET_STRUCTURE = "OPTIONS_AND_MARKET_STRUCTURE"
    CREDIT_AND_FINANCING = "CREDIT_AND_FINANCING"
    INDEX_AND_REBALANCE = "INDEX_AND_REBALANCE"
    INSIDER_ACTIVITY = "INSIDER_ACTIVITY"


class EventType(str, Enum):
    """
    Complete taxonomy of 65 event types APEX detects and trades.

    Naming convention: CATEGORY_SPECIFIC_EVENT
    Every value here has a corresponding entry in EVENT_METADATA.
    """

    # ── Mergers & Acquisitions ───────────────────────────────
    MA_ACQUISITION_TARGET = "MA_ACQUISITION_TARGET"
    MA_ACQUISITION_ACQUIRER = "MA_ACQUISITION_ACQUIRER"
    MA_HOSTILE_APPROACH = "MA_HOSTILE_APPROACH"
    MA_DEAL_BREAK = "MA_DEAL_BREAK"
    MA_MERGER_OF_EQUALS = "MA_MERGER_OF_EQUALS"
    MA_DEAL_AMENDMENT = "MA_DEAL_AMENDMENT"
    MA_COMPETING_BID = "MA_COMPETING_BID"
    MA_GO_PRIVATE = "MA_GO_PRIVATE"
    MA_TAKE_PRIVATE_LBO = "MA_TAKE_PRIVATE_LBO"
    TENDER_OFFER_TARGET = "TENDER_OFFER_TARGET"
    TENDER_OFFER_ACQUIRER = "TENDER_OFFER_ACQUIRER"

    # ── Activist Engagement ──────────────────────────────────
    ACTIVIST_13D_NEW = "ACTIVIST_13D_NEW"
    ACTIVIST_13D_AMENDMENT = "ACTIVIST_13D_AMENDMENT"
    ACTIVIST_13G_TO_13D = "ACTIVIST_13G_TO_13D"
    ACTIVIST_SETTLEMENT = "ACTIVIST_SETTLEMENT"
    ACTIVIST_BOARD_SEAT = "ACTIVIST_BOARD_SEAT"
    ACTIVIST_PROXY_FIGHT = "ACTIVIST_PROXY_FIGHT"
    ACTIVIST_LETTER_PUBLIC = "ACTIVIST_LETTER_PUBLIC"
    ACTIVIST_STAKE_INCREASE = "ACTIVIST_STAKE_INCREASE"
    ACTIVIST_STAKE_DECREASE = "ACTIVIST_STAKE_DECREASE"

    # ── Spinoffs & Restructuring ─────────────────────────────
    SPINOFF_ANNOUNCED = "SPINOFF_ANNOUNCED"
    SPINOFF_RECORD_DATE = "SPINOFF_RECORD_DATE"
    SPINOFF_COMPLETED = "SPINOFF_COMPLETED"
    TRACKING_STOCK = "TRACKING_STOCK"
    CORPORATE_SPLIT = "CORPORATE_SPLIT"
    ASSET_SALE = "ASSET_SALE"
    DIVESTITURE = "DIVESTITURE"
    BANKRUPTCY_FILING = "BANKRUPTCY_FILING"
    BANKRUPTCY_EMERGENCE = "BANKRUPTCY_EMERGENCE"

    # ── Capital Allocation ───────────────────────────────────
    SPECIAL_DIVIDEND = "SPECIAL_DIVIDEND"
    DIVIDEND_INITIATION = "DIVIDEND_INITIATION"
    DIVIDEND_CUT = "DIVIDEND_CUT"
    DIVIDEND_INCREASE = "DIVIDEND_INCREASE"
    ACCELERATED_BUYBACK = "ACCELERATED_BUYBACK"
    BUYBACK_AUTHORIZATION = "BUYBACK_AUTHORIZATION"
    RIGHTS_OFFERING = "RIGHTS_OFFERING"
    PIPE_TRANSACTION = "PIPE_TRANSACTION"
    SECONDARY_OFFERING = "SECONDARY_OFFERING"
    CONVERTIBLE_ISSUANCE = "CONVERTIBLE_ISSUANCE"

    # ── Operational ──────────────────────────────────────────
    DEFENSE_CONTRACT_AWARD = "DEFENSE_CONTRACT_AWARD"
    BACKLOG_REVISION = "BACKLOG_REVISION"
    PLANT_SHUTDOWN = "PLANT_SHUTDOWN"
    PLANT_RESTART = "PLANT_RESTART"
    CAPACITY_EXPANSION = "CAPACITY_EXPANSION"
    SUPPLY_AGREEMENT = "SUPPLY_AGREEMENT"

    # ── Management & Governance ──────────────────────────────
    CEO_CHANGE = "CEO_CHANGE"
    CFO_CHANGE = "CFO_CHANGE"
    MANAGEMENT_CHANGE_OTHER = "MANAGEMENT_CHANGE_OTHER"
    BOARD_CHANGE = "BOARD_CHANGE"

    # ── Regulatory & Legal ───────────────────────────────────
    CREDIT_RATING_UPGRADE = "CREDIT_RATING_UPGRADE"
    CREDIT_RATING_DOWNGRADE = "CREDIT_RATING_DOWNGRADE"
    REGULATORY_APPROVAL = "REGULATORY_APPROVAL"
    REGULATORY_DENIAL = "REGULATORY_DENIAL"
    SEC_INVESTIGATION = "SEC_INVESTIGATION"
    LITIGATION_MATERIAL = "LITIGATION_MATERIAL"

    # ── Resource & Mining ────────────────────────────────────
    RESOURCE_ESTIMATE_UPDATE = "RESOURCE_ESTIMATE_UPDATE"
    MINE_FINAL_INVESTMENT_DECISION = "MINE_FINAL_INVESTMENT_DECISION"
    MINE_PERMIT_APPROVAL = "MINE_PERMIT_APPROVAL"
    MINE_PERMIT_DENIAL = "MINE_PERMIT_DENIAL"
    MINE_DEVELOPMENT = "MINE_DEVELOPMENT"
    MINE_EXPLORATION = "MINE_EXPLORATION"
    STREAMING_DEAL = "STREAMING_DEAL"
    ROYALTY_DEAL = "ROYALTY_DEAL"
    CAPEX_REVISION_UP = "CAPEX_REVISION_UP"
    CAPEX_REVISION_DOWN = "CAPEX_REVISION_DOWN"

    # ── Commodity ────────────────────────────────────────────
    SUPPLY_SHOCK = "SUPPLY_SHOCK"
    INVENTORY_ANOMALY = "INVENTORY_ANOMALY"
    RIG_COUNT_INFLECTION = "RIG_COUNT_INFLECTION"
    OPEC_DECISION = "OPEC_DECISION"

    # ── Earnings & Guidance ──────────────────────────────────
    EARNINGS_BEAT = "EARNINGS_BEAT"
    EARNINGS_MISS = "EARNINGS_MISS"
    GUIDANCE_RAISE = "GUIDANCE_RAISE"
    GUIDANCE_CUT = "GUIDANCE_CUT"
    PRE_ANNOUNCEMENT = "PRE_ANNOUNCEMENT"

    # ── Options & Market Structure ───────────────────────────
    OPTIONS_ANOMALY = "OPTIONS_ANOMALY"

    # ── Index & Rebalance ────────────────────────────────────
    INDEX_ADDITION = "INDEX_ADDITION"
    INDEX_DELETION = "INDEX_DELETION"

    # ── Insider Activity ─────────────────────────────────────
    INSIDER_CLUSTER_BUY = "INSIDER_CLUSTER_BUY"
    INSIDER_LARGE_SALE = "INSIDER_LARGE_SALE"


@dataclass(frozen=True)
class EventMeta:
    """
    Metadata for an event type. Controls routing, alerting, and downstream behavior.

    Attributes:
        display_name: Human-readable label for the dashboard.
        category: EventCategory grouping.
        typical_hold_days: (min, max) expected holding period.
        base_win_rate: Historical win rate from event studies (0.0–1.0).
        primary_sec_forms: SEC form types that trigger this event.
        requires_fundamental: Whether L3 must run before signal generation.
        analyst_alert_threshold: Confidence needed to generate analyst alert.
    """

    display_name: str
    category: EventCategory
    typical_hold_days: tuple[int, int]
    base_win_rate: float
    primary_sec_forms: list[str] = field(default_factory=list)
    requires_fundamental: bool = True
    analyst_alert_threshold: float = 0.65


# ── EVENT_METADATA: maps every EventType to its metadata ─────────
EVENT_METADATA: dict[EventType, EventMeta] = {
    # ── M&A ──────────────────────────────────────────────────
    EventType.MA_ACQUISITION_TARGET: EventMeta(
        display_name="Acquisition Target",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(30, 180),
        base_win_rate=0.72,
        primary_sec_forms=["8-K", "SC TO", "DEFM14A", "S-4"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.MA_ACQUISITION_ACQUIRER: EventMeta(
        display_name="Acquirer Announced",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(30, 180),
        base_win_rate=0.48,
        primary_sec_forms=["8-K", "S-4"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.MA_HOSTILE_APPROACH: EventMeta(
        display_name="Hostile Approach",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(60, 270),
        base_win_rate=0.55,
        primary_sec_forms=["SC TO", "DFAN14A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MA_DEAL_BREAK: EventMeta(
        display_name="Deal Break",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(1, 30),
        base_win_rate=0.35,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.MA_MERGER_OF_EQUALS: EventMeta(
        display_name="Merger of Equals",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(60, 270),
        base_win_rate=0.60,
        primary_sec_forms=["8-K", "S-4"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.MA_DEAL_AMENDMENT: EventMeta(
        display_name="Deal Amendment",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(7, 60),
        base_win_rate=0.58,
        primary_sec_forms=["8-K", "SC TO-A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.MA_COMPETING_BID: EventMeta(
        display_name="Competing Bid",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(14, 120),
        base_win_rate=0.65,
        primary_sec_forms=["SC TO", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MA_GO_PRIVATE: EventMeta(
        display_name="Go-Private Transaction",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(30, 180),
        base_win_rate=0.70,
        primary_sec_forms=["SC 13E-3", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.MA_TAKE_PRIVATE_LBO: EventMeta(
        display_name="Take-Private / LBO",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(30, 180),
        base_win_rate=0.68,
        primary_sec_forms=["SC TO", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.TENDER_OFFER_TARGET: EventMeta(
        display_name="Tender Offer (Target)",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(20, 90),
        base_win_rate=0.75,
        primary_sec_forms=["SC TO", "SC 14D9"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.TENDER_OFFER_ACQUIRER: EventMeta(
        display_name="Tender Offer (Acquirer)",
        category=EventCategory.MERGERS_AND_ACQUISITIONS,
        typical_hold_days=(20, 90),
        base_win_rate=0.45,
        primary_sec_forms=["SC TO"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),

    # ── Activist ─────────────────────────────────────────────
    EventType.ACTIVIST_13D_NEW: EventMeta(
        display_name="Activist 13D (New Filing)",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(30, 180),
        base_win_rate=0.62,
        primary_sec_forms=["SC 13D"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.ACTIVIST_13D_AMENDMENT: EventMeta(
        display_name="Activist 13D Amendment",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(14, 120),
        base_win_rate=0.55,
        primary_sec_forms=["SC 13D/A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ACTIVIST_13G_TO_13D: EventMeta(
        display_name="13G to 13D Conversion",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(30, 180),
        base_win_rate=0.64,
        primary_sec_forms=["SC 13D"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.ACTIVIST_SETTLEMENT: EventMeta(
        display_name="Activist Settlement",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(14, 90),
        base_win_rate=0.58,
        primary_sec_forms=["8-K", "DEFA14A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ACTIVIST_BOARD_SEAT: EventMeta(
        display_name="Activist Board Seat",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(30, 180),
        base_win_rate=0.60,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ACTIVIST_PROXY_FIGHT: EventMeta(
        display_name="Proxy Fight",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(30, 120),
        base_win_rate=0.52,
        primary_sec_forms=["DFAN14A", "PREC14A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.ACTIVIST_LETTER_PUBLIC: EventMeta(
        display_name="Public Activist Letter",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(7, 90),
        base_win_rate=0.50,
        primary_sec_forms=[],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.ACTIVIST_STAKE_INCREASE: EventMeta(
        display_name="Activist Stake Increase",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(14, 120),
        base_win_rate=0.58,
        primary_sec_forms=["SC 13D/A"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ACTIVIST_STAKE_DECREASE: EventMeta(
        display_name="Activist Stake Decrease",
        category=EventCategory.ACTIVIST_ENGAGEMENT,
        typical_hold_days=(1, 14),
        base_win_rate=0.40,
        primary_sec_forms=["SC 13D/A"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),

    # ── Spinoffs & Restructuring ─────────────────────────────
    EventType.SPINOFF_ANNOUNCED: EventMeta(
        display_name="Spinoff Announced",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(30, 180),
        base_win_rate=0.65,
        primary_sec_forms=["8-K", "10-12B"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.SPINOFF_RECORD_DATE: EventMeta(
        display_name="Spinoff Record Date Set",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(7, 30),
        base_win_rate=0.60,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.SPINOFF_COMPLETED: EventMeta(
        display_name="Spinoff Completed",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(1, 60),
        base_win_rate=0.58,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.TRACKING_STOCK: EventMeta(
        display_name="Tracking Stock Issuance",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(30, 180),
        base_win_rate=0.55,
        primary_sec_forms=["S-1", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.CORPORATE_SPLIT: EventMeta(
        display_name="Corporate Split / Breakup",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(30, 270),
        base_win_rate=0.62,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ASSET_SALE: EventMeta(
        display_name="Material Asset Sale",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(7, 60),
        base_win_rate=0.56,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.DIVESTITURE: EventMeta(
        display_name="Divestiture",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(14, 90),
        base_win_rate=0.57,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.BANKRUPTCY_FILING: EventMeta(
        display_name="Bankruptcy Filing",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(90, 365),
        base_win_rate=0.30,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.BANKRUPTCY_EMERGENCE: EventMeta(
        display_name="Bankruptcy Emergence",
        category=EventCategory.SPINOFFS_AND_RESTRUCTURING,
        typical_hold_days=(30, 180),
        base_win_rate=0.62,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),

    # ── Capital Allocation ───────────────────────────────────
    EventType.SPECIAL_DIVIDEND: EventMeta(
        display_name="Special Dividend",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(1, 30),
        base_win_rate=0.60,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.DIVIDEND_INITIATION: EventMeta(
        display_name="Dividend Initiation",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 60),
        base_win_rate=0.58,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.DIVIDEND_CUT: EventMeta(
        display_name="Dividend Cut / Suspension",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(1, 30),
        base_win_rate=0.45,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.DIVIDEND_INCREASE: EventMeta(
        display_name="Dividend Increase",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 60),
        base_win_rate=0.56,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
    EventType.ACCELERATED_BUYBACK: EventMeta(
        display_name="Accelerated Share Repurchase (ASR)",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 90),
        base_win_rate=0.62,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.BUYBACK_AUTHORIZATION: EventMeta(
        display_name="Buyback Authorization",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 90),
        base_win_rate=0.54,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
    EventType.RIGHTS_OFFERING: EventMeta(
        display_name="Rights Offering",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(14, 60),
        base_win_rate=0.48,
        primary_sec_forms=["S-1", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.PIPE_TRANSACTION: EventMeta(
        display_name="PIPE Transaction",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 90),
        base_win_rate=0.52,
        primary_sec_forms=["8-K", "S-1"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.SECONDARY_OFFERING: EventMeta(
        display_name="Secondary Offering",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(3, 30),
        base_win_rate=0.45,
        primary_sec_forms=["S-1", "424B"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.CONVERTIBLE_ISSUANCE: EventMeta(
        display_name="Convertible Issuance",
        category=EventCategory.CAPITAL_ALLOCATION,
        typical_hold_days=(7, 60),
        base_win_rate=0.50,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),

    # ── Operational ──────────────────────────────────────────
    EventType.DEFENSE_CONTRACT_AWARD: EventMeta(
        display_name="Defense Contract Award",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(1, 30),
        base_win_rate=0.62,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.BACKLOG_REVISION: EventMeta(
        display_name="Backlog Revision",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(7, 60),
        base_win_rate=0.55,
        primary_sec_forms=["10-Q", "10-K", "8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.PLANT_SHUTDOWN: EventMeta(
        display_name="Plant Shutdown / Curtailment",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(7, 90),
        base_win_rate=0.45,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.PLANT_RESTART: EventMeta(
        display_name="Plant Restart",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(7, 90),
        base_win_rate=0.58,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.CAPACITY_EXPANSION: EventMeta(
        display_name="Capacity Expansion",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(14, 120),
        base_win_rate=0.55,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.SUPPLY_AGREEMENT: EventMeta(
        display_name="Major Supply Agreement",
        category=EventCategory.OPERATIONAL,
        typical_hold_days=(7, 60),
        base_win_rate=0.57,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),

    # ── Management & Governance ──────────────────────────────
    EventType.CEO_CHANGE: EventMeta(
        display_name="CEO Change",
        category=EventCategory.MANAGEMENT_AND_GOVERNANCE,
        typical_hold_days=(7, 90),
        base_win_rate=0.52,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.65,
    ),
    EventType.CFO_CHANGE: EventMeta(
        display_name="CFO Change",
        category=EventCategory.MANAGEMENT_AND_GOVERNANCE,
        typical_hold_days=(7, 60),
        base_win_rate=0.50,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
    EventType.MANAGEMENT_CHANGE_OTHER: EventMeta(
        display_name="Management Change (Other)",
        category=EventCategory.MANAGEMENT_AND_GOVERNANCE,
        typical_hold_days=(3, 30),
        base_win_rate=0.48,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.75,
    ),
    EventType.BOARD_CHANGE: EventMeta(
        display_name="Board Change",
        category=EventCategory.MANAGEMENT_AND_GOVERNANCE,
        typical_hold_days=(7, 60),
        base_win_rate=0.50,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),

    # ── Regulatory & Legal ───────────────────────────────────
    EventType.CREDIT_RATING_UPGRADE: EventMeta(
        display_name="Credit Rating Upgrade",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(3, 30),
        base_win_rate=0.58,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.CREDIT_RATING_DOWNGRADE: EventMeta(
        display_name="Credit Rating Downgrade",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(3, 30),
        base_win_rate=0.42,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.REGULATORY_APPROVAL: EventMeta(
        display_name="Regulatory Approval",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(1, 14),
        base_win_rate=0.65,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.65,
    ),
    EventType.REGULATORY_DENIAL: EventMeta(
        display_name="Regulatory Denial",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(1, 14),
        base_win_rate=0.35,
        primary_sec_forms=["8-K"],
        requires_fundamental=False,
        analyst_alert_threshold=0.60,
    ),
    EventType.SEC_INVESTIGATION: EventMeta(
        display_name="SEC Investigation",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(30, 365),
        base_win_rate=0.38,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.LITIGATION_MATERIAL: EventMeta(
        display_name="Material Litigation",
        category=EventCategory.REGULATORY_AND_LEGAL,
        typical_hold_days=(14, 180),
        base_win_rate=0.42,
        primary_sec_forms=["8-K", "10-Q"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),

    # ── Resource & Mining ────────────────────────────────────
    EventType.RESOURCE_ESTIMATE_UPDATE: EventMeta(
        display_name="Resource/Reserve Estimate (NI 43-101)",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.58,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MINE_FINAL_INVESTMENT_DECISION: EventMeta(
        display_name="Mine FID",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(30, 180),
        base_win_rate=0.60,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MINE_PERMIT_APPROVAL: EventMeta(
        display_name="Mine Permit Approval",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.65,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MINE_PERMIT_DENIAL: EventMeta(
        display_name="Mine Permit Denial",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(1, 30),
        base_win_rate=0.30,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),
    EventType.MINE_DEVELOPMENT: EventMeta(
        display_name="Mine Development Update",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(14, 120),
        base_win_rate=0.52,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.MINE_EXPLORATION: EventMeta(
        display_name="Exploration Results",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.50,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.STREAMING_DEAL: EventMeta(
        display_name="Streaming / Royalty Deal",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.56,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.ROYALTY_DEAL: EventMeta(
        display_name="Royalty Deal",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.55,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.CAPEX_REVISION_UP: EventMeta(
        display_name="CapEx Revision (Up)",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.45,
        primary_sec_forms=["8-K", "10-Q"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.CAPEX_REVISION_DOWN: EventMeta(
        display_name="CapEx Revision (Down)",
        category=EventCategory.RESOURCE_AND_MINING,
        typical_hold_days=(7, 60),
        base_win_rate=0.55,
        primary_sec_forms=["8-K", "10-Q"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),

    # ── Commodity ────────────────────────────────────────────
    EventType.SUPPLY_SHOCK: EventMeta(
        display_name="Supply Shock",
        category=EventCategory.COMMODITY,
        typical_hold_days=(1, 14),
        base_win_rate=0.55,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.60,
    ),
    EventType.INVENTORY_ANOMALY: EventMeta(
        display_name="Inventory Anomaly",
        category=EventCategory.COMMODITY,
        typical_hold_days=(1, 7),
        base_win_rate=0.52,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.65,
    ),
    EventType.RIG_COUNT_INFLECTION: EventMeta(
        display_name="Rig Count Inflection",
        category=EventCategory.COMMODITY,
        typical_hold_days=(7, 60),
        base_win_rate=0.53,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
    EventType.OPEC_DECISION: EventMeta(
        display_name="OPEC Decision Impact",
        category=EventCategory.COMMODITY,
        typical_hold_days=(1, 30),
        base_win_rate=0.50,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.65,
    ),

    # ── Earnings & Guidance ──────────────────────────────────
    EventType.EARNINGS_BEAT: EventMeta(
        display_name="Earnings Beat",
        category=EventCategory.EARNINGS_AND_GUIDANCE,
        typical_hold_days=(1, 30),
        base_win_rate=0.58,
        primary_sec_forms=["8-K", "10-Q"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.EARNINGS_MISS: EventMeta(
        display_name="Earnings Miss",
        category=EventCategory.EARNINGS_AND_GUIDANCE,
        typical_hold_days=(1, 30),
        base_win_rate=0.42,
        primary_sec_forms=["8-K", "10-Q"],
        requires_fundamental=True,
        analyst_alert_threshold=0.70,
    ),
    EventType.GUIDANCE_RAISE: EventMeta(
        display_name="Guidance Raise",
        category=EventCategory.EARNINGS_AND_GUIDANCE,
        typical_hold_days=(7, 60),
        base_win_rate=0.63,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.GUIDANCE_CUT: EventMeta(
        display_name="Guidance Cut",
        category=EventCategory.EARNINGS_AND_GUIDANCE,
        typical_hold_days=(7, 60),
        base_win_rate=0.40,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.PRE_ANNOUNCEMENT: EventMeta(
        display_name="Pre-Announcement",
        category=EventCategory.EARNINGS_AND_GUIDANCE,
        typical_hold_days=(1, 14),
        base_win_rate=0.50,
        primary_sec_forms=["8-K"],
        requires_fundamental=True,
        analyst_alert_threshold=0.60,
    ),

    # ── Options & Market Structure ───────────────────────────
    EventType.OPTIONS_ANOMALY: EventMeta(
        display_name="Options Flow Anomaly",
        category=EventCategory.OPTIONS_AND_MARKET_STRUCTURE,
        typical_hold_days=(1, 14),
        base_win_rate=0.55,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.75,
    ),

    # ── Index & Rebalance ────────────────────────────────────
    EventType.INDEX_ADDITION: EventMeta(
        display_name="Index Addition",
        category=EventCategory.INDEX_AND_REBALANCE,
        typical_hold_days=(7, 30),
        base_win_rate=0.62,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
    EventType.INDEX_DELETION: EventMeta(
        display_name="Index Deletion",
        category=EventCategory.INDEX_AND_REBALANCE,
        typical_hold_days=(7, 30),
        base_win_rate=0.55,
        primary_sec_forms=[],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),

    # ── Insider Activity ─────────────────────────────────────
    EventType.INSIDER_CLUSTER_BUY: EventMeta(
        display_name="Insider Cluster Buy",
        category=EventCategory.INSIDER_ACTIVITY,
        typical_hold_days=(30, 180),
        base_win_rate=0.60,
        primary_sec_forms=["Form 4"],
        requires_fundamental=True,
        analyst_alert_threshold=0.65,
    ),
    EventType.INSIDER_LARGE_SALE: EventMeta(
        display_name="Insider Large Sale",
        category=EventCategory.INSIDER_ACTIVITY,
        typical_hold_days=(7, 60),
        base_win_rate=0.45,
        primary_sec_forms=["Form 4"],
        requires_fundamental=False,
        analyst_alert_threshold=0.70,
    ),
}


def get_event_meta(event_type: EventType) -> EventMeta:
    """Look up metadata for an event type. Raises KeyError if missing."""
    if event_type not in EVENT_METADATA:
        raise KeyError(
            f"No metadata for {event_type.value}. "
            f"Add an entry to EVENT_METADATA in shared/constants/event_types.py"
        )
    return EVENT_METADATA[event_type]
