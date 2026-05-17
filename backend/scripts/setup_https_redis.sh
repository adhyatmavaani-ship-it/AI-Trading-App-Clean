#!/usr/bin/env bash
set -euo pipefail

DOMAIN_API="${1:-api.mydomain.com}"
DOMAIN_WS="${2:-ws.mydomain.com}"
LETSENCRYPT_EMAIL="${3:-admin@mydomain.com}"
APP_HOME="${APP_HOME:-$HOME/AI-Trading-App-Clean/backend}"
SERVICE_NAME="${SERVICE_NAME:-ai-trading-backend.service}"
REDIS_URL="${REDIS_URL:-redis://127.0.0.1:6379/0}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-ai-trading}"

if [[ ! -d "$APP_HOME" ]]; then
  echo "Backend directory not found: $APP_HOME" >&2
  exit 1
fi

if [[ ! -x "$APP_HOME/.venv/bin/uvicorn" ]]; then
  echo "Uvicorn not found in $APP_HOME/.venv/bin/uvicorn" >&2
  exit 1
fi

echo "Installing production packages..."
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx redis-server ufw fail2ban

echo "Hardening Redis for localhost-only persistent production use..."
sudo cp /etc/redis/redis.conf "/etc/redis/redis.conf.bak.$(date +%Y%m%d%H%M%S)"
sudo sed -ri 's/^#?\s*bind .*/bind 127.0.0.1 -::1/' /etc/redis/redis.conf
sudo sed -ri 's/^#?\s*protected-mode .*/protected-mode yes/' /etc/redis/redis.conf
sudo sed -ri 's/^#?\s*supervised .*/supervised systemd/' /etc/redis/redis.conf
sudo sed -ri 's/^#?\s*appendonly .*/appendonly yes/' /etc/redis/redis.conf
sudo sed -ri 's/^#?\s*appendfsync .*/appendfsync everysec/' /etc/redis/redis.conf
sudo sed -ri 's/^#?\s*tcp-keepalive .*/tcp-keepalive 60/' /etc/redis/redis.conf
if grep -q '^maxmemory ' /etc/redis/redis.conf; then
  sudo sed -ri 's/^maxmemory .*/maxmemory 256mb/' /etc/redis/redis.conf
else
  echo 'maxmemory 256mb' | sudo tee -a /etc/redis/redis.conf >/dev/null
fi
if grep -q '^maxmemory-policy ' /etc/redis/redis.conf; then
  sudo sed -ri 's/^maxmemory-policy .*/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
else
  echo 'maxmemory-policy allkeys-lru' | sudo tee -a /etc/redis/redis.conf >/dev/null
fi
sudo systemctl enable --now redis-server
sudo systemctl restart redis-server

echo "Switching backend service to localhost-only bind behind nginx and injecting Redis env..."
sudo mkdir -p "/etc/systemd/system/${SERVICE_NAME}.d"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.d/override.conf" >/dev/null <<EOF
[Service]
Environment=REDIS_URL=${REDIS_URL}
Environment=PUBLIC_BASE_URL=https://${DOMAIN_API}
Environment=ENVIRONMENT=prod
ExecStart=
ExecStart=${APP_HOME}/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "Writing bootstrap nginx config for ACME + HTTP redirect..."
sudo tee "/etc/nginx/sites-available/${NGINX_SITE_NAME}" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN_API} ${DOMAIN_WS};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}
EOF

sudo ln -sfn "/etc/nginx/sites-available/${NGINX_SITE_NAME}" "/etc/nginx/sites-enabled/${NGINX_SITE_NAME}"
sudo rm -f /etc/nginx/sites-enabled/default

echo "Installing fail2ban defaults..."
sudo tee /etc/fail2ban/jail.local >/dev/null <<'EOF'
[sshd]
enabled = true
backend = systemd
port = ssh
maxretry = 5
findtime = 10m
bantime = 1h
EOF
sudo systemctl enable --now fail2ban
sudo systemctl restart fail2ban

echo "Applying UFW rules..."
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw delete allow 8000/tcp >/dev/null 2>&1 || true
sudo ufw --force enable
sudo ufw reload

echo "Requesting Let's Encrypt certificates..."
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot \
  -w /var/www/html \
  -d "${DOMAIN_API}" \
  -d "${DOMAIN_WS}" \
  --agree-tos \
  --email "${LETSENCRYPT_EMAIL}" \
  --non-interactive

echo "Writing final TLS nginx config..."
sudo tee "/etc/nginx/sites-available/${NGINX_SITE_NAME}" >/dev/null <<EOF
upstream ai_trading_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

map \$http_upgrade \$connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN_API} ${DOMAIN_WS};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN_API};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN_API}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN_API}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location / {
        proxy_pass http://ai_trading_backend;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        send_timeout 60s;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name ${DOMAIN_WS};

    ssl_certificate /etc/letsencrypt/live/${DOMAIN_WS}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN_WS}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;
    ssl_prefer_server_ciphers off;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location /ws/ {
        proxy_pass http://ai_trading_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$connection_upgrade;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_buffering off;
        proxy_cache off;
        proxy_connect_timeout 10s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;
        send_timeout 3600s;
    }

    location / {
        return 404;
    }
}
EOF

sudo nginx -t
sudo systemctl reload nginx

echo "Verification:"
echo "1. curl -I https://${DOMAIN_API}/v1/health"
echo "2. curl -I http://${DOMAIN_API}/v1/health"
echo "3. redis-cli -h 127.0.0.1 -p 6379 ping"
echo "4. sudo journalctl -u ${SERVICE_NAME} -n 200 --no-pager"
echo "5. sudo journalctl -u nginx -n 100 --no-pager"
echo "6. sudo systemctl status certbot.timer --no-pager"
