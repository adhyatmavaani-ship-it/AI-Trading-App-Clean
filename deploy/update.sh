#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-quentrader}"
APP_USER="${APP_USER:-quentrader}"
APP_DIR="${APP_DIR:-/opt/quentrader}"
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
REPO_BRANCH="${REPO_BRANCH:-main}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash deploy/update.sh" >&2
  exit 1
fi

git config --global --add safe.directory "${APP_DIR}" >/dev/null 2>&1 || true

if [[ -d "${APP_DIR}/.git" ]]; then
  git -C "${APP_DIR}" fetch --depth 1 origin "${REPO_BRANCH}"
  git -C "${APP_DIR}" checkout "${REPO_BRANCH}"
  git -C "${APP_DIR}" reset --hard "origin/${REPO_BRANCH}"
elif [[ -f "${PACKAGE_ROOT}/backend/app/main.py" || -f "${PACKAGE_ROOT}/backend/main.py" ]]; then
  if [[ "$(readlink -f "${PACKAGE_ROOT}")" != "$(readlink -f "${APP_DIR}")" ]]; then
    rsync -a --delete \
      --exclude ".git" \
      --exclude ".venv" \
      --exclude "backend/.venv" \
      --exclude "__pycache__" \
      --exclude ".pytest_cache" \
      --exclude "*.pyc" \
      --exclude "logs" \
      --exclude "deploy/releases" \
      "${PACKAGE_ROOT}/" "${APP_DIR}/"
  fi
else
  echo "No update source found. Run from an uploaded repo root or deploy a git checkout in ${APP_DIR}." >&2
  exit 1
fi

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" /var/log/quentrader
"${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt" gunicorn

(
  cd "${APP_DIR}/backend"
  "${APP_DIR}/.venv/bin/python" -m compileall -q app db api engine services models utils main.py
)

systemctl restart "${APP_NAME}"

for _ in $(seq 1 30); do
  if curl -fsS "http://${BIND_HOST}:${BIND_PORT}/health/ready" >/dev/null || curl -fsS "http://${BIND_HOST}:${BIND_PORT}/health" >/dev/null; then
    echo "Update complete. Health check passed."
    exit 0
  fi
  sleep 2
done

echo "Update health check failed. Recent service logs:" >&2
journalctl -u "${APP_NAME}" -n 80 --no-pager >&2 || true
exit 1
