# AI-Powered Autonomous Crypto Trading System

> **Status**: Advanced Pre-Production System | **Last Updated**: April 2026

A production-grade AI-driven cryptocurrency trading platform with institutional-grade risk management, execution safety, monitoring, and observability.

## Quick Links
- **[Runtime Guide](RUNTIME.md)** - Supported versions, local setup, CI contract, beta preflight

- 📚 **[Deployment Guide](DEPLOYMENT.md)** - How to deploy locally, Docker, Kubernetes, Cloud Run
- ✅ **[Production Checklist](PRODUCTION_CHECKLIST.md)** - Pre-deployment validation steps
- 🔐 **[Security & Auth](#security--authentication)** - Authentication, authorization, rate limiting
- 📊 **[Monitoring](#monitoring--health-checks)** - Prometheus metrics, health checks, dashboards

## Folder Structure

```text
backend/                      FastAPI backend, services, models, execution
  app/
    api/routes/               API endpoints (trading, monitoring, health)
    core/                     Core utilities (config, exceptions, metrics, circuit breaker)
    middleware/               Auth, rate limiting, request context
    models/                   Data models
    schemas/                  Request/response schemas
    services/                 Business logic (40+ services)
    workers/                  Background tasks (market streams, workers)
  tests/                      Unit, integration, E2E tests (28+ test files)
  requirements.txt            Python dependencies
  Dockerfile                  Container image

cloud_functions/              Firebase Cloud Functions
flutter_app/                  Flutter mobile dashboard
infrastructure/               Kubernetes, Terraform, Docker Compose, Helm
DEPLOYMENT.md                 Deployment guide for all platforms
PRODUCTION_CHECKLIST.md       Pre-production validation
```

## Key Services

### AI & Decision Making
- **AIEngine**: LSTM/Transformer hybrid forecaster + classifier (BUY/SELL/HOLD)
- **StrategyEngine**: Market regime detection → strategy selection
- **AlphaEngine**: Fuses AI, whale flow, sentiment, liquidity into alpha score

### Risk & Safety
- **RiskEngine**: Position sizing, volatility throttling, daily loss limits, consecutive loss pauses
- **DrawdownProtectionService**: Rolling equity monitoring, size reduction, trading pause
- **SecurityScanner**: Honeypot detection, ownership analysis, rug-pull prevention
- **MetaController**: Governance gate - final approval/veto on trades

### Execution
- **ExecutionEngine**: Live multi-exchange orders with primary/backup failover, slippage checks, chunk execution, retries
- **PaperExecutionEngine**: Simulated trading for backtesting
- **VirtualOrderManager**: Order batching and aggregation for institutional-style execution
- **LiquiditySlippageEngine**: Orderbook impact analysis and chunk scheduling

### Data & Monitoring
- **MarketDataService**: Price feeds with Redis caching
- **PerformanceTracker**: Win rate, profit factor, correlation tracking
- **SystemMonitorService**: Latency, error rates, active trades, rollout stages
- **PortfolioLedgerService**: Real-time PnL, realized/unrealized tracking

### Advanced Features
- **WhaleTracker**: Smart money wallet detection across Ethereum/Solana/Base
- **SentimentEngine**: Narrative classification and hype-vs-volume analysis
- **TaxEngine**: Per-trade tax estimation
- **SelfHealingPPOService**: RL-based strategy recovery
- **SimulationTester**: Stress testing (1000+ trades under failure scenarios)
- **RolloutManager**: Staged capital deployment (SHADOW → MICRO → LIMITED → EXPANDED)

## Quick Start

### Local Development

```bash
# 1. Clone and setup
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
echo "TRADING_MODE=paper
REDIS_URL=redis://localhost:6379/0
BINANCE_TESTNET=true
PRIMARY_EXCHANGE=binance
BACKUP_EXCHANGES=[\"kraken\",\"coinbase\"]
AUTH_API_KEYS_JSON=[{\"api_key\":\"local-dev-token\",\"user_id\":\"alice\",\"key_id\":\"local-key\"}]" > .env

# 3. Start Redis (Docker or local)
docker run -d -p 6379:6379 redis:7-alpine

# 4. Run tests
pytest tests/ -v

# 5. Start backend
uvicorn app.main:app --reload
# API docs: http://localhost:8000/docs
```

### Docker Compose

```bash
cd infrastructure/docker
docker-compose up --build
# Backend: http://localhost:8000
# Redis: localhost:6379
```

### Kubernetes (Helm)

```bash
# Development
helm install trading infrastructure/helm -f infrastructure/helm/values-dev.yaml

# Production
helm install trading infrastructure/helm -f infrastructure/helm/values-prod.yaml

# Check status
kubectl get pods
kubectl port-forward svc/trading-backend 8000:80
curl http://localhost:8000/health
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

## Architecture Highlights

### Layered Decision Stack
```
User Request
    ↓
Authentication & Validation
    ↓
AI Signal Generation (forecaster + classifier)
    ↓
Strategy Selection (market regime detection)
    ↓
Whale/Sentiment Analysis (context overlays)
    ↓
Alpha Scoring (unified decision gate)
    ↓
Risk Evaluation (position sizing, volatility adjustment)
    ↓
Meta Controller (governance gate - final approval)
    ↓
Execution (paper or live channel)
    ↓
State Persistence (Redis + Firestore)
    ↓
Monitoring & Alerting
```

### Safety Mechanisms
- **2% base risk per trade** → Dynamic volatility adjustment
- **5% daily loss limit** → Auto-pause if exceeded
- **3 consecutive losses** → Trading paused until reset
- **20% max exposure per coin** → Portfolio concentration cap
- **6% drawdown protection** → Size reduction triggered
- **Rate limiting** → 120 requests/min per user
- **Circuit breaker** → Protects against cascading API failures

## Security & Authentication

### API Key Authentication

All endpoints (except health checks) require authentication:

```bash
# Header-based authentication
curl -X POST http://localhost:8000/v1/trading/evaluate/BTCUSDT \
  -H "X-API-Key: user_test_abc123" \
  -H "Content-Type: application/json"

# Or Bearer token
curl -X POST http://localhost:8000/v1/trading/evaluate/BTCUSDT \
  -H "Authorization: Bearer user_test_abc123" \
  -H "Content-Type: application/json"
```

### Features
- ✅ API key validation on every request
- ✅ Per-user isolation (cannot access other users' trades)
- ✅ Request correlation IDs for tracing
- ✅ Role-based access control (Admin, Trader, Viewer)
- ✅ Rate limiting (per-user, not IP-based)
- ✅ Graceful shutdown (15s termination grace)

See [Authentication Middleware](backend/app/middleware/auth.py) for implementation.

## Monitoring & Health Checks

### Health Endpoints

```bash
# Minimal check (for load balancers)
GET /health
→ {"status": "ok", "version": "7fa26d4", "commit": "<full_sha>"}

# Kubernetes liveness probe
GET /health/live
→ {"status": "alive", "timestamp": "2026-04-25T...", "version": "7fa26d4"}

# Kubernetes readiness probe (checks dependencies)
GET /health/ready
→ {
    "status": "ready",
    "checks": {
      "redis": "ready",
      "firestore": "ready",
      "market_data": "ready"
    }
  }

# Detailed diagnostics
GET /health/detailed
→ {
    "service": "ai-trading-backend",
    "version": "7fa26d4",
    "commit": "<full_sha>",
    "environment": "prod",
    "dependencies": { ... },
    "system": { ... },
    "limits": { ... }
  }
```

### Prometheus Metrics

```bash
# Get all metrics in Prometheus format
GET /v1/monitoring/metrics

# Key metrics exported:
# - trading_executions_total{side,status}
# - trading_execution_latency_seconds
# - api_requests_total{method,endpoint,status_code}
# - api_request_latency_seconds{endpoint}
# - risk_limit_breaches_total{limit_type}
# - circuit_breaker_state{service}
# - cache_hits_total{cache_type}
# - firestore_latency_seconds{operation}
```

### Grafana Dashboards

Key panels:
- Trade execution latency (p50, p95, p99)
- Error rate by endpoint
- Active trades count
- Portfolio drawdown %
- Cache hit rate (>80% target)
- API rate limit usage
- Circuit breaker states

## API Endpoints

### Trading

```
POST   /v1/trading/evaluate/{symbol}
       → Evaluate symbol for trading opportunity
       → Returns: AI signal, confidence, risk assessment

POST   /v1/trading/execute
       → Execute a trade
       → Returns: Trade ID, status, allocation

POST   /v1/trading/sniper/{symbol}
       → Coordinated entry (whale + sentiment aligned)
       → Returns: Trade result

POST   /v1/trading/close
       → Close/partial close a position
       → Returns: Exit confirmation, realized PnL
```

### Portfolio & Monitor

```
GET    /v1/frontend/portfolio/{user_id}
       → User portfolio summary
       → Returns: PnL, positions, drawdown

GET    /v1/monitoring/system
       → System-wide health
       → Returns: Latency, error rate, active trades

GET    /v1/monitoring/metrics
       → Prometheus metrics
       → Returns: Text format metrics
```

## Error Handling

All errors follow a consistent format:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {"field": "symbol", "message": "Invalid symbol", "type": "value_error"}
    ]
  }
}
```

### Status Codes
- **200** - Success
- **400** - Validation error
- **401** - Authentication failed
- **403** - Authorization failed / Risk limit exceeded
- **409** - State conflict (e.g., no open position to close)
- **429** - Rate limit exceeded
- **500** - Server error
- **503** - Service unavailable

See [Custom Exceptions](backend/app/core/exceptions.py) for all error types.

## Configuration

### Environment Variables

**Required (Production)**
```
ENVIRONMENT=prod                    # local, dev, staging, prod
TRADING_MODE=live                   # paper, live
REDIS_URL=redis://redis:6379/0
FIRESTORE_PROJECT_ID=my-gcp-project
AUTH_API_KEYS_JSON=[...]           # or Firestore-backed API keys
```

**Exchange Routing**
```
PRIMARY_EXCHANGE=binance            # first exchange attempted for live execution
BACKUP_EXCHANGES=["kraken","coinbase"]
BINANCE_TESTNET=true                # only affects the Binance adapter
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
KRAKEN_API_KEY=...
KRAKEN_API_SECRET=...
COINBASE_API_KEY=...
COINBASE_API_SECRET=...
COINBASE_API_PASSPHRASE=...
```

**Risk Settings**
```
BASE_RISK_PER_TRADE=0.02           # 2% per trade
DAILY_LOSS_LIMIT=0.05              # 5% daily max loss
MAX_CONSECUTIVE_LOSSES=3            # Pause after 3 losses
MAX_COIN_EXPOSURE_PCT=0.20         # 20% max per coin
```

**Performance**
```
MARKET_DATA_CACHE_TTL=15            # 15 second cache
RATE_LIMIT_PER_MINUTE=120
EXECUTION_CHUNK_DELAY_MS=350        # Order chunking delay
```

See [Config](backend/app/core/config.py) for all 100+ settings.

## Testing

```bash
# Run all tests
pytest backend/tests/ -v

# With coverage report
pytest backend/tests/ --cov=backend/app --cov-report=html
open htmlcov/index.html

# Run specific test file
pytest backend/tests/test_risk_engine.py -v

# Run tests matching pattern
pytest backend/tests/ -k "risk" -v

# Load testing
python infrastructure/loadtest/distributed_load_validation.py
```

**Test Coverage**
- ✅ 28+ test files
- ✅ Unit tests: RiskEngine, ExecutionEngine, PortfolioLedger, etc.
- ✅ Integration tests: Trading orchestrator flows
- ✅ E2E tests: Full trade lifecycle
- ✅ Reliability tests: Chaos scenarios, failure injection

## Deployment

### Local Development
See [Quick Start](#quick-start) above or [DEPLOYMENT.md](DEPLOYMENT.md#local-development-setup)

### Docker Compose
```bash
cd infrastructure/docker
docker-compose up --build
```

### Kubernetes/Helm
```bash
# Production deployment
helm install trading infrastructure/helm \
  -f infrastructure/helm/values-prod.yaml \
  --namespace trading-prod

# Check health
kubectl get pods -n trading-prod
kubectl logs -f deployment/trading-backend -n trading-prod
```

### Cloud Run
```bash
gcloud run deploy trading-backend \
  --source=backend \
  --region=us-central1 \
  --memory=1Gi \
  --set-env-vars ENVIRONMENT=prod,TRADING_MODE=paper,PRIMARY_EXCHANGE=binance,BACKUP_EXCHANGES='["kraken","coinbase"]'
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment instructions.

## Production Checklist

Before deploying to production, review [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md):

- ✅ Authentication & Authorization
- ✅ Infrastructure & Deployment
- ✅ Performance & Reliability
- ✅ Testing & QA
- ✅ Monitoring & Alerting
- ✅ Disaster Recovery
- ✅ Operations & Runbooks

**TL;DR**: ~50 items covering security, infrastructure, testing, monitoring, backups, and disaster recovery.

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker logs <container-id>
# or
kubectl logs pod/trading-backend-xxxxx

# Common issue: "Firestore project_id not configured"
# Solution: Set FIRESTORE_PROJECT_ID in .env or ConfigMap
```

### High Latency
```bash
# Check active trades
curl http://localhost:8000/v1/monitoring/system | jq .

# Check Prometheus for slowest endpoints
# Common cause: N+1 market data queries
```

### Health Check Failing
```bash
# Get detailed status
curl http://localhost:8000/v1/health/detailed | jq .

# Check specific dependency
# - Redis: Is Redis running? Can backend connect?
# - Firestore: Valid credentials? Network access?
# - Market data: primary exchange API accessible?
```

## Development Roadmap

### Completed ✅
- Multi-layer decision engine (AI + risk + governance)
- Live/paper execution modes
- Full portfolio accounting
- Monitoring & health checks
- **New**: Authentication & authorization
- **New**: Kubernetes/Helm charts
- **New**: Prometheus metrics
- **New**: Graceful shutdown
- **New**: Circuit breaker pattern
- **New**: Correlation IDs for tracing
- **New**: Comprehensive documentation

### In Progress 🟨
- Live exchange reconciliation worker
- Advanced chaos testing
- Expanded exchange coverage and production credential rollout
- Web dashboard (Flutter mobile complete)

### Future 🔮
- Federated learning for collaborative signal generation
- Advanced portfolio optimization (Markowitz)
- Options strategies
- Futures/derivatives support

## Contribution Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a pull request

**Code Standards**:
- Type hints on all functions
- Docstrings on all modules/classes
- Tests for all new features (pytest)
- Follow PEP 8 (use black/isort)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- 📖 **Documentation**: See [DEPLOYMENT.md](DEPLOYMENT.md) and [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md)
- 🐛 **Issues**: GitHub Issues for bugs
- 💬 **Discussions**: GitHub Discussions for feature requests
- 📧 **Email**: api@example.com

## Acknowledgments

Built with:
- FastAPI & Uvicorn
- PyTorch (LSTM/Transformer models)
- Scikit-learn (classifiers)
- Redis (state management)
- Google Cloud Firestore (persistence)
- Prometheus (metrics)
- Kubernetes (orchestration)
- Helm (package management)

---

**Last Updated**: April 25, 2026  
**Status**: Production Ready (with checklist)  
**Version**: 1.0.0
