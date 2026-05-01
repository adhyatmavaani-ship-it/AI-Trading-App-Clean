# Production Checklist

This checklist is repo-specific. Use it before calling the system production-ready for public or real-money use.

## Current Verdict

- Status: not production-ready for live market launch
- Safe status today: internal demo, paper trading, controlled beta
- Default production stance: `TRADING_MODE=paper`

## Hard Blockers

- [ ] Confirm the production entrypoint and keep deploy/runtime aligned.
  The hosted app currently starts `backend/app/main.py`. Any new backend flow added outside that path must be intentionally integrated or excluded from launch scope.
- [ ] Remove repo-tracked runtime databases and local state from release artifacts.
  Local files like `trades.db` and ad hoc sqlite buffers must not be the authoritative production record.
- [ ] Set production auth explicitly.
  `AUTH_API_KEYS_JSON` or Firestore-backed auth must be configured before public access.
- [ ] Restrict CORS in production.
  `CORS_ALLOWED_ORIGINS` cannot be `*` in `prod`.
- [ ] Keep `FORCE_EXECUTION_OVERRIDE_ENABLED=false` in production.
- [ ] If `TRADING_MODE=live`, provide real exchange credentials and test them in staging first.
- [ ] Prove end-to-end paper flow in a hosted environment.
  Required path: auth -> evaluate -> execute -> monitor -> close -> PnL -> UI surfaces.

## Required Hosted Validation

- [ ] `GET /health`
- [ ] `GET /health/live`
- [ ] `GET /health/ready`
- [ ] `GET /v1/diag/exchange`
- [ ] `GET /v1/market/summary`
- [ ] `GET /v1/market/candles?symbol=BTCUSDT`
- [ ] `GET /v1/activity/live`
- [ ] `GET /v1/activity/readiness`
- [ ] `GET /v1/user/pnl`
- [ ] `POST /v1/backtest/run`
- [ ] `GET /v1/admin/model/state`

## Risk Controls That Must Be Verified Manually

- [ ] Max daily loss blocks further execution
- [ ] Consecutive-loss stop engages after threshold breach
- [ ] Drawdown protection reduces or pauses risk
- [ ] Kill switch blocks execution immediately
- [ ] Rejected trades are logged with reason
- [ ] Approved trades are persisted with user attribution

## Persistence And Recovery

- [ ] Decide the production system of record for trades, executions, and audit history
- [ ] Confirm backup and restore procedure
- [ ] Confirm restart recovery for active trades and background jobs
- [ ] Confirm Render/hosted filesystem is not treated as durable storage

## Release Gate

Do not enable live trading until all items below are true:

- [ ] runtime safety tests pass
- [ ] route auth and execution tests pass
- [ ] hosted smoke test passes
- [ ] staging paper-trading cycle passes
- [ ] operator rollback and freeze controls are validated
- [ ] exchange fallback behavior is validated under failure
