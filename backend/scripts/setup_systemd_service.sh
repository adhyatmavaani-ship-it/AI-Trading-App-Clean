#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="ai-trading-backend"
UNIT_NAME="${SERVICE_NAME}.service"
PUBLIC_HOST="${PUBLIC_HOST:-69.62.74.7}"
APP_HOME_INPUT="${1:-$HOME/AI-Trading-App-Clean/backend}"
APP_HOME="$(realpath "$APP_HOME_INPUT")"

if [[ ! -d "$APP_HOME" ]]; then
  echo "Backend directory not found: $APP_HOME" >&2
  exit 1
fi

if [[ ! -f "$APP_HOME/app/main.py" ]]; then
  echo "Production entrypoint missing: $APP_HOME/app/main.py" >&2
  exit 1
fi

if [[ ! -f "$APP_HOME/requirements.txt" ]]; then
  echo "requirements.txt missing in $APP_HOME" >&2
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  SERVICE_USER="${SUDO_USER:-root}"
else
  SERVICE_USER="${USER}"
fi

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  echo "Service user does not exist: $SERVICE_USER" >&2
  exit 1
fi

SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
VENV_DIR="$APP_HOME/.venv"
PYTHON_BIN="$VENV_DIR/bin/python"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"

log() {
  printf '\n[%s] %s\n' "$(date '+%F %T')" "$*"
}

run_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

ensure_venv() {
  if [[ ! -d "$VENV_DIR" ]]; then
    log "Creating virtualenv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  fi

  log "Installing backend dependencies"
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$APP_HOME/requirements.txt"
}

warn_if_env_missing() {
  if [[ ! -f "$APP_HOME/.env" ]]; then
    log "WARNING: $APP_HOME/.env is missing. The service will start only if env vars are provided another way."
  fi
}

stop_old_manual_processes() {
  log "Stopping old manual uvicorn processes"
  run_sudo systemctl stop "$UNIT_NAME" >/dev/null 2>&1 || true

  local patterns=(
    "uvicorn app.main:app --host 0.0.0.0 --port 8000"
    "uvicorn app.main:app --host 0.0.0.0 --port 10000"
    "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
    "python -m uvicorn app.main:app --host 0.0.0.0 --port 10000"
  )

  for pattern in "${patterns[@]}"; do
    run_sudo pkill -f "$pattern" >/dev/null 2>&1 || true
  done

  sleep 2
  run_sudo pgrep -af "uvicorn .*app.main:app" || true
}

write_unit() {
  log "Writing systemd unit to $UNIT_PATH"
  run_sudo tee "$UNIT_PATH" >/dev/null <<EOF
[Unit]
Description=AI Trading FastAPI Backend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_HOME
Environment=PYTHONUNBUFFERED=1
Environment=ENVIRONMENT=prod
Environment=PORT=8000
ExecStart=$UVICORN_BIN app.main:app --host 0.0.0.0 --port 8000 --no-access-log --log-level warning
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
}

reload_and_enable() {
  log "Reloading systemd and enabling service"
  run_sudo systemctl daemon-reload
  run_sudo systemctl enable --now "$UNIT_NAME"
}

open_firewall() {
  if command -v ufw >/dev/null 2>&1; then
    log "Opening firewall ports with ufw"
    run_sudo ufw allow OpenSSH >/dev/null 2>&1 || true
    run_sudo ufw allow 8000/tcp >/dev/null 2>&1 || true
    run_sudo ufw allow 80/tcp >/dev/null 2>&1 || true
    run_sudo ufw allow 443/tcp >/dev/null 2>&1 || true
    run_sudo ufw --force enable >/dev/null 2>&1 || true
    run_sudo ufw reload >/dev/null 2>&1 || true
    run_sudo ufw status verbose || true
  else
    log "ufw not installed; skipping firewall configuration"
  fi
}

verify_http() {
  log "Verifying local HTTP health"
  curl -fsS --max-time 15 "http://127.0.0.1:8000/v1/health" || {
    log "Local health check failed"
    return 1
  }

  log "Verifying public HTTP health"
  curl -fsS --max-time 15 "http://${PUBLIC_HOST}:8000/v1/health" || {
    log "Public health check failed"
    return 1
  }
}

verify_websocket() {
  local api_key=""

  if [[ -f "$APP_HOME/.env" ]]; then
    api_key="$("$PYTHON_BIN" - <<'PY' "$APP_HOME/.env"
import json
import pathlib
import sys

env_path = pathlib.Path(sys.argv[1])
value = ""
for line in env_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, raw = line.split("=", 1)
    if key.strip() == "AUTH_API_KEYS_JSON":
        value = raw.strip()
        break

if not value:
    print("")
    raise SystemExit(0)

try:
    parsed = json.loads(value)
except Exception:
    print("")
    raise SystemExit(0)

if isinstance(parsed, list) and parsed:
    first = parsed[0]
    if isinstance(first, dict):
        print(str(first.get("api_key", "")).strip())
        raise SystemExit(0)

print("")
PY
)"
  fi

  if [[ -z "$api_key" ]]; then
    log "Skipping websocket verification because AUTH_API_KEYS_JSON could not be parsed from .env"
    return 0
  fi

  log "Verifying websocket ping"
  "$PYTHON_BIN" - <<'PY' "$api_key"
import asyncio
import sys
import websockets

api_key = sys.argv[1]
url = "ws://127.0.0.1:8000/ws/signals"

async def main():
    async with websockets.connect(url, open_timeout=10, extra_headers={"X-API-Key": api_key}) as ws:
        await ws.send("ping")
        reply = await asyncio.wait_for(ws.recv(), timeout=10)
        print(reply)
        if "pong" not in reply:
            raise RuntimeError(f"Unexpected websocket reply: {reply}")

asyncio.run(main())
PY
}

show_final_state() {
  log "Service status"
  run_sudo systemctl status "$UNIT_NAME" --no-pager -l || true

  log "Listening socket"
  run_sudo ss -ltnp | grep ":8000" || true

  log "Remaining uvicorn processes"
  run_sudo pgrep -af "uvicorn .*app.main:app" || true

  cat <<EOF

Service commands:
  sudo systemctl start $UNIT_NAME
  sudo systemctl stop $UNIT_NAME
  sudo systemctl restart $UNIT_NAME
  sudo systemctl status $UNIT_NAME --no-pager -l
  sudo journalctl -u $SERVICE_NAME -f

EOF
}

main() {
  log "Target backend directory: $APP_HOME"
  log "Service will run as: $SERVICE_USER:$SERVICE_GROUP"
  ensure_venv
  warn_if_env_missing
  stop_old_manual_processes
  write_unit
  reload_and_enable
  open_firewall
  verify_http
  verify_websocket
  show_final_state
}

main "$@"
