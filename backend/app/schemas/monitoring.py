from datetime import datetime

from pydantic import BaseModel


class DrawdownStatus(BaseModel):
    current_equity: float
    peak_equity: float
    rolling_drawdown: float
    state: str
    cooldown_until: datetime | None = None


class RolloutStatus(BaseModel):
    stage_index: int
    stage_name: str = "SHADOW"
    capital_fraction: float
    mode: str
    eligible_for_upgrade: bool
    downgrade_flag: bool = False


class ModelStabilityStatus(BaseModel):
    active_model_version: str
    fallback_model_version: str | None = None
    live_win_rate: float
    training_win_rate: float
    drift_score: float
    calibration_error: float = 0.0
    feature_drift_score: float = 0.0
    concept_drift_score: float = 0.0
    concentration_drift_score: float = 0.0
    retraining_triggered: bool = False
    trading_frequency_multiplier: float = 1.0
    degraded: bool


class ModelUpdateNotice(BaseModel):
    message: str = ""
    model_version: str | None = None
    trigger_mode: str | None = None
    updated_at: datetime | None = None


class ModelPromotionEvent(BaseModel):
    event: str = "promotion"
    model_version: str = "unknown"
    previous_model_version: str | None = None
    promoted_at: datetime | None = None
    summary: str = ""
    recent_validation_accuracy_lift: float = 0.0
    trigger_mode: str | None = None
    training_samples: int = 0
    validation_samples: int = 0


class PortfolioConcentrationStatus(BaseModel):
    gross_exposure_pct: float = 0.0
    max_symbol_exposure_pct: float = 0.0
    max_side_exposure_pct: float = 0.0
    max_theme_exposure_pct: float = 0.0
    max_cluster_exposure_pct: float = 0.0
    max_beta_bucket_exposure_pct: float = 0.0
    gross_exposure_drift: float = 0.0
    cluster_concentration_drift: float = 0.0
    beta_bucket_concentration_drift: float = 0.0
    cluster_turnover: float = 0.0
    factor_sleeve_budget_turnover: float = 0.0
    max_factor_sleeve_budget_gap_pct: float = 0.0
    severity: str = "normal"
    severity_reason: str | None = None
    factor_regime: str = "RANGING"
    factor_model: str = "pca_covariance_regime_universe_v1"
    factor_universe_symbols: list[str] = []
    factor_weights: dict[str, float] = {}
    factor_attribution: dict[str, float] = {}
    factor_sleeve_performance: dict[str, dict[str, float | int | str]] = {}
    factor_sleeve_budget_targets: dict[str, float] = {}
    factor_sleeve_budget_deltas: dict[str, float] = {}
    dominant_factor_sleeve: str | None = None
    dominant_symbol: str | None = None
    dominant_side: str | None = None
    dominant_theme: str | None = None
    dominant_cluster: str | None = None
    dominant_beta_bucket: str | None = None
    dominant_over_budget_sleeve: str | None = None
    dominant_under_budget_sleeve: str | None = None
    top_budget_gaining_sleeves: list[str] = []
    top_budget_losing_sleeves: list[str] = []
    symbol_count: int = 0
    theme_count: int = 0
    cluster_count: int = 0
    beta_bucket_count: int = 0


class PortfolioConcentrationSnapshot(BaseModel):
    updated_at: datetime | None = None
    gross_exposure_pct: float = 0.0
    max_symbol_exposure_pct: float = 0.0
    max_side_exposure_pct: float = 0.0
    max_theme_exposure_pct: float = 0.0
    max_cluster_exposure_pct: float = 0.0
    max_beta_bucket_exposure_pct: float = 0.0
    gross_exposure_drift: float = 0.0
    cluster_concentration_drift: float = 0.0
    beta_bucket_concentration_drift: float = 0.0
    cluster_turnover: float = 0.0
    factor_sleeve_budget_turnover: float = 0.0
    max_factor_sleeve_budget_gap_pct: float = 0.0
    severity: str = "normal"
    severity_reason: str | None = None
    factor_regime: str = "RANGING"
    factor_model: str = "pca_covariance_regime_universe_v1"
    factor_universe_symbols: list[str] = []
    factor_weights: dict[str, float] = {}
    factor_attribution: dict[str, float] = {}
    factor_sleeve_performance: dict[str, dict[str, float | int | str]] = {}
    factor_sleeve_budget_targets: dict[str, float] = {}
    factor_sleeve_budget_deltas: dict[str, float] = {}
    dominant_factor_sleeve: str | None = None
    dominant_symbol: str | None = None
    dominant_side: str | None = None
    dominant_theme: str | None = None
    dominant_cluster: str | None = None
    dominant_beta_bucket: str | None = None
    dominant_over_budget_sleeve: str | None = None
    dominant_under_budget_sleeve: str | None = None
    top_budget_gaining_sleeves: list[str] = []
    top_budget_losing_sleeves: list[str] = []
    symbol_count: int = 0
    theme_count: int = 0
    cluster_count: int = 0
    beta_bucket_count: int = 0


class PortfolioConcentrationHistoryResponse(BaseModel):
    latest: PortfolioConcentrationSnapshot
    history: list[PortfolioConcentrationSnapshot] = []


class ModelStabilityConcentrationHistoryEntry(BaseModel):
    updated_at: datetime | None = None
    score: float = 0.0
    gross_exposure_drift: float = 0.0
    cluster_concentration_drift: float = 0.0
    beta_bucket_concentration_drift: float = 0.0
    cluster_turnover: float = 0.0
    factor_sleeve_budget_turnover: float = 0.0
    max_factor_sleeve_budget_gap_pct: float = 0.0
    severity: str = "normal"
    severity_reason: str | None = None


class ModelStabilityConcentrationHistoryResponse(BaseModel):
    latest_status: ModelStabilityStatus
    latest_state: ModelStabilityConcentrationHistoryEntry
    history: list[ModelStabilityConcentrationHistoryEntry] = []
    latest_notice: ModelUpdateNotice | None = None
    latest_promotion: ModelPromotionEvent | None = None


class SystemHealthResponse(BaseModel):
    trading_mode: str
    api_status: str
    latency_ms_p50: float
    latency_ms_p95: float
    active_trades: int
    error_count: int
    duplicate_signals_blocked: int
    total_signals: int = 0
    whale_veto_blocked: int = 0
    blocked_profitable_signals: int = 0
    veto_efficiency_ratio: float = 0.0
    execution_latency_ms: float = 0.0
    execution_slippage_bps: float = 0.0
    failed_orders: int = 0
    partial_fills: int = 0
    slippage_spikes: int = 0
    degraded_mode: bool = False
    drawdown: DrawdownStatus
    rollout: RolloutStatus
    model_stability: ModelStabilityStatus
    portfolio_concentration: PortfolioConcentrationStatus
