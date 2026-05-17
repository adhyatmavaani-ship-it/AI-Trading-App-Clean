#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="ai-trading-backend"
PUBLIC_HOST="${PUBLIC_HOST:-69.62.74.7}"
APP_HOME="${1:-/root/AI-Trading-App-Clean/backend}"
VENV_DIR="$APP_HOME/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"
NGINX_SITE="/etc/nginx/sites-available/ai-trading-backend"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root from the Hostinger VPS console." >&2
    exit 1
  fi
}

verify_app_home() {
  if [[ ! -d "$APP_HOME" ]]; then
    echo "Backend directory not found: $APP_HOME" >&2
    exit 1
  fi
  if [[ ! -f "$APP_HOME/app/main.py" ]]; then
    echo "Production entrypoint missing: $APP_HOME/app/main.py" >&2
    exit 1
  fi
  if [[ ! -f "$APP_HOME/requirements.txt" ]]; then
    echo "requirements.txt missing: $APP_HOME/requirements.txt" >&2
    exit 1
  fi
}

install_packages() {
  log "Installing OS packages"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    curl \
    nginx \
    python3-venv \
    ufw
}

install_backend() {
  if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating Python virtualenv"
    python3 -m venv "$VENV_DIR"
  fi

  log "Installing backend dependencies"
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$APP_HOME/requirements.txt"
}

write_systemd_service() {
  log "Writing backend systemd service"
  cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=AI Trading FastAPI Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$APP_HOME
Environment=PYTHONUNBUFFERED=1
Environment=ENVIRONMENT=prod
Environment=PORT=8000
ExecStart=$UVICORN_BIN app.main:app --host 127.0.0.1 --port 8000 --no-access-log --log-level warning
Restart=always
RestartSec=5
TimeoutStartSec=60
KillMode=control-group
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
}

write_nginx_proxy() {
  log "Writing Nginx port 80 reverse proxy"
  cat >"$NGINX_SITE" <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    client_max_body_size 10m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 90s;
        proxy_send_timeout 90s;
    }
}
EOF

  ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/ai-trading-backend
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx
}

open_firewall() {
  log "Opening SSH and app HTTP ports"
  ufw allow 22/tcp >/dev/null 2>&1 || true
  ufw allow OpenSSH >/dev/null 2>&1 || true
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
  ufw --force enable >/dev/null 2>&1 || true
  ufw reload >/dev/null 2>&1 || true
  ufw status verbose || true
}

verify_connectivity() {
  log "Checking backend service"
  systemctl status "$SERVICE_NAME" --no-pager -l || true

  log "Checking local backend health"
  curl -fsS --max-time 20 http://127.0.0.1:8000/v1/health

  log "Checking local Nginx proxy health"
  curl -fsS --max-time 20 http://127.0.0.1/v1/health

  log "Listening sockets"
  ss -ltnp | grep -E '(:22|:80|:443|:8000)' || true

  cat <<EOF

Public checks to run from your PC:
  curl http://${PUBLIC_HOST}/v1/health
  curl http://${PUBLIC_HOST}/v1/signals/live

If those still timeout, fix Hostinger VPS firewall/security rules for inbound TCP 22, 80, and 443.
EOF
}

main() {
  require_root
  verify_app_home
  install_packages
  install_backend
  write_systemd_service
  write_nginx_proxy
  open_firewall
  verify_connectivity
}

main "$@"
