# 🚀 Production Deployment Checklist

## Pre-Deployment (Before you ship)

### Security & Authentication
- [ ] **API Key Management**
  - [ ] Implement API key generation and storage in database
  - [ ] Add API key rotation strategy (e.g., 90-day expiry)
  - [ ] Remove all hardcoded secrets from codebase
  - [ ] Use Google Secret Manager or HashiCorp Vault for secrets
  - [ ] Test: Start server without any API key → should deny all requests

- [ ] **Authorization & Multi-Tenancy**
  - [ ] Verify user isolation - users cannot access other users' trades
  - [ ] Add role-based access control (Admin, Trader, Viewer)
  - [ ] Test: Try to close another user's trade → should fail with 403
  - [ ] Verify trades only execute for authenticated user

- [ ] **CORS Configuration**
  - [ ] Configure CORS_ORIGINS for frontend domain
  - [ ] Disable credentials in CORS (unless absolutely needed)
  - [ ] Test from different origins

- [ ] **HTTPS & TLS**
  - [ ] All production traffic HTTPS only
  - [ ] Use valid certificates (not self-signed)
  - [ ] Enable HSTS headers (`Strict-Transport-Security`)

### Infrastructure & Deployment
- [ ] **Docker & Kubernetes**
  - [ ] Health checks configured in Dockerfile/Helm
    - [ ] Liveness probe: `/health/live`
    - [ ] Readiness probe: `/health/ready`
  - [ ] Resource limits set (memory, CPU)
  - [ ] Graceful shutdown enabled (15s termination grace)
  - [ ] Pod disruption budgets configured
  - [ ] Rolling updates strategy defined

- [ ] **Environment Configuration**
  - [ ] Production `.env` file created (never committed)
  - [ ] All settings have sensible defaults
  - [ ] Config validation runs on startup
  - [ ] Environment detection working (dev vs prod)

- [ ] **Database & Persistence**
  - [ ] Firestore indexes created for all queries (check Firestore logs for warnings)
  - [ ] Backup strategy defined (daily snapshots)
  - [ ] Data retention policy defined
  - [ ] Firestore security rules reviewed and tightened

- [ ] **Redis**
  - [ ] Redis persistence enabled (AOF or RDB)
  - [ ] Redis backups configured
  - [ ] Memory limits set
  - [ ] Eviction policy chosen (default: allkeys-lru)

- [ ] **Monitoring & Logging**
  - [ ] Logs forwarded to Cloud Logging or ELK
  - [ ] PII redaction enabled (no trade IDs, user IDs in stdout)
  - [ ] Log retention policy set (30/90/365 days)
  - [ ] Error aggregation tool connected (Sentry, Rollbar)

### Performance & Reliability
- [ ] **Load Testing**
  - [ ] Run load test: 100 concurrent users on 10 seconds
  - [ ] Check: Response times < 500ms at p95
  - [ ] No memory leaks detected (monitor for 24 hours)
  - [ ] Database connections pooled (not exhausted)

- [ ] **Caching Strategy**
  - [ ] Cache TTLs reviewed and appropriate
  - [ ] Cache invalidation tested
  - [ ] Cache hit ratio > 80% for market data
  - [ ] Redis memory usage acceptable

- [ ] **Execution Reliability**
  - [ ] Order idempotency working (request IDs tracked)
  - [ ] Retry logic verified (exponential backoff)
  - [ ] Partial fills tracked and reconciled
  - [ ] Crash recovery tested

- [ ] **Database Migration**
  - [ ] Firestore schema versioning documented
  - [ ] Backward compatibility maintained
  - [ ] Data migration tested in staging first

### Testing & QA
- [ ] **Test Coverage**
  - [ ] Unit tests: >70% coverage
  - [ ] Integration tests: Critical flows working
  - [ ] E2E tests: evaluate → execute → close flow
  - [ ] All tests passing locally and in CI

- [ ] **Security Testing**
  - [ ] Authentication tests: Missing API key → 401
  - [ ] Authorization tests: Different user → 403
  - [ ] Input validation: Malformed JSON → 422
  - [ ] Rate limiting: >120 requests/min → 429
  - [ ] SQL injection attempt → handling gracefully

- [ ] **Smoke Tests (Post-Deploy)**
  - [ ] Health check returns 200
  - [ ] Can authenticate with valid API key
  - [ ] Can fetch symbol evaluation
  - [ ] Can execute paper trade
  - [ ] Can view portfolio PnL

### Monitoring & Alerting
- [ ] **Prometheus Metrics**
  - [ ] Metrics endpoint accessible at `/v1/monitoring/metrics`
  - [ ] Scrape job configured in Prometheus
  - [ ] Dashboards created for key metrics:
    - Trade execution latency (p50, p95, p99)
    - Error rate (by endpoint)
    - Active trade count
    - Portfolio drawdown

- [ ] **Alerts**
  - [ ] Error rate > 5% → PagerDuty alert
  - [ ] Latency p95 > 1s → warning
  - [ ] Drawdown > 6% → warning
  - [ ] Redis connectivity loss → critical
  - [ ] Firestore quota exceeded → critical

- [ ] **Health Checks**
  - [ ] `/v1/health` responds quickly
  - [ ] `/v1/health/ready` checks all dependencies
  - [ ] `/v1/health/detailed` shows diagnostics

### Disaster Recovery
- [ ] **Backups**
  - [ ] Firestore automated backups enabled
  - [ ] Redis snapshots created hourly
  - [ ] Test restore from backup (at least monthly)
  - [ ] RTO/RPO targets defined

- [ ] **Failover**
  - [ ] Multi-region replication configured
  - [ ] Failover process documented
  - [ ] Database failover tested

### Operations & Runbooks
- [ ] **Documentation**
  - [ ] Deployment guide created (`DEPLOYMENT.md`)
  - [ ] Troubleshooting guide created (`TROUBLESHOOTING.md`)
  - [ ] API documentation complete (`/docs` endpoint)
  - [ ] On-call runbook created

- [ ] **Secrets Management**
  - [ ] API keys stored in Secret Manager
  - [ ] Database credentials never in code
  - [ ] Rotation strategy documented
  - [ ] Access auditing enabled

---

## Day-1 (After Deployment)

### Immediate Validation
- [ ] Monitor error rates (should be <0.1%)
- [ ] Check latency (p95 < 500ms)
- [ ] Monitor database query times
- [ ] Verify traders can execute paper trades
- [ ] Check log aggregation is receiving logs

### First Week
- [ ] No cascading failures observed
- [ ] Cache hit rates healthy
- [ ] No database connection pool exhaustion
- [ ] Graceful handling of API errors from Binance
- [ ] Traders provided API keys, wallets funded

---

## Example Health Check Configuration (Kubernetes)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-backend
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: backend
        image: trading:1.0.0
        ports:
        - containerPort: 8000
        
        # Liveness probe - restart if dead
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        # Readiness probe - remove from LB if not ready
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 2
        
        # Resource limits
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
      
      # Graceful shutdown
      terminationGracePeriodSeconds: 30
```

---

## Example Prometheus Scrape Config

```yaml
scrape_configs:
- job_name: 'trading-backend'
  static_configs:
  - targets: ['localhost:8000']
  metrics_path: '/v1/monitoring/metrics'
  scrape_interval: 15s
  scrape_timeout: 10s
```

---

## Example Alert Rules

```yaml
groups:
- name: trading_alerts
  rules:
  - alert: HighErrorRate
    expr: rate(api_requests_total{status_code=~"5.."}[5m]) > 0.05
    for: 5m
    annotations:
      summary: "High error rate ({{ $value | humanizePercentage }})"
  
  - alert: HighLatency
    expr: histogram_quantile(0.95, api_request_latency_seconds) > 1.0
    for: 10m
    annotations:
      summary: "High p95 latency ({{ $value | humanizeDuration }})"
  
  - alert: CircuitBreakerOpen
    expr: circuit_breaker_state > 0
    for: 1m
    annotations:
      summary: "Circuit breaker OPEN for {{ $labels.service }}"
```

---

## Pre-Production Checklist Summary

| Category | Status | Owner |
|----------|--------|-------|
| Security | ⚠️ | Security Lead |
| Infrastructure | ⚠️ | DevOps Lead |
| Testing | ⚠️ | QA Lead |
| Monitoring | ⚠️ | Infrastructure Lead |
| Operations | ⚠️ | On-Call Engineer |

---

## Rollback Plan

If production deployment fails:
1. Scale down new pods: `kubectl scale deployment trading-backend --replicas=0`
2. Revert to previous image tag
3. Scale back up: `kubectl scale deployment trading-backend --replicas=3`
4. Validate health checks passing
5. Page oncall engineer

**Estimated rollback time: < 2 minutes**
