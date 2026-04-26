from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


ALLOWED_STRATEGIES = {"ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"}
REQUIRED_RISK_KEYS = {
    "BASE_RISK_PER_TRADE",
    "DAILY_LOSS_LIMIT",
    "GLOBAL_MAX_CAPITAL_LOSS",
    "ROLLING_DRAWDOWN_LIMIT",
    "PAUSE_DRAWDOWN_LIMIT",
    "MAX_COIN_EXPOSURE_PCT",
}
MAX_BASE_RISK_PER_TRADE = 0.02
MAX_DAILY_LOSS_LIMIT = 0.05
MAX_GLOBAL_MAX_CAPITAL_LOSS = 0.10
MAX_ROLLING_DRAWDOWN_LIMIT = 0.06
MAX_PAUSE_DRAWDOWN_LIMIT = 0.10
MAX_COIN_EXPOSURE_PCT = 0.20
REQUIRED_CANARY_WEIGHT = 10


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a YAML object")
    return payload


def _to_float(config: dict, key: str) -> float:
    value = str(config[key]).strip()
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"config.{key} must be numeric") from exc


def _validate_manifest(manifest: dict, path: Path) -> None:
    ai_model_version = str(manifest.get("ai_model_version", "")).strip()
    if not ai_model_version:
        raise ValueError(f"{path}: ai_model_version is required")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", ai_model_version):
        raise ValueError(f"{path}: ai_model_version contains unsupported characters")

    strategy = manifest.get("strategy")
    if not isinstance(strategy, dict):
        raise ValueError(f"{path}: strategy configuration is required")
    default_strategy = str(strategy.get("default", "")).strip()
    enabled = strategy.get("enabled")
    if default_strategy not in ALLOWED_STRATEGIES:
        raise ValueError(f"{path}: strategy.default is unsupported")
    if not isinstance(enabled, list) or not enabled:
        raise ValueError(f"{path}: strategy.enabled must be a non-empty list")
    normalized_enabled = [str(item).strip() for item in enabled]
    if any(item not in ALLOWED_STRATEGIES for item in normalized_enabled):
        raise ValueError(f"{path}: strategy.enabled contains unsupported strategies")
    if default_strategy not in normalized_enabled:
        raise ValueError(f"{path}: strategy.default must exist in strategy.enabled")


def _validate_values(values: dict, path: Path, manifest: dict) -> None:
    config = values.get("config")
    if not isinstance(config, dict):
        raise ValueError(f"{path}: config section is required")

    missing = sorted(key for key in REQUIRED_RISK_KEYS if key not in config or str(config[key]).strip() == "")
    if missing:
        raise ValueError(f"{path}: missing required config keys: {', '.join(missing)}")

    base_risk = _to_float(config, "BASE_RISK_PER_TRADE")
    daily_loss_limit = _to_float(config, "DAILY_LOSS_LIMIT")
    global_max_capital_loss = _to_float(config, "GLOBAL_MAX_CAPITAL_LOSS")
    rolling_drawdown_limit = _to_float(config, "ROLLING_DRAWDOWN_LIMIT")
    pause_drawdown_limit = _to_float(config, "PAUSE_DRAWDOWN_LIMIT")
    max_coin_exposure = _to_float(config, "MAX_COIN_EXPOSURE_PCT")

    if base_risk > MAX_BASE_RISK_PER_TRADE:
        raise ValueError(f"{path}: unsafe BASE_RISK_PER_TRADE {base_risk:.4f} > {MAX_BASE_RISK_PER_TRADE:.4f}")
    if daily_loss_limit > MAX_DAILY_LOSS_LIMIT:
        raise ValueError(f"{path}: unsafe DAILY_LOSS_LIMIT {daily_loss_limit:.4f} > {MAX_DAILY_LOSS_LIMIT:.4f}")
    if global_max_capital_loss > MAX_GLOBAL_MAX_CAPITAL_LOSS:
        raise ValueError(
            f"{path}: unsafe GLOBAL_MAX_CAPITAL_LOSS {global_max_capital_loss:.4f} > {MAX_GLOBAL_MAX_CAPITAL_LOSS:.4f}"
        )
    if rolling_drawdown_limit > MAX_ROLLING_DRAWDOWN_LIMIT:
        raise ValueError(
            f"{path}: unsafe ROLLING_DRAWDOWN_LIMIT {rolling_drawdown_limit:.4f} > {MAX_ROLLING_DRAWDOWN_LIMIT:.4f}"
        )
    if pause_drawdown_limit > MAX_PAUSE_DRAWDOWN_LIMIT:
        raise ValueError(
            f"{path}: unsafe PAUSE_DRAWDOWN_LIMIT {pause_drawdown_limit:.4f} > {MAX_PAUSE_DRAWDOWN_LIMIT:.4f}"
        )
    if pause_drawdown_limit < rolling_drawdown_limit:
        raise ValueError(f"{path}: PAUSE_DRAWDOWN_LIMIT must be >= ROLLING_DRAWDOWN_LIMIT")
    if max_coin_exposure > MAX_COIN_EXPOSURE_PCT:
        raise ValueError(
            f"{path}: unsafe MAX_COIN_EXPOSURE_PCT {max_coin_exposure:.4f} > {MAX_COIN_EXPOSURE_PCT:.4f}"
        )

    expected_model_version = str(manifest["ai_model_version"]).strip()
    actual_model_version = str(config.get("AI_MODEL_VERSION", "")).strip()
    if not actual_model_version:
        raise ValueError(f"{path}: missing required config key: AI_MODEL_VERSION")
    if actual_model_version != expected_model_version:
        raise ValueError(
            f"{path}: AI_MODEL_VERSION {actual_model_version} does not match manifest ai_model_version {expected_model_version}"
        )

    expected_default_strategy = str(manifest["strategy"]["default"]).strip()
    actual_default_strategy = str(config.get("DEFAULT_STRATEGY", "")).strip()
    if not actual_default_strategy:
        raise ValueError(f"{path}: missing required config key: DEFAULT_STRATEGY")
    if actual_default_strategy != expected_default_strategy:
        raise ValueError(
            f"{path}: DEFAULT_STRATEGY {actual_default_strategy} does not match manifest strategy.default {expected_default_strategy}"
        )

    enabled_strategies_raw = str(config.get("ENABLED_STRATEGIES", "")).strip()
    if not enabled_strategies_raw:
        raise ValueError(f"{path}: missing required config key: ENABLED_STRATEGIES")
    configured_enabled = [item.strip() for item in enabled_strategies_raw.split(",") if item.strip()]
    if configured_enabled != manifest["strategy"]["enabled"]:
        raise ValueError(f"{path}: ENABLED_STRATEGIES does not match manifest strategy.enabled")

    canary = values.get("canary")
    if canary is None:
        return
    if not isinstance(canary, dict):
        raise ValueError(f"{path}: canary section must be an object")
    weight = int(canary.get("weight", 0))
    if weight != REQUIRED_CANARY_WEIGHT:
        raise ValueError(f"{path}: canary.weight must be {REQUIRED_CANARY_WEIGHT} for the supported rollout policy")
    analysis = canary.get("analysis")
    if not isinstance(analysis, dict):
        raise ValueError(f"{path}: canary.analysis section is required")
    for key in (
        "durationSeconds",
        "intervalSeconds",
        "maxErrorRate",
        "minTradeSuccessRate",
        "maxLatencyMs",
        "maxGrossExposurePct",
        "maxSymbolExposurePct",
        "maxThemeExposurePct",
        "maxClusterExposurePct",
        "maxBetaBucketExposurePct",
        "maxGrossExposureDriftPct",
        "maxClusterConcentrationDriftPct",
        "maxBetaBucketConcentrationDriftPct",
        "maxClusterTurnover",
        "maxFactorSleeveBudgetTurnover",
        "maxFactorSleeveBudgetGapPct",
        "minimumRequestSamples",
        "minimumTradeSamples",
    ):
        if key not in analysis or str(analysis[key]).strip() == "":
            raise ValueError(f"{path}: canary.analysis.{key} is required")
    duration_seconds = int(analysis["durationSeconds"])
    interval_seconds = int(analysis["intervalSeconds"])
    max_error_rate = float(analysis["maxErrorRate"])
    min_trade_success_rate = float(analysis["minTradeSuccessRate"])
    max_latency_ms = float(analysis["maxLatencyMs"])
    minimum_request_samples = int(analysis["minimumRequestSamples"])
    minimum_trade_samples = int(analysis["minimumTradeSamples"])

    if duration_seconds <= 0:
        raise ValueError(f"{path}: canary.analysis.durationSeconds must be positive")
    if interval_seconds <= 0:
        raise ValueError(f"{path}: canary.analysis.intervalSeconds must be positive")
    if interval_seconds > duration_seconds:
        raise ValueError(f"{path}: canary.analysis.intervalSeconds must be <= durationSeconds")
    if not 0.0 <= max_error_rate <= 1.0:
        raise ValueError(f"{path}: canary.analysis.maxErrorRate must be between 0 and 1")
    if not 0.0 <= min_trade_success_rate <= 1.0:
        raise ValueError(f"{path}: canary.analysis.minTradeSuccessRate must be between 0 and 1")
    if max_latency_ms <= 0:
        raise ValueError(f"{path}: canary.analysis.maxLatencyMs must be positive")
    for key in (
        "maxGrossExposurePct",
        "maxSymbolExposurePct",
        "maxThemeExposurePct",
        "maxClusterExposurePct",
        "maxBetaBucketExposurePct",
        "maxGrossExposureDriftPct",
        "maxClusterConcentrationDriftPct",
        "maxBetaBucketConcentrationDriftPct",
        "maxClusterTurnover",
        "maxFactorSleeveBudgetTurnover",
        "maxFactorSleeveBudgetGapPct",
    ):
        value = float(analysis[key])
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{path}: canary.analysis.{key} must be between 0 and 1")
    if minimum_request_samples <= 0:
        raise ValueError(f"{path}: canary.analysis.minimumRequestSamples must be positive")
    if minimum_trade_samples < 0:
        raise ValueError(f"{path}: canary.analysis.minimumTradeSamples must be >= 0")

    ingress = values.get("ingress")
    if not isinstance(ingress, dict) or not ingress.get("enabled"):
        raise ValueError(f"{path}: ingress.enabled must be true for weighted canary routing")

    rollout_monitoring = values.get("rolloutMonitoring")
    if not isinstance(rollout_monitoring, dict) or not rollout_monitoring.get("enabled", True):
        raise ValueError(f"{path}: rolloutMonitoring.enabled must be true for post-promotion rollback protection")
    for section_name in ("prometheus", "alertmanager", "analysis"):
        if not isinstance(rollout_monitoring.get(section_name), dict):
            raise ValueError(f"{path}: rolloutMonitoring.{section_name} section is required")
    for section_name in ("prometheus", "alertmanager"):
        section = rollout_monitoring[section_name]
        for key in ("namespace", "serviceName", "port"):
            if str(section.get(key, "")).strip() == "":
                raise ValueError(f"{path}: rolloutMonitoring.{section_name}.{key} is required")
        if int(section["port"]) <= 0:
            raise ValueError(f"{path}: rolloutMonitoring.{section_name}.port must be positive")
    rollout_analysis = rollout_monitoring["analysis"]
    for key in (
        "durationSeconds",
        "intervalSeconds",
        "lookbackWindow",
        "maxErrorRate",
        "minTradeSuccessRate",
        "maxLatencyMs",
        "maxGrossExposurePct",
        "maxSymbolExposurePct",
        "maxThemeExposurePct",
        "maxClusterExposurePct",
        "maxBetaBucketExposurePct",
        "maxGrossExposureDriftPct",
        "maxClusterConcentrationDriftPct",
        "maxBetaBucketConcentrationDriftPct",
        "maxClusterTurnover",
        "maxFactorSleeveBudgetTurnover",
        "maxFactorSleeveBudgetGapPct",
        "minimumRequestSamples",
        "minimumTradeSamples",
        "alertNames",
    ):
        if key not in rollout_analysis or str(rollout_analysis[key]).strip() == "":
            raise ValueError(f"{path}: rolloutMonitoring.analysis.{key} is required")
    if int(rollout_analysis["durationSeconds"]) <= 0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.durationSeconds must be positive")
    if int(rollout_analysis["intervalSeconds"]) <= 0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.intervalSeconds must be positive")
    if int(rollout_analysis["intervalSeconds"]) > int(rollout_analysis["durationSeconds"]):
        raise ValueError(f"{path}: rolloutMonitoring.analysis.intervalSeconds must be <= durationSeconds")
    if not 0.0 <= float(rollout_analysis["maxErrorRate"]) <= 1.0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.maxErrorRate must be between 0 and 1")
    if not 0.0 <= float(rollout_analysis["minTradeSuccessRate"]) <= 1.0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.minTradeSuccessRate must be between 0 and 1")
    if float(rollout_analysis["maxLatencyMs"]) <= 0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.maxLatencyMs must be positive")
    for key in (
        "maxGrossExposurePct",
        "maxSymbolExposurePct",
        "maxThemeExposurePct",
        "maxClusterExposurePct",
        "maxBetaBucketExposurePct",
        "maxGrossExposureDriftPct",
        "maxClusterConcentrationDriftPct",
        "maxBetaBucketConcentrationDriftPct",
        "maxClusterTurnover",
        "maxFactorSleeveBudgetTurnover",
        "maxFactorSleeveBudgetGapPct",
    ):
        value = float(rollout_analysis[key])
        if not 0.0 < value <= 1.0:
            raise ValueError(f"{path}: rolloutMonitoring.analysis.{key} must be between 0 and 1")
    if int(rollout_analysis["minimumRequestSamples"]) <= 0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.minimumRequestSamples must be positive")
    if int(rollout_analysis["minimumTradeSamples"]) < 0:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.minimumTradeSamples must be >= 0")
    alert_names = rollout_analysis["alertNames"]
    if not isinstance(alert_names, list) or not alert_names:
        raise ValueError(f"{path}: rolloutMonitoring.analysis.alertNames must be a non-empty list")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate release manifest and deployment values before deploy.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--values-file", default="")
    args = parser.parse_args()

    try:
        manifest_path = Path(args.manifest).resolve()
        manifest = _load_json(manifest_path)
        _validate_manifest(manifest, manifest_path)

        values_path = Path(args.values_file).resolve() if args.values_file else (manifest_path.parents[2] / manifest["values_file"]).resolve()
        values = _load_yaml(values_path)
        _validate_values(values, values_path, manifest)
        print(f"Pre-deploy validation passed for {manifest_path}")
        return 0
    except Exception as exc:
        print(f"Pre-deploy validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
