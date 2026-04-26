from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
try:
    import torch
    from torch import nn
except ModuleNotFoundError:
    torch = None
    nn = None

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_cache import RedisCache


class ShockGenerator(nn.Module if nn is not None else object):
    def __init__(self, latent_dim: int = 8, output_dim: int = 3):
        if nn is not None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(latent_dim, 16),
                nn.GELU(),
                nn.Linear(16, output_dim),
                nn.Tanh(),
            )
        else:
            self.net = None

    def forward(self, latent):
        if self.net is None:
            array = np.asarray(latent, dtype=np.float32)
            return np.tanh(array[:, :3])
        return self.net(latent)


class ShockDiscriminator(nn.Module if nn is not None else object):
    def __init__(self, input_dim: int = 3):
        if nn is not None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_dim, 16),
                nn.GELU(),
                nn.Linear(16, 1),
                nn.Sigmoid(),
            )
        else:
            self.net = None

    def forward(self, features):
        if self.net is None:
            array = np.asarray(features, dtype=np.float32)
            return 1 / (1 + np.exp(-array.mean(axis=1, keepdims=True)))
        return self.net(features)


@dataclass
class GenerativeSimulationEngine:
    settings: Settings
    cache: RedisCache
    firestore: FirestoreRepository | None = None

    def __post_init__(self) -> None:
        self.generator = ShockGenerator()
        self.discriminator = ShockDiscriminator()
        if torch is not None:
            torch.manual_seed(42)
        else:
            np.random.seed(42)

    def dream_market_paths(
        self,
        *,
        symbol: str,
        base_price: float,
        horizon_minutes: int,
        path_count: int,
        shock_scenario: dict,
    ) -> dict:
        returns = self._generate_paths(base_price, horizon_minutes, path_count, shock_scenario)
        final_returns = returns[:, -1]
        bounce_probability = float(np.mean(final_returns > 0))
        drawdown_probability = float(np.mean(final_returns < -0.02))
        confidence = "HIGH" if bounce_probability >= 0.90 else "MEDIUM" if bounce_probability >= 0.65 else "LOW"
        heatmap = self._probability_heatmap(returns)
        report = {
            "symbol": symbol,
            "horizon_minutes": horizon_minutes,
            "path_count": path_count,
            "shock_scenario": shock_scenario,
            "bounce_probability": round(bounce_probability, 6),
            "drawdown_probability": round(drawdown_probability, 6),
            "confidence": confidence,
            "heatmap": heatmap,
            "headline": (
                f"{bounce_probability:.0%} probability of bounce in next {horizon_minutes} mins "
                f"based on {path_count:,} simulations."
            ),
        }
        self.cache.set_json(
            f"generative_sim:{symbol.upper()}",
            report,
            ttl=self.settings.monitor_state_ttl_seconds,
        )
        if self.firestore is not None:
            self.firestore.save_performance_snapshot(f"generative-sim:{symbol.upper()}", report)
        return report

    def _generate_paths(self, base_price: float, horizon_minutes: int, path_count: int, shock_scenario: dict) -> np.ndarray:
        steps = max(5, horizon_minutes)
        if torch is not None:
            latent = torch.randn(path_count, 8)
            synthetic_shocks = self.generator(latent).detach().numpy()
        else:
            latent = np.random.normal(size=(path_count, 8)).astype(np.float32)
            synthetic_shocks = np.asarray(self.generator.forward(latent), dtype=np.float32)
        btc_shock = float(shock_scenario.get("btc_drop_pct", 0.0))
        inflation_shock = float(shock_scenario.get("inflation_surprise", 0.0))
        volatility = max(0.005, abs(btc_shock) * 0.7 + inflation_shock * 0.003 + 0.01)
        drift = -abs(btc_shock) * 0.15 + max(0.0, 0.03 - inflation_shock * 0.01)
        paths = np.zeros((path_count, steps), dtype=np.float32)
        paths[:, 0] = base_price
        for step in range(1, steps):
            noise = np.random.normal(loc=drift / steps, scale=volatility / math.sqrt(steps), size=path_count)
            adversarial = synthetic_shocks[:, 0] * 0.002 + synthetic_shocks[:, 1] * inflation_shock * 0.001
            returns = noise + adversarial
            paths[:, step] = paths[:, step - 1] * (1 + returns)
        return paths / base_price - 1

    def _probability_heatmap(self, returns: np.ndarray) -> list[dict]:
        checkpoints = [5, 15, 30, min(60, returns.shape[1] - 1)]
        heatmap = []
        for checkpoint in checkpoints:
            idx = min(checkpoint, returns.shape[1] - 1)
            checkpoint_returns = returns[:, idx]
            heatmap.append(
                {
                    "minute": idx,
                    "profit_prob": round(float(np.mean(checkpoint_returns > 0)), 6),
                    "loss_prob": round(float(np.mean(checkpoint_returns < 0)), 6),
                    "tail_risk_prob": round(float(np.mean(checkpoint_returns < -0.03)), 6),
                }
            )
        return heatmap
