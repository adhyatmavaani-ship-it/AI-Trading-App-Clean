#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

usage() {
  cat <<'EOF'
Usage:
  scripts/k8s_post_deploy_smoke.sh <namespace> <deployment> <service> <token> [context]

Environment overrides:
  PYTHON_BIN             Python executable to use
  K8S_SMOKE_REMOTE_PORT  Service port to port-forward from (default: 80)
  K8S_SMOKE_TIMEOUT      Rollout and endpoint timeout in seconds (default: 180)
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 4 ]]; then
  usage
  exit $([[ $# -lt 4 ]] && echo 1 || echo 0)
fi

NAMESPACE="$1"
DEPLOYMENT="$2"
SERVICE="$3"
TOKEN="$4"
CONTEXT="${5:-}"
REMOTE_PORT="${K8S_SMOKE_REMOTE_PORT:-80}"
TIMEOUT_SECONDS="${K8S_SMOKE_TIMEOUT:-180}"

cd "$ROOT_DIR"
"$PYTHON_BIN" scripts/k8s_post_deploy_smoke.py \
  --namespace "$NAMESPACE" \
  --deployment "$DEPLOYMENT" \
  --service "$SERVICE" \
  --token "$TOKEN" \
  --remote-port "$REMOTE_PORT" \
  --timeout-seconds "$TIMEOUT_SECONDS" \
  --context "$CONTEXT"
