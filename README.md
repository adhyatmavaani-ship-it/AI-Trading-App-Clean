# Autonomous AI Trading Terminal

Autonomous AI trading terminal with institutional logic, real-time market hunting, and a high-signal operator workflow.

This project combines a FastAPI trading backend, a Flutter mobile dashboard, async backtesting, and a dynamic market scanner into one opinionated system designed for fast market awareness, explainable AI trade logic, and resilient paper-to-live operations.

## The Hook

The terminal is built around three product ideas:

- `Market Hunter`: a rotating scanner that ranks active symbols by opportunity and keeps the app focused on tradeable momentum instead of a static watchlist
- `Institutional Logic`: confluence-based AI decisions with natural-language reasoning, logic tags, confluence bars, risk flags, and marker-level explanations
- `Live Pulse UI`: neon sentiment gauge, confidence bands, heatmap-style conviction zones, chart overlays, scanner strip, and logic feed that make the market feel alive

## Key Visuals

- Neon `Market Sentiment` gauge blended with scanner strength
- Live scanner strip with `potential_score`, hot badges, and micro-sparklines
- Candle charts with `ENTRY`, `EXIT`, and ghost setup markers
- Confidence halos, full-width conviction bands, and curved trade bridges
- AI logic feed with confluence breakdown, risk flags, reasoning tags, and conviction sparkline
- Chart quick-switch dock with scanner awareness and header heartbeat watermark

## Core Capabilities

### Market Hunter

- Scans a broad symbol universe and promotes the strongest opportunities into an active watchlist
- Keeps `BTCUSDT` and `ETHUSDT` fixed while rotating the remaining active slots
- Uses `potential_score`, volatility, and volume-spike context to surface action quickly
- Returns refresh and rotation metadata so the frontend can show urgency and countdown

### AI Decision Engine

- Scores setups with multi-indicator confluence instead of single-trigger entries
- Explains intent in natural language through `reason`, `message`, `logic_tags`, and `confluence_breakdown`
- Emits filled markers, rejected setups, and almost-trades so users can see what the AI liked and what it passed on
- Tracks confidence history so conviction direction is visible, not just the current snapshot

### Risk-First Design

- Spread, liquidity, and volatility-aware filters before execution
- Dynamic position sizing and confidence-aware risk controls
- Drawdown, exposure, and concentration protections across symbols and portfolio sleeves
- Strict trade gating plus optional `force_execution_override_enabled` for tightly controlled overrides

### Trust Layer

- Async backtesting with resumable job state
- Strategy comparison flows with verdict banners and delta chips
- Persistent job tracking with bounded history retention
- Frontend explanations that connect scanner, chart, and backtest surfaces into one story

## Technical Architecture

### Backend

- `FastAPI` application for trading, scanner, analytics, diagnostics, and backtest APIs
- `Redis` optional acceleration for cache/pubsub style workflows
- `CCXT` exchange integration with multi-exchange fallback
- Market-data service hardened for region restrictions and per-exchange retry isolation
- Async job layer for backtests with persistence and restart recovery

### Frontend

- `Flutter` app with custom painters for market charts, overlays, confidence bands, and micro-sparklines
- Scanner-aware Pulse dashboard
- Marker detail sheets with confluence bars, strategy tags, and risk alerts
- Lightweight production logging with network debug interceptors enabled only in debug builds

### Resilience

- Exchange fallback across `binance`, `kraken`, and `coinbase`
- Graceful handling for provider restrictions and authorization failures
- Rolling scanner caches and bounded historical buffers for Render-class memory budgets
- Backtest job retention pruning so long-running free-tier instances do not grow forever

## System Flow

```text
Market breadth scan
  -> active symbol rotation
  -> candle + order-book fetch
  -> confluence scoring and trade gating
  -> marker / sentiment / confidence interval payloads
  -> Flutter Pulse UI, chart overlays, logic feed, backtest review
```

## Project Structure

```text
backend/               FastAPI backend, services, routes, tests
flutter_app/           Flutter mobile terminal UI
cloud_functions/       Firebase / auxiliary serverless logic
deploy/                release manifests and deployment assets
infrastructure/        Helm, load-test, and infra support files
README.md              product and architecture overview
DEPLOYMENT.md          deployment guide
PRODUCTION_OPS.md      production handoff and smoke-check runbook
PRODUCTION_CHECKLIST.md preflight validation checklist
RUNTIME.md             runtime and environment notes
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Flutter

```bash
cd flutter_app
flutter pub get
flutter run
```

## Important Endpoints

- `GET /health`
- `GET /health/ready`
- `GET /v1/diag/exchange`
- `GET /v1/activity/live`
- `GET /v1/activity/readiness`
- `GET /v1/market/candles`
- `GET /v1/market/summary`
- `POST /v1/market/summary`
- `GET /v1/user/pnl`
- `POST /v1/backtest/run`
- `POST /v1/backtest/compare`

## Real Environment Variables

These names are backed by the current codebase and are the ones operators should care about first:

- `ENVIRONMENT`
- `LOG_LEVEL`
- `JSON_LOGS`
- `TRADING_MODE`
- `REDIS_URL`
- `AUTH_API_KEYS_JSON`
- `PRIMARY_EXCHANGE`
- `BACKUP_EXCHANGES`
- `MARKET_DATA_MODE`
- `MARKET_DATA_EXCHANGE_RETRY_SECONDS`
- `DEBUG_ROUTES_ENABLED`
- `SCANNER_FIXED_SYMBOLS`
- `SCANNER_ACTIVE_SYMBOL_LIMIT`
- `SCANNER_CANDIDATE_LIMIT`
- `SCANNER_REFRESH_MINUTES`
- `SCANNER_ROTATION_HOURS`
- `FORCE_EXECUTION_OVERRIDE_ENABLED`
- `BACKTEST_DATA_DIR`
- `BACKTEST_CHUNK_HOURS`
- `BACKTEST_JOB_HISTORY_LIMIT`
- `BACKTEST_RESUME_ENABLED`

See [PRODUCTION_OPS.md](PRODUCTION_OPS.md) for recommended values and operational notes.

## Deployment Notes

- `MARKET_DATA_MODE=auto` is the intended production default
- If Binance is blocked in a region, the backend should fall through to backup exchanges instead of stalling
- Debug diagnostics like `/v1/diag/exchange` are available when debug routes are enabled or when not running in `prod`
- Flutter production builds suppress verbose network logging by default

## Recommended Reading

- [PRODUCTION_OPS.md](PRODUCTION_OPS.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- [OPERATIONS.md](OPERATIONS.md)
- [RUNTIME.md](RUNTIME.md)

## Current Positioning

This repo is no longer just an API plus a chart shell. It is a full-stack trading terminal with:

- explainable AI reasoning
- scanner-driven market discovery
- institutional-style chart overlays
- async backtest trust tooling
- production-aware fallback and recovery behavior

If you want the shortest description for a pitch, use:

`Autonomous AI Trading Terminal with Institutional Logic and Real-time Market Hunting.`
