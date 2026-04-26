"""Prometheus metrics and monitoring for the trading system."""

from prometheus_client import Counter, Gauge, Histogram, generate_latest

# Trade execution metrics
trade_executions = Counter(
    "trading_executions_total",
    "Total trade executions",
    ["side", "status"],  # BUY/SELL, SUCCESS/FAILURE
)

trade_pnl = Gauge(
    "trading_pnl_realtime",
    "Realized P&L in USD",
)

active_trades = Gauge(
    "trading_active_trades",
    "Number of currently active trades",
)

trade_execution_latency = Histogram(
    "trading_execution_latency_seconds",
    "Time taken to execute trade (seconds)",
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# API metrics
api_requests = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)

api_latency = Histogram(
    "api_request_latency_seconds",
    "API request latency (seconds)",
    ["endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
)

rate_limit_exceeded = Counter(
    "rate_limit_exceeded_total",
    "Rate limit exceedances",
    ["client_id"],
)

# Risk metrics
risk_limit_breaches = Counter(
    "risk_limit_breaches_total",
    "Risk limit violations",
    ["limit_type"],  # daily_loss, exposure, etc.
)

drawdown_percentage = Gauge(
    "drawdown_percentage",
    "Current portfolio drawdown percentage",
)

# Market data metrics
market_data_errors = Counter(
    "market_data_errors_total",
    "Market data fetch errors",
    ["exchange", "error_type"],
)

market_data_latency = Histogram(
    "market_data_latency_seconds",
    "Market data fetch latency (seconds)",
    ["exchange"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# System metrics
external_api_errors = Counter(
    "external_api_errors_total",
    "External API errors (Binance, etc.)",
    ["service", "error_type"],
)

cache_hits = Counter(
    "cache_hits_total",
    "Cache hits",
    ["cache_type"],  # redis, memory, etc.
)

cache_misses = Counter(
    "cache_misses_total",
    "Cache misses",
    ["cache_type"],
)

# Circuitbreaker metrics
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half-open)",
    ["service"],
)

# Database metrics
firestore_operations = Counter(
    "firestore_operations_total",
    "Firestore operations",
    ["operation", "status"],  # read/write, success/failure
)

firestore_latency = Histogram(
    "firestore_latency_seconds",
    "Firestore operation latency (seconds)",
    ["operation"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0),
)

model_calibration_error = Gauge(
    "model_calibration_error",
    "Absolute difference between predicted trade win probability and realized win rate",
)

model_feature_drift_score = Gauge(
    "model_feature_drift_score",
    "Feature distribution drift score against training baseline",
)

model_concept_drift_score = Gauge(
    "model_concept_drift_score",
    "Concept drift score between training win rate and live win rate",
)

model_concentration_drift_score = Gauge(
    "model_concentration_drift_score",
    "Portfolio concentration drift pressure influencing live model stability",
)

model_degraded_state = Gauge(
    "model_degraded_state",
    "Model degraded state (0=healthy, 1=degraded)",
)

model_retraining_requested = Gauge(
    "model_retraining_requested",
    "Whether the retraining pipeline has been requested (0/1)",
)

trading_frequency_multiplier = Gauge(
    "trading_frequency_multiplier",
    "Multiplier applied to trading frequency and capital allocation under unstable data",
)

portfolio_gross_exposure_pct = Gauge(
    "portfolio_gross_exposure_pct",
    "Current gross portfolio exposure as a fraction of capital",
)

portfolio_max_symbol_exposure_pct = Gauge(
    "portfolio_max_symbol_exposure_pct",
    "Largest single-symbol portfolio exposure as a fraction of capital",
)

portfolio_max_side_exposure_pct = Gauge(
    "portfolio_max_side_exposure_pct",
    "Largest single-side portfolio exposure as a fraction of capital",
)

portfolio_max_theme_exposure_pct = Gauge(
    "portfolio_max_theme_exposure_pct",
    "Largest single-theme portfolio exposure as a fraction of capital",
)

portfolio_max_cluster_exposure_pct = Gauge(
    "portfolio_max_cluster_exposure_pct",
    "Largest behavior-cluster portfolio exposure as a fraction of capital",
)

portfolio_max_beta_bucket_exposure_pct = Gauge(
    "portfolio_max_beta_bucket_exposure_pct",
    "Largest beta-bucket portfolio exposure as a fraction of capital",
)

portfolio_gross_exposure_drift_pct = Gauge(
    "portfolio_gross_exposure_drift_pct",
    "Change in gross portfolio exposure as a fraction of capital",
)

portfolio_cluster_concentration_drift_pct = Gauge(
    "portfolio_cluster_concentration_drift_pct",
    "Change in maximum behavior-cluster concentration as a fraction of capital",
)

portfolio_beta_bucket_concentration_drift_pct = Gauge(
    "portfolio_beta_bucket_concentration_drift_pct",
    "Change in maximum beta-bucket concentration as a fraction of capital",
)

portfolio_cluster_turnover = Gauge(
    "portfolio_cluster_turnover",
    "Fraction of tracked symbols that changed behavior cluster between snapshots",
)

portfolio_factor_sleeve_budget_turnover = Gauge(
    "portfolio_factor_sleeve_budget_turnover",
    "Half-turnover in target sleeve budget shares between portfolio concentration snapshots",
)

portfolio_max_factor_sleeve_budget_gap_pct = Gauge(
    "portfolio_max_factor_sleeve_budget_gap_pct",
    "Largest absolute gap between target and actual sleeve capital share",
)


def get_metrics() -> bytes:
    """Return Prometheus-formatted metrics."""
    return generate_latest()
