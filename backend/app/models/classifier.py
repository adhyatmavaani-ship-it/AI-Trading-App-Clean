from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier


@dataclass
class TradeClassifier:
    model: GradientBoostingClassifier

    @classmethod
    def create(cls) -> "TradeClassifier":
        return cls(
            model=GradientBoostingClassifier(
                n_estimators=300,
                learning_rate=0.03,
                max_depth=3,
                random_state=42,
            )
        )

    def fit(self, x: np.ndarray, y: np.ndarray) -> None:
        self.model.fit(x, y)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        return self.model.predict_proba(x)

    def save(self, path: str) -> None:
        joblib.dump(self.model, path)

    @classmethod
    def load(cls, path: str) -> "TradeClassifier":
        return cls(model=joblib.load(path))
