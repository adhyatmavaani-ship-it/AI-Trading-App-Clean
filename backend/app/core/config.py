import json
import os
from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_app_version() -> str:
    return (
        os.environ.get("APP_VERSION")
        or os.environ.get("RENDER_GIT_COMMIT")
        or "unknown"
    )


def _short_app_version(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) == 40 and all(ch in "0123456789abcdef" for ch in normalized.lower()):
        return normalized[:7]
    return normalized or "unknown"


class Settings(BaseSettings):
    service_name: str = "ai-trading-backend"
    app_version: str = Field(default_factory=_default_app_version)
    app_version_short: str = Field(default_factory=lambda: _short_app_version(_default_app_version()))
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    debug_routes_enabled: bool = False
    log_level: str = "INFO"
    trading_mode: Literal["paper", "live"] = "paper"
    json_logs: bool = True
    # CORS_ALLOWED_ORIGINS accepts either:
    # - JSON: ["https://myapp.onrender.com", "http://localhost:3000"]
    # - CSV:  https://myapp.onrender.com,http://localhost:3000
    #
    # Wildcard origins are intentionally blocked in production because they
    # disable origin-level access control for browser clients.
    cors_allowed_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = False
    cors_allow_wildcard_non_prod: bool = False
    # PUBLIC_BASE_URL should be the canonical frontend/backend public origin,
    # for example: https://ai-trading-app-clean.onrender.com
    public_base_url: str = ""

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = False
    primary_exchange: str = "binance"
    backup_exchanges: list[str] = Field(default_factory=lambda: ["kraken", "coinbase"])
    market_data_mode: Literal["auto", "exchange", "simulated"] = "auto"
    market_data_exchange_retry_seconds: float = 30.0
    supported_quote_assets: list[str] = Field(default_factory=lambda: ["USDT", "USDC", "USD", "BTC", "ETH", "EUR", "GBP"])
    kraken_api_key: str = ""
    kraken_api_secret: str = ""
    coinbase_api_key: str = ""
    coinbase_api_secret: str = ""
    coinbase_api_passphrase: str = ""

    firestore_project_id: str = ""
    google_credentials_json: str = ""
    google_application_credentials: str = ""
    secret_manager_project_id: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = "black-swan-intel"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    redis_url: str = ""
    market_data_cache_ttl: int = 15
    model_dir: str = "artifacts"
    training_buffer_path: str = "artifacts/training_buffer.sqlite3"

    default_quote_asset: str = "USDT"
    base_risk_per_trade: float = 0.01
    daily_loss_limit: float = 0.03
    user_max_capital_allocation_pct: float = 0.20
    max_consecutive_losses: int = 3
    slippage_bps: int = 25
    taker_fee_bps: int = 10
    maker_fee_bps: int = 5
    abnormal_loss_limit: float = 0.08
    global_max_capital_loss: float = 0.10
    max_coin_exposure_pct: float = 0.20
    max_portfolio_exposure_pct: float = 0.65
    max_portfolio_side_exposure_pct: float = 0.45
    max_portfolio_theme_exposure_pct: float = 0.35
    max_portfolio_cluster_exposure_pct: float = 0.40
    max_portfolio_beta_bucket_exposure_pct: float = 0.45
    portfolio_correlation_reduce_threshold: float = 0.65
    portfolio_correlation_min_multiplier: float = 0.40
    portfolio_correlation_lookback_candles: int = 96
    portfolio_correlation_min_overlap: int = 24
    portfolio_cluster_correlation_threshold: float = 0.80
    portfolio_same_symbol_penalty: float = 0.75
    portfolio_theme_map_json: str = ""
    portfolio_factor_basket_json: str = ""
    portfolio_factor_active_symbol_limit: int = 4
    portfolio_concentration_history_limit: int = 96
    portfolio_factor_history_limit: int = 96
    portfolio_factor_performance_window_trades: int = 20
    portfolio_factor_sleeve_budget_floor: float = 0.08
    portfolio_factor_sleeve_budget_cap: float = 0.45
    portfolio_concentration_soft_alert_drift: float = 0.04
    portfolio_concentration_hard_alert_drift: float = 0.08
    portfolio_concentration_soft_turnover: float = 0.20
    portfolio_concentration_hard_turnover: float = 0.40
    default_portfolio_balance: float = 10_000
    atr_period: int = 14
    paper_fill_noise_bps: int = 5
    rate_limit_per_minute: int = 120
    rate_limit_per_hour: int = 2_000
    optimization_cache_ttl_seconds: int = 900
    optimization_max_parallelism: int = 4
    trade_probability_threshold: float = 0.55
    probability_position_floor: float = 0.35
    probability_position_ceiling: float = 1.15
    probability_position_smoothing: float = 1.5
    regime_trending_size_boost: float = 0.25
    regime_ranging_size_multiplier: float = 0.70
    regime_high_vol_size_multiplier: float = 0.50
    regime_high_vol_skip_volatility: float = 0.06
    regime_position_smoothing: float = 0.20
    probability_min_training_samples: int = 30
    probability_training_window_days: int = 180
    probability_validation_split: float = 0.25
    probability_min_validation_samples: int = 12
    probability_min_precision: float = 0.50
    probability_max_calibration_error: float = 0.18
    probability_training_frequency_hours: int = 24
    retrain_batch_size: int = 50
    retrain_recent_trade_window: int = 10
    retrain_emergency_win_rate_floor: float = 0.40
    retrain_recent_validation_trades: int = 10
    retrain_min_accuracy_lift: float = 0.05
    retrain_high_confidence_threshold: float = 0.75
    retrain_high_confidence_loss_weight: float = 2.0
    retrain_manual_rollback_cooldown_hours: int = 48
    probability_live_window_size: int = 200
    probability_feature_drift_threshold: float = 0.20
    probability_concept_drift_threshold: float = 0.18
    probability_concentration_drift_threshold: float = 0.10
    probability_concentration_turnover_threshold: float = 0.45
    probability_concentration_reduction_threshold: float = 0.06
    model_stability_concentration_history_limit: int = 32
    probability_frequency_reduction_threshold: float = 0.12
    probability_reduced_trading_multiplier: float = 0.5
    ai_fallback_confidence_threshold: float = 0.60
    ai_layer_disable_ttl_seconds: int = 900
    alert_webhook_url: str = ""
    auth_api_keys_json: str = ""
    auth_cache_ttl_seconds: int = 300
    auth_api_keys_collection: str = "api_keys"
    trust_forwarded_for: bool = True
    rolling_drawdown_limit: float = 0.06
    pause_drawdown_limit: float = 0.10
    cooldown_minutes: int = 60
    drawdown_reduction_factor: float = 0.50
    signal_dedup_ttl_seconds: int = 3600
    monitor_state_ttl_seconds: int = 86_400
    portfolio_snapshot_cache_ttl_seconds: int = 2
    model_drift_threshold: float = 0.15
    rollout_min_trades: int = 50
    rollout_win_rate_threshold: float = 0.53
    rollout_profit_factor_threshold: float = 1.10
    rollout_stages: list[float] = Field(default_factory=lambda: [0.0, 0.01, 0.10, 0.25])
    rebalance_interval_hours: int = 24
    correlation_penalty_threshold: float = 0.75
    private_rpc_url: str = ""
    transaction_relay_url: str = ""
    ethereum_rpc_url: str = ""
    solana_rpc_url: str = ""
    base_rpc_url: str = ""
    ethereum_ws_url: str = ""
    solana_ws_url: str = ""
    base_ws_url: str = ""
    auto_trade_on_whale_signal: bool = False
    alpha_trade_threshold: float = 40.0
    max_slippage_bps: int = 35
    trade_safety_max_slippage_bps: int = 35
    trade_safety_min_liquidity_coverage_ratio: float = 1.0
    trade_safety_max_volatility: float = 0.05
    execution_chunk_delay_ms: int = 350
    chunk_delay_min_seconds: int = 5
    chunk_delay_max_seconds: int = 45
    latency_spike_threshold_ms: int = 200
    min_net_profit_threshold: float = 0.001
    micro_single_trade_capital_threshold: float = 50.0
    micro_max_capital_threshold: float = 100.0
    exchange_min_notional: float = 10.0
    micro_slippage_threshold_bps: int = 150
    micro_min_alpha_score: float = 80.0
    micro_max_trades_small_account: int = 2
    micro_max_trades_standard: int = 5
    micro_daily_loss_limit: float = 0.03
    signal_broadcast_channel: str = "signals:central"
    signal_execution_channel: str = "signals:fanout"
    live_activity_channel: str = "live_activity"
    signal_version_ttl_seconds: int = 604_800
    websocket_listener_enabled: bool = True
    websocket_redis_reconnect_seconds: float = 1.0
    execution_shard_count: int = 64
    execution_queue_batch_size: int = 250
    randomized_execution_delay_min_ms: int = 250
    randomized_execution_delay_max_ms: int = 3_000
    delayed_queue_min_ms: int = 15_000
    delayed_queue_max_ms: int = 90_000
    high_priority_alpha_threshold: float = 90.0
    execution_rate_limit_per_second: int = 8
    enable_virtual_order_management: bool = True
    virtual_order_window_ms: int = 5_000
    virtual_order_max_retries: int = 3
    virtual_order_precision: int = 8

    websocket_symbols: list[str] = Field(
        default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )
    market_universe_symbols: list[str] = Field(
        default_factory=lambda: [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "BNBUSDT",
            "XRPUSDT",
            "ADAUSDT",
            "DOGEUSDT",
            "AVAXUSDT",
            "LINKUSDT",
            "DOTUSDT",
            "MATICUSDT",
            "PEPEUSDT",
            "SUIUSDT",
            "ARBUSDT",
            "OPUSDT",
            "APTUSDT",
            "NEARUSDT",
            "ATOMUSDT",
        ]
    )
    market_universe_scan_limit: int = 18
    market_universe_refresh_seconds: float = 5.0
    scanner_fixed_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    scanner_candidate_limit: int = 50
    scanner_active_symbol_limit: int = 10
    scanner_rotation_hours: int = 4
    scanner_refresh_minutes: int = 15
    scanner_min_quote_volume: float = 1_000_000.0
    dual_track_bias_ttl_seconds: int = 900
    dual_track_warmup_ttl_seconds: int = 120
    dual_track_brain_poll_seconds: int = 5
    dual_track_sniper_min_rsi: float = 52.0
    dual_track_sniper_max_rsi: float = 48.0
    self_heal_evening_hour_utc: int = 20
    self_heal_evening_minute_utc: int = 0
    sniper_threshold_ttl_seconds: int = 604800
    meta_max_trades_per_hour: int = 12
    meta_health_max_latency_ms: float = 250.0
    meta_health_min_api_success_rate: float = 0.95
    meta_health_max_redis_latency_ms: float = 15.0
    meta_sniper_volatility_ceiling: float = 0.02
    meta_ai_volatility_ceiling: float = 0.06
    meta_min_liquidity_stability: float = 0.55
    meta_conflict_gate_threshold: float = 0.35
    meta_risk_reduction_multiplier: float = 0.5
    meta_winning_streak_step: float = 0.05
    meta_max_capital_boost: float = 1.25
    meta_bearish_macro_multiplier: float = 0.5
    meta_regime_min_win_rate: float = 0.48
    meta_regime_target_win_rate: float = 0.58
    meta_regime_min_r_multiple: float = 0.0
    meta_regime_target_r_multiple: float = 0.75
    meta_regime_drawdown_soft_limit: float = 0.04
    meta_regime_drawdown_hard_limit: float = 0.06
    meta_min_capital_multiplier: float = 0.25
    meta_concentration_soft_limit_ratio: float = 0.85
    meta_concentration_hard_limit_ratio: float = 0.98
    meta_concentration_reduction_multiplier: float = 0.70
    meta_factor_sleeve_soft_limit: float = 0.35
    meta_factor_sleeve_hard_limit: float = 0.55
    meta_factor_sleeve_recent_win_rate_floor: float = 0.45
    meta_factor_sleeve_rotation_boost: float = 1.08
    meta_factor_sleeve_rotation_floor: float = 0.65
    meta_factor_sleeve_skip_win_rate: float = 0.35
    meta_factor_sleeve_skip_avg_pnl: float = -0.01
    meta_factor_sleeve_priority_boost: float = 1.08
    meta_factor_sleeve_priority_floor: float = 0.90
    probability_factor_sleeve_priority_boost: float = 1.06
    probability_factor_sleeve_priority_floor: float = 0.92
    signal_safe_test_mode: bool = True
    signal_min_publish_confidence: float = 0.20
    signal_force_min_candidates: int = 1
    signal_diagnostics_limit: int = 10
    user_experience_mode: Literal["low", "medium", "high"] = "low"
    activity_history_limit: int = 100
    activity_near_miss_score_delta: float = 10.0
    strict_trade_score_threshold: float = 70.0
    strict_trade_confidence_floor: float = 0.70
    force_execution_override_enabled: bool = False
    force_execution_override_confidence_floor: float = 0.35
    strict_trade_volume_spike_threshold: float = 1.50
    strict_trade_structure_adx_floor: float = 22.0
    max_active_trades: int = 2
    learning_enabled: bool = True
    learning_min_pattern_samples: int = 4
    learning_blacklist_win_rate_threshold: float = 0.35
    learning_whitelist_win_rate_threshold: float = 0.65
    learning_confidence_penalty: float = 0.18
    learning_confidence_boost: float = 0.10
    learning_score_penalty: float = 18.0
    learning_score_boost: float = 8.0
    learning_memory_ttl_seconds: int = 2_592_000
    strict_trade_partial_take_profit_rr: float = 1.0
    strict_trade_min_take_profit_rr: float = 1.5
    strict_trade_partial_take_profit_fraction: float = 0.4
    active_trade_monitor_enabled: bool = True
    active_trade_monitor_interval_seconds: float = 5.0
    active_trade_monitor_opposite_candle_atr_threshold: float = 1.0
    active_trade_monitor_volume_spike_threshold: float = 1.5
    active_trade_monitor_break_even_rr: float = 1.2
    active_trade_monitor_break_even_lock_rr: float = 0.1
    trailing_aggressiveness: float = 1.0
    risk_profile_low_confidence_floor: float = 0.85
    risk_profile_medium_confidence_floor: float = 0.70
    risk_profile_high_confidence_floor: float = 0.60
    risk_profile_low_daily_loss_limit: float = 0.01
    risk_profile_medium_daily_loss_limit: float = 0.03
    risk_profile_high_daily_loss_limit: float = 0.07
    risk_profile_low_risk_fraction: float = 0.005
    risk_profile_medium_risk_fraction: float = 0.01
    risk_profile_high_risk_fraction: float = 0.015
    risk_profile_low_max_active_trades: int = 1
    risk_profile_medium_max_active_trades: int = 2
    risk_profile_high_max_active_trades: int = 3
    risk_profile_low_allowed_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    risk_profile_medium_allowed_symbols: list[str] = Field(default_factory=list)
    risk_profile_high_allowed_symbols: list[str] = Field(default_factory=list)
    local_paper_active_rollout_fraction: float = 1.0
    regime_trending_ema_spread_threshold: float = 0.003
    regime_high_vol_atr_multiplier: float = 1.5
    regime_low_vol_atr_multiplier: float = 0.7
    regime_ranging_structure_penalty: float = 0.7
    regime_high_vol_allocation_multiplier: float = 0.75
    regime_low_vol_trade_frequency_multiplier: float = 0.85
    regime_trending_allocation_multiplier: float = 1.1
    symbol_priority_allocation_boost: float = 1.1
    portfolio_base_risk_per_trade: float = 0.01
    portfolio_confidence_risk_boost_threshold: float = 0.8
    portfolio_confidence_risk_boost_multiplier: float = 1.2
    portfolio_symbol_score_boost_threshold: float = 0.6
    portfolio_symbol_score_boost_multiplier: float = 1.3
    portfolio_trending_risk_multiplier: float = 1.2
    portfolio_high_vol_risk_multiplier: float = 0.6
    portfolio_low_vol_risk_multiplier: float = 0.85
    portfolio_max_risk_per_trade: float = 0.02
    portfolio_max_total_risk: float = 0.05
    portfolio_max_correlated_trades: int = 2
    portfolio_drawdown_soft_threshold: float = 0.05
    portfolio_drawdown_hard_threshold: float = 0.10
    portfolio_drawdown_soft_multiplier: float = 0.75
    portfolio_drawdown_hard_multiplier: float = 0.5
    strategy_stability_lock_lookback_trades: int = 10
    confluence_weight_structure: float = 0.4
    confluence_weight_momentum: float = 0.3
    confluence_weight_volume: float = 0.3
    confluence_weight_min_bound: float = 0.1
    confluence_weight_max_bound: float = 0.7
    symbol_priority_min_multiplier: float = 0.7
    symbol_priority_max_multiplier: float = 1.3
    symbol_priority_min_trades: int = 3
    symbol_priority_bad_win_rate: float = 0.40
    symbol_priority_good_win_rate: float = 0.60
    symbol_priority_step: float = 0.1
    strategy_optimizer_enabled: bool = True
    strategy_optimizer_interval_seconds: float = 300.0
    strategy_adaptation_cooldown_seconds: int = 3600
    analytics_history_limit: int = 500
    backtest_data_dir: str = "backtest_data"
    backtest_chunk_hours: int = 24
    backtest_cache_ttl_seconds: int = 86_400
    backtest_job_history_limit: int = 200
    backtest_max_days: int = 30
    backtest_min_days: int = 1
    backtest_status_log_limit: int = 200
    backtest_status_poll_seconds: float = 2.0
    backtest_heartbeat_seconds: float = 5.0
    backtest_resume_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return []
            if normalized.startswith("["):
                try:
                    parsed = json.loads(normalized)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in normalized.split(",") if item.strip()]
        return value

    @property
    def render_external_url(self) -> str:
        return str(os.environ.get("RENDER_EXTERNAL_URL", "") or "").strip()

    @property
    def is_production(self) -> bool:
        return str(self.environment).lower() == "prod"

    @property
    def effective_debug_routes_enabled(self) -> bool:
        if self.debug_routes_enabled:
            return True
        return not self.is_production

    def _default_public_origin(self) -> str:
        for candidate in (self.public_base_url, self.render_external_url):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _is_valid_cors_origin(origin: str) -> bool:
        parsed = urlparse(str(origin or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _is_loopback_origin(origin: str) -> bool:
        parsed = urlparse(str(origin or "").strip())
        host = str(parsed.hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "0.0.0.0"}

    def _resolve_cors_allowed_origins(self, warnings: list[str], errors: list[str]) -> list[str]:
        origins = [str(origin).strip().rstrip("/") for origin in self.cors_allowed_origins if str(origin).strip()]
        default_origin = self._default_public_origin()

        if not origins:
            if default_origin:
                warnings.append(
                    "CORS_ALLOWED_ORIGINS was not set; defaulting to PUBLIC_BASE_URL/RENDER_EXTERNAL_URL"
                )
                return [default_origin]
            if not self.is_production and self.cors_allow_wildcard_non_prod:
                warnings.append(
                    "CORS_ALLOWED_ORIGINS was not set; falling back to '*' because CORS_ALLOW_WILDCARD_NON_PROD=true"
                )
                return ["*"]
            if self.is_production:
                errors.append(
                    "CORS_ALLOWED_ORIGINS is required in prod when PUBLIC_BASE_URL or RENDER_EXTERNAL_URL is unavailable. "
                    'Example: CORS_ALLOWED_ORIGINS=["https://myapp.onrender.com","http://localhost:3000"]'
                )
            return []

        if "*" in origins:
            if self.is_production:
                errors.append(
                    "CORS_ALLOWED_ORIGINS cannot contain '*' in prod. "
                    'Set explicit origins instead, for example: CORS_ALLOWED_ORIGINS=["https://myapp.onrender.com","http://localhost:3000"]'
                )
                return origins
            if not self.cors_allow_wildcard_non_prod:
                errors.append(
                    "CORS_ALLOWED_ORIGINS cannot contain '*' unless CORS_ALLOW_WILDCARD_NON_PROD=true in local/dev/staging."
                )
                return origins
            warnings.append("CORS_ALLOWED_ORIGINS includes '*' for non-production use")
            return ["*"]

        invalid_origins = [origin for origin in origins if not self._is_valid_cors_origin(origin)]
        if invalid_origins:
            errors.append(
                "CORS_ALLOWED_ORIGINS contains invalid origin values: "
                + ", ".join(invalid_origins)
                + '. Example: ["https://myapp.onrender.com","http://localhost:3000"]'
            )
        if self.is_production:
            loopback_origins = [origin for origin in origins if self._is_loopback_origin(origin)]
            if loopback_origins:
                warnings.append(
                    "CORS_ALLOWED_ORIGINS contained loopback origins in prod and they were removed: "
                    + ", ".join(loopback_origins)
                )
                origins = [origin for origin in origins if origin not in loopback_origins]
                if not origins:
                    if default_origin:
                        warnings.append(
                            "All configured prod CORS origins were loopback-only; defaulting to PUBLIC_BASE_URL/RENDER_EXTERNAL_URL"
                        )
                        return [default_origin]
                    errors.append(
                        "CORS_ALLOWED_ORIGINS cannot be loopback-only in prod. "
                        'Set explicit public origins, for example: CORS_ALLOWED_ORIGINS=["https://myapp.onrender.com"]'
                    )
        return origins

    @staticmethod
    def _validate_google_credentials_json(raw_json: str) -> None:
        normalized = str(raw_json or "").strip()
        if not normalized:
            raise ValueError("GOOGLE_CREDENTIALS_JSON is required when FIRESTORE_PROJECT_ID is configured")
        try:
            parsed = json.loads(normalized)
        except json.JSONDecodeError as exc:
            raise ValueError(f"GOOGLE_CREDENTIALS_JSON must be valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("GOOGLE_CREDENTIALS_JSON must be a JSON object")
        required_fields = (
            "type",
            "project_id",
            "private_key_id",
            "private_key",
            "client_email",
            "client_id",
            "token_uri",
        )
        missing_fields = [field for field in required_fields if not str(parsed.get(field) or "").strip()]
        if missing_fields:
            raise ValueError(
                "GOOGLE_CREDENTIALS_JSON is missing required fields: "
                + ", ".join(missing_fields)
            )

    def validate_runtime_safety(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        self.cors_allowed_origins = self._resolve_cors_allowed_origins(warnings, errors)

        if self.firestore_project_id:
            try:
                self._validate_google_credentials_json(self.google_credentials_json)
            except ValueError as exc:
                errors.append(str(exc))

        if self.is_production:
            if self.force_execution_override_enabled:
                errors.append("FORCE_EXECUTION_OVERRIDE_ENABLED must be false in prod")
            if not self.auth_api_keys_json and not self.firestore_project_id:
                errors.append("prod requires AUTH_API_KEYS_JSON or FIRESTORE_PROJECT_ID for authenticated access")
            if self.binance_testnet:
                errors.append("BINANCE_TESTNET must be false in prod")
            if self.training_buffer_path.strip().lower().endswith(".sqlite3"):
                warnings.append(
                    "TRAINING_BUFFER_PATH points to a local sqlite file in prod; use managed persistence or a mounted persistent disk for authoritative training data"
                )

        if self.trading_mode == "live":
            live_credential_sets = (
                bool(self.binance_api_key and self.binance_api_secret),
                bool(self.kraken_api_key and self.kraken_api_secret),
                bool(self.coinbase_api_key and self.coinbase_api_secret and self.coinbase_api_passphrase),
            )
            if not any(live_credential_sets):
                errors.append("TRADING_MODE=live requires at least one configured live exchange credential set")
            if self.environment != "prod":
                warnings.append("TRADING_MODE=live outside prod should be restricted to controlled staging only")

        if errors:
            raise ValueError("; ".join(errors))

        setattr(self, "_runtime_warnings", warnings)

    @property
    def runtime_warnings(self) -> list[str]:
        return list(getattr(self, "_runtime_warnings", []))


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_safety()
    return settings
