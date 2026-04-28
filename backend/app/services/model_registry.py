from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

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
        self.probability_versions_dir = self.model_dir / "probability_versions"
        self.probability_versions_dir.mkdir(parents=True, exist_ok=True)
        self.probability_registry_path = self.model_dir / "model_registry.json"
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
        previous_metadata = self.load_probability_metadata() or {}
        previous_version = str(previous_metadata.get("model_version", "") or "").strip() or None
        promoted_at = datetime.now(timezone.utc).isoformat()
        enriched_metadata = {
            **metadata,
            "promoted_at": promoted_at,
            "previous_model_version": previous_version,
        }
        if self.probability_model_path.exists():
            shutil.copy2(self.probability_model_path, self.probability_fallback_model_path)
        if self.probability_scaler_path.exists():
            shutil.copy2(self.probability_scaler_path, self.probability_fallback_scaler_path)
        if self.probability_metadata_path.exists():
            shutil.copy2(self.probability_metadata_path, self.probability_fallback_metadata_path)
        if previous_version:
            self._snapshot_probability_bundle(
                version=previous_version,
                model_path=self.probability_model_path,
                scaler_path=self.probability_scaler_path,
                metadata_path=self.probability_metadata_path,
            )
        self._atomic_joblib_dump(scaler, self.probability_scaler_path)
        self._atomic_joblib_dump(model, self.probability_model_path)
        self._atomic_text_write(
            self.probability_metadata_path,
            json.dumps(enriched_metadata, indent=2, sort_keys=True),
        )
        current_version = str(enriched_metadata.get("model_version", "unknown") or "unknown")
        self._snapshot_probability_bundle(
            version=current_version,
            model_path=self.probability_model_path,
            scaler_path=self.probability_scaler_path,
            metadata_path=self.probability_metadata_path,
        )
        self._append_probability_registry_event(
            {
                "event": "promotion",
                "model_version": current_version,
                "previous_model_version": previous_version,
                "promoted_at": promoted_at,
                "summary": self._promotion_summary(enriched_metadata),
                "recent_validation_accuracy_lift": float(
                    enriched_metadata.get("recent_validation_accuracy_lift", 0.0) or 0.0
                ),
                "trigger_mode": str(enriched_metadata.get("trigger_mode", "") or ""),
                "training_samples": int(enriched_metadata.get("training_samples", 0) or 0),
                "validation_samples": int(enriched_metadata.get("validation_samples", 0) or 0),
            }
        )

    def activate_probability_fallback(self) -> dict | None:
        if not self.probability_fallback_model_path.exists() or not self.probability_fallback_scaler_path.exists():
            return None
        shutil.copy2(self.probability_fallback_model_path, self.probability_model_path)
        shutil.copy2(self.probability_fallback_scaler_path, self.probability_scaler_path)
        metadata = self.load_probability_fallback_metadata()
        if metadata is not None:
            self.save_probability_metadata(metadata)
            self._append_probability_registry_event(
                {
                    "event": "rollback",
                    "model_version": str(metadata.get("model_version", "unknown") or "unknown"),
                    "previous_model_version": None,
                    "promoted_at": datetime.now(timezone.utc).isoformat(),
                    "summary": "Fallback model activated after live degradation.",
                    "recent_validation_accuracy_lift": float(
                        metadata.get("recent_validation_accuracy_lift", 0.0) or 0.0
                    ),
                    "trigger_mode": "rollback",
                    "training_samples": int(metadata.get("training_samples", 0) or 0),
                    "validation_samples": int(metadata.get("validation_samples", 0) or 0),
                }
            )
        return metadata

    def load_probability_registry(self) -> dict:
        if not self.probability_registry_path.exists():
            return {"events": []}
        return json.loads(self.probability_registry_path.read_text(encoding="utf-8"))

    def latest_probability_registry_event(self) -> dict | None:
        events = list((self.load_probability_registry() or {}).get("events", []))
        return events[-1] if events else None

    def annotate_latest_probability_event(self, **updates) -> dict | None:
        registry = self.load_probability_registry()
        events = list(registry.get("events", []))
        if not events:
            return None
        latest = dict(events[-1])
        latest.update(updates)
        if any(key in updates for key in ("trigger_mode", "recent_validation_accuracy_lift", "model_version")):
            latest["summary"] = self._promotion_summary(latest)
        events[-1] = latest
        self._atomic_text_write(
            self.probability_registry_path,
            json.dumps({"events": events[-50:]}, indent=2, sort_keys=True),
        )
        return latest

    def annotate_latest_probability_promotion(self, *, trigger_mode: str) -> None:
        metadata = self.load_probability_metadata() or {}
        if metadata:
            metadata["trigger_mode"] = trigger_mode
            self._atomic_text_write(
                self.probability_metadata_path,
                json.dumps(metadata, indent=2, sort_keys=True),
            )
        registry = self.load_probability_registry()
        events = list(registry.get("events", []))
        if not events:
            return
        self.annotate_latest_probability_event(trigger_mode=trigger_mode)

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

    def _snapshot_probability_bundle(
        self,
        *,
        version: str,
        model_path: Path,
        scaler_path: Path,
        metadata_path: Path,
    ) -> None:
        target_dir = self.probability_versions_dir / version
        target_dir.mkdir(parents=True, exist_ok=True)
        if model_path.exists():
            shutil.copy2(model_path, target_dir / model_path.name)
        if scaler_path.exists():
            shutil.copy2(scaler_path, target_dir / scaler_path.name)
        if metadata_path.exists():
            shutil.copy2(metadata_path, target_dir / metadata_path.name)

    def _append_probability_registry_event(self, event: dict) -> None:
        registry = self.load_probability_registry()
        events = list(registry.get("events", []))
        events.append(event)
        self._atomic_text_write(
            self.probability_registry_path,
            json.dumps({"events": events[-50:]}, indent=2, sort_keys=True),
        )

    def _atomic_joblib_dump(self, payload, destination: Path) -> None:
        temp_path = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
        joblib.dump(payload, temp_path)
        os.replace(temp_path, destination)

    def _atomic_text_write(self, destination: Path, content: str) -> None:
        temp_path = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, destination)

    def _promotion_summary(self, metadata: dict) -> str:
        model_version = str(metadata.get("model_version", "unknown") or "unknown")
        lift = float(metadata.get("recent_validation_accuracy_lift", 0.0) or 0.0)
        trigger_mode = str(metadata.get("trigger_mode", "scheduled") or "scheduled")
        return (
            f"Model {model_version} promoted via {trigger_mode} retrain "
            f"with {lift * 100:.1f}% recent-window accuracy lift."
        )

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
