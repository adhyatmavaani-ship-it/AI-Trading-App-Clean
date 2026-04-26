from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.metrics import (
    model_calibration_error,
    model_concentration_drift_score,
    model_concept_drift_score,
    model_degraded_state,
    model_feature_drift_score,
    model_retraining_requested,
    trading_frequency_multiplier,
)
from app.schemas.monitoring import ModelStabilityStatus
from app.services.redis_cache import RedisCache

if TYPE_CHECKING:
    from app.services.model_registry import ModelRegistry


@dataclass
class ModelStabilityService:
    settings: Settings
    registry: ModelRegistry
    cache: RedisCache

    def load_status(self) -> ModelStabilityStatus:
        payload = self.cache.get_json("model:stability")
        if payload:
            return ModelStabilityStatus(**payload)
        metadata = self.registry.load_probability_metadata() if hasattr(self.registry, "load_probability_metadata") else {}
        return ModelStabilityStatus(
            active_model_version=(metadata or {}).get("model_version", self.registry.current_version()),
            fallback_model_version=None,
            live_win_rate=0.0,
            training_win_rate=float((metadata or {}).get("positive_rate", 0.60)),
            drift_score=0.0,
            calibration_error=float((metadata or {}).get("calibration_error", 0.0)),
            feature_drift_score=0.0,
            concept_drift_score=0.0,
            concentration_drift_score=0.0,
            retraining_triggered=False,
            trading_frequency_multiplier=1.0,
            degraded=False,
        )

    def update_concentration_state(self, profile: dict | None) -> ModelStabilityStatus:
        profile = profile or {}
        state = {
            "score": self._concentration_drift_score(profile),
            "gross_exposure_drift": float(profile.get("gross_exposure_drift", 0.0) or 0.0),
            "cluster_concentration_drift": float(profile.get("cluster_concentration_drift", 0.0) or 0.0),
            "beta_bucket_concentration_drift": float(profile.get("beta_bucket_concentration_drift", 0.0) or 0.0),
            "cluster_turnover": float(profile.get("cluster_turnover", 0.0) or 0.0),
            "factor_sleeve_budget_turnover": float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
            "max_factor_sleeve_budget_gap_pct": float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
        }
        self.cache.set_json("model:concentration_state", state, ttl=self.settings.monitor_state_ttl_seconds)
        self._append_concentration_history(state)
        status = self.load_status()
        adjusted = self._with_concentration_overlay(status, state)
        self.cache.set_json("model:stability", adjusted.model_dump(), ttl=self.settings.monitor_state_ttl_seconds)
        self.cache.set(
            "model:retraining_requested",
            "1" if adjusted.retraining_triggered else "0",
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self._update_metrics(adjusted)
        return adjusted

    def record_live_outcome(
        self,
        won: bool,
        *,
        predicted_probability: float | None = None,
        feature_snapshot: dict[str, float] | None = None,
        model_version: str | None = None,
    ) -> ModelStabilityStatus:
        status = self.load_status()
        metadata = self.registry.load_probability_metadata() if hasattr(self.registry, "load_probability_metadata") else {}
        metrics = self.cache.get_json("model:live_metrics") or {"wins": 0, "trades": 0, "probability_sum": 0.0}
        metrics["trades"] += 1
        metrics["wins"] += int(won)
        if predicted_probability is not None:
            bounded_probability = max(0.0, min(float(predicted_probability), 1.0))
            metrics["probability_sum"] += bounded_probability
        live_win_rate = metrics["wins"] / max(metrics["trades"], 1)
        average_probability = metrics["probability_sum"] / max(metrics["trades"], 1)
        calibration_error = abs(average_probability - live_win_rate)
        concept_drift_score = abs(float((metadata or {}).get("positive_rate", status.training_win_rate)) - live_win_rate)
        feature_drift_score = self._feature_drift(feature_snapshot, metadata or {})
        concentration_state = self.cache.get_json("model:concentration_state") or {}
        concentration_drift_score = float(concentration_state.get("score", status.concentration_drift_score) or 0.0)
        drift_score = max(concept_drift_score, feature_drift_score, calibration_error, concentration_drift_score)
        enough_trades = metrics["trades"] >= max(self.settings.probability_min_validation_samples, 20)
        degraded = (
            enough_trades
            and (
                calibration_error >= self.settings.probability_max_calibration_error
                or concept_drift_score >= self.settings.probability_concept_drift_threshold
            )
        )
        reduce_frequency = feature_drift_score >= self.settings.probability_frequency_reduction_threshold
        concentration_reduce = concentration_drift_score >= self.settings.probability_concentration_reduction_threshold
        multiplier = self.settings.probability_reduced_trading_multiplier if (reduce_frequency or concentration_reduce) else 1.0
        retraining_triggered = (
            degraded
            or feature_drift_score >= self.settings.probability_feature_drift_threshold
            or concentration_drift_score >= self.settings.probability_concentration_drift_threshold
        )
        active_model_version = str(model_version or status.active_model_version)
        fallback_model_version = status.fallback_model_version or str(
            (self.registry.load_probability_fallback_metadata() or {}).get("model_version", active_model_version)
        ) if hasattr(self.registry, "load_probability_fallback_metadata") else status.fallback_model_version or active_model_version
        if degraded and hasattr(self.registry, "activate_probability_fallback"):
            activated = self.registry.activate_probability_fallback()
            if activated is not None:
                active_model_version = str(activated.get("model_version", fallback_model_version))
        updated = ModelStabilityStatus(
            active_model_version=active_model_version,
            fallback_model_version=fallback_model_version,
            live_win_rate=live_win_rate,
            training_win_rate=float((metadata or {}).get("positive_rate", status.training_win_rate)),
            drift_score=drift_score,
            calibration_error=calibration_error,
            feature_drift_score=feature_drift_score,
            concept_drift_score=concept_drift_score,
            concentration_drift_score=concentration_drift_score,
            retraining_triggered=retraining_triggered,
            trading_frequency_multiplier=multiplier,
            degraded=degraded,
        )
        self.cache.set_json("model:live_metrics", metrics, ttl=self.settings.monitor_state_ttl_seconds)
        self.cache.set_json("model:stability", updated.model_dump(), ttl=self.settings.monitor_state_ttl_seconds)
        self.cache.set(
            "model:retraining_requested",
            "1" if retraining_triggered else "0",
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        self._update_metrics(updated)
        return updated

    def retraining_requested(self) -> bool:
        return bool(int(self.cache.get("model:retraining_requested") or 0))

    def concentration_history(self) -> list[dict]:
        bucket = self.cache.get_json("model:concentration_history") or {}
        return list(bucket.get("entries", []))

    def _feature_drift(self, feature_snapshot: dict[str, float] | None, metadata: dict) -> float:
        if not feature_snapshot:
            return 0.0
        baseline = metadata.get("feature_means") or {}
        if not baseline:
            return 0.0
        comparisons: list[float] = []
        for key, baseline_value in baseline.items():
            live_value = feature_snapshot.get(key)
            if live_value is None:
                continue
            baseline_float = float(baseline_value)
            live_float = float(live_value)
            if not math.isfinite(live_float):
                continue
            denom = max(abs(baseline_float), 1e-6)
            comparisons.append(min(abs(live_float - baseline_float) / denom, 1.0))
        if not comparisons:
            return 0.0
        return float(sum(comparisons) / len(comparisons))

    def _concentration_drift_score(self, profile: dict) -> float:
        gross_exposure_drift = abs(float(profile.get("gross_exposure_drift", 0.0) or 0.0))
        cluster_concentration_drift = abs(float(profile.get("cluster_concentration_drift", 0.0) or 0.0))
        beta_bucket_concentration_drift = abs(float(profile.get("beta_bucket_concentration_drift", 0.0) or 0.0))
        cluster_turnover = abs(float(profile.get("cluster_turnover", 0.0) or 0.0))
        factor_sleeve_budget_turnover = abs(float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0))
        max_factor_sleeve_budget_gap_pct = abs(float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0))
        return max(
            gross_exposure_drift,
            cluster_concentration_drift,
            beta_bucket_concentration_drift,
            cluster_turnover,
            factor_sleeve_budget_turnover,
            max_factor_sleeve_budget_gap_pct,
        )

    def _with_concentration_overlay(self, status: ModelStabilityStatus, concentration_state: dict) -> ModelStabilityStatus:
        concentration_drift_score = float(concentration_state.get("score", status.concentration_drift_score) or 0.0)
        reduce_for_concentration = concentration_drift_score >= self.settings.probability_concentration_reduction_threshold
        retraining_triggered = (
            status.retraining_triggered
            or concentration_drift_score >= self.settings.probability_concentration_drift_threshold
        )
        multiplier = min(
            float(status.trading_frequency_multiplier),
            float(self.settings.probability_reduced_trading_multiplier),
        ) if reduce_for_concentration else float(status.trading_frequency_multiplier)
        return status.model_copy(
            update={
                "concentration_drift_score": concentration_drift_score,
                "drift_score": max(float(status.drift_score), concentration_drift_score),
                "trading_frequency_multiplier": multiplier,
                "retraining_triggered": retraining_triggered,
            }
        )

    def _append_concentration_history(self, concentration_state: dict) -> None:
        history_key = "model:concentration_history"
        bucket = self.cache.get_json(history_key) or {"entries": []}
        keep = max(int(self.settings.model_stability_concentration_history_limit), 1)
        entries = list(bucket.get("entries", []))[-(keep - 1) :]
        entries.append(
            {
                **concentration_state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.cache.set_json(
            history_key,
            {"entries": entries},
            ttl=self.settings.monitor_state_ttl_seconds,
        )

    def _update_metrics(self, status: ModelStabilityStatus) -> None:
        model_calibration_error.set(status.calibration_error)
        model_feature_drift_score.set(status.feature_drift_score)
        model_concept_drift_score.set(status.concept_drift_score)
        model_concentration_drift_score.set(status.concentration_drift_score)
        model_degraded_state.set(1 if status.degraded else 0)
        model_retraining_requested.set(1 if status.retraining_triggered else 0)
        trading_frequency_multiplier.set(status.trading_frequency_multiplier)
