from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    service_name: str = "ai-trading-backend"
    environment: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: str = "INFO"
    trading_mode: Literal["paper", "live"] = "paper"
    json_logs: bool = True

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    firestore_project_id: str = ""
    google_application_credentials: str = ""
    secret_manager_project_id: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = "black-swan-intel"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    redis_url: str = "redis://redis:6379/0"
    market_data_cache_ttl: int = 15
    model_dir: str = "artifacts"

    default_quote_asset: str = "USDT"
    base_risk_per_trade: float = 0.02
    daily_loss_limit: float = 0.05
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
    alpha_trade_threshold: float = 60.0
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

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
