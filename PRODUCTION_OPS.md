# Production Ops Runbook

This document is the production handoff for operating the AI trading terminal on Render-class infrastructure and similar lightweight environments. It is written as an operator-focused companion to the product-facing [README.md](README.md): what must be configured, what must be checked after deploy, and how the system is expected to behave when exchanges or infrastructure degrade.

## Deployment Intent

Recommended operating stance:

- `TRADING_MODE=paper` by default until live users are explicitly allowlisted
- `MARKET_DATA_MODE=auto` so exchange data is used when available and fallback stays active when a provider is restricted
- `JSON_LOGS=true` in hosted environments
- `ENVIRONMENT=prod` for real production deploys
- `FORCE_EXECUTION_OVERRIDE_ENABLED=false` unless a human operator has a tightly controlled reason to enable it

## Environment Variables Checklist

### Core Runtime

- `ENVIRONMENT=prod`
- `LOG_LEVEL=INFO`
- `JSON_LOGS=true`
- `TRADING_MODE=paper`
- `REDIS_URL=...`
- `AUTH_API_KEYS_JSON=[{"api_key":"...","user_id":"...","key_id":"..."}]`

### Exchange and Market Data

- `PRIMARY_EXCHANGE=binance`
- `BACKUP_EXCHANGES=["kraken","coinbase"]`
- `MARKET_DATA_MODE=auto`
- `MARKET_DATA_EXCHANGE_RETRY_SECONDS=30`
- `BINANCE_API_KEY=...`
- `BINANCE_API_SECRET=...`
- `KRAKEN_API_KEY=...`
- `KRAKEN_API_SECRET=...`
- `COINBASE_API_KEY=...`
- `COINBASE_API_SECRET=...`
- `COINBASE_API_PASSPHRASE=...`

### Scanner and UX

- `SCANNER_FIXED_SYMBOLS=["BTCUSDT","ETHUSDT"]`
- `SCANNER_CANDIDATE_LIMIT=50`
- `SCANNER_ACTIVE_SYMBOL_LIMIT=10`
- `SCANNER_REFRESH_MINUTES=15`
- `SCANNER_ROTATION_HOURS=4`
- `USER_EXPERIENCE_MODE=high`

### Risk and Execution

- `FORCE_EXECUTION_OVERRIDE_ENABLED=false`
- `MAX_ACTIVE_TRADES=2`
- `STRICT_TRADE_CONFIDENCE_FLOOR=0.70`
- `STRICT_TRADE_SCORE_THRESHOLD=70`

### Backtest and Persistence

- `BACKTEST_DATA_DIR=backtest_data`
- `BACKTEST_CHUNK_HOURS=24`
- `BACKTEST_JOB_HISTORY_LIMIT=200`
- `BACKTEST_RESUME_ENABLED=true`
- `BACKTEST_HEARTBEAT_SECONDS=5`

### Adaptive Learning And Safety

- `TRAINING_BUFFER_PATH=artifacts/training_buffer.sqlite3`
- `RETRAIN_BATCH_SIZE=50`
- `RETRAIN_RECENT_TRADE_WINDOW=10`
- `RETRAIN_EMERGENCY_WIN_RATE_FLOOR=0.40`
- `RETRAIN_RECENT_VALIDATION_TRADES=10`
- `RETRAIN_MIN_ACCURACY_LIFT=0.05`
- `RETRAIN_HIGH_CONFIDENCE_THRESHOLD=0.75`
- `RETRAIN_HIGH_CONFIDENCE_LOSS_WEIGHT=2.0`
- `RETRAIN_MANUAL_ROLLBACK_COOLDOWN_HOURS=48`

## Why These Matter

- `MARKET_DATA_MODE=auto` allows the platform to keep functioning when a preferred exchange is blocked or degraded
- `BACKUP_EXCHANGES` is critical for surviving region restrictions and partial provider outages
- `FORCE_EXECUTION_OVERRIDE_ENABLED` should remain off in normal operations because it weakens the system's default risk gate
- `BACKTEST_CHUNK_HOURS` and `BACKTEST_JOB_HISTORY_LIMIT` are the main levers for keeping free-tier memory and disk usage stable
- `TRAINING_BUFFER_PATH` keeps labeled retraining samples durable even when Firestore writes are unavailable
- `RETRAIN_BATCH_SIZE` and `RETRAIN_RECENT_TRADE_WINDOW` decide whether learning is routine or emergency-driven
- `RETRAIN_MANUAL_ROLLBACK_COOLDOWN_HOURS` protects operators from immediate re-promotion after a manual rollback

## Warm-Up Expectations

On Render-style cold starts, the first few requests may include:

- process spin-up
- exchange adapter initialization
- scanner cache warm-up
- market summary or candle cache population

Expected post-deploy check:

1. hit `GET /health`
2. hit `GET /health/ready`
3. hit `GET /v1/diag/exchange`
4. hit `GET /v1/market/summary`
5. hit `GET /v1/market/candles?symbol=BTCUSDT`

Capture the first 2-3 request latencies so you know the real cold-start readiness window.

## Post-Deploy Smoke Check

### 1. Health

- `GET /health`
- `GET /health/ready`

Success signal:

- process responds
- readiness is not blocked on a dead market-data loop

### 2. Exchange Fallback

- `GET /v1/diag/exchange`

What to confirm:

- market-data diagnostics load successfully
- if Binance is region-blocked, backup exchanges still initialize
- service is not stuck waiting for one failed provider retry window

Why this matters:

The market-data layer retries per exchange, so a failed Binance attempt should not stop Kraken or Coinbase from coming online.

### 3. Summary + Candles

- `GET /v1/market/summary`
- `POST /v1/market/summary`
- `GET /v1/market/candles`

What to confirm:

- scanner payload includes active symbols and countdown fields
- candles include markers, conviction intervals, and confidence history
- response times settle after warm-up

### 4. PnL and User Surfaces

- `GET /v1/user/pnl`
- `GET /v1/activity/live`
- `GET /v1/activity/readiness`

What to confirm:

- PnL route resolves without stale-user leakage
- activity and readiness payloads are populated
- logic feed and frontend chips have usable data

### 5. Backtest Stress

Run a short async backtest, ideally 7 days.

Suggested checks:

- create a job through the async backtest route
- poll status until completion
- export CSV if needed
- verify memory remains stable during execution
- verify completed job is still resumable or restorable after restart

Why this matters:

Job persistence is enabled and persisted history is pruned to a bounded limit, which is especially important on low-memory instances.

### 6. Admin Safety Controls

- `GET /v1/admin/model/state`
- `POST /v1/admin/model/rollback`
- `POST /v1/admin/model/freeze`

What to confirm:

- active and fallback model versions are visible to the operator
- rollback immediately changes the active model version in monitoring payloads
- manual rollback starts cooldown protection for auto-retraining
- freeze mode sets `learning_frozen` behavior without stopping sample collection

Why this matters:

these controls are the human-in-the-loop override layer for black-swan conditions, bad live promotions, or operator-directed pauses in adaptation.

## Monitoring

The most useful operator endpoints are:

- `GET /health` for process liveness
- `GET /health/ready` for service readiness
- `GET /v1/diag/exchange` for exchange status and fallback validation
- `GET /v1/user/pnl` for user-scoped PnL surface health
- `GET /v1/activity/readiness` for UI-facing readiness state
- `GET /v1/monitoring/model-stability/concentration` for AI state, fallback mode, and latest promotion details
- `GET /v1/admin/model/state` for guarded operator review before rollback or freeze actions

Suggested habit:

Capture these checks after every deploy and after any exchange-related incident so you can compare warm, degraded, and recovered states.

## Flutter Production Verification

Point the Flutter app to the production base URL and verify:

- scanner strip updates without lag
- market sentiment gauge updates cleanly
- logic feed renders confluence and risk chips
- chart markers, confidence bands, and ambient glow stay in sync
- hot badges, heartbeat watermark, and quick-switch dock feel responsive

Important behavior:

- verbose network logging should not appear in release mode
- `403` and `451` responses should surface as readable failures instead of opaque transport errors

## Troubleshooting

### `451` or region restriction from Binance

Meaning:

- provider is blocked by region or legal restriction

What to do:

1. confirm with `GET /v1/diag/exchange`
2. verify `BACKUP_EXCHANGES` includes working providers
3. keep `MARKET_DATA_MODE=auto`
4. confirm backup exchange credentials are valid if required

Expected app behavior:

- backend should continue through fallback providers
- frontend should show a readable restriction message rather than raw failure noise

### `403` failures

Meaning:

- auth or permission issue

What to do:

1. verify `AUTH_API_KEYS_JSON`
2. confirm the request is sending `X-API-Key` or bearer token
3. confirm user-specific resources are being accessed by the right owner

### Readiness stays degraded

What to inspect:

- `GET /health/ready`
- `GET /v1/diag/exchange`
- Render logs for repeated exchange failures
- Redis connectivity if configured

### Backtest storage drift

What to inspect:

- contents of `BACKTEST_DATA_DIR/jobs`
- whether `BACKTEST_JOB_HISTORY_LIMIT` is too high for the instance size

Expected behavior:

- old persisted job files should be pruned automatically

### Manual rollback was triggered

What to inspect:

- `GET /v1/admin/model/state`
- `GET /v1/monitoring/model-stability/concentration`
- latest event in `artifacts/model_registry.json`

Expected behavior:

- active model changes to the previous stable fallback
- rollback cooldown remains active for the configured window, default `48` hours
- latest AI state notice reflects manual rollback

### Learning freeze is enabled

Meaning:

- retraining is intentionally blocked by an elevated operator

What to do:

1. confirm freeze status in `GET /v1/admin/model/state`
2. verify samples are still entering the training buffer
3. clear freeze only after the market regime is considered stable enough for learning again

## Operator Summary

If you want the shortest possible deploy checklist, use this:

1. deploy with `MARKET_DATA_MODE=auto`
2. confirm `GET /health/ready`
3. confirm `GET /v1/diag/exchange`
4. run one summary request and one candles request
5. run one 7-day async backtest
6. verify AI state and admin safety endpoints
7. verify Flutter release build against production URL

## Related Docs

- [README.md](README.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- [OPERATIONS.md](OPERATIONS.md)
- [RUNTIME.md](RUNTIME.md)
