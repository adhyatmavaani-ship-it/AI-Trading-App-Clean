# 🚀 Quick Reference Guide

## Development Setup (5 Minutes)

```bash
# Clone and setup Python
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
TRADING_MODE=paper
REDIS_URL=redis://localhost:6379/0
BINANCE_TESTNET=true
PRIMARY_EXCHANGE=binance
BACKUP_EXCHANGES=["kraken","coinbase"]
AUTH_API_KEYS_JSON=[{"api_key":"local-dev-token","user_id":"alice","key_id":"local-key"}]
ENVIRONMENT=local
LOG_LEVEL=DEBUG
EOF

# Start Redis (Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Run backend
uvicorn app.main:app --reload

# In Browser: http://localhost:8000/docs
```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_risk_engine.py::test_daily_loss_limit -v

# Watch mode
ptw tests/
```

## API Usage Examples

### With Authentication

```bash
API_KEY="user_test_abc123"

# Evaluate symbol
curl -X POST http://localhost:8000/v1/trading/evaluate/BTCUSDT \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json"

# Execute trade
curl -X POST http://localhost:8000/v1/trading/execute \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "quantity": 0.01,
    "order_type": "MARKET"
  }'

# Close trade
curl -X POST http://localhost:8000/v1/trading/close \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_test",
    "trade_id": "12345",
    "exit_price": 45000.0,
    "closed_quantity": 0.01,
    "exit_fee": 5.0,
    "reason": "manual_close"
  }'
```

### Health Checks (No Auth Required)

```bash
# Basic health
curl http://localhost:8000/health

# Root metadata
curl http://localhost:8000/

# Readiness check (K8s)
curl http://localhost:8000/v1/health/ready

# Detailed diagnostics
curl http://localhost:8000/v1/health/detailed | jq .

# System monitoring
curl http://localhost:8000/v1/monitoring/system | jq .

# Prometheus metrics
curl http://localhost:8000/v1/monitoring/metrics
```

## Docker Compose

```bash
# Start everything
cd infrastructure/docker
docker-compose up --build

# Tear down
docker-compose down

# Reset (remove volumes)
docker-compose down -v

# View logs
docker-compose logs -f backend
```

## Kubernetes (Helm)

```bash
# Development namespace
kubectl create namespace trading-dev
helm install trading infrastructure/helm \
  -f infrastructure/helm/values-dev.yaml \
  -n trading-dev

# Production namespace
kubectl create namespace trading-prod
helm install trading infrastructure/helm \
  -f infrastructure/helm/values-prod.yaml \
  -n trading-prod

# Check status
kubectl get pods -n trading-prod
kubectl logs -f deployment/trading-backend -n trading-prod

# Port forward
kubectl port-forward svc/trading-backend 8000:80 -n trading-prod

# Helm upgrade
helm upgrade trading infrastructure/helm \
  -f infrastructure/helm/values-prod.yaml \
  -n trading-prod

# Rollback
helm rollback trading -n trading-prod
```

## Monitoring

### Prometheus Setup

```yaml
# Add to prometheus.yml scrape_configs:
- job_name: 'trading-backend'
  static_configs:
  - targets: ['localhost:8000']
  metrics_path: '/v1/monitoring/metrics'
  scrape_interval: 15s
```

### Key Metrics

```bash
# Trade execution latency
curl http://localhost:8000/v1/monitoring/metrics | grep trading_execution_latency

# Error rate
curl http://localhost:8000/v1/monitoring/metrics | grep api_requests_total

# Active trades
curl http://localhost:8000/v1/monitoring/metrics | grep trading_active_trades
```

### Grafana Queries

```promql
# P95 latency per endpoint
histogram_quantile(0.95, api_request_latency_seconds)

# Error rate by endpoint
rate(api_requests_total{status_code=~"5.."}[5m])

# Active trades
trading_active_trades

# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

## Common Issues

### Port Already in Use

```bash
# Find what's using 8000
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Linux/Mac
taskkill /PID <PID> /F  # Windows
```

### Redis Connection Error

```bash
# Check if Redis is running
redis-cli ping

# Or start with Docker
docker run -d -p 6379:6379 redis:7-alpine

# Verify connection from Python
python -c "import redis; r = redis.Redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

### High Memory Usage

```bash
# Check active trades
curl http://localhost:8000/v1/monitoring/system | jq .active_trades

# Check cache size (Redis)
redis-cli INFO memory

# Restart service
docker restart <container-id>
```

## Code Quality

### Format Code

```bash
# Auto-format with black
black backend/app

# Sort imports
isort backend/app

# Lint with flake8
flake8 backend/app --max-line-length=120

# Type check with mypy
mypy backend/app --ignore-missing-imports
```

### Pre-commit Hook

```bash
# Create .git/hooks/pre-commit
#!/bin/bash
black backend/app
isort backend/app
flake8 backend/app
mypy backend/app
pytest backend/tests/ -q
```

## Debugging

### Enable Debug Logs

```bash
# In .env
LOG_LEVEL=DEBUG
JSON_LOGS=false  # Easier to read in development

# Or set env variable
export LOG_LEVEL=DEBUG
```

### Add Breakpoint

```python
import pdb; pdb.set_trace()  # Regular Python
breakpoint()  # Python 3.7+
import ipdb; ipdb.set_trace()  # If ipdb installed
```

### Docker Container Debugging

```bash
# Enter container
docker exec -it <container-id> /bin/bash

# View logs with timestamps
docker logs -f --timestamps <container-id>
```

## Environment Variables Quick Reference

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | local | Deployment env |
| `TRADING_MODE` | paper | Trade execution mode |
| `LOG_LEVEL` | INFO | Logging verbosity |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `PRIMARY_EXCHANGE` | binance | First live exchange attempted |
| `BACKUP_EXCHANGES` | ["kraken","coinbase"] | Fallback exchange order |
| `BINANCE_TESTNET` | true | Use Binance testnet |
| `AUTH_API_KEYS_JSON` | empty | Inline API key bootstrap config |
| `DAILY_LOSS_LIMIT` | 0.05 | 5% daily max loss |
| `BASE_RISK_PER_TRADE` | 0.02 | 2% per trade |
| `RATE_LIMIT_PER_MINUTE` | 120 | API rate limit |

See `backend/app/core/config.py` for all ~100 settings.

## Performance Tuning

### Increase Concurrency

```bash
# Run with multiple workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000

# Or in Docker
docker run -e WORKERS=4 trading-backend
```

### Redis Pipeline for Batch Operations

```python
# Instead of N requests
for key in keys:
    cache.set(key, value)

# Use pipeline
from redis import Redis
r = Redis.from_url('...')
pipe = r.pipeline()
for key in keys:
    pipe.set(key, value)
pipe.execute()  # Single network round-trip
```

### Limit Cache Sizes

```bash
# In Redis config
maxmemory 1gb
maxmemory-policy allkeys-lru

# Or via CLI
redis-cli CONFIG SET maxmemory 1gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

## Deployment Checklist

Before deploying to production:

- [ ] All tests passing: `pytest tests/ -v`
- [ ] No linting issues: `flake8 backend/app`
- [ ] Type checking passes: `mypy backend/app`
- [ ] Health check responds: `curl http://localhost:8000/health`
- [ ] Authentication works: Provide API key, verify 401 without it
- [ ] Metrics available: `curl http://localhost:8000/v1/monitoring/metrics | head`
- [ ] Environment variables set
- [ ] Secrets in place (API keys, credentials)
- [ ] Reviewed [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)

## Support

- 📖 **Docs**: See [DEPLOYMENT.md](DEPLOYMENT.md) and [README.md](README.md)
- 🐛 **Bugs**: Open GitHub issue
- 💬 **Questions**: GitHub discussions
- 📧 **Email**: api@example.com

---

**Quick Tip**: Bookmark this file! Reference it daily during development.
