# Production Ops Runbook

This document is the production handoff for operating the AI trading terminal on Render-class infrastructure and similar lightweight environments.

## What This Covers

- required environment variables
- startup expectations
- smoke-check flow after deploy
- fallback verification
- backtest stability checks
- troubleshooting for provider restrictions and degraded readiness

## Deployment Intent

Recommended operating stance:

- `TRADING_MODE=paper` by default until live users are explicitly allowlisted
- `MARKET_DATA_MODE=auto` so the backend can use exchange data when available and degrade gracefully when a provider is restricted
- `JSON_LOGS=true` in hosted environments
- `ENVIRONMENT=prod` for actual production deploys

## Environment Variables

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

the market-data layer now retries per exchange, so a failed Binance attempt should not stop Kraken or Coinbase from coming online.

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

job persistence is enabled and persisted history is pruned to a bounded limit, which is especially important on low-memory instances.

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

## Operator Summary

If you want the shortest possible deploy checklist, use this:

1. deploy with `MARKET_DATA_MODE=auto`
2. confirm `GET /health/ready`
3. confirm `GET /v1/diag/exchange`
4. run one summary request and one candles request
5. run one 7-day async backtest
6. verify Flutter release build against production URL

## Related Docs

- [README.md](README.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- [OPERATIONS.md](OPERATIONS.md)
- [RUNTIME.md](RUNTIME.md)
