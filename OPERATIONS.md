# Operator Runbook

This runbook is the practical reference for release operators using GitHub Actions and Kubernetes smoke checks.

## Environment protection

Configure GitHub Environments in repository settings:

- `staging`
- `production`

Recommended protection rules:

- required reviewers on `production`
- optional reviewers on `staging`
- environment-scoped secrets instead of broad repo secrets where possible

The deploy workflows bind directly to these environments, so approval gates are enforced by GitHub settings rather than by ad hoc workflow inputs.

### Deploy smoke workflow

The manual deploy smoke workflow at [deploy-smoke.yml](./.github/workflows/deploy-smoke.yml) requires:

- `KUBECONFIG_B64`
  - Base64-encoded kubeconfig with access to the target cluster and namespace
- `DEPLOY_SMOKE_API_TOKEN`
  - A valid backend API token accepted by the deployed environment

### Deploy staging and deploy production workflows

The staged deployment workflows at [deploy-staging.yml](./.github/workflows/deploy-staging.yml) and [deploy-production.yml](./.github/workflows/deploy-production.yml) require the same secrets:

- `KUBECONFIG_B64`
- `DEPLOY_SMOKE_API_TOKEN`

It assumes the image digest you deploy is already published, signed with cosign, and pullable by the cluster.
It also assumes Prometheus and Alertmanager are reachable through the Kubernetes service names configured in the Helm values file.

### Sign release image workflow

The signing workflow at [sign-release-image.yml](./.github/workflows/sign-release-image.yml) requires:

- GitHub OIDC enabled for Actions
- optional registry credentials for private registries:
  - `REGISTRY_USERNAME`
  - `REGISTRY_PASSWORD`

It signs the manifest-pinned image digest with cosign and stores the signature in the registry.

## Manual workflow inputs

### `Deploy Smoke`

Sample `workflow_dispatch` inputs:

```text
environment_name: staging
namespace: trading-staging
deployment: trading-backend
service: trading-backend
context: staging-cluster
```

Use this after a rollout when you want post-deploy validation without redeploying.

### `Deploy Staging`

Sample `workflow_dispatch` inputs:

```text
release_manifest: deploy/releases/staging.json
```

Use this when you want GitHub Actions to:

1. validate release and trading-risk configuration
2. verify the cosign signature before deployment
3. deploy a 10% canary
4. monitor error rate, trade success rate, and latency
5. auto-promote on healthy metrics or auto-rollback on failure
6. run post-deploy smoke validation
7. run the staging chaos resilience suite for exchange failure, Redis disconnect, and websocket drop scenarios
8. monitor the promoted stable rollout through Prometheus and Alertmanager
9. rollback automatically to the previous stable Helm revision if post-promotion degradation appears

### `Deploy Production`

Sample `workflow_dispatch` inputs:

```text
release_manifest: deploy/releases/production.json
```

This workflow is intended to run behind the protected `production` GitHub environment.

### `Sign Release Image`

Sample `workflow_dispatch` inputs:

```text
release_manifest: deploy/releases/staging.json
```

Use this before staging or production deploys when a new immutable image digest is introduced into a release manifest.

## Release promotion

Artifact promotion is manifest-driven. Instead of typing an image reference into a deployment workflow, update the production manifest from the staging manifest explicitly:

```bash
python scripts/release_manifest.py promote \
  --source deploy/releases/staging.json \
  --target deploy/releases/production.json
```

That copies the staged image repository/digest into the production manifest and records promotion metadata.

Typical flow:

1. update `deploy/releases/staging.json` with the release candidate image
2. run `Sign Release Image`
3. run `Deploy Staging` and let the canary gate promote or rollback automatically
4. validate staging
5. run `release_manifest.py promote`
6. review/commit the manifest change
7. run `Deploy Production` and let the production canary gate promote or rollback automatically
8. let the post-promotion monitor finish before treating the rollout as complete

## Local operator commands

### Beta preflight

Bash:

```bash
./scripts/beta_preflight.sh
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\beta_preflight.ps1
```

### Post-deploy Kubernetes smoke

Bash:

```bash
./scripts/k8s_post_deploy_smoke.sh trading-prod trading-backend trading-backend YOUR_TOKEN prod-cluster
```

PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\k8s_post_deploy_smoke.ps1 `
  -Namespace trading-prod `
  -Deployment trading-backend `
  -Service trading-backend `
  -Token YOUR_TOKEN `
  -Context prod-cluster
```

Optional environment variables:

- `PYTHON_BIN`
- `K8S_SMOKE_REMOTE_PORT`
- `K8S_SMOKE_TIMEOUT`

## Recommended release flow

1. Run local beta preflight.
2. Ensure CI is green.
3. Sign the staging digest from `deploy/releases/staging.json`.
4. Deploy staging from `deploy/releases/staging.json`.
5. Confirm canary metrics stayed healthy and the rollout promoted cleanly.
6. Promote the staging artifact into `deploy/releases/production.json`.
7. Deploy production from the promoted manifest.
8. Wait for the post-promotion monitor to complete cleanly.
9. Run deploy smoke if rollout happened outside the staged workflows.
10. Keep beta in `paper` mode by default.
11. Enable live trading only for allowlisted users.

## References

- [RUNTIME.md](./RUNTIME.md)
- [DEPLOYMENT.md](./DEPLOYMENT.md)
- [PRODUCTION_CHECKLIST.md](./PRODUCTION_CHECKLIST.md)
