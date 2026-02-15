-- ╔══════════════════════════════════════════════════════════════╗
-- ║  APEX Trading System — Initial Database Schema             ║
-- ║  Run against Supabase SQL Editor to create all tables.     ║
-- ╚══════════════════════════════════════════════════════════════╝
--
-- Schemas:
--   market    — Securities master, price data, commodity data
--   events    — Corporate events, options anomalies
--   fundamentals — Snapshot data, comps, valuations
--   signals   — Factor outputs, alpha signals, event studies
--   risk      — Portfolio state, risk snapshots, position records
--   execution — Orders, fills, execution quality
--   system    — Workflow runs, audit logs

-- ════════════════════════════════════════════════════════════
-- SCHEMA CREATION
-- ════════════════════════════════════════════════════════════

CREATE SCHEMA IF NOT EXISTS market;
CREATE SCHEMA IF NOT EXISTS events;
CREATE SCHEMA IF NOT EXISTS fundamentals;
CREATE SCHEMA IF NOT EXISTS signals;
CREATE SCHEMA IF NOT EXISTS risk;
CREATE SCHEMA IF NOT EXISTS execution;
CREATE SCHEMA IF NOT EXISTS system;

-- ════════════════════════════════════════════════════════════
-- MARKET SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE market.securities_master (
    figi                     VARCHAR(12) PRIMARY KEY,
    ticker                   VARCHAR(20) NOT NULL,
    name                     TEXT NOT NULL,
    exchange                 VARCHAR(20) NOT NULL,
    instrument_type          VARCHAR(20) NOT NULL DEFAULT 'equity',
    sector                   VARCHAR(100),
    industry                 VARCHAR(200),
    currency                 VARCHAR(3) NOT NULL DEFAULT 'USD',
    market_cap_usd           NUMERIC,
    average_daily_volume_30d BIGINT,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    country                  VARCHAR(5) NOT NULL DEFAULT 'US',
    cik                      VARCHAR(20),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_securities_ticker ON market.securities_master(ticker);
CREATE INDEX idx_securities_sector ON market.securities_master(sector);
CREATE INDEX idx_securities_exchange ON market.securities_master(exchange);
CREATE INDEX idx_securities_cik ON market.securities_master(cik) WHERE cik IS NOT NULL;

CREATE TABLE market.prices_eod (
    figi        VARCHAR(12) NOT NULL REFERENCES market.securities_master(figi),
    date        DATE NOT NULL,
    open        NUMERIC NOT NULL,
    high        NUMERIC NOT NULL,
    low         NUMERIC NOT NULL,
    close       NUMERIC NOT NULL,
    volume      BIGINT NOT NULL,
    vwap        NUMERIC,
    adj_close   NUMERIC,
    source      VARCHAR(30) NOT NULL DEFAULT 'POLYGON',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (figi, date)
);

CREATE INDEX idx_prices_eod_date ON market.prices_eod(date);

CREATE TABLE market.options_chain_snapshots (
    id                       UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                     VARCHAR(12) NOT NULL REFERENCES market.securities_master(figi),
    timestamp                TIMESTAMPTZ NOT NULL,
    total_call_volume        BIGINT NOT NULL DEFAULT 0,
    total_put_volume         BIGINT NOT NULL DEFAULT 0,
    put_call_ratio           NUMERIC NOT NULL DEFAULT 0,
    unusual_call_volume      BIGINT,
    unusual_put_volume       BIGINT,
    largest_trade_premium    NUMERIC,
    implied_volatility_atm   NUMERIC,
    iv_30d_percentile        NUMERIC,
    oi_call                  BIGINT,
    oi_put                   BIGINT,
    source                   VARCHAR(30) NOT NULL DEFAULT 'POLYGON_OPTIONS'
);

CREATE INDEX idx_options_figi_ts ON market.options_chain_snapshots(figi, timestamp);

CREATE TABLE market.commodity_data (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    commodity   VARCHAR(50) NOT NULL,
    date        DATE NOT NULL,
    value       NUMERIC NOT NULL,
    unit        VARCHAR(30) NOT NULL,
    data_type   VARCHAR(20) NOT NULL,
    source      VARCHAR(30) NOT NULL,
    metadata    JSONB,
    UNIQUE(commodity, date, data_type, source)
);

CREATE INDEX idx_commodity_date ON market.commodity_data(commodity, date);

CREATE TABLE market.insider_transactions (
    id                 UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi               VARCHAR(12) NOT NULL REFERENCES market.securities_master(figi),
    filing_date        DATE NOT NULL,
    accession_no       VARCHAR(30) NOT NULL UNIQUE,
    insider_name       TEXT NOT NULL,
    insider_title      TEXT NOT NULL,
    transaction_type   VARCHAR(20) NOT NULL DEFAULT 'buy',
    shares             INTEGER NOT NULL,
    price_per_share    NUMERIC,
    total_value_usd    NUMERIC,
    shares_owned_after INTEGER,
    is_10b5_1          BOOLEAN NOT NULL DEFAULT FALSE,
    source             VARCHAR(30) NOT NULL DEFAULT 'EDGAR'
);

CREATE INDEX idx_insider_figi_date ON market.insider_transactions(figi, filing_date);
CREATE INDEX idx_insider_type ON market.insider_transactions(transaction_type);

-- ════════════════════════════════════════════════════════════
-- EVENTS SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE events.corporate_events (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                VARCHAR(12) NOT NULL,
    ticker              VARCHAR(20) NOT NULL,
    event_type          VARCHAR(50) NOT NULL,
    event_category      VARCHAR(50) NOT NULL,
    confidence          NUMERIC(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    headline            VARCHAR(500) NOT NULL,
    summary             TEXT NOT NULL,
    source              VARCHAR(30) NOT NULL,
    source_url          TEXT,
    source_ref          VARCHAR(100),
    deal_value_usd      NUMERIC,
    premium_pct         NUMERIC,
    consideration_type  VARCHAR(10),
    detected_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_date          TIMESTAMPTZ,
    expected_close_date TIMESTAMPTZ,
    status              VARCHAR(30) NOT NULL DEFAULT 'new',
    dedup_hash          VARCHAR(64) UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_figi ON events.corporate_events(figi);
CREATE INDEX idx_events_type ON events.corporate_events(event_type);
CREATE INDEX idx_events_status ON events.corporate_events(status);
CREATE INDEX idx_events_detected ON events.corporate_events(detected_at);
CREATE INDEX idx_events_confidence ON events.corporate_events(confidence);

CREATE TABLE events.options_anomalies (
    id                        UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                      VARCHAR(12) NOT NULL,
    ticker                    VARCHAR(20) NOT NULL,
    detected_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    volume_zscore             NUMERIC NOT NULL,
    put_call_ratio            NUMERIC NOT NULL,
    put_call_ratio_zscore     NUMERIC NOT NULL,
    dominant_direction        VARCHAR(10) NOT NULL,
    largest_trade_premium_usd NUMERIC,
    otm_sweep_detected        BOOLEAN NOT NULL DEFAULT FALSE,
    has_known_explanation      BOOLEAN NOT NULL DEFAULT FALSE,
    explanation               TEXT,
    anomaly_score             INTEGER NOT NULL CHECK (anomaly_score >= 0 AND anomaly_score <= 100),
    linked_event_id           UUID REFERENCES events.corporate_events(id)
);

CREATE INDEX idx_options_anomaly_figi ON events.options_anomalies(figi);
CREATE INDEX idx_options_anomaly_score ON events.options_anomalies(anomaly_score);

-- ════════════════════════════════════════════════════════════
-- FUNDAMENTALS SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE fundamentals.snapshots (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                    VARCHAR(12) NOT NULL,
    event_id                UUID NOT NULL REFERENCES events.corporate_events(id),
    snapshot_date           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revenue_ttm             NUMERIC,
    ebitda_ttm              NUMERIC,
    net_income_ttm          NUMERIC,
    free_cash_flow_ttm      NUMERIC,
    total_debt              NUMERIC,
    cash_and_equivalents    NUMERIC,
    net_debt                NUMERIC,
    shares_outstanding      BIGINT,
    book_value_per_share    NUMERIC,
    tangible_book_per_share NUMERIC,
    ev_ebitda               NUMERIC,
    pe_ratio                NUMERIC,
    pb_ratio                NUMERIC,
    fcf_yield               NUMERIC,
    dividend_yield          NUMERIC,
    ev_revenue              NUMERIC,
    roic                    NUMERIC,
    roe                     NUMERIC,
    gross_margin            NUMERIC,
    operating_margin        NUMERIC,
    net_margin              NUMERIC,
    debt_to_ebitda          NUMERIC,
    interest_coverage       NUMERIC,
    current_ratio           NUMERIC,
    revenue_growth_yoy      NUMERIC,
    ebitda_growth_yoy       NUMERIC,
    eps_growth_yoy          NUMERIC,
    xbrl_filing_accession   VARCHAR(30),
    last_updated            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fundamental_figi ON fundamentals.snapshots(figi);
CREATE INDEX idx_fundamental_event ON fundamentals.snapshots(event_id);

CREATE TABLE fundamentals.comps_tables (
    id                          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    subject_figi                VARCHAR(12) NOT NULL,
    event_id                    UUID NOT NULL REFERENCES events.corporate_events(id),
    comps                       JSONB NOT NULL,
    implied_ev_ebitda           NUMERIC,
    implied_pe                  NUMERIC,
    implied_fair_value_per_share NUMERIC,
    generated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE fundamentals.valuation_scenarios (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                VARCHAR(12) NOT NULL,
    event_id            UUID NOT NULL REFERENCES events.corporate_events(id),
    current_price       NUMERIC NOT NULL,
    scenarios           JSONB NOT NULL,
    expected_return     NUMERIC NOT NULL,
    upside_downside_ratio NUMERIC NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE fundamentals.mining_navs (
    id                         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                       VARCHAR(12) NOT NULL,
    event_id                   UUID NOT NULL REFERENCES events.corporate_events(id),
    total_resources_moz        NUMERIC,
    total_reserves_moz         NUMERIC,
    commodity_price_assumption NUMERIC,
    all_in_sustaining_cost     NUMERIC,
    mine_nav_usd               NUMERIC,
    exploration_value_usd      NUMERIC,
    net_cash_usd               NUMERIC,
    corporate_adjustment_usd   NUMERIC,
    total_nav_usd              NUMERIC,
    nav_per_share              NUMERIC,
    current_price              NUMERIC,
    discount_to_nav_pct        NUMERIC,
    discount_rate_pct          NUMERIC NOT NULL DEFAULT 5.0,
    generated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- SIGNALS SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE signals.factor_outputs (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    factor_name             VARCHAR(50) NOT NULL,
    figi                    VARCHAR(12) NOT NULL,
    event_id                UUID NOT NULL REFERENCES events.corporate_events(id),
    raw_value               NUMERIC NOT NULL,
    z_score                 NUMERIC NOT NULL,
    percentile              NUMERIC NOT NULL CHECK (percentile >= 0 AND percentile <= 100),
    signal_direction        VARCHAR(10) NOT NULL,
    information_coefficient NUMERIC,
    computed_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_factor_event ON signals.factor_outputs(event_id);
CREATE INDEX idx_factor_name ON signals.factor_outputs(factor_name);

CREATE TABLE signals.alpha_signals (
    id                         UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_id                   UUID NOT NULL REFERENCES events.corporate_events(id),
    figi                       VARCHAR(12) NOT NULL,
    event_type                 VARCHAR(50) NOT NULL,
    composite_score            NUMERIC(5,4) NOT NULL CHECK (composite_score >= 0 AND composite_score <= 1),
    conviction                 INTEGER NOT NULL CHECK (conviction >= 1 AND conviction <= 5),
    direction                  VARCHAR(10) NOT NULL,
    expected_return_annualized NUMERIC,
    win_probability            NUMERIC CHECK (win_probability >= 0 AND win_probability <= 1),
    factor_scores              JSONB NOT NULL DEFAULT '{}'::jsonb,
    factor_weights             JSONB NOT NULL DEFAULT '{}'::jsonb,
    ml_deal_break_prob         NUMERIC,
    ml_earnings_surprise       NUMERIC,
    generated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_version              VARCHAR(20) NOT NULL DEFAULT 'v1.0.0',
    is_stale                   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_signals_event ON signals.alpha_signals(event_id);
CREATE INDEX idx_signals_figi ON signals.alpha_signals(figi);
CREATE INDEX idx_signals_score ON signals.alpha_signals(composite_score);

CREATE TABLE signals.event_studies (
    id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type        VARCHAR(50) NOT NULL UNIQUE,
    sample_size       INTEGER NOT NULL CHECK (sample_size >= 10),
    avg_return_1d     NUMERIC NOT NULL,
    avg_return_5d     NUMERIC NOT NULL,
    avg_return_20d    NUMERIC NOT NULL,
    avg_return_60d    NUMERIC NOT NULL,
    median_return_20d NUMERIC NOT NULL,
    win_rate_20d      NUMERIC NOT NULL CHECK (win_rate_20d >= 0 AND win_rate_20d <= 1),
    volatility_20d    NUMERIC NOT NULL,
    sharpe_20d        NUMERIC,
    optimal_hold_days INTEGER NOT NULL CHECK (optimal_hold_days >= 1),
    last_updated      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- RISK SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE risk.positions (
    id                UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi              VARCHAR(12) NOT NULL,
    ticker            VARCHAR(20) NOT NULL,
    direction         VARCHAR(10) NOT NULL,
    quantity          INTEGER NOT NULL,
    avg_entry_price   NUMERIC NOT NULL,
    current_price     NUMERIC NOT NULL,
    market_value_usd  NUMERIC NOT NULL,
    unrealized_pnl_usd NUMERIC NOT NULL DEFAULT 0,
    unrealized_pnl_pct NUMERIC NOT NULL DEFAULT 0,
    weight_pct        NUMERIC NOT NULL DEFAULT 0,
    sector            VARCHAR(100),
    event_id          UUID REFERENCES events.corporate_events(id),
    event_type        VARCHAR(50),
    entry_date        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    days_held         INTEGER NOT NULL DEFAULT 0,
    stop_loss_price   NUMERIC,
    target_price      NUMERIC,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_positions_figi ON risk.positions(figi);
CREATE INDEX idx_positions_active ON risk.positions(is_active) WHERE is_active = TRUE;

CREATE TABLE risk.portfolio_snapshots (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    snapshot_time           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    nav                     NUMERIC NOT NULL,
    cash                    NUMERIC NOT NULL,
    gross_exposure          NUMERIC NOT NULL,
    net_exposure            NUMERIC NOT NULL,
    long_exposure           NUMERIC NOT NULL,
    short_exposure          NUMERIC NOT NULL,
    gross_leverage          NUMERIC NOT NULL,
    net_leverage            NUMERIC NOT NULL,
    largest_position_pct    NUMERIC NOT NULL,
    top5_concentration_pct  NUMERIC NOT NULL,
    sector_exposures        JSONB NOT NULL DEFAULT '{}'::jsonb,
    daily_pnl_usd           NUMERIC NOT NULL DEFAULT 0,
    daily_pnl_pct           NUMERIC NOT NULL DEFAULT 0,
    mtd_pnl_pct             NUMERIC NOT NULL DEFAULT 0,
    ytd_pnl_pct             NUMERIC NOT NULL DEFAULT 0,
    portfolio_var_1d_95     NUMERIC,
    portfolio_beta          NUMERIC,
    active_positions_count  INTEGER NOT NULL DEFAULT 0
);

-- TimescaleDB hypertable for time-series risk data
-- Uncomment if TimescaleDB extension is available:
-- SELECT create_hypertable('risk.portfolio_snapshots', 'snapshot_time');

CREATE INDEX idx_risk_snapshot_time ON risk.portfolio_snapshots(snapshot_time);

CREATE TABLE risk.pre_trade_checks (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    approved         BOOLEAN NOT NULL,
    request          JSONB NOT NULL,
    checks_passed    JSONB NOT NULL DEFAULT '[]'::jsonb,
    checks_failed    JSONB NOT NULL DEFAULT '[]'::jsonb,
    rejection_reason TEXT,
    risk_metrics     JSONB,
    checked_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE risk.stop_loss_alerts (
    id                   UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    figi                 VARCHAR(12) NOT NULL,
    ticker               VARCHAR(20) NOT NULL,
    event_id             UUID REFERENCES events.corporate_events(id),
    direction            VARCHAR(10) NOT NULL,
    trigger_price        NUMERIC NOT NULL,
    current_price        NUMERIC NOT NULL,
    stop_type            VARCHAR(20) NOT NULL DEFAULT 'initial',
    loss_pct             NUMERIC NOT NULL,
    recommended_action   VARCHAR(20) NOT NULL DEFAULT 'close_full',
    triggered_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actioned             BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE risk.stress_test_reports (
    id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    portfolio_state       JSONB NOT NULL,
    scenarios             JSONB NOT NULL,
    results               JSONB NOT NULL,
    worst_case_loss_pct   NUMERIC NOT NULL,
    worst_case_scenario   VARCHAR(100) NOT NULL,
    passes_stress_test    BOOLEAN NOT NULL,
    run_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- EXECUTION SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE execution.orders (
    id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_id              UUID NOT NULL REFERENCES events.corporate_events(id),
    figi                  VARCHAR(12) NOT NULL,
    ticker                VARCHAR(20) NOT NULL,
    direction             VARCHAR(10) NOT NULL,
    strategy              VARCHAR(20) NOT NULL,
    urgency               VARCHAR(10) NOT NULL DEFAULT 'MEDIUM',
    quantity              INTEGER NOT NULL CHECK (quantity > 0),
    limit_price           NUMERIC,
    decision_price        NUMERIC NOT NULL,
    algo_duration_minutes INTEGER,
    max_pct_volume        NUMERIC,
    risk_check_id         UUID REFERENCES risk.pre_trade_checks(id),
    analyst_approval_id   UUID NOT NULL,
    fundamental_snapshot_id UUID NOT NULL,
    signal_id             UUID NOT NULL,
    conviction            INTEGER NOT NULL CHECK (conviction >= 1 AND conviction <= 5),
    status                VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_event ON execution.orders(event_id);
CREATE INDEX idx_orders_status ON execution.orders(status);

CREATE TABLE execution.fills (
    id                    UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    execution_request_id  UUID NOT NULL REFERENCES execution.orders(id),
    ibkr_order_id         INTEGER,
    ibkr_exec_id          VARCHAR(50),
    fill_price            NUMERIC NOT NULL CHECK (fill_price > 0),
    fill_quantity          INTEGER NOT NULL CHECK (fill_quantity > 0),
    fill_value_usd        NUMERIC NOT NULL CHECK (fill_value_usd > 0),
    exchange              VARCHAR(20),
    commission_usd        NUMERIC DEFAULT 0,
    fill_time             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fills_order ON execution.fills(execution_request_id);

CREATE TABLE execution.results (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    execution_request_id    UUID NOT NULL REFERENCES execution.orders(id),
    event_id                UUID NOT NULL REFERENCES events.corporate_events(id),
    figi                    VARCHAR(12) NOT NULL,
    ticker                  VARCHAR(20) NOT NULL,
    direction               VARCHAR(10) NOT NULL,
    total_quantity_filled    INTEGER NOT NULL,
    total_quantity_requested INTEGER NOT NULL,
    avg_fill_price          NUMERIC NOT NULL,
    total_value_usd         NUMERIC NOT NULL,
    total_commission_usd    NUMERIC NOT NULL DEFAULT 0,
    status                  VARCHAR(20) NOT NULL,
    fill_rate               NUMERIC NOT NULL CHECK (fill_rate >= 0 AND fill_rate <= 1),
    first_fill_time         TIMESTAMPTZ,
    last_fill_time          TIMESTAMPTZ,
    total_execution_seconds NUMERIC,
    analyst_approval_id     UUID NOT NULL,
    strategy_used           VARCHAR(20) NOT NULL,
    completed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE execution.quality_reports (
    id                            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    execution_result_id           UUID NOT NULL REFERENCES execution.results(id),
    figi                          VARCHAR(12) NOT NULL,
    implementation_shortfall_bps  NUMERIC NOT NULL,
    market_impact_bps             NUMERIC NOT NULL,
    timing_cost_bps               NUMERIC NOT NULL,
    decision_price                NUMERIC NOT NULL,
    arrival_price                 NUMERIC NOT NULL,
    avg_fill_price                NUMERIC NOT NULL,
    rating                        VARCHAR(20) NOT NULL,
    requires_review               BOOLEAN NOT NULL DEFAULT FALSE,
    computed_at                   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ════════════════════════════════════════════════════════════
-- SYSTEM SCHEMA
-- ════════════════════════════════════════════════════════════

CREATE TABLE system.workflow_runs (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workflow_name VARCHAR(100) NOT NULL,
    run_id        VARCHAR(100) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at  TIMESTAMPTZ,
    error         TEXT,
    trigger_data  JSONB
);

CREATE INDEX idx_workflow_name ON system.workflow_runs(workflow_name);
CREATE INDEX idx_workflow_status ON system.workflow_runs(status);

CREATE TABLE system.analyst_approvals (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_id    UUID NOT NULL REFERENCES events.corporate_events(id),
    analyst     VARCHAR(100) NOT NULL,
    decision    VARCHAR(20) NOT NULL CHECK (decision IN ('approved', 'rejected')),
    notes       TEXT,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approvals_event ON system.analyst_approvals(event_id);

-- ════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- ════════════════════════════════════════════════════════════

-- Enable RLS on all tables (policies to be configured per environment)
ALTER TABLE market.securities_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE events.corporate_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE system.analyst_approvals ENABLE ROW LEVEL SECURITY;

-- Service role bypass (for API writes)
CREATE POLICY "service_role_full_access" ON market.securities_master
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_full_access" ON events.corporate_events
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_full_access" ON risk.positions
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_full_access" ON execution.orders
    FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "service_role_full_access" ON system.analyst_approvals
    FOR ALL USING (auth.role() = 'service_role');
