# APEX // SOVEREIGN TERMINAL v3.0

APEX is a high-frequency event-driven trading system built for the Sovereign Analyst. It implements an 8-layer architecture ranging from low-level data ingest to a high-density analyst dashboard.

## Quick Start (Docker)

The fastest way to get APEX running is via Docker Compose.

### 1. Prerequisites
- Docker & Docker Compose
- Supabase account (for database and auth)
- Redis (included in Docker)
- IBKR Gateway/TWS (optional, for execution)

### 2. Configuration
Copy the example environment file and fill in your API keys:
```bash
cp .env.example .env
```
Key variables required:python
- `SUPABASE_URL` & `SUPABASE_SERVICE_KEY`
- `POLYGON_API_KEY`
- `ANTHROPIC_API_KEY` (for event classification)

### 3. Database Setup
Apply the initial Supabase schema located in:
`migrations/20250201_initial_schema.sql`
Run this in your Supabase SQL Editor.

### 4. Launch the Stack
```bash
docker-compose --profile all up --build
```
This will start:
- **Infrastructure**: Redis, n8n, Grafana
- **Services**: Ingest, Detection, Fundamental, Signals, Risk, Execution
- **Interface**: Analyst Terminal (Streamlit) @ `http://localhost:8501`

---

## 8-Layer Architecture

| Layer | Responsibility | Service |
|---|---|---|
| **L1** | Data Infrastructure | `ingest` (Celery) |
| **L2** | Event Detection | `detection` (FastAPI) |
| **L3** | Fundamental Engine | `fundamental` (FastAPI) |
| **L4** | Quant Signal Framework | `signals` (FastAPI) |
| **L5** | Risk Management | `risk` (FastAPI) |
| **L6** | Portfolio Construction | `risk` (Internal) |
| **L7** | Execution Management | `execution` (FastAPI) |
| **L8** | Research Workflow | `dashboard` (Streamlit) |

## Development & Testing

To run individual services for development:
```bash
# Example: Start Detection service
uvicorn services.detection.app:app --reload --port 8001
```

To run import verification locally:
```bash
python3 -c "import services.detection.app; print('Success')"
```
*Note: Local execution requires installing dependencies from `pyproject.toml`.*
