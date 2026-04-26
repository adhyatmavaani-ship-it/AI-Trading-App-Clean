from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ModuleNotFoundError:
    gym = None
    spaces = None

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.vec_env import DummyVecEnv
except ModuleNotFoundError:
    PPO = None
    DummyVecEnv = None

from app.core.config import Settings

if TYPE_CHECKING:
    from app.services.firestore_repo import FirestoreRepository
    from app.services.redis_cache import RedisCache


@dataclass
class RewardProfile:
    volatility_penalty: float = 1.0
    low_volume_penalty: float = 1.0
    confidence_miscalibration_penalty: float = 0.6
    reward_floor: float = -2.5


class LossAdaptiveRewardEnv(gym.Env if gym is not None else object):
    metadata = {"render_modes": []}

    def __init__(self, observation: np.ndarray, reward_profile: RewardProfile):
        if gym is not None:
            super().__init__()
        self._observation = observation.astype(np.float32)
        self.reward_profile = reward_profile
        if spaces is not None:
            self.observation_space = spaces.Box(low=-5.0, high=5.0, shape=(7,), dtype=np.float32)
            self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(3,), dtype=np.float32)

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        if gym is not None:
            super().reset(seed=seed)
        return self._observation, {}

    def step(self, action: np.ndarray):
        volatility = float(self._observation[0])
        illiquidity = float(self._observation[1])
        confidence_gap = float(self._observation[2])
        realized_loss = float(self._observation[3])
        expected_edge = float(self._observation[4])
        slippage_pct = float(self._observation[5])
        imbalance = float(self._observation[6])

        volatility_penalty = max(0.1, self.reward_profile.volatility_penalty + float(action[0]) * 0.25)
        low_volume_penalty = max(0.1, self.reward_profile.low_volume_penalty + float(action[1]) * 0.25)
        confidence_penalty = max(
            0.1,
            self.reward_profile.confidence_miscalibration_penalty + float(action[2]) * 0.20,
        )

        reward = (
            -volatility_penalty * volatility * illiquidity
            - low_volume_penalty * illiquidity * (0.5 + slippage_pct * 2)
            - confidence_penalty * confidence_gap
            - realized_loss
            - max(0.0, -expected_edge) * 0.5
            - imbalance * 0.15
        )
        reward = max(self.reward_profile.reward_floor, reward)
        info = {
            "proposed_profile": {
                "volatility_penalty": round(volatility_penalty, 6),
                "low_volume_penalty": round(low_volume_penalty, 6),
                "confidence_miscalibration_penalty": round(confidence_penalty, 6),
                "reward_floor": self.reward_profile.reward_floor,
            }
        }
        return self._observation, reward, True, False, info


class HeuristicPPOModel:
    def __init__(self):
        self.env = None

    def set_env(self, env) -> None:
        self.env = env

    def learn(self, total_timesteps: int, progress_bar: bool = False):
        return self

    def predict(self, observation, deterministic: bool = True):
        observation = np.asarray(observation, dtype=np.float32)
        action = np.array(
            [
                min(1.0, observation[0] * 6),
                min(1.0, observation[1] * 4),
                min(1.0, observation[2] * 3),
            ],
            dtype=np.float32,
        )
        return action, None

    def save(self, path: str) -> None:
        Path(path).write_text("heuristic-ppo-fallback", encoding="utf-8")


@dataclass
class SelfHealingPPOService:
    settings: Settings
    cache: RedisCache | None = None
    firestore: FirestoreRepository | None = None

    def __post_init__(self) -> None:
        self.artifact_dir = Path(self.settings.model_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.reward_profile_path = self.artifact_dir / "self_healing_reward_profile.json"
        self.ppo_model_path = self.artifact_dir / "self_healing_ppo.zip"
        self.report_dir = self.artifact_dir / "post_mortems"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def handle_trade_outcome(self, trade_id: str, active_trade: dict, pnl: float) -> dict | None:
        if pnl >= 0:
            return None

        reward_profile = self._load_reward_profile()
        context = self._extract_context(active_trade, pnl)
        feature_importance = self._feature_importance(context)
        updated_profile, ppo_diagnostics = self._train_ppo(context, reward_profile)
        self._save_reward_profile(updated_profile)
        report = self._build_post_mortem_report(
            trade_id=trade_id,
            active_trade=active_trade,
            pnl=pnl,
            context=context,
            feature_importance=feature_importance,
            previous_profile=reward_profile,
            updated_profile=updated_profile,
            ppo_diagnostics=ppo_diagnostics,
        )
        self._persist_report(trade_id, report)
        if str(active_trade.get("strategy", "")).startswith("SNIPER"):
            self.record_sniper_trade_outcome(active_trade, pnl, report)
        return report

    def record_sniper_trade_outcome(self, active_trade: dict, pnl: float, report: dict | None = None) -> None:
        symbol = str(active_trade.get("symbol", "")).upper()
        if not symbol or self.cache is None:
            return
        history_key = f"self_healing:sniper_history:{symbol}"
        history = self.cache.get_json(history_key) or {"trades": []}
        thresholds = self.cache.get_json(f"dual_track:thresholds:{symbol}") or self._default_sniper_thresholds()
        history["trades"] = list(history.get("trades", []))[-199:]
        history["trades"].append(
            {
                "symbol": symbol,
                "strategy": active_trade.get("strategy", ""),
                "pnl": pnl,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "entry_rsi_1m": float((active_trade.get("feature_snapshot") or {}).get("1m_rsi", 50.0)),
                "entry_rsi_5m": float((active_trade.get("feature_snapshot") or {}).get("5m_rsi", 50.0)),
                "thresholds": thresholds,
                "report_driver": next(iter((report or {}).get("feature_importance", {})), ""),
            }
        )
        self.cache.set_json(history_key, history, ttl=self.settings.sniper_threshold_ttl_seconds)

    def nightly_sniper_threshold_tuning(self) -> dict:
        if self.cache is None:
            return {"updated_symbols": 0, "symbols": []}
        updated = []
        for key in self._cache_keys("self_healing:sniper_history:"):
            symbol = key.split(":")[-1].upper()
            history = self.cache.get_json(key) or {"trades": []}
            trades = list(history.get("trades", []))
            if not trades:
                continue
            updated_thresholds = self._optimize_sniper_thresholds(symbol, trades)
            self.cache.set_json(
                f"dual_track:thresholds:{symbol}",
                updated_thresholds,
                ttl=self.settings.sniper_threshold_ttl_seconds,
            )
            updated.append({"symbol": symbol, "thresholds": updated_thresholds, "samples": len(trades)})
        result = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_symbols": len(updated),
            "symbols": updated,
        }
        self.cache.set_json("self_healing:sniper_threshold_review", result, ttl=self.settings.monitor_state_ttl_seconds)
        if self.firestore is not None:
            self.firestore.save_performance_snapshot("self_healing:sniper_thresholds", result)
        return result

    def _extract_context(self, active_trade: dict, pnl: float) -> dict[str, float]:
        feature_snapshot = active_trade.get("feature_snapshot", {}) or {}
        notional = max(float(active_trade.get("notional", 0.0)), 1e-8)
        volume_15m = float(feature_snapshot.get("15m_volume", 0.0))
        expected_risk = float(active_trade.get("expected_risk", 0.0))
        slippage_pct = float(active_trade.get("actual_slippage_bps", active_trade.get("expected_slippage_bps", 0.0))) / 10_000
        volume_ratio = min(1.0, volume_15m / 2_500_000) if volume_15m > 0 else 0.0
        illiquidity = 1.0 - volume_ratio
        realized_loss_pct = abs(pnl) / notional
        confidence = float(active_trade.get("confidence", 0.5))
        expected_return = float(active_trade.get("expected_return", 0.0))
        confidence_error = max(0.0, confidence - max(0.0, 1.0 - realized_loss_pct * 8))
        volatility_proxy = max(
            expected_risk,
            abs(float(feature_snapshot.get("1m_return", 0.0))) * 8,
            abs(float(feature_snapshot.get("5m_return", 0.0))) * 4,
        )
        return {
            "volatility": round(volatility_proxy, 6),
            "volume_15m": round(volume_15m, 2),
            "volume_ratio": round(volume_ratio, 6),
            "illiquidity": round(illiquidity, 6),
            "confidence": round(confidence, 6),
            "confidence_error": round(confidence_error, 6),
            "expected_return": round(expected_return, 6),
            "expected_risk": round(expected_risk, 6),
            "realized_loss_pct": round(realized_loss_pct, 6),
            "slippage_pct": round(slippage_pct, 6),
            "order_book_imbalance": round(abs(float(feature_snapshot.get("order_book_imbalance", 0.0))), 6),
            "regime_confidence": round(float(active_trade.get("regime_confidence", 0.5)), 6),
        }

    def _feature_importance(self, context: dict[str, float]) -> dict[str, float]:
        raw_scores = {
            "volatility_regime": context["volatility"] * (0.6 + context["illiquidity"]),
            "low_volume_session": context["illiquidity"] * (0.8 + context["slippage_pct"] * 8),
            "confidence_miscalibration": context["confidence_error"] * (0.8 + context["regime_confidence"]),
            "order_book_instability": context["order_book_imbalance"] * (0.4 + context["volatility"]),
            "return_expectation_gap": max(0.0, context["expected_return"]) + context["realized_loss_pct"],
        }
        total = sum(raw_scores.values()) or 1.0
        normalized = {key: round(value / total, 6) for key, value in raw_scores.items()}
        return dict(sorted(normalized.items(), key=lambda item: item[1], reverse=True))

    def _train_ppo(self, context: dict[str, float], reward_profile: RewardProfile) -> tuple[RewardProfile, dict]:
        observation = np.array(
            [
                context["volatility"],
                context["illiquidity"],
                context["confidence_error"],
                context["realized_loss_pct"],
                context["expected_return"] - context["slippage_pct"],
                context["slippage_pct"],
                context["order_book_imbalance"],
            ],
            dtype=np.float32,
        )

        def build_env():
            return LossAdaptiveRewardEnv(observation=observation, reward_profile=reward_profile)

        env = DummyVecEnv([build_env]) if DummyVecEnv is not None else build_env()
        model = self._load_or_create_model(env)
        if hasattr(model, "set_env"):
            model.set_env(env)
        model.learn(total_timesteps=128, progress_bar=False)
        action, _ = model.predict(observation, deterministic=True)
        action = np.asarray(action, dtype=np.float32)
        heuristic_scale = 1.0 + context["realized_loss_pct"] * 4
        if context["volatility"] >= 0.03 and context["volume_ratio"] <= 0.35:
            heuristic_scale += 0.35

        updated_profile = RewardProfile(
            volatility_penalty=round(
                max(0.2, reward_profile.volatility_penalty + max(0.0, float(action[0])) * 0.20 + context["volatility"] * heuristic_scale),
                6,
            ),
            low_volume_penalty=round(
                max(0.2, reward_profile.low_volume_penalty + max(0.0, float(action[1])) * 0.20 + context["illiquidity"] * heuristic_scale),
                6,
            ),
            confidence_miscalibration_penalty=round(
                max(
                    0.2,
                    reward_profile.confidence_miscalibration_penalty
                    + max(0.0, float(action[2])) * 0.15
                    + context["confidence_error"] * 0.75,
                ),
                6,
            ),
            reward_floor=reward_profile.reward_floor,
        )
        model.save(str(self.ppo_model_path))
        return updated_profile, {
            "timesteps": 128,
            "policy_action": [round(float(component), 6) for component in action.tolist()],
            "observation": [round(float(component), 6) for component in observation.tolist()],
        }

    def _build_post_mortem_report(
        self,
        *,
        trade_id: str,
        active_trade: dict,
        pnl: float,
        context: dict[str, float],
        feature_importance: dict[str, float],
        previous_profile: RewardProfile,
        updated_profile: RewardProfile,
        ppo_diagnostics: dict,
    ) -> dict:
        top_driver = next(iter(feature_importance.keys()), "confidence_miscalibration")
        expected_return = float(active_trade.get("expected_return", 0.0))
        notional = max(float(active_trade.get("notional", 0.0)), 1e-8)
        realized_return = pnl / notional
        return {
            "trade_id": trade_id,
            "symbol": active_trade.get("symbol", "unknown"),
            "side": active_trade.get("side", "unknown"),
            "status": active_trade.get("status", "unknown"),
            "pnl": round(pnl, 6),
            "entry_context": context,
            "feature_importance": feature_importance,
            "confidence_diagnosis": {
                "predicted_confidence": context["confidence"],
                "expected_return_at_entry": expected_return,
                "realized_return": round(realized_return, 6),
                "confidence_gap": context["confidence_error"],
                "why_confidence_was_wrong": self._why_confidence_was_wrong(context, top_driver),
            },
            "reward_adjustment": {
                "before": asdict(previous_profile),
                "after": asdict(updated_profile),
                "delta": {
                    "volatility_penalty": round(updated_profile.volatility_penalty - previous_profile.volatility_penalty, 6),
                    "low_volume_penalty": round(updated_profile.low_volume_penalty - previous_profile.low_volume_penalty, 6),
                    "confidence_miscalibration_penalty": round(
                        updated_profile.confidence_miscalibration_penalty - previous_profile.confidence_miscalibration_penalty,
                        6,
                    ),
                },
                "adjustment_rule": "Penalize high-volatility entries during low-volume sessions and down-weight overconfident signals after losses.",
            },
            "ppo_update": ppo_diagnostics,
            "next_signal_guidance": self._next_signal_guidance(updated_profile, context),
        }

    def _why_confidence_was_wrong(self, context: dict[str, float], top_driver: str) -> str:
        if context["volatility"] >= 0.03 and context["volume_ratio"] <= 0.35:
            return (
                "The model entered during a fast regime shift with thin session volume, so confidence overstated "
                "the true fill quality and understated downside variance."
            )
        if top_driver == "confidence_miscalibration":
            return "The classifier confidence remained elevated even though realized downside moved outside the expected risk envelope."
        if top_driver == "low_volume_session":
            return "Liquidity was too thin relative to the expected edge, so slippage and adverse selection erased the forecast advantage."
        return "Feature interactions at entry overstated signal quality and the reward function is now reweighting those conditions."

    def _next_signal_guidance(self, profile: RewardProfile, context: dict[str, float]) -> dict:
        max_entry_volatility = max(0.01, 0.035 - (profile.volatility_penalty - 1.0) * 0.005)
        min_volume_ratio = min(0.85, 0.30 + (profile.low_volume_penalty - 1.0) * 0.10)
        confidence_floor = min(0.95, 0.55 + profile.confidence_miscalibration_penalty * 0.08)
        return {
            "max_entry_volatility": round(max_entry_volatility, 6),
            "min_volume_ratio": round(min_volume_ratio, 6),
            "min_confidence_if_illiquid": round(confidence_floor, 6),
            "current_context_rejected": context["volatility"] > max_entry_volatility and context["volume_ratio"] < min_volume_ratio,
        }

    def _persist_report(self, trade_id: str, report: dict) -> None:
        report_path = self.report_dir / f"{trade_id}.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if self.cache is not None:
            self.cache.set_json(
                f"self_healing:post_mortem:{trade_id}",
                report,
                ttl=self.settings.monitor_state_ttl_seconds,
            )
            self.cache.set_json(
                "self_healing:reward_profile",
                self._load_reward_profile_dict(),
                ttl=self.settings.monitor_state_ttl_seconds,
            )
        if self.firestore is not None:
            self.firestore.save_performance_snapshot(f"self_healing:{trade_id}", report)

    def _load_reward_profile(self) -> RewardProfile:
        if self.reward_profile_path.exists():
            payload = json.loads(self.reward_profile_path.read_text(encoding="utf-8"))
            return RewardProfile(**payload)
        if self.cache is not None:
            payload = self.cache.get_json("self_healing:reward_profile")
            if payload:
                return RewardProfile(**payload)
        return RewardProfile()

    def _load_reward_profile_dict(self) -> dict:
        return asdict(self._load_reward_profile())

    def _save_reward_profile(self, profile: RewardProfile) -> None:
        payload = asdict(profile)
        self.reward_profile_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if self.cache is not None:
            self.cache.set_json(
                "self_healing:reward_profile",
                payload,
                ttl=self.settings.monitor_state_ttl_seconds,
            )

    def _load_or_create_model(self, env):
        if PPO is None or DummyVecEnv is None:
            return HeuristicPPOModel()
        if self.ppo_model_path.exists():
            return PPO.load(str(self.ppo_model_path), env=env)
        return PPO(
            "MlpPolicy",
            env,
            learning_rate=3e-4,
            n_steps=32,
            batch_size=32,
            gamma=0.95,
            gae_lambda=0.92,
            ent_coef=0.01,
            verbose=0,
        )

    def _optimize_sniper_thresholds(self, symbol: str, trades: list[dict]) -> dict:
        losses = [trade for trade in trades if float(trade.get("pnl", 0.0)) < 0]
        current = self.cache.get_json(f"dual_track:thresholds:{symbol}") or self._default_sniper_thresholds()
        if not losses:
            return current
        avg_loss_rsi_1m = sum(float(trade.get("entry_rsi_1m", current["long_entry_rsi"])) for trade in losses) / len(losses)
        avg_loss_rsi_5m = sum(float(trade.get("entry_rsi_5m", current["long_confirmation_rsi"])) for trade in losses) / len(losses)
        long_entry_rsi = min(65.0, max(current["long_entry_rsi"], avg_loss_rsi_1m + 1.0))
        long_confirmation_rsi = min(60.0, max(current["long_confirmation_rsi"], avg_loss_rsi_5m + 0.5))
        short_entry_rsi = max(35.0, min(current["short_entry_rsi"], avg_loss_rsi_1m - 1.0))
        short_confirmation_rsi = max(40.0, min(current["short_confirmation_rsi"], avg_loss_rsi_5m - 0.5))
        return {
            "long_entry_rsi": round(long_entry_rsi, 4),
            "long_confirmation_rsi": round(long_confirmation_rsi, 4),
            "short_entry_rsi": round(short_entry_rsi, 4),
            "short_confirmation_rsi": round(short_confirmation_rsi, 4),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "nightly_self_healing_ppo",
        }

    def _default_sniper_thresholds(self) -> dict:
        return {
            "long_entry_rsi": float(self.settings.dual_track_sniper_min_rsi),
            "long_confirmation_rsi": 50.0,
            "short_entry_rsi": float(self.settings.dual_track_sniper_max_rsi),
            "short_confirmation_rsi": 50.0,
        }

    def _cache_keys(self, prefix: str) -> list[str]:
        if hasattr(self.cache, "keys"):
            return list(self.cache.keys(f"{prefix}*"))
        return [key for key in getattr(self.cache, "store", {}) if str(key).startswith(prefix)]

