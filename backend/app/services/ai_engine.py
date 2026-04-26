from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import expit

from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.model_registry import ModelRegistry

try:  # pragma: no cover - environment dependent
    import torch
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    torch = None


@dataclass
class AIEngine:
    registry: ModelRegistry

    def infer(self, snapshot: FeatureSnapshot) -> AIInference:
        vector = self.registry.vectorize_features(snapshot.features)
        scaler = self.registry.load_scaler()
        if scaler is not None:
            vector = scaler.transform(vector.reshape(1, -1))[0]
        forecast = self._forecast_return(vector)
        expected_risk = float(max(snapshot.volatility, abs(snapshot.atr / max(snapshot.price, 1e-8))))
        heuristic_score = float(
            np.tanh(
                snapshot.order_book_imbalance * 1.5
                + snapshot.features.get("15m_ema_spread", 0.0) * 50
                - expected_risk
            )
        )

        classifier = self.registry.load_classifier()
        if hasattr(classifier.model, "classes_"):
            probabilities = classifier.predict_proba(vector.reshape(1, -1))[0]
            class_labels = list(classifier.model.classes_)
        else:
            probabilities = np.array([0.2, 0.6, 0.2])
            class_labels = ["BUY", "HOLD", "SELL"]

        probability_map = dict(zip(class_labels, probabilities))
        buy_prob = float(probability_map.get("BUY", 0.0))
        sell_prob = float(probability_map.get("SELL", 0.0))
        hold_prob = float(probability_map.get("HOLD", 0.0))
        forecast_buy = float(expit(forecast * 50))
        forecast_sell = float(expit(-forecast * 50))
        heuristic_buy = max(0.0, heuristic_score)
        heuristic_sell = max(0.0, -heuristic_score)
        ensemble_buy = 0.5 * buy_prob + 0.3 * forecast_buy + 0.2 * heuristic_buy
        ensemble_sell = 0.5 * sell_prob + 0.3 * forecast_sell + 0.2 * heuristic_sell
        ensemble_hold = max(0.0, 1 - max(ensemble_buy, ensemble_sell))
        calibrated_buy = float(expit((ensemble_buy - 0.5) * 4))
        calibrated_sell = float(expit((ensemble_sell - 0.5) * 4))
        calibrated_hold = float(min(1.0, max(0.0, ensemble_hold)))

        if max(calibrated_buy, calibrated_sell) < 0.55:
            decision = "HOLD"
            confidence = calibrated_hold if calibrated_hold else 1 - max(calibrated_buy, calibrated_sell)
        elif calibrated_buy >= calibrated_sell:
            decision = "BUY"
            confidence = calibrated_buy
        else:
            decision = "SELL"
            confidence = calibrated_sell

        expected_return = float(
            0.6 * forecast + 0.25 * (calibrated_buy - calibrated_sell) * expected_risk + 0.15 * heuristic_score * 0.01
        )

        reason = (
            f"ensemble decision from forecast={forecast:.4f}, expected_return={expected_return:.4f}, "
            f"expected_risk={expected_risk:.4f}, regime={snapshot.regime}, "
            f"imbalance={snapshot.order_book_imbalance:.4f}"
        )
        return AIInference(
            price_forecast_return=forecast,
            expected_return=expected_return,
            expected_risk=expected_risk,
            trade_probability=confidence,
            confidence_score=confidence,
            decision=decision,
            model_version=self.registry.current_version(),
            model_breakdown={
                "classifier_buy": buy_prob,
                "classifier_sell": sell_prob,
                "classifier_hold": hold_prob,
                "forecast_buy": forecast_buy,
                "forecast_sell": forecast_sell,
                "heuristic_score": heuristic_score,
                "calibrated_buy": calibrated_buy,
                "calibrated_sell": calibrated_sell,
            },
            reason=reason,
        )

    def _forecast_return(self, vector: np.ndarray) -> float:
        if torch is None or not self.registry.sequence_model_supported():
            return 0.0
        try:
            sequence = torch.tensor(vector.reshape(1, 1, -1), dtype=torch.float32)
            sequence_model = self.registry.load_sequence_model(input_size=sequence.shape[-1])
            with torch.no_grad():
                return float(sequence_model(sequence).item())
        except Exception:
            return 0.0
