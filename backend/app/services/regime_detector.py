from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans


@dataclass
class RegimeDetector:
    """Clusters feature states into production-friendly market regimes."""

    cluster_model: KMeans | None = field(default=None, init=False)

    def classify(self, trend_strength: float, volatility: float, mean_reversion: float) -> tuple[str, float]:
        vector = np.array([[trend_strength, volatility, mean_reversion]], dtype=np.float32)
        if self.cluster_model is None:
            seeded = np.array(
                [
                    [0.8, 0.2, 0.2],
                    [0.2, 0.2, 0.8],
                    [0.4, 0.9, 0.5],
                ],
                dtype=np.float32,
            )
            self.cluster_model = KMeans(n_clusters=3, n_init=10, random_state=42)
            self.cluster_model.fit(seeded)
        cluster = int(self.cluster_model.predict(vector)[0])
        centers = self.cluster_model.cluster_centers_
        center = centers[cluster]
        distance = float(np.linalg.norm(vector[0] - center))
        confidence = float(1 / (1 + distance))
        if center[1] > max(center[0], center[2]):
            return "VOLATILE", confidence
        if center[0] >= center[2]:
            return "TRENDING", confidence
        return "RANGING", confidence
