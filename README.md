# Autonomous AI Trading Terminal

Autonomous AI Trading Terminal with Institutional Logic and Real-time Market Hunting.

This project is a full-stack trading system that combines a FastAPI backend, a Flutter terminal UI, async backtesting, and a rotating market scanner into one production-oriented workflow. The goal is not just signal generation, but usable operator context: why the AI likes a setup, how risk is being constrained, and where the next opportunity is emerging across the market.

## The Hook

This terminal is built to feel like a live trading desk rather than a code demo.

- `Autonomous Market Hunting`: the system keeps scanning and rotating through a high-opportunity coin universe instead of waiting on a static watchlist
- `Institutional Logic`: entries are confluence-based, filtered, and explained in natural language so decisions are visible, not mysterious
- `Operator-Grade Visuals`: neon sentiment gauge, conviction heatmaps, chart markers, and AI logic feed make market state immediately legible

### Key Visuals

- Neon `Market Sentiment` gauge blended with scanner strength
- Live scanner strip with `potential_score`, hot badges, and micro-sparklines
- Candle charts with `ENTRY`, `EXIT`, and ghost setup markers
- Confidence halos, conviction bands, and curved trade bridges
- AI logic feed with confluence breakdown, risk flags, reasoning tags, and conviction sparkline
- Quick-switch chart dock with scanner awareness and heartbeat watermark

## Core Capabilities

### Market Hunter

The scanner behaves like a market hunter. It sweeps a broad candidate set, keeps core majors like `BTCUSDT` and `ETHUSDT` pinned, and auto-rotates the remaining active slots across the strongest opportunities. By ranking symbols through `potential_score`, volatility context, and volume expansion, the app stays focused on what is becoming tradeable now rather than what was interesting hours ago.

- Broad candidate scan with rotating active watchlist logic
- Top-opportunity surfacing with `potential_score`
- Fixed majors plus dynamic symbol rotation
- Refresh and countdown metadata for frontend urgency cues

### AI Decision Engine

The decision layer uses confluence instead of one-indicator triggers. Entries are shaped by multiple technical and contextual checks, then translated into operator-readable reasoning through `reason`, `message`, `logic_tags`, and `confluence_breakdown`. The result is an explainable signal engine that shows not just fills, but also rejections and near-misses.

- Multi-indicator confluence scoring
- Natural-language reasoning and logic tags
- Marker-level visibility into accepted and rejected setups
- Confidence history so direction and conviction can be tracked over time

### Risk-First Design

The system is intentionally conservative in how it thinks about execution. Spread filters, liquidity checks, volatility gating, and dynamic position sizing are used before a trade is allowed through. Risk controls remain first-class even when confidence is high, with guarded override behavior available only through explicit configuration.

- Spread, liquidity, and volatility-aware gating
- Dynamic position sizing
- Confidence-aware risk controls
- Exposure, drawdown, and concentration protections
- Optional `FORCE_EXECUTION_OVERRIDE_ENABLED` for tightly controlled interventions

### Trust Layer

- Async backtesting with resumable job state
- Strategy comparison flows with verdict banners and delta chips
- Persistent job tracking with bounded history retention
- Frontend storytelling that connects scanner, chart, and backtest surfaces
- Trigger-gated retraining with emergency win-rate watchdogs and batch-based sample accumulation
- Atomic model promotion with fallback bundles, audit trail snapshots, and guarded manual rollback controls
- Admin safety overrides including `AI Learning Freeze` and `Rollback to Stable`

## Technical Architecture

### Backend

The backend is a `FastAPI` service backed by optional `Redis` acceleration and `CCXT` exchange connectivity. It exposes trading, scanner, analytics, diagnostics, and backtest APIs while also handling multi-exchange fallback. If one provider is restricted or degraded, the market-data layer is designed to isolate that failure and continue through backup exchanges.

- `FastAPI` for API orchestration and async workflows
- `Redis` for cache and pubsub-style acceleration when available
- `CCXT` for exchange adapters and multi-exchange fallback
- Per-exchange retry isolation for restricted or failing providers
- Async backtest job persistence and restart recovery

### Frontend

The frontend is a `Flutter` terminal built around custom visual primitives rather than generic charts. `CustomPainter`-driven annotations render conviction bands, trade markers, heatmap-like overlays, and micro-sparklines so the operator can read both state and reasoning at a glance.

- `Flutter` dashboard for mobile-first terminal workflows
- `CustomPainter` overlays for advanced chart annotations
- Scanner-aware Pulse dashboard and logic feed
- Marker detail sheets with confluence bars, tags, and risk alerts
- Release-safe logging with debug interceptors disabled in production builds

### Resilience

The system is designed to stay stable even on lightweight infrastructure like Render Free Tier. Async jobs, rolling caches, bounded history retention, and data chunking keep memory pressure predictable while preserving enough historical context for backtests and UI continuity.

- Exchange fallback across `binance`, `kraken`, and `coinbase`
- Graceful handling for `403` and `451` provider failures
- Rolling scanner caches and bounded buffers for low-memory instances
- Backtest chunking and retention pruning for long-lived stability
- Free-tier friendly async recovery behavior
- Local SQLite training buffer fallback when Firestore is unavailable
- Rollback cooldowns to prevent immediate re-promotion after a manual safety intervention

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
- `GET /v1/monitoring/model-stability/concentration`
- `GET /v1/activity/live`
- `GET /v1/activity/readiness`
- `GET /v1/market/candles`
- `GET /v1/market/summary`
- `POST /v1/market/summary`
- `GET /v1/user/pnl`
- `POST /v1/backtest/run`
- `POST /v1/backtest/compare`
- `GET /v1/admin/model/state`
- `POST /v1/admin/model/rollback`
- `POST /v1/admin/model/freeze`

## Deployment And Ops

### Environment Variables Checklist

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
- `TRAINING_BUFFER_PATH`
- `RETRAIN_BATCH_SIZE`
- `RETRAIN_RECENT_TRADE_WINDOW`
- `RETRAIN_EMERGENCY_WIN_RATE_FLOOR`
- `RETRAIN_RECENT_VALIDATION_TRADES`
- `RETRAIN_MIN_ACCURACY_LIFT`
- `RETRAIN_HIGH_CONFIDENCE_THRESHOLD`
- `RETRAIN_HIGH_CONFIDENCE_LOSS_WEIGHT`
- `RETRAIN_MANUAL_ROLLBACK_COOLDOWN_HOURS`
- `BACKTEST_DATA_DIR`
- `BACKTEST_CHUNK_HOURS`
- `BACKTEST_JOB_HISTORY_LIMIT`
- `BACKTEST_RESUME_ENABLED`

See [PRODUCTION_OPS.md](PRODUCTION_OPS.md) for recommended values, deploy defaults, and smoke-check guidance.

### Monitoring

- `GET /v1/diag/exchange` verifies provider availability, fallback health, and restriction handling
- `GET /v1/user/pnl` validates user-scoped portfolio surfaces and catches stale ownership or auth issues early
- `GET /health` and `GET /health/ready` separate liveness from actual operator readiness
- `GET /v1/activity/readiness` helps confirm UI-facing state is populated after deploy
- `GET /v1/monitoring/model-stability/concentration` exposes AI state, fallback status, recent lift, and latest promotion notice
- `GET /v1/admin/model/state` gives elevated operators the active/fallback model pair plus rollback/freeze guard state

### Troubleshooting Notes

- `MARKET_DATA_MODE=auto` is the intended production default
- If Binance returns `451` due to region restriction, the backend should fall through to backup exchanges instead of stalling
- `FORCE_EXECUTION_OVERRIDE_ENABLED` should stay `false` outside tightly controlled operator scenarios
- Manual rollback starts a retraining cooldown window so the same unstable candidate is not re-promoted immediately
- `AI Learning Freeze` stops retraining but continues collecting fresh labeled samples for later review
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

If you want the shortest pitch line, use:

`Autonomous AI Trading Terminal with Institutional Logic and Real-time Market Hunting.`
