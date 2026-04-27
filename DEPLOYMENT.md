# Deployment Guide

This document covers rollout flow and environment-specific deployment steps.

For exact runtime versions, local setup, CI behavior, and beta preflight commands, use [RUNTIME.md](./RUNTIME.md).

## Deployment baseline

Use these supported versions everywhere:

- Python `3.11`
- Node.js `20`
- Flutter stable
- Redis `7+`

Before any deployment, run the repo preflight from the repo root:

- Bash: [`scripts/beta_preflight.sh`](./scripts/beta_preflight.sh)
- PowerShell: [`scripts/beta_preflight.ps1`](./scripts/beta_preflight.ps1)

## Local and beta expectations

Recommended beta defaults:

- `TRADING_MODE=paper`
- `ENVIRONMENT=staging` or `prod`
- `PRIMARY_EXCHANGE=binance`
- `BACKUP_EXCHANGES=["kraken","coinbase"]`
- `JSON_LOGS=true`
- real Redis
- Firestore configured
- authenticated API keys configured
- Cloud Functions secret `BACKEND_API_KEY` provisioned
- live trading protected behind allowlist or feature flag

Health and readiness probes:

- `/health/live`
- `/health/ready`

Realtime websocket endpoints:

- `/ws/signals`
- `/v1/ws/signals`

## Docker image

Build from `backend/`:

```bash
cd backend
docker build -t trading-backend:1.0.0 .
```

For Kubernetes deployments, promote and deploy immutable image digests from the release manifests in `deploy/releases/`.

Run locally against a reachable Redis instance:

```bash
docker run -it \
  -p 8000:8000 \
  -e ENVIRONMENT=local \
  -e TRADING_MODE=paper \
  -e PRIMARY_EXCHANGE=binance \
  -e BACKUP_EXCHANGES='["kraken","coinbase"]' \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  -e AUTH_API_KEYS_JSON='[{"api_key":"docker-token","user_id":"alice","key_id":"docker-key"}]' \
  trading-backend:1.0.0
```

For live exchange routing, provide credentials only for the exchanges you want enabled:

```bash
-e BINANCE_API_KEY=... \
-e BINANCE_API_SECRET=... \
-e KRAKEN_API_KEY=... \
-e KRAKEN_API_SECRET=... \
-e COINBASE_API_KEY=... \
-e COINBASE_API_SECRET=... \
-e COINBASE_API_PASSPHRASE=...
```

## Docker Compose

```bash
cd infrastructure/docker
docker-compose up --build
```

Verify:

```bash
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

## Helm and Kubernetes

Prerequisites:

- image published to your registry
- namespace created
- Redis available
- Firestore credentials and project configured
- API keys provisioned

Example deploy:

```bash
helm upgrade --install trading-backend infrastructure/helm \
  -f infrastructure/helm/values-prod.yaml \
  --namespace trading-prod \
  --create-namespace
```

The chart is wired for immutable image references and expects `image.repository` plus `image.digest`.
Staging and production workflows also verify a cosign signature for that digest before Helm deploy proceeds.
Those workflows now perform a 10% ingress-based canary rollout, monitor live metrics from the canary service, and only promote the digest to the stable deployment when the canary stays healthy.
The staging workflow also runs a chaos resilience suite after smoke validation to simulate exchange API failure, Redis disconnection, and websocket drop recovery before the rollout is treated as healthy.

Verify rollout:

```bash
kubectl rollout status deployment/trading-backend -n trading-prod --timeout=180s
kubectl get pods -n trading-prod
kubectl logs deployment/trading-backend -n trading-prod
```

Run post-deploy smoke validation:

```bash
python scripts/k8s_post_deploy_smoke.py \
  --namespace trading-prod \
  --deployment trading-backend \
  --service trading-backend \
  --token YOUR_DEPLOY_SMOKE_TOKEN
```

That smoke check validates:

- rollout completion
- `/health/live`
- `/health/ready`
- authenticated `GET /`
- authenticated websocket `ping/pong`

## GitHub Actions deploy smoke

There is also a manual workflow at [deploy-smoke.yml](./.github/workflows/deploy-smoke.yml).

It expects these GitHub secrets:

- `KUBECONFIG_B64`
- `DEPLOY_SMOKE_API_TOKEN`

Use it after a Helm rollout to run the same Kubernetes smoke check from GitHub Actions.

## Image signing and verification

Container images are signed with cosign and signatures are stored in the registry alongside the image digest.

Release flow:

1. publish image digest
2. run [sign-release-image.yml](./.github/workflows/sign-release-image.yml)
3. deploy with [deploy-staging.yml](./.github/workflows/deploy-staging.yml) or [deploy-production.yml](./.github/workflows/deploy-production.yml)

Deploy workflows verify the signature before Helm runs. Deployment fails closed when:

- the signature is missing
- the signature is invalid
- the signing identity does not match the release manifest policy

## Canary rollout policy

The Kubernetes/Helm deployment path uses a weighted NGINX ingress canary:

- stable deployment stays on the currently running digest
- canary deployment receives 10% of traffic
- canary metrics are scraped from the canary service

Promotion checks:

- API error rate
- trade success rate
- request latency

After promotion, the workflow keeps monitoring the stable rollout:

- Prometheus is queried for stable-rollout error rate, trade success rate, and latency
- Alertmanager is checked for active rollout degradation alerts
- Helm rolls back automatically to the previous stable revision when post-promotion degradation is detected

Deployment fails closed and rolls back automatically when:

- canary metrics breach the configured thresholds
- the canary does not become ready
- rollout commands fail
- post-promotion Prometheus checks breach the configured thresholds
- Alertmanager shows active rollout degradation alerts

## Cloud Run

Example:

```bash
gcloud run deploy trading-backend \
  --source=backend \
  --region=us-central1 \
  --platform=managed \
  --memory=1Gi \
  --cpu=1 \
  --timeout=60 \
  --max-instances=100 \
  --set-env-vars ENVIRONMENT=prod,TRADING_MODE=paper,PRIMARY_EXCHANGE=binance,BACKUP_EXCHANGES='["kraken","coinbase"]' \
  --service-account=trading-sa@my-project.iam.gserviceaccount.com
```

After deployment, verify:

```bash
curl https://YOUR_SERVICE_URL/health/live
curl https://YOUR_SERVICE_URL/health/ready
curl https://YOUR_SERVICE_URL/health
curl https://YOUR_SERVICE_URL/
```

## Render

The repo-level [render.yaml](./render.yaml) intentionally does not store live API keys or a fixed app version.

Configure these Render environment variables in the dashboard:

- `ENVIRONMENT`
- `TRADING_MODE`
- `REDIS_URL`
- `FIRESTORE_PROJECT_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `AUTH_API_KEYS_JSON` or Firestore-backed auth
- `PRIMARY_EXCHANGE`
- `BACKUP_EXCHANGES`
- exchange credentials for any enabled live adapter

Recommended Render defaults:

- `TRADING_MODE=paper`
- `PRIMARY_EXCHANGE=binance`
- `BACKUP_EXCHANGES=["kraken","coinbase"]`

After deploy, verify runtime metadata:

```bash
curl https://YOUR_RENDER_URL/health
curl https://YOUR_RENDER_URL/health/detailed
curl https://YOUR_RENDER_URL/
```

## Recommended rollout flow

1. Run beta preflight locally.
2. Merge only after CI is green.
3. Deploy with Helm or Cloud Run.
4. Run post-deploy smoke check.
5. Keep beta in paper mode by default.
6. Enable live execution only for allowlisted users.

## References

- [RUNTIME.md](./RUNTIME.md)
- [OPERATIONS.md](./OPERATIONS.md)
- [README.md](./README.md)
- [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md)
