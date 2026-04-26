from __future__ import annotations

from dataclasses import dataclass

from stable_baselines3 import PPO


@dataclass
class StrategyRLAgent:
    model: PPO

    def predict(self, observation):
        action, _ = self.model.predict(observation, deterministic=True)
        return action

    def save(self, path: str) -> None:
        self.model.save(path)

    @classmethod
    def load(cls, path: str) -> "StrategyRLAgent":
        return cls(model=PPO.load(path))
