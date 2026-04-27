from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import joblib
import numpy as np

from app.core.config import Settings
from app.models.classifier import TradeClassifier

if TYPE_CHECKING:
    from app.models.lstm_transformer import LSTMTransformer

try:  # pragma: no cover - environment dependent
    import torch
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    torch = None


class ModelRegistry:
    def __init__(self, settings: Settings):
        self.model_dir = Path(settings.model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.sequence_model_path = self.model_dir / "sequence_model.pt"
        self.classifier_path = self.model_dir / "trade_classifier.joblib"
        self.scaler_path = self.model_dir / "feature_scaler.joblib"
        self.probability_model_path = self.model_dir / "trade_probability_model.joblib"
        self.probability_scaler_path = self.model_dir / "trade_probability_scaler.joblib"
        self.probability_fallback_model_path = self.model_dir / "trade_probability_model_fallback.joblib"
        self.probability_fallback_scaler_path = self.model_dir / "trade_probability_scaler_fallback.joblib"
        self.probability_metadata_path = self.model_dir / "trade_probability_metadata.json"
        self.probability_fallback_metadata_path = self.model_dir / "trade_probability_metadata_fallback.json"
        self.version_path = self.model_dir / "model_version.txt"

    def load_sequence_model(self, input_size: int):
        if torch is None:
            raise RuntimeError("PyTorch is not installed")
        from app.models.lstm_transformer import LSTMTransformer

        model = LSTMTransformer(input_size=input_size)
        if self.sequence_model_path.exists():
            state = torch.load(self.sequence_model_path, map_location="cpu")
            model.load_state_dict(state)
        model.eval()
        return model

    def save_sequence_model(self, model: "LSTMTransformer") -> None:
        if torch is None:
            raise RuntimeError("PyTorch is not installed")
        torch.save(model.state_dict(), self.sequence_model_path)

    def sequence_model_supported(self) -> bool:
        return torch is not None

    def load_classifier(self) -> TradeClassifier:
        if self.classifier_path.exists():
            return TradeClassifier.load(str(self.classifier_path))
        return TradeClassifier.create()

    def save_classifier(self, classifier: TradeClassifier) -> None:
        classifier.save(str(self.classifier_path))

    def save_scaler(self, scaler) -> None:
        joblib.dump(scaler, self.scaler_path)

    def load_scaler(self):
        return joblib.load(self.scaler_path) if self.scaler_path.exists() else None

    def load_probability_model(self):
        return joblib.load(self.probability_model_path) if self.probability_model_path.exists() else None

    def save_probability_model(self, model) -> None:
        joblib.dump(model, self.probability_model_path)

    def load_probability_scaler(self):
        return joblib.load(self.probability_scaler_path) if self.probability_scaler_path.exists() else None

    def save_probability_scaler(self, scaler) -> None:
        joblib.dump(scaler, self.probability_scaler_path)

    def load_probability_fallback_model(self):
        return joblib.load(self.probability_fallback_model_path) if self.probability_fallback_model_path.exists() else None

    def load_probability_fallback_scaler(self):
        return joblib.load(self.probability_fallback_scaler_path) if self.probability_fallback_scaler_path.exists() else None

    def load_probability_metadata(self) -> dict | None:
        if not self.probability_metadata_path.exists():
            return None
        return json.loads(self.probability_metadata_path.read_text(encoding="utf-8"))

    def save_probability_metadata(self, metadata: dict) -> None:
        self.probability_metadata_path.write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_probability_fallback_metadata(self) -> dict | None:
        if not self.probability_fallback_metadata_path.exists():
            return None
        return json.loads(self.probability_fallback_metadata_path.read_text(encoding="utf-8"))

    def promote_probability_model(self, model, scaler, metadata: dict) -> None:
        if self.probability_model_path.exists():
            shutil.copy2(self.probability_model_path, self.probability_fallback_model_path)
        if self.probability_scaler_path.exists():
            shutil.copy2(self.probability_scaler_path, self.probability_fallback_scaler_path)
        if self.probability_metadata_path.exists():
            shutil.copy2(self.probability_metadata_path, self.probability_fallback_metadata_path)
        self.save_probability_scaler(scaler)
        self.save_probability_model(model)
        self.save_probability_metadata(metadata)

    def activate_probability_fallback(self) -> dict | None:
        if not self.probability_fallback_model_path.exists() or not self.probability_fallback_scaler_path.exists():
            return None
        shutil.copy2(self.probability_fallback_model_path, self.probability_model_path)
        shutil.copy2(self.probability_fallback_scaler_path, self.probability_scaler_path)
        metadata = self.load_probability_fallback_metadata()
        if metadata is not None:
            self.save_probability_metadata(metadata)
        return metadata

    def current_version(self) -> str:
        if self.version_path.exists():
            return self.version_path.read_text(encoding="utf-8").strip()
        return "v1"

    def bump_version(self) -> str:
        current = self.current_version()
        prefix = current[0]
        number = int(current[1:]) if current[1:].isdigit() else 1
        next_version = f"{prefix}{number + 1}"
        self.version_path.write_text(next_version, encoding="utf-8")
        return next_version

    @staticmethod
    def vectorize_features(features: dict[str, float]) -> np.ndarray:
        keys = sorted(features.keys())
        return np.array(
            [ModelRegistry._coerce_feature_value(features[key]) for key in keys],
            dtype=np.float32,
        )

    @staticmethod
    def _coerce_feature_value(value) -> float:
        if isinstance(value, bool):
            return 1.0 if value else 0.0
        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)
        if value is None:
            return 0.0
        normalized = str(value).strip().upper()
        regime_map = {
            "DUMPING": -1.0,
            "BEARISH": -1.0,
            "SELL": -1.0,
            "RANGING": 0.0,
            "STAGNANT": 0.0,
            "LOW_VOL": 0.25,
            "HOLD": 0.0,
            "TRENDING": 1.0,
            "BULLISH": 1.0,
            "BUY": 1.0,
            "HIGH_VOL": 2.0,
            "VOLATILE": 2.0,
        }
        if normalized in regime_map:
            return regime_map[normalized]
        try:
            return float(normalized)
        except ValueError:
            return 0.0
