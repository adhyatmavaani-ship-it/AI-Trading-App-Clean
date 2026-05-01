# Runtime and Deployment Guide

This guide is the reproducible source of truth for local development, CI, and beta deployments.

## Supported runtimes

- Python: `3.11`
- Node.js: `20`
- Flutter: stable channel
- Redis: `7+`

The repository pins Python with [`.python-version`](./.python-version) and Cloud Functions Node with [`cloud_functions/.nvmrc`](./cloud_functions/.nvmrc).

## Local backend setup

From the repo root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Create `backend/.env` from [`backend/.env.example`](./backend/.env.example). Minimum local paper-trading config:

```env
ENVIRONMENT=local
TRADING_MODE=paper
JSON_LOGS=false
REDIS_URL=redis://127.0.0.1:6379/0
AUTH_API_KEYS_JSON=[{"api_key":"local-dev-token","user_id":"alice","key_id":"local-key"}]
FIRESTORE_PROJECT_ID=
WEBSOCKET_LISTENER_ENABLED=true
```

## Local verification

Backend:

```bash
cd backend
python -m compileall app tests
python -m unittest discover -s tests -v
python ./scripts/process_smoke_check.py --token local-dev-token
```

Flutter:

```bash
cd flutter_app
flutter pub get
flutter analyze
```

Cloud Functions:

```bash
cd cloud_functions
npm ci
npm test
node --check index.js
```

## FastAPI process smoke check

[`backend/scripts/process_smoke_check.py`](./backend/scripts/process_smoke_check.py) boots the real FastAPI app with `uvicorn`, waits for `/health/live`, validates authenticated `GET /`, and completes an authenticated websocket ping/pong against `/ws/signals`.

It intentionally runs with:

- `TRADING_MODE=paper`
- `WEBSOCKET_LISTENER_ENABLED=false`
- an inline `AUTH_API_KEYS_JSON` seed
- a dummy local Redis URL

That makes the smoke test reproducible in CI and on developer machines without depending on Redis or Firestore availability.

Manual run:

```bash
cd backend
python ./scripts/process_smoke_check.py --token smoke-token
```

## CI contract

GitHub Actions runs:

1. backend dependency install on Python `3.11`
2. `python -m compileall app tests`
3. `python -m unittest discover -s tests -v`
4. `python -m unittest tests.test_app_boot -v`
5. `python ./scripts/process_smoke_check.py`
6. Flutter `flutter analyze`
7. Cloud Functions `npm test` and `node --check index.js`

The smoke step is the process-level guard for:

- FastAPI importability
- app startup/shutdown
- unauthenticated health access
- authenticated HTTP access
- authenticated websocket access

## API key provisioning

For local or staging operators, generate a key from the repo:

```powershell
cd backend
python scripts/generate_api_key.py --user-id alice --key-id alice-staging
```

Persist the hashed record directly to Firestore when the project is configured:

```powershell
cd backend
python scripts/generate_api_key.py --user-id alice --key-id alice-prod --expires-in-days 30 --persist-firestore
```

The script prints the plaintext `api_key` once, plus a `config_record` JSON snippet you can paste into `AUTH_API_KEYS_JSON` when you are not persisting through Firestore.

## Beta deployment profile

Recommended beta defaults:

- `TRADING_MODE=paper`
- `ENVIRONMENT=staging` or `prod`
- `JSON_LOGS=true`
- real Redis
- Firestore configured
- API keys provisioned through config or Firestore
- Cloud Functions secret `BACKEND_API_KEY` provisioned
- real-money execution behind allowlist or feature flag

Minimum beta preflight:

```bash
cd backend
python -m unittest discover -s tests -v
python ./scripts/process_smoke_check.py --token beta-smoke-token
```

```bash
cd flutter_app
flutter analyze
```

```bash
cd cloud_functions
npm test
```

## Runtime notes

- Use Python `3.11` locally to match CI.
- Keep `WEBSOCKET_LISTENER_ENABLED=true` in normal app environments. Set it to `false` only for isolated smoke/process checks.
- Health probes should target:
  - `/health/live`
  - `/health/ready`
- Websocket clients should use:
  - `/ws/signals`
  - `/v1/ws/signals`

## Deployment docs

- [README](./README.md)
- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [OPERATIONS.md](./OPERATIONS.md)
- [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md)
