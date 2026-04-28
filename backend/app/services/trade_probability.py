from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from app.core.config import Settings
from app.schemas.trading import FeatureSnapshot
from app.trading.strategies.base import StrategyDecision

if TYPE_CHECKING:
    from app.services.model_registry import ModelRegistry


PROBABILITY_FEATURE_ORDER = (
    "trend_strength",
    "rsi",
    "adx",
    "atr_ratio",
    "ema_distance",
    "price_return",
    "breakout_strength",
    "volume_spike",
    "candle_body_pct",
    "upper_wick_pct",
    "lower_wick_pct",
    "engulfing",
    "doji",
    "sentiment_score",
    "regime_trending",
)

REGIME_ORDER = ("TRENDING", "RANGING", "HIGH_VOL")


@dataclass
class TradeProbabilityEngine:
    settings: Settings
    registry: "ModelRegistry"
    firestore: object | None = None
    _model: object | None = field(default=None, init=False, repr=False)
    _scaler: StandardScaler | None = field(default=None, init=False, repr=False)
    _metadata: dict | None = field(default=None, init=False, repr=False)

    def analyze_training_data(self, samples: list[dict] | None = None) -> dict:
        rows = samples if samples is not None else self._load_samples()
        dataset = self.build_dataset(rows)
        issues: list[str] = []
        if not dataset:
            return {
                "issues_found": ["no_recent_samples"],
                "sample_count": 0,
                "window_days": self.settings.probability_training_window_days,
                "data_quality": {
                    "nan_rows": 0,
                    "invalid_rows": 0,
                    "label_balance": 0.0,
                },
                "drift": {
                    "feature_distribution_shift": 0.0,
                    "win_rate_shift": 0.0,
                    "drift_detected": False,
                },
            }

        vectors = np.array([row["vector"] for row in dataset], dtype=np.float32)
        labels = np.array([row["label"] for row in dataset], dtype=np.int32)
        nan_rows = int(np.sum(~np.isfinite(vectors).all(axis=1)))
        if nan_rows:
            issues.append("non_finite_feature_rows")
        label_balance = float(np.mean(labels)) if len(labels) else 0.0
        if label_balance < 0.2 or label_balance > 0.8:
            issues.append("class_imbalance")

        split_index = max(len(dataset) // 2, 1)
        early = vectors[:split_index]
        late = vectors[split_index:]
        feature_shift = self._feature_distribution_shift(early, late)
        early_win_rate = float(np.mean(labels[:split_index])) if split_index else 0.0
        late_win_rate = float(np.mean(labels[split_index:])) if len(labels[split_index:]) else early_win_rate
        win_rate_shift = abs(late_win_rate - early_win_rate)
        drift_detected = feature_shift >= self.settings.model_drift_threshold or win_rate_shift >= self.settings.model_drift_threshold
        if drift_detected:
            issues.append("distribution_drift_detected")

        report = {
            "issues_found": issues,
            "sample_count": len(dataset),
            "window_days": self.settings.probability_training_window_days,
            "data_quality": {
                "nan_rows": nan_rows,
                "invalid_rows": 0,
                "label_balance": round(label_balance, 6),
            },
            "drift": {
                "feature_distribution_shift": round(feature_shift, 6),
                "win_rate_shift": round(win_rate_shift, 6),
                "drift_detected": drift_detected,
            },
        }
        if self.firestore is not None and hasattr(self.firestore, "save_model_report"):
            self.firestore.save_model_report("trade_probability_analysis", report)
        return report

    def train(
        self,
        samples: list[dict] | None = None,
        *,
        recent_validation_window: int | None = None,
        min_recent_accuracy_lift: float = 0.0,
    ) -> dict:
        rows = samples if samples is not None else self._load_samples()
        analysis = self.analyze_training_data(rows)
        dataset = self.build_dataset(rows)
        if len(dataset) < self.settings.probability_min_training_samples:
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "insufficient_samples",
                "analysis": analysis,
            }

        x = np.array([row["vector"] for row in dataset], dtype=np.float32)
        y = np.array([row["label"] for row in dataset], dtype=np.int32)
        if len(np.unique(y)) < 2:
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "single_class_labels",
                "analysis": analysis,
            }

        split_index = self._split_index(len(dataset))
        if split_index <= 0 or (len(dataset) - split_index) < self.settings.probability_min_validation_samples:
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "insufficient_validation_window",
                "analysis": analysis,
            }

        train_rows = dataset[:split_index]
        val_rows = dataset[split_index:]
        best_metrics, best_model, best_scaler = self._train_model_bundle(train_rows, val_rows)
        if not best_metrics["accepted"]:
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "candidate_failed_validation",
                "candidate_metrics": best_metrics,
                "analysis": analysis,
            }

        recent_window_gate = self._recent_window_gate(
            candidate_model=best_model,
            candidate_scaler=best_scaler,
            dataset=dataset,
            recent_validation_window=recent_validation_window,
            min_recent_accuracy_lift=min_recent_accuracy_lift,
        )
        if not recent_window_gate["accepted"]:
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "candidate_failed_recent_window_gate",
                "recent_window_gate": recent_window_gate,
                "candidate_metrics": best_metrics,
                "analysis": analysis,
            }

        previous = self._load_metadata() or {}
        if previous and not self._outperforms(best_metrics, previous):
            return {
                "trained": False,
                "samples": len(dataset),
                "reason": "candidate_worse_than_active",
                "candidate_metrics": best_metrics,
                "active_metrics": previous,
                "analysis": analysis,
            }

        version = self._next_probability_version(previous)
        metadata = {
            "model_type": "regime_ensemble",
            "model_version": version,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "samples": len(dataset),
            "training_samples": int(len(train_rows)),
            "validation_samples": int(len(val_rows)),
            "training_window_days": int(self.settings.probability_training_window_days),
            "accuracy": round(best_metrics["accuracy"], 6),
            "precision": round(best_metrics["precision"], 6),
            "calibration_error": round(best_metrics["calibration_error"], 6),
            "positive_rate": round(best_metrics["positive_rate"], 6),
            "recent_validation_window": int(recent_window_gate.get("window", 0) or 0),
            "recent_validation_candidate_accuracy": round(
                float(recent_window_gate.get("candidate_accuracy", 0.0) or 0.0),
                6,
            ),
            "recent_validation_incumbent_accuracy": round(
                float(recent_window_gate.get("incumbent_accuracy", 0.0) or 0.0),
                6,
            ),
            "recent_validation_accuracy_lift": round(
                float(recent_window_gate.get("candidate_accuracy", 0.0) or 0.0)
                - float(recent_window_gate.get("incumbent_accuracy", 0.0) or 0.0),
                6,
            ),
            "feature_means": self._feature_means(x),
            "regime_performance": best_metrics["regime_performance"],
            "trade_intelligence": self._trade_intelligence(dataset),
        }
        self.registry.promote_probability_model(best_model, best_scaler, metadata)
        self._model = best_model
        self._scaler = best_scaler
        self._metadata = metadata
        return {
            "trained": True,
            "samples": len(dataset),
            "model_version": version,
            "performance": metadata,
            "previous_performance": previous or None,
            "recent_window_gate": recent_window_gate,
            "analysis": analysis,
        }

    def build_dataset(self, samples: list[dict]) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.probability_training_window_days)
        dataset: list[dict] = []
        for sample in samples:
            created_at = self._sample_timestamp(sample)
            if created_at is not None and created_at < cutoff:
                continue
            row = self._training_row(sample)
            if row is not None:
                dataset.append(row)
        dataset.sort(key=lambda item: item["timestamp"])
        return dataset

    def score(
        self,
        *,
        snapshot: FeatureSnapshot | None = None,
        decision: StrategyDecision | None = None,
        frame: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
        features: dict[str, float] | None = None,
    ) -> tuple[float, dict[str, float]]:
        self._refresh_active_model()
        probability_features = features or self.extract_features(
            snapshot=snapshot,
            decision=decision,
            frame=frame,
        )
        probability = self._predict_probability(probability_features)
        return probability, probability_features

    def enrich_decision(
        self,
        decision: StrategyDecision,
        *,
        snapshot: FeatureSnapshot | None = None,
        frame: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
        features: dict[str, float] | None = None,
    ) -> StrategyDecision:
        probability, probability_features = self.score(
            snapshot=snapshot,
            decision=decision,
            frame=frame,
            features=features,
        )
        sleeve_budget_overlay = self._sleeve_budget_overlay(
            metadata=decision.metadata,
            snapshot_features=snapshot.features if snapshot is not None else {},
        )
        adjusted_probability = max(
            0.0,
            min(1.0, probability * float(sleeve_budget_overlay["probability_multiplier"])),
        )
        metadata = {
            **decision.metadata,
            "raw_trade_success_probability": round(probability, 6),
            "trade_success_probability": round(adjusted_probability, 6),
            "trade_probability_threshold": round(self.settings.trade_probability_threshold, 6),
            "trend_strength": round(probability_features["trend_strength"], 6),
            "probability_rsi": round(probability_features["rsi"], 6),
            "breakout_strength": round(probability_features["breakout_strength"], 6),
            "probability_volume": round(probability_features["volume_spike"], 6),
            "probability_model_version": str((self._load_metadata() or {}).get("model_version", "heuristic")),
            "probability_calibration_error": round(float((self._load_metadata() or {}).get("calibration_error", 0.0)), 6),
            "selected_regime_model": self._regime_label(probability_features).lower(),
            "sleeve_budget_probability_multiplier": round(float(sleeve_budget_overlay["probability_multiplier"]), 6),
            "sleeve_budget_priority_reason": str(sleeve_budget_overlay["reason"]),
        }
        final_score = decision.confidence * adjusted_probability
        metadata["final_score"] = round(final_score, 6)
        if decision.signal == "HOLD":
            return StrategyDecision(
                strategy=decision.strategy,
                signal=decision.signal,
                confidence=decision.confidence,
                metadata=metadata,
            )

        meta_filter = self._meta_filter_decision(
            strategy=decision.strategy,
            regime=self._regime_label(probability_features),
            final_score=final_score,
        )
        metadata.update(meta_filter)
        if adjusted_probability < self.settings.trade_probability_threshold:
            metadata["reason"] = "trade_probability_below_threshold"
            metadata["adjusted_confidence"] = 0.0
            return StrategyDecision(
                strategy=decision.strategy,
                signal="HOLD",
                confidence=0.0,
                metadata=metadata,
            )

        if not meta_filter["allow_trade"]:
            metadata["adjusted_confidence"] = 0.0
            return StrategyDecision(
                strategy=decision.strategy,
                signal="HOLD",
                confidence=0.0,
                metadata=metadata,
            )

        adjusted_confidence = max(0.0, min(1.0, final_score))
        metadata["adjusted_confidence"] = round(adjusted_confidence, 6)
        return StrategyDecision(
            strategy=decision.strategy,
            signal=decision.signal,
            confidence=adjusted_confidence,
            metadata=metadata,
        )

    def _sleeve_budget_overlay(
        self,
        *,
        metadata: dict[str, float | str | int],
        snapshot_features: dict[str, float],
    ) -> dict[str, float | str]:
        target_share = float(
            metadata.get(
                "factor_sleeve_budget_target",
                snapshot_features.get("factor_sleeve_budget_target", 0.0),
            )
            or 0.0
        )
        budget_delta = float(
            metadata.get(
                "factor_sleeve_budget_delta",
                snapshot_features.get("factor_sleeve_budget_delta", 0.0),
            )
            or 0.0
        )
        recent_win_rate = float(
            metadata.get(
                "factor_sleeve_recent_win_rate",
                snapshot_features.get("factor_sleeve_recent_win_rate", 0.5),
            )
            or 0.0
        )
        recent_avg_pnl = float(
            metadata.get(
                "factor_sleeve_recent_avg_pnl",
                snapshot_features.get("factor_sleeve_recent_avg_pnl", 0.0),
            )
            or 0.0
        )
        recent_closed_trades = int(
            metadata.get(
                "factor_sleeve_recent_closed_trades",
                snapshot_features.get("factor_sleeve_recent_closed_trades", 0),
            )
            or 0
        )
        budget_turnover = float(
            metadata.get(
                "factor_sleeve_budget_turnover",
                snapshot_features.get("factor_sleeve_budget_turnover", 0.0),
            )
            or 0.0
        )
        budget_gap = float(
            metadata.get(
                "max_factor_sleeve_budget_gap_pct",
                snapshot_features.get("max_factor_sleeve_budget_gap_pct", 0.0),
            )
            or 0.0
        )
        sleeve_name = str(
            metadata.get(
                "factor_sleeve_name",
                snapshot_features.get("factor_sleeve_name", "sleeve"),
            )
            or "sleeve"
        )
        if target_share <= 0.0 or recent_closed_trades < 3:
            return {"probability_multiplier": 1.0, "reason": "insufficient_sleeve_budget_context"}
        if (
            budget_turnover >= self.settings.portfolio_concentration_soft_turnover
            or budget_gap >= self.settings.portfolio_concentration_soft_alert_drift
        ):
            return {
                "probability_multiplier": 1.0,
                "reason": "sleeve_rotation_unstable_probability_boost_suppressed",
            }
        if budget_delta > 0.05 and recent_win_rate >= 0.55 and recent_avg_pnl > 0.0:
            boost = min(
                float(self.settings.probability_factor_sleeve_priority_boost),
                1.0 + budget_delta * 0.4,
            )
            return {
                "probability_multiplier": boost,
                "reason": f"{sleeve_name} sleeve quality improved ranking priority",
            }
        if budget_delta < -0.05 and (recent_win_rate < 0.45 or recent_avg_pnl < 0.0):
            reduction = max(
                float(self.settings.probability_factor_sleeve_priority_floor),
                1.0 + budget_delta * 0.5,
            )
            return {
                "probability_multiplier": reduction,
                "reason": f"{sleeve_name} sleeve budget pressure reduced ranking priority",
            }
        return {"probability_multiplier": 1.0, "reason": "neutral_sleeve_budget_pressure"}

    def extract_features(
        self,
        *,
        snapshot: FeatureSnapshot | None = None,
        decision: StrategyDecision | None = None,
        frame: pd.DataFrame | dict[str, pd.DataFrame] | None = None,
    ) -> dict[str, float]:
        metadata = decision.metadata if decision is not None else {}
        working_frame = self._signal_frame(frame)
        candle_features = self._candle_features(working_frame)
        snapshot_features = snapshot.features if snapshot is not None else {}

        volume = 0.0
        volume_spike = 0.0
        adx = float(snapshot_features.get("15m_adx", snapshot_features.get("5m_adx", 0.0)))
        atr = float(snapshot_features.get("atr", snapshot_features.get("15m_atr", 0.0)))
        price = float(snapshot.price if snapshot is not None else snapshot_features.get("price", 0.0) or 0.0)
        ema_distance = float(snapshot_features.get("15m_ema_spread", snapshot_features.get("5m_ema_spread", 0.0)))
        price_return = float(snapshot_features.get("15m_return", snapshot_features.get("5m_return", 0.0)))
        sentiment_score = float(snapshot_features.get("news_score", snapshot_features.get("sentiment_score", 0.5)))

        if working_frame is not None and not working_frame.empty:
            volume_series = working_frame["volume"].astype(float) if "volume" in working_frame.columns else pd.Series([0.0])
            volume = float(volume_series.iloc[-1])
            baseline = float(volume_series.tail(20).mean()) if len(volume_series) else 0.0
            volume_spike = volume / max(baseline, 1e-8)
            if "close" in working_frame.columns and len(working_frame["close"]) >= 2:
                closes = working_frame["close"].astype(float)
                price = float(closes.iloc[-1])
                price_return = float(closes.pct_change().iloc[-1] or 0.0)
            ema_distance = self._frame_ema_distance(working_frame, ema_distance)

        trend_strength = float(
            metadata.get(
                "trend_strength",
                adx / 100 if adx else snapshot_features.get("trend_strength", 0.0),
            )
        )
        rsi = float(
            metadata.get(
                "rsi",
                snapshot_features.get("15m_rsi", snapshot_features.get("5m_rsi", 50.0)),
            )
        )
        breakout_strength = float(
            metadata.get(
                "breakout_strength",
                metadata.get("base_confidence", decision.confidence if decision is not None else 0.0),
            )
        )
        regime_type = str(metadata.get("regime_type", snapshot.regime if snapshot is not None else "RANGING")).upper()
        features = {
            "trend_strength": trend_strength,
            "rsi": rsi,
            "adx": adx,
            "atr_ratio": atr / max(abs(price), 1e-8),
            "ema_distance": ema_distance / max(abs(price), 1e-8),
            "price_return": price_return,
            "breakout_strength": breakout_strength,
            "volume_spike": volume_spike if volume_spike else math.log1p(max(volume, 0.0)),
            "candle_body_pct": candle_features["body_pct"],
            "upper_wick_pct": candle_features["upper_wick_pct"],
            "lower_wick_pct": candle_features["lower_wick_pct"],
            "engulfing": candle_features["engulfing"],
            "doji": candle_features["doji"],
            "sentiment_score": sentiment_score,
            "regime_trending": 1.0 if regime_type == "TRENDING" else 0.0,
        }
        return self._sanitize_features(features)

    def _predict_probability(self, features: dict[str, float]) -> float:
        vector = self._vectorize(features)
        model = self._load_model()
        scaler = self._load_scaler()
        if model is None or scaler is None:
            return self._heuristic_probability(features)
        if isinstance(model, dict) and model.get("type") == "regime_ensemble":
            return self._predict_regime_ensemble(model, scaler, vector, features)
        if getattr(model, "_probability_requires_scaler", True):
            transformed = scaler.transform(vector.reshape(1, -1))
        else:
            transformed = vector.reshape(1, -1)
        probability = model.predict_proba(transformed)[0][1]
        return float(max(0.0, min(probability, 1.0)))

    def _heuristic_probability(self, features: dict[str, float]) -> float:
        normalized_rsi = 1.0 - min(abs(features["rsi"] - 50.0) / 50.0, 1.0)
        score = (
            0.22 * min(features["trend_strength"], 1.0)
            + 0.10 * min(features["adx"] / 40.0, 1.0)
            + 0.08 * max(0.0, 1.0 - min(features["atr_ratio"] / 0.06, 1.0))
            + 0.12 * max(0.0, 1.0 - min(abs(features["ema_distance"]) / 0.03, 1.0))
            + 0.12 * max(0.0, 0.5 + features["price_return"] * 10.0)
            + 0.14 * min(features["breakout_strength"], 1.0)
            + 0.08 * min(features["volume_spike"], 2.0) / 2.0
            + 0.06 * min(features["candle_body_pct"], 1.0)
            + 0.04 * min(features["lower_wick_pct"], 1.0)
            + 0.02 * features["engulfing"]
            + 0.02 * (1.0 - features["doji"])
        )
        score *= 0.85 + 0.15 * features["regime_trending"]
        return float(max(0.0, min(score, 1.0)))

    def _training_row(self, sample: dict) -> dict | None:
        outcome = sample.get("outcome")
        if outcome is None:
            return None
        source = sample.get("probability_features") or sample.get("features") or {}
        timestamp = self._sample_timestamp(sample) or datetime.now(timezone.utc)
        try:
            features = self._sample_probability_features(source, sample)
            vector = self._vectorize(features)
        except (TypeError, ValueError):
            return None
        regime = str(source.get("regime_type", sample.get("regime", "")) or "").upper()
        if regime not in REGIME_ORDER:
            regime = self._regime_label(features)
        return {
            "vector": vector,
            "label": int(float(outcome) > 0.0),
            "timestamp": timestamp,
            "regime": regime,
            "features": features,
            "sample_weight": self._sample_weight(sample=sample, label=int(float(outcome) > 0.0)),
            "sample": sample,
        }

    def _load_samples(self) -> list[dict]:
        if self.firestore is None or not hasattr(self.firestore, "list_training_samples"):
            return []
        return list(self.firestore.list_training_samples(limit=5000))

    def _vectorize(self, features: dict[str, float]) -> np.ndarray:
        return np.array([float(features[key]) for key in PROBABILITY_FEATURE_ORDER], dtype=np.float32)

    def _sample_probability_features(self, source: dict, sample: dict) -> dict[str, float]:
        price = max(float(source.get("price", 100.0) or 100.0), 1e-8)
        atr = float(source.get("atr", source.get("15m_atr", source.get("5m_atr", 0.0))) or 0.0)
        ema_spread = float(source.get("15m_ema_spread", source.get("5m_ema_spread", 0.0)) or 0.0)
        regime_hint = str(source.get("regime_type", sample.get("regime", "RANGING"))).upper()
        return self._sanitize_features(
            {
                "trend_strength": float(source.get("trend_strength", source.get("15m_adx", 0.0) / 100)),
                "rsi": float(source.get("rsi", source.get("15m_rsi", source.get("5m_rsi", 50.0)))),
                "adx": float(source.get("adx", source.get("15m_adx", source.get("5m_adx", 0.0)))),
                "atr_ratio": float(source.get("atr_ratio", atr / price)),
                "ema_distance": float(source.get("ema_distance", ema_spread / price)),
                "price_return": float(source.get("price_return", source.get("15m_return", source.get("5m_return", 0.0)))),
                "breakout_strength": float(source.get("breakout_strength", source.get("strategy_confidence", sample.get("confidence", 0.0)))),
                "volume_spike": float(source.get("volume_spike", source.get("volume", math.log1p(float(source.get("15m_volume", source.get("5m_volume", 0.0))))))),
                "candle_body_pct": float(source.get("candle_body_pct", 0.5)),
                "upper_wick_pct": float(source.get("upper_wick_pct", 0.25)),
                "lower_wick_pct": float(source.get("lower_wick_pct", 0.25)),
                "engulfing": float(source.get("engulfing", 0.0)),
                "doji": float(source.get("doji", 0.0)),
                "sentiment_score": float(source.get("sentiment_score", source.get("news_score", 0.5))),
                "regime_trending": float(source.get("regime_trending", 1.0 if regime_hint == "TRENDING" else 0.0)),
            }
        )

    def _load_model(self):
        if self._model is None:
            self._model = self.registry.load_probability_model()
        return self._model

    def _load_scaler(self):
        if self._scaler is None:
            self._scaler = self.registry.load_probability_scaler()
        return self._scaler

    def _load_metadata(self) -> dict | None:
        if self._metadata is None and hasattr(self.registry, "load_probability_metadata"):
            self._metadata = self.registry.load_probability_metadata()
        return self._metadata

    def _refresh_active_model(self) -> None:
        if not hasattr(self.registry, "load_probability_metadata"):
            return
        latest_metadata = self.registry.load_probability_metadata()
        latest_version = str((latest_metadata or {}).get("model_version", ""))
        cached_version = str((self._metadata or {}).get("model_version", ""))
        if latest_version and latest_version != cached_version:
            self._model = None
            self._scaler = None
            self._metadata = latest_metadata

    def _signal_frame(self, frame: pd.DataFrame | dict[str, pd.DataFrame] | None) -> pd.DataFrame | None:
        if frame is None:
            return None
        if isinstance(frame, dict):
            preferred = frame.get("5m")
            if preferred is None:
                preferred = frame.get("15m")
            if preferred is None:
                preferred = next(iter(frame.values()))
            return preferred
        return frame

    def _sample_timestamp(self, sample: dict) -> datetime | None:
        raw = sample.get("closed_at") or sample.get("updated_at") or sample.get("created_at")
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        if hasattr(raw, "to_datetime"):
            converted = raw.to_datetime()
            return converted if converted.tzinfo else converted.replace(tzinfo=timezone.utc)
        if isinstance(raw, str):
            normalized = raw.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return None

    def _split_index(self, size: int) -> int:
        fraction = min(max(float(self.settings.probability_validation_split), 0.1), 0.5)
        validation_size = max(int(round(size * fraction)), self.settings.probability_min_validation_samples)
        return max(size - validation_size, 0)

    def _validation_metrics(self, labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float | bool]:
        predictions = (probabilities >= self.settings.trade_probability_threshold).astype(np.int32)
        accuracy = float(np.mean(predictions == labels)) if len(labels) else 0.0
        true_positive = int(np.sum((predictions == 1) & (labels == 1)))
        predicted_positive = int(np.sum(predictions == 1))
        precision = float(true_positive / predicted_positive) if predicted_positive else 0.0
        calibration_error = self._calibration_error(labels, probabilities)
        positive_rate = float(np.mean(labels)) if len(labels) else 0.0
        accepted = (
            precision >= self.settings.probability_min_precision
            and calibration_error <= self.settings.probability_max_calibration_error
        )
        return {
            "accuracy": accuracy,
            "precision": precision,
            "calibration_error": calibration_error,
            "positive_rate": positive_rate,
            "accepted": accepted,
        }

    def _calibration_error(self, labels: np.ndarray, probabilities: np.ndarray, bins: int = 5) -> float:
        if len(labels) == 0:
            return 1.0
        edges = np.linspace(0.0, 1.0, bins + 1)
        weighted_error = 0.0
        total = float(len(labels))
        for index in range(bins):
            left = edges[index]
            right = edges[index + 1]
            mask = (probabilities >= left) & (probabilities < right if index < bins - 1 else probabilities <= right)
            if not np.any(mask):
                continue
            bucket_prob = float(np.mean(probabilities[mask]))
            bucket_actual = float(np.mean(labels[mask]))
            weighted_error += abs(bucket_prob - bucket_actual) * (float(np.sum(mask)) / total)
        return weighted_error

    def _outperforms(self, candidate: dict, incumbent: dict) -> bool:
        incumbent_precision = float(incumbent.get("precision", 0.0))
        incumbent_calibration = float(incumbent.get("calibration_error", 1.0))
        incumbent_accuracy = float(incumbent.get("accuracy", 0.0))
        if float(candidate["precision"]) > incumbent_precision + 0.01:
            return True
        if float(candidate["precision"]) + 0.01 < incumbent_precision:
            return False
        if float(candidate["calibration_error"]) + 0.01 < incumbent_calibration:
            return True
        if float(candidate["calibration_error"]) > incumbent_calibration + 0.01:
            return False
        return float(candidate["accuracy"]) >= incumbent_accuracy

    def _next_probability_version(self, previous: dict | None) -> str:
        raw = str((previous or {}).get("model_version", "prob-v0"))
        prefix, _, number = raw.rpartition("v")
        if number.isdigit():
            return f"{prefix}v{int(number) + 1}"
        return "prob-v1"

    def _feature_distribution_shift(self, early: np.ndarray, late: np.ndarray) -> float:
        if len(early) == 0 or len(late) == 0:
            return 0.0
        early_mean = np.nanmean(early, axis=0)
        late_mean = np.nanmean(late, axis=0)
        denom = np.maximum(np.abs(early_mean), 1e-6)
        relative = np.abs(late_mean - early_mean) / denom
        return float(np.mean(np.clip(relative, 0.0, 1.0)))

    def _feature_means(self, matrix: np.ndarray) -> dict[str, float]:
        means = np.nanmean(matrix, axis=0)
        return {
            feature: round(float(value), 6)
            for feature, value in zip(PROBABILITY_FEATURE_ORDER, means)
        }

    def _train_model_bundle(self, train_rows: list[dict], val_rows: list[dict]) -> tuple[dict, dict, StandardScaler]:
        x_train = np.array([row["vector"] for row in train_rows], dtype=np.float32)
        y_train = np.array([row["label"] for row in train_rows], dtype=np.int32)
        sample_weights = np.array([float(row.get("sample_weight", 1.0) or 1.0) for row in train_rows], dtype=np.float32)
        x_val = np.array([row["vector"] for row in val_rows], dtype=np.float32)
        y_val = np.array([row["label"] for row in val_rows], dtype=np.int32)
        scaler = StandardScaler()
        x_train_scaled = scaler.fit_transform(x_train)
        x_val_scaled = scaler.transform(x_val)
        global_models, global_metrics = self._fit_candidate_pair(
            x_train=x_train,
            x_train_scaled=x_train_scaled,
            y_train=y_train,
            sample_weight=sample_weights,
            x_val=x_val,
            x_val_scaled=x_val_scaled,
            y_val=y_val,
        )
        regime_models: dict[str, dict] = {}
        regime_performance: dict[str, dict[str, float | int]] = {}
        for regime in REGIME_ORDER:
            regime_train = [row for row in train_rows if row["regime"] == regime]
            regime_val = [row for row in val_rows if row["regime"] == regime]
            if len(regime_train) < self.settings.probability_min_training_samples:
                continue
            if len(regime_val) < 2 or len({row["label"] for row in regime_train}) < 2 or len({row["label"] for row in regime_val}) < 2:
                continue
            rx_train = np.array([row["vector"] for row in regime_train], dtype=np.float32)
            ry_train = np.array([row["label"] for row in regime_train], dtype=np.int32)
            rx_val = np.array([row["vector"] for row in regime_val], dtype=np.float32)
            ry_val = np.array([row["label"] for row in regime_val], dtype=np.int32)
            rx_train_scaled = scaler.transform(rx_train)
            rx_val_scaled = scaler.transform(rx_val)
            candidate_models, candidate_metrics = self._fit_candidate_pair(
                x_train=rx_train,
                x_train_scaled=rx_train_scaled,
                y_train=ry_train,
                sample_weight=np.array([float(row.get("sample_weight", 1.0) or 1.0) for row in regime_train], dtype=np.float32),
                x_val=rx_val,
                x_val_scaled=rx_val_scaled,
                y_val=ry_val,
            )
            regime_models[regime] = candidate_models
            regime_performance[regime] = {
                "samples": len(regime_train) + len(regime_val),
                "accuracy": round(candidate_metrics["accuracy"], 6),
                "precision": round(candidate_metrics["precision"], 6),
                "calibration_error": round(candidate_metrics["calibration_error"], 6),
                "ensemble_weight_logistic": round(candidate_models["weights"]["logistic"], 6),
                "ensemble_weight_gradient_boosting": round(candidate_models["weights"]["gradient_boosting"], 6),
            }
        bundle = {"type": "regime_ensemble", "global": global_models, "regimes": regime_models}
        global_metrics["regime_performance"] = regime_performance
        return global_metrics, bundle, scaler

    def _fit_candidate_pair(
        self,
        *,
        x_train: np.ndarray,
        x_train_scaled: np.ndarray,
        y_train: np.ndarray,
        sample_weight: np.ndarray,
        x_val: np.ndarray,
        x_val_scaled: np.ndarray,
        y_val: np.ndarray,
    ) -> tuple[dict, dict]:
        logistic = LogisticRegression(random_state=42, max_iter=1000, class_weight="balanced")
        logistic.fit(x_train_scaled, y_train, sample_weight=sample_weight)
        setattr(logistic, "_probability_requires_scaler", True)
        gb = GradientBoostingClassifier(random_state=42)
        gb.fit(x_train, y_train, sample_weight=sample_weight)
        setattr(gb, "_probability_requires_scaler", False)
        logistic_probs = logistic.predict_proba(x_val_scaled)[:, 1]
        gb_probs = gb.predict_proba(x_val)[:, 1]
        logistic_metrics = self._validation_metrics(y_val, logistic_probs)
        gb_metrics = self._validation_metrics(y_val, gb_probs)
        logistic_weight = self._candidate_weight(logistic_metrics)
        gb_weight = self._candidate_weight(gb_metrics)
        total = max(logistic_weight + gb_weight, 1e-8)
        logistic_weight /= total
        gb_weight /= total
        blended = logistic_probs * logistic_weight + gb_probs * gb_weight
        ensemble_metrics = self._validation_metrics(y_val, blended)
        ensemble_metrics["model_name"] = "regime_ensemble"
        return (
            {
                "logistic": logistic,
                "gradient_boosting": gb,
                "weights": {"logistic": logistic_weight, "gradient_boosting": gb_weight},
            },
            ensemble_metrics,
        )

    def _candidate_weight(self, metrics: dict[str, float | bool]) -> float:
        precision = float(metrics["precision"])
        calibration = float(metrics["calibration_error"])
        accuracy = float(metrics["accuracy"])
        return max(0.05, precision * 0.55 + accuracy * 0.25 + max(0.0, 1.0 - calibration) * 0.20)

    def _predict_regime_ensemble(
        self,
        model_bundle: dict,
        scaler: StandardScaler,
        vector: np.ndarray,
        features: dict[str, float],
    ) -> float:
        regime = self._regime_label(features)
        selected = model_bundle.get("regimes", {}).get(regime) or model_bundle["global"]
        logistic_prob = selected["logistic"].predict_proba(scaler.transform(vector.reshape(1, -1)))[0][1]
        gb_prob = selected["gradient_boosting"].predict_proba(vector.reshape(1, -1))[0][1]
        weights = selected["weights"]
        probability = logistic_prob * float(weights["logistic"]) + gb_prob * float(weights["gradient_boosting"])
        return float(max(0.0, min(probability, 1.0)))

    def _regime_label(self, features: dict[str, float]) -> str:
        if float(features.get("atr_ratio", 0.0)) >= 0.025:
            return "HIGH_VOL"
        if float(features.get("regime_trending", 0.0)) >= 0.5 or float(features.get("adx", 0.0)) >= 25.0:
            return "TRENDING"
        return "RANGING"

    def _trade_intelligence(self, dataset: list[dict]) -> dict[str, dict[str, float]]:
        buckets: dict[str, list[dict]] = {regime: [] for regime in REGIME_ORDER}
        for row in dataset:
            buckets.setdefault(row["regime"], []).append(row)
        intelligence: dict[str, dict[str, float]] = {}
        for regime, rows in buckets.items():
            if not rows:
                continue
            r_values = [self._sample_r_multiple(row["sample"]) for row in rows]
            durations = [self._sample_duration_hours(row["sample"]) for row in rows]
            drawdowns = [self._sample_drawdown(row["sample"]) for row in rows]
            wins = [row["label"] for row in rows]
            intelligence[regime] = {
                "sample_count": float(len(rows)),
                "win_rate": round(float(np.mean(wins)), 6),
                "avg_r_multiple": round(float(np.mean(r_values)), 6),
                "avg_duration_hours": round(float(np.mean(durations)), 6),
                "avg_drawdown": round(float(np.mean(drawdowns)), 6),
            }
        return intelligence

    def _sample_weight(self, *, sample: dict, label: int) -> float:
        if label != 0:
            return 1.0
        confidence = max(
            float(sample.get("trade_success_probability", 0.0) or 0.0),
            float(sample.get("raw_trade_success_probability", 0.0) or 0.0),
            float(sample.get("confidence", 0.0) or 0.0),
        )
        threshold = float(self.settings.retrain_high_confidence_threshold)
        multiplier = float(self.settings.retrain_high_confidence_loss_weight)
        if confidence < threshold or multiplier <= 1.0:
            return 1.0
        confidence_scale = min((confidence - threshold) / max(1.0 - threshold, 1e-6), 1.0)
        return 1.0 + ((multiplier - 1.0) * confidence_scale)

    def _recent_window_gate(
        self,
        *,
        candidate_model,
        candidate_scaler,
        dataset: list[dict],
        recent_validation_window: int | None,
        min_recent_accuracy_lift: float,
    ) -> dict:
        window = max(int(recent_validation_window or 0), 0)
        if window <= 0:
            return {"accepted": True, "reason": "disabled"}
        recent_rows = dataset[-window:]
        if len(recent_rows) < max(2, window):
            return {"accepted": True, "reason": "insufficient_recent_rows", "window": len(recent_rows)}
        incumbent_model = self.registry.load_probability_model()
        incumbent_scaler = self.registry.load_probability_scaler()
        candidate_accuracy = self._accuracy_for_rows(candidate_model, candidate_scaler, recent_rows)
        if incumbent_model is None or incumbent_scaler is None:
            return {
                "accepted": True,
                "reason": "no_incumbent_model",
                "candidate_accuracy": round(candidate_accuracy, 6),
                "window": len(recent_rows),
            }
        incumbent_accuracy = self._accuracy_for_rows(incumbent_model, incumbent_scaler, recent_rows)
        accepted = candidate_accuracy >= incumbent_accuracy + float(min_recent_accuracy_lift)
        return {
            "accepted": accepted,
            "reason": "passed" if accepted else "insufficient_recent_accuracy_lift",
            "candidate_accuracy": round(candidate_accuracy, 6),
            "incumbent_accuracy": round(incumbent_accuracy, 6),
            "required_lift": round(float(min_recent_accuracy_lift), 6),
            "window": len(recent_rows),
        }

    def _accuracy_for_rows(self, model, scaler, rows: list[dict]) -> float:
        probabilities = self._predict_rows(model, scaler, rows)
        labels = np.array([row["label"] for row in rows], dtype=np.int32)
        predictions = (probabilities >= self.settings.trade_probability_threshold).astype(np.int32)
        return float(np.mean(predictions == labels)) if len(labels) else 0.0

    def _predict_rows(self, model, scaler, rows: list[dict]) -> np.ndarray:
        probabilities: list[float] = []
        if isinstance(model, dict) and model.get("type") == "regime_ensemble":
            for row in rows:
                probabilities.append(self._predict_regime_ensemble(model, scaler, row["vector"], row["features"]))
            return np.array(probabilities, dtype=np.float32)
        for row in rows:
            vector = row["vector"].reshape(1, -1)
            transformed = scaler.transform(vector) if getattr(model, "_probability_requires_scaler", True) else vector
            probabilities.append(float(model.predict_proba(transformed)[0][1]))
        return np.array(probabilities, dtype=np.float32)

    def _sample_r_multiple(self, sample: dict) -> float:
        pnl = float(sample.get("realized_pnl", sample.get("outcome", 0.0)) or 0.0)
        expected_risk = abs(float(sample.get("expected_risk", 0.01) or 0.01))
        notional = float(sample.get("executed_notional", sample.get("requested_notional", 1.0)) or 1.0)
        return pnl / max(expected_risk * notional, 1e-6)

    def _sample_duration_hours(self, sample: dict) -> float:
        start = self._sample_timestamp(sample)
        end = self._sample_timestamp({"closed_at": sample.get("closed_at"), "updated_at": sample.get("updated_at")})
        if start is None or end is None:
            return 0.0
        return max((end - start).total_seconds() / 3600.0, 0.0)

    def _sample_drawdown(self, sample: dict) -> float:
        return abs(float(sample.get("rolling_drawdown", sample.get("drawdown", 0.0)) or 0.0))

    def _meta_filter_decision(self, *, strategy: str, regime: str, final_score: float) -> dict[str, float | str | bool]:
        metadata = self._load_metadata() or {}
        regime_stats = (metadata.get("trade_intelligence") or {}).get(regime, {})
        win_rate = float(regime_stats.get("win_rate", metadata.get("positive_rate", 0.5)))
        avg_r_multiple = float(regime_stats.get("avg_r_multiple", 0.0))
        avg_drawdown = float(regime_stats.get("avg_drawdown", 0.0))
        allow_trade = True
        reason = "meta_model_approved"
        if win_rate < 0.48:
            allow_trade = False
            reason = "meta_model_low_regime_win_rate"
        elif avg_r_multiple <= 0.0:
            allow_trade = False
            reason = "meta_model_negative_r_multiple"
        elif avg_drawdown >= self.settings.rolling_drawdown_limit:
            allow_trade = False
            reason = "meta_model_regime_drawdown"
        elif final_score < max(self.settings.trade_probability_threshold, 0.35):
            allow_trade = False
            reason = "meta_model_low_final_score"
        return {
            "meta_model_allow_trade": allow_trade,
            "meta_model_reason": reason,
            "meta_model_regime": regime,
            "meta_model_regime_win_rate": round(win_rate, 6),
            "meta_model_avg_r_multiple": round(avg_r_multiple, 6),
            "meta_model_avg_drawdown": round(avg_drawdown, 6),
            "allow_trade": allow_trade,
        }

    def _sanitize_features(self, features: dict[str, float]) -> dict[str, float]:
        sanitized: dict[str, float] = {}
        bounds = {
            "trend_strength": (0.0, 1.5),
            "rsi": (0.0, 100.0),
            "adx": (0.0, 100.0),
            "atr_ratio": (0.0, 1.0),
            "ema_distance": (-1.0, 1.0),
            "price_return": (-1.0, 1.0),
            "breakout_strength": (0.0, 1.5),
            "volume_spike": (0.0, 10.0),
            "candle_body_pct": (0.0, 1.0),
            "upper_wick_pct": (0.0, 1.0),
            "lower_wick_pct": (0.0, 1.0),
            "engulfing": (0.0, 1.0),
            "doji": (0.0, 1.0),
            "sentiment_score": (0.0, 1.0),
            "regime_trending": (0.0, 1.0),
        }
        for key in PROBABILITY_FEATURE_ORDER:
            value = float(features.get(key, 0.0))
            if not math.isfinite(value):
                value = 0.0
            lower, upper = bounds[key]
            sanitized[key] = max(lower, min(value, upper))
        return sanitized

    def _candle_features(self, frame: pd.DataFrame | None) -> dict[str, float]:
        if frame is None or len(frame) < 1:
            return {
                "body_pct": 0.0,
                "upper_wick_pct": 0.0,
                "lower_wick_pct": 0.0,
                "engulfing": 0.0,
                "doji": 0.0,
            }
        latest = frame.iloc[-1]
        open_price = float(latest.get("open", latest.get("close", 0.0)))
        close_price = float(latest.get("close", open_price))
        high_price = float(latest.get("high", max(open_price, close_price)))
        low_price = float(latest.get("low", min(open_price, close_price)))
        candle_range = max(high_price - low_price, 1e-8)
        body = abs(close_price - open_price)
        upper_wick = max(high_price - max(open_price, close_price), 0.0)
        lower_wick = max(min(open_price, close_price) - low_price, 0.0)
        engulfing = 0.0
        if len(frame) >= 2:
            previous = frame.iloc[-2]
            prev_open = float(previous.get("open", previous.get("close", 0.0)))
            prev_close = float(previous.get("close", prev_open))
            engulfing = 1.0 if body > abs(prev_close - prev_open) and (
                min(open_price, close_price) <= min(prev_open, prev_close)
                and max(open_price, close_price) >= max(prev_open, prev_close)
            ) else 0.0
        body_pct = body / candle_range
        doji = 1.0 if body_pct <= 0.1 else 0.0
        return {
            "body_pct": body_pct,
            "upper_wick_pct": upper_wick / candle_range,
            "lower_wick_pct": lower_wick / candle_range,
            "engulfing": engulfing,
            "doji": doji,
        }

    def _frame_ema_distance(self, frame: pd.DataFrame, fallback: float) -> float:
        if "close" not in frame.columns or len(frame) < 5:
            return float(fallback)
        closes = frame["close"].astype(float)
        fast = closes.ewm(span=9, adjust=False).mean().iloc[-1]
        slow = closes.ewm(span=21, adjust=False).mean().iloc[-1]
        return float(fast - slow)
