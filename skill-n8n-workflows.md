---
name: n8n-workflows
description: Use this skill when building, modifying, or debugging n8n workflows in the antigravity/APEX system. Covers APEX-specific workflow patterns, node configurations, error handling, environment variable usage, webhook design, inter-service communication, and workflow export/import conventions. Trigger when the task involves any n8n workflow JSON, n8n node configuration, cron scheduling, webhook triggers, or the workflows/ directory.
---

# n8n Workflows Skill — antigravity/APEX

n8n is the nervous system that connects APEX's data sources, processing services, and alerting. It handles timing, retries, error isolation, and the complex conditional routing that would otherwise require brittle Python scheduling code. This skill documents APEX's specific workflow patterns.

---

## Core Principles for APEX Workflows

1. **Workflows are glue, not logic.** Heavy computation (LLM calls, factor calculations, risk checks) happens in Python microservices called via HTTP. n8n handles the "when, what, and if it fails."
2. **Every workflow logs to Supabase.** The `workflow_runs` table tracks every execution with status, duration, and error details.
3. **No secrets in workflows.** All API keys and credentials come from n8n environment variables (Settings → Variables), never hardcoded in node configurations.
4. **Workflows are version-controlled.** Every workflow is exported to `workflows/` as JSON and committed to git. Name convention: `{workflow-name}.json`.

---

## Standard Workflow Template

Every new workflow follows this structure:

```
[Trigger Node]
    ↓
[Workflow Logger: START]      ← Always first after trigger
    ↓
[Core Processing Nodes]
    ↓
[Workflow Logger: SUCCESS]    ← On happy path
[Error Handler]               ← On any node failure
    ↓
[Alert: Slack #ops-alerts]    ← Only for critical failures
```

### Workflow Logger Node (Code Node)

Add this Code node immediately after every trigger and before every terminal state:

```javascript
// Workflow Logger — paste this into every "log start" Code node

const workflowName = $workflow.name;
const runId = $execution.id;
const status = $input.first().json.log_status || 'RUNNING';  // Passed via parameter

const logEntry = {
  workflow_name: workflowName,
  run_id: runId,
  status: status,
  started_at: new Date().toISOString(),
  trigger_data: JSON.stringify($input.first().json).substring(0, 1000),  // First 1KB
};

// Write to Supabase
const response = await $http.request({
  method: 'POST',
  url: `${$env.SUPABASE_URL}/rest/v1/system.workflow_runs`,
  headers: {
    'apikey': $env.SUPABASE_ANON_KEY,
    'Authorization': `Bearer ${$env.SUPABASE_ANON_KEY}`,
    'Content-Type': 'application/json',
    'Prefer': 'resolution=merge-duplicates',
  },
  body: JSON.stringify(logEntry),
});

return [{ json: { ...logEntry, logged: true } }];
```

---

## Workflow: edgar-realtime-monitor

**Trigger:** Schedule — every 60 seconds, 24/7 (filings happen outside US market hours)

**Purpose:** Detect new SEC filings for securities in our universe

```
[Schedule: every 60s]
    ↓
[HTTP: GET EDGAR EFTS API]
    URL: https://efts.sec.gov/LATEST/search-index
    Params: 
      q: ""
      forms: "8-K,13D,13G,SC+TO,DEFM14A,S-4,Form+4"
      dateRange: "custom"
      startdt: {{ $vars.EDGAR_LAST_POLL_TS }}  ← stored as n8n variable, updated each run
      enddt: {{ $now.toISO() }}
    
    ↓
[Code: Filter & Deduplicate]
    - Filter hits by form whitelist
    - Remove accession numbers already in Supabase (batch check)
    - Return only new, unprocessed filings
    
    ↓
[IF: any new filings?]
    NO → [Update EDGAR_LAST_POLL_TS] → [End]
    YES ↓
    
[Split in Batches: 5 per batch]    ← Prevent overwhelming the LLM API
    ↓
[HTTP: POST /classify-event]       ← Python FastAPI service
    URL: {{ $env.CLASSIFICATION_SERVICE_URL }}/classify
    Body: { accession_no, form_type, cik, filing_url }
    Timeout: 30 seconds
    
    ↓
[IF: confidence >= 0.65?]
    NO → [HTTP: POST Supabase events (status=low_confidence)] → next item
    YES ↓
    
[HTTP: POST Supabase events (status=new)]
    ↓
[HTTP: POST Redis publish new_event]
    URL: {{ $env.REDIS_REST_URL }}/publish
    Body: { channel: "apex:events:new", message: {{ event_json }} }
    
    ↓
[IF: event.confidence >= 0.80?]
    YES → [Slack: #event-alerts] with event summary
    
[Update EDGAR_LAST_POLL_TS]        ← Always update, even if no new filings
```

**Key configuration:**
```
EDGAR_LAST_POLL_TS: n8n workflow variable (persists between runs)
Initial value: "2024-01-01T00:00:00"
Update frequency: After each successful poll, set to current timestamp minus 5 minutes (overlap buffer)
```

**Error handling:**
- EDGAR API 429 (rate limit): Wait node (30 seconds) → retry once → if still fails, continue without updating timestamp (will retry same window next poll)
- EDGAR API 500: Log error, send Slack alert to #ops-critical, continue (don't update timestamp)
- Classification service timeout: Log, skip this filing, continue with others

---

## Workflow: fundamental-enricher

**Trigger:** Redis Subscribe on `apex:events:new` channel (via Webhook trigger listening to a Redis-to-HTTP bridge)

**Purpose:** Automatically trigger fundamental analysis for every new high-confidence event

```
[Webhook: POST /n8n/new-event]     ← Redis bridge calls this on new_event channel message
    Body: CorporateEvent JSON
    ↓
[Code: Parse & validate event]
    - Parse JSON to CorporateEvent schema
    - Check event type is in REQUIRES_FUNDAMENTAL list
    - If not requires_fundamental → End (no-op)
    
    ↓
[HTTP: POST /fundamental/enrich]   ← Python FastAPI fundamental service
    URL: {{ $env.FUNDAMENTAL_SERVICE_URL }}/enrich
    Body: { event_id, figi, event_type }
    Timeout: 60 seconds            ← XBRL pull + comps can take 30-60s
    
    ↓
[IF: enrichment successful?]
    NO → [Retry once after 30s] → [Log failure to Supabase] → [Alert #ops]
    YES ↓
    
[HTTP: POST /signals/generate]     ← Trigger signal generation
    URL: {{ $env.SIGNAL_SERVICE_URL }}/generate
    Body: { event_id }
    
    ↓
[HTTP: POST /dashboard/notify]     ← Tell analyst dashboard to refresh
    Body: { event_id, figi, priority }
```

---

## Workflow: options-flow-scanner

**Trigger:** Schedule — every 5 minutes, 9:30 AM – 4:00 PM EST weekdays only

```
[Schedule: every 5min, market hours]
    ↓
[HTTP: GET Polygon options volume]
    For each figi in active universe (paginated)
    
    ↓
[Code: Compute z-scores]
    For each ticker:
    - Current options volume vs. 20-day rolling average
    - Put/call ratio vs. 30-day average
    - OTM call sweep detection
    
    ↓
[IF: any z-score > 4.0?]          ← 4 sigma is the alert threshold
    YES ↓
    
[HTTP: POST Supabase options_anomalies table]
    ↓
[HTTP: POST /classify-options-anomaly]    ← LLM context check
    Check if known event explains the flow (earnings, known news)
    If no known explanation: this is pre-event positioning
    
    ↓
[IF: unexplained and z-score > 5.0?]
    YES → [Slack: #options-flow alert with details]
    YES → [HTTP: POST Supabase events (type=OPTIONS_ANOMALY)]
```

---

## Workflow: risk-monitor

**Trigger:** Schedule — every 30 seconds, 9:25 AM – 4:30 PM EST weekdays

```
[Schedule: every 30s]
    ↓
[HTTP: GET /risk/snapshot]         ← Python risk service computes live snapshot
    URL: {{ $env.RISK_SERVICE_URL }}/snapshot
    Timeout: 5 seconds             ← Must be fast; this runs constantly
    
    ↓
[HTTP: POST Supabase risk_snapshots]    ← Write to TimescaleDB hypertable
    ↓
[Code: Check limits]
    - gross_exposure > 1.45 * nav → WARNING
    - gross_exposure > 1.50 * nav → CRITICAL
    - single_sector_pct > 0.30 → WARNING
    - single_sector_pct > 0.35 → CRITICAL
    - daily_loss_pct < -0.025 → WARNING
    - daily_loss_pct < -0.030 → CRITICAL + HALT NEW POSITIONS
    
    ↓
[IF: any CRITICAL?]
    YES → [Slack: #risk-critical @risk-team] + [HTTP: POST /risk/halt-new-positions]
    
[IF: any WARNING?]
    YES → [Slack: #risk-warnings] (no halt)
```

**Important:** The 30-second risk snapshot is how Grafana's risk dashboard stays real-time. Never increase this interval without understanding the impact on dashboard freshness.

---

## Workflow: eod-report

**Trigger:** Schedule — 5:30 PM EST, weekdays only (after options expiry data is complete)

```
[Schedule: 5:30 PM EST weekdays]
    ↓
[HTTP: POST /reporting/generate-eod]
    URL: {{ $env.REPORTING_SERVICE_URL }}/eod
    Timeout: 300 seconds           ← Report generation can take 2-5 minutes
    Returns: { report_url, summary_json }
    
    ↓
[Code: Format summary message]
    Extract: daily P&L, top movers, active events count, risk metrics
    
    ↓
[Slack: #daily-pnl]
    Message: Formatted daily summary with key stats
    Include: Link to full PDF report
    
    ↓
[HTTP: POST Supabase reports table]
    Store report URL for dashboard access
```

---

## Environment Variables Used in Workflows

All n8n environment variables (Settings → Variables in n8n UI):

```
# Service URLs (all internal; no external exposure)
CLASSIFICATION_SERVICE_URL  http://classification:8001
FUNDAMENTAL_SERVICE_URL     http://fundamental:8002
SIGNAL_SERVICE_URL          http://signals:8003
RISK_SERVICE_URL            http://risk:8004
REPORTING_SERVICE_URL       http://reporting:8005

# Supabase
SUPABASE_URL                https://your-project.supabase.co
SUPABASE_ANON_KEY           eyJ...  (read-only key for n8n; write via service role in Python services)

# Redis REST Bridge
REDIS_REST_URL              http://redis-rest:8080  (Upstash Redis REST or custom bridge)

# Alerting
SLACK_BOT_TOKEN             xoxb-...
SLACK_OPS_CHANNEL           #ops-alerts
SLACK_RISK_CHANNEL          #risk-critical
SLACK_EVENTS_CHANNEL        #event-alerts

# APEX control
APEX_ENV                    paper  (or production)

# n8n workflow state (workflow variables, not environment)
EDGAR_LAST_POLL_TS          2024-01-01T00:00:00  (updated by edgar-realtime-monitor)
```

---

## Error Handling Patterns

### Pattern 1: Retry with Backoff
For transient errors (rate limits, timeouts):
```
[HTTP Node with error]
    ↓ (on error output)
[Wait: 30 seconds]
    ↓
[HTTP Node: retry once]
    ↓ (on error output)
[Log error to Supabase] + [Slack alert if critical]
    ↓
[End: continue processing remaining items]
```

### Pattern 2: Partial Batch Failure
For batch operations where some items fail:
```javascript
// Code node after batch HTTP call
const results = $input.all();
const successes = results.filter(r => !r.json.error);
const failures = results.filter(r => r.json.error);

if (failures.length > 0) {
  // Log failures but don't block the successes
  for (const fail of failures) {
    console.error(`Failed: ${JSON.stringify(fail.json)}`);
  }
}

// Continue with successes only
return successes;
```

### Pattern 3: Alert Deduplication
Prevent Slack spam from repeated failures:
```javascript
// Before sending Slack alert, check if we sent one in the last 15 minutes
const alertKey = `n8n:alert:${$workflow.name}:${errorType}`;
const lastAlert = await $http.request({
  url: `${$env.REDIS_REST_URL}/get/${alertKey}`,
});

if (!lastAlert.data.result) {
  // No recent alert — send it and set a 15-minute cooldown
  // ... send Slack message ...
  await $http.request({
    method: 'POST',
    url: `${$env.REDIS_REST_URL}/set/${alertKey}/1/EX/900`,  // 900s = 15 min TTL
  });
}
```

---

## Exporting and Versioning Workflows

```bash
# Export a workflow after modifying in n8n UI
# Settings → Workflows → Export → JSON
# Save to: workflows/{workflow-name}.json

# Git commit convention:
git add workflows/edgar-realtime-monitor.json
git commit -m "chore(n8n): add 13G form to EDGAR monitor filter list"

# Import workflow to a new n8n instance:
# Settings → Workflows → Import from File
```

---

## Critical Rules

1. **No business logic in n8n Code nodes.** Route, filter, transform data shape. Compute in Python services.
2. **Always log workflow start and end to Supabase `system.workflow_runs`.** This is your operational audit trail.
3. **Every n8n variable with a secret goes through Settings → Variables, never in node configs.** Credentials in node configs are visible in workflow exports.
4. **Test every new workflow with the "Test Workflow" button before activating.** Check every output path including error branches.
5. **Market hours scheduling:** Use the Schedule trigger with `Timezone: America/New_York` and cron expressions that respect 9:30 AM – 4:00 PM. Never use UTC for market-hours workflows.
6. **Export the workflow JSON to `workflows/` after every non-trivial change.** Treat the JSON file as the source of truth; the n8n database as the running instance.
7. **Use `Split in Batches` for any loop over multiple items.** Never use a JavaScript for-loop to make sequential HTTP calls inside a Code node — it blocks the node and creates timeout risk.
8. **EDGAR poll interval is 60 seconds minimum.** SEC EDGAR has rate limits. Faster polling results in 429 responses and gaps in coverage.
