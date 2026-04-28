# Admin Safety Manual

This document is the operator quick-reference for manual model controls.

## Guarded Endpoints

- `GET /v1/admin/model/state`
- `POST /v1/admin/model/rollback`
- `POST /v1/admin/model/freeze?enabled=true|false`

These routes require elevated credentials that can execute for other users.

## When To Roll Back

- the latest promoted model shows unstable live behavior
- AI state indicates degraded decisions after a promotion
- a black-swan event makes the new model's recent learning unreliable

Rollback behavior:

- swaps the active probability model to the fallback bundle
- updates monitoring payloads to show the restored active version
- writes a manual rollback audit event
- starts a retraining cooldown, default `48` hours

## When To Freeze Learning

- market conditions are disorderly and labels are likely noisy
- you want to keep collecting samples without adapting yet
- you have triggered a manual rollback and want a hard pause

Freeze behavior:

- blocks retraining triggers
- keeps snapshot and outcome collection running
- can be removed later without losing buffered samples

## Operator Check

Before rollback:

- inspect active and fallback versions from `GET /v1/admin/model/state`
- review recent accuracy lift and summary
- confirm fallback is a known stable bundle

After rollback:

- confirm `GET /v1/monitoring/model-stability/concentration`
- confirm cooldown is active
- confirm the Flutter AI State panel reflects the rollback
