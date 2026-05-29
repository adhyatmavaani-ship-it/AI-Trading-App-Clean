#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-quentrader}"
APP_USER="${APP_USER:-quentrader}"
APP_DIR="${APP_DIR:-/opt/quentrader}"
ENV_DIR="${ENV_DIR:-/etc/quentrader}"
LOG_DIR="${LOG_DIR:-/var/log/quentrader}"
DOMAIN="${DOMAIN:-quentrader.com}"
BIND_HOST="${BIND_HOST:-127.0.0.1}"
BIND_PORT="${BIND_PORT:-8000}"
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root: sudo bash deploy/install.sh" >&2
    exit 1
  fi
}

detect_entrypoint() {
  local root="$1"
  if [[ -f "${root}/render.yaml" ]] && grep -Eq "startCommand:.*app\.main:app" "${root}/render.yaml"; then
    echo "app.main:app"
    return
  fi
  if [[ -f "${root}/backend/app/main.py" ]] && grep -q "app = FastAPI" "${root}/backend/app/main.py"; then
    echo "app.main:app"
    return
  fi
  if [[ -f "${root}/backend/main.py" ]] && grep -q "app = FastAPI" "${root}/backend/main.py"; then
    echo "main:app"
    return
  fi
  echo "Unable to detect FastAPI entrypoint" >&2
  exit 1
}

copy_release() {
  mkdir -p "${APP_DIR}"
  if [[ -n "${REPO_URL}" && ! -d "${APP_DIR}/.git" ]]; then
    git clone --branch "${REPO_BRANCH}" --depth 1 "${REPO_URL}" "${APP_DIR}"
    return
  fi
  if [[ -d "${APP_DIR}/.git" && -n "${REPO_URL}" ]]; then
    git -C "${APP_DIR}" fetch --depth 1 origin "${REPO_BRANCH}"
    git -C "${APP_DIR}" checkout "${REPO_BRANCH}"
    git -C "${APP_DIR}" reset --hard "origin/${REPO_BRANCH}"
    return
  fi
  if [[ -f "${PACKAGE_ROOT}/backend/app/main.py" || -f "${PACKAGE_ROOT}/backend/main.py" ]]; then
    if [[ "$(readlink -f "${PACKAGE_ROOT}")" == "$(readlink -f "${APP_DIR}")" ]]; then
      return
    fi
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
    return
  fi
  if [[ -f "${APP_DIR}/backend/app/main.py" || -f "${APP_DIR}/backend/main.py" ]]; then
    return
  fi
  echo "No repository content found. Upload the repo or set REPO_URL before running." >&2
  exit 1
}

write_logrotate() {
  cat > "/etc/logrotate.d/${APP_NAME}" <<EOF
${LOG_DIR}/*.log {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    create 0640 ${APP_USER} ${APP_USER}
}
EOF
}

wait_for_health() {
  local url_ready="http://${BIND_HOST}:${BIND_PORT}/health/ready"
  local url_health="http://${BIND_HOST}:${BIND_PORT}/health"
  for _ in $(seq 1 30); do
    if curl -fsS "${url_ready}" >/dev/null || curl -fsS "${url_health}" >/dev/null; then
      echo "Health check passed: ${url_ready} or ${url_health}"
      return
    fi
    sleep 2
  done
  echo "Health check failed. Recent service logs:" >&2
  journalctl -u "${APP_NAME}" -n 80 --no-pager >&2 || true
  exit 1
}

stop_legacy_services() {
  for legacy_service in ai-trading-backend.service ai-trading-healthcheck.service; do
    if systemctl list-unit-files "${legacy_service}" >/dev/null 2>&1; then
      systemctl stop "${legacy_service}" >/dev/null 2>&1 || true
      systemctl disable "${legacy_service}" >/dev/null 2>&1 || true
    fi
  done
}

require_root
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 \
  python3-venv \
  python3-pip \
  nginx \
  curl \
  rsync \
  git \
  logrotate

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --home-dir "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

git config --global --add safe.directory "${APP_DIR}" >/dev/null 2>&1 || true
copy_release
ENTRYPOINT="$(detect_entrypoint "${APP_DIR}")"

mkdir -p "${ENV_DIR}" "${LOG_DIR}" "${APP_DIR}/backend/app_data" "${APP_DIR}/backend/artifacts"
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" "${LOG_DIR}"
chmod 0750 "${ENV_DIR}" "${LOG_DIR}"
git config --global --add safe.directory "${APP_DIR}" >/dev/null 2>&1 || true

python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip wheel
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt" gunicorn

if [[ ! -f "${ENV_DIR}/${APP_NAME}.env" ]]; then
  cp "${APP_DIR}/deploy/env.example" "${ENV_DIR}/${APP_NAME}.env"
  sed -i "s#^PUBLIC_BASE_URL=.*#PUBLIC_BASE_URL=https://${DOMAIN}#" "${ENV_DIR}/${APP_NAME}.env"
  sed -i "s#^CORS_ALLOWED_ORIGINS=.*#CORS_ALLOWED_ORIGINS='[\"https://${DOMAIN}\",\"https://www.${DOMAIN}\",\"https://srv1664694.hstgr.cloud\"]'#" "${ENV_DIR}/${APP_NAME}.env"
fi
chown root:"${APP_USER}" "${ENV_DIR}/${APP_NAME}.env"
chmod 0640 "${ENV_DIR}/${APP_NAME}.env"

if grep -Eq "^AUTH_API_KEYS_JSON=('\\[\\]'|\\[\\])$" "${ENV_DIR}/${APP_NAME}.env"; then
  INITIAL_API_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
  sed -i "s#^AUTH_API_KEYS_JSON=.*#AUTH_API_KEYS_JSON='[\"${INITIAL_API_KEY}\"]'#" "${ENV_DIR}/${APP_NAME}.env"
  echo "Generated initial API key in ${ENV_DIR}/${APP_NAME}.env; rotate it after first login."
fi

install -m 0644 "${APP_DIR}/deploy/quentrader.service" "/etc/systemd/system/${APP_NAME}.service"
sed -i "s#app.main:app#${ENTRYPOINT}#g" "/etc/systemd/system/${APP_NAME}.service"
install -m 0644 "${APP_DIR}/deploy/nginx.conf" "/etc/nginx/sites-available/${APP_NAME}"
sed -i "s#quentrader.com#${DOMAIN}#g" "/etc/nginx/sites-available/${APP_NAME}"
ln -sfn "/etc/nginx/sites-available/${APP_NAME}" "/etc/nginx/sites-enabled/${APP_NAME}"
rm -f /etc/nginx/sites-enabled/default
write_logrotate

nginx -t
systemctl daemon-reload
stop_legacy_services
systemctl enable "${APP_NAME}"
systemctl restart "${APP_NAME}"
systemctl reload nginx
wait_for_health

cat <<EOF

${APP_NAME} deployment complete.
Entrypoint: ${ENTRYPOINT}
Exact start command: sudo systemctl start ${APP_NAME}
Health check: curl -fsS http://${BIND_HOST}:${BIND_PORT}/health/ready

Optional HTTPS step after DNS points to this VPS:
  sudo apt-get install -y certbot python3-certbot-nginx
  sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}
EOF
