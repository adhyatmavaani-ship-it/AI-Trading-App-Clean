import asyncio
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.schemas.backtest import BacktestRequest, StrategyOptimizationRequest
from app.services.backtesting import BacktestingEngine
from app.services.risk_engine import RiskEngine
from app.services.strategy_engine import StrategyEngine
from app.services.trade_probability import TradeProbabilityEngine
from app.trading.strategies.base import StrategyDecision


class StubMarketData:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("5m",)):
        payload = {interval: self.frame.copy() for interval in intervals}
        if "15m" not in payload:
            payload["15m"] = self.frame.copy()
        if "1h" not in payload:
            payload["1h"] = self.frame.copy()
        return payload


class StubProbabilityRegistry:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.metadata = None
        self.fallback_model = None
        self.fallback_scaler = None

    def save_probability_model(self, model):
        self.model = model

    def save_probability_scaler(self, scaler):
        self.scaler = scaler

    def promote_probability_model(self, model, scaler, metadata):
        self.fallback_model = self.model
        self.fallback_scaler = self.scaler
        self.model = model
        self.scaler = scaler
        self.metadata = metadata

    def load_probability_model(self):
        return self.model

    def load_probability_scaler(self):
        return self.scaler

    def load_probability_metadata(self):
        return self.metadata


class StubProbabilityFirestore:
    def __init__(self):
        self.reports = []

    def save_model_report(self, report_type, payload):
        self.reports.append({"report_type": report_type, **payload})
        return f"report-{len(self.reports)}"


class TradingIntelligenceLayerTest(unittest.TestCase):
    def _sample_frame(self) -> pd.DataFrame:
        closes = [100.0] * 30 + [100.0 + i for i in range(40)]
        opens = [closes[0], *closes[:-1]]
        highs = [price + 1.0 for price in closes]
        lows = [price - 1.0 for price in closes]
        volumes = [1000.0] * len(closes)
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        open_times = [
            int((start + timedelta(minutes=5 * idx)).timestamp() * 1000)
            for idx in range(len(closes))
        ]
        return pd.DataFrame(
            {
                "open_time": open_times,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )

    def test_strategy_engine_detects_breakout_buy(self):
        engine = StrategyEngine()
        frame = pd.DataFrame(
            {
                "open": [100.0 + i * 0.1 for i in range(24)],
                "high": [101.0 + i * 0.1 for i in range(24)],
                "low": [99.0 + i * 0.1 for i in range(24)],
                "close": [100.0 + i * 0.1 for i in range(23)] + [110.0],
                "volume": [1000.0] * 24,
            }
        )

        decision = engine.analyze(frame, preferred_strategy="breakout")

        self.assertEqual(decision.signal, "BUY")
        self.assertGreater(decision.confidence, 0.4)

    def test_hybrid_strategy_detects_trend_pullback_breakout_buy(self):
        engine = StrategyEngine()
        higher = pd.DataFrame(
            {
                "open": [100.0 + i * 0.8 for i in range(260)],
                "high": [101.0 + i * 0.8 for i in range(260)],
                "low": [99.0 + i * 0.8 for i in range(260)],
                "close": [100.0 + i * 0.8 for i in range(260)],
                "volume": [1200.0] * 260,
            }
        )
        lower_closes = [
            100.0,
            100.4,
            100.9,
            101.3,
            101.9,
            102.4,
            102.9,
            103.3,
            103.8,
            104.1,
            104.4,
            104.7,
            105.0,
            105.3,
            105.6,
            105.9,
            106.1,
            106.3,
            106.6,
            106.8,
            106.1,
            105.4,
            104.8,
            104.3,
            103.9,
            103.7,
            103.9,
            104.2,
            104.6,
            105.0,
            105.5,
            106.0,
            106.5,
            107.0,
            107.4,
            107.8,
            108.2,
            108.6,
            109.0,
            110.4,
        ]
        lower = pd.DataFrame(
            {
                "open": [100.0] + lower_closes[:-1],
                "high": [price + 0.5 for price in lower_closes[:-1]] + [111.0],
                "low": [price - 0.4 for price in lower_closes[:-1]] + [109.7],
                "close": lower_closes,
                "volume": [950.0] * 39 + [2400.0],
            }
        )

        decision = engine.analyze(
            {"5m": lower, "1h": higher},
            preferred_strategy="hybrid_crypto",
        )

        self.assertEqual(decision.signal, "BUY")
        self.assertGreater(decision.confidence, 0.5)
        self.assertIn("stop_loss", decision.metadata)
        self.assertIn("take_profit", decision.metadata)
        self.assertEqual(decision.metadata["regime_type"], "TRENDING")
        self.assertIn("adjusted_confidence", decision.metadata)

    def test_hybrid_strategy_is_blocked_in_ranging_regime(self):
        engine = StrategyEngine()
        higher = pd.DataFrame(
            {
                "open": [100.0 + ((-1) ** i) * 0.2 for i in range(260)],
                "high": [100.8 + ((-1) ** i) * 0.2 for i in range(260)],
                "low": [99.2 + ((-1) ** i) * 0.2 for i in range(260)],
                "close": [100.0 + ((-1) ** i) * 0.15 for i in range(260)],
                "volume": [1000.0] * 260,
            }
        )
        lower = pd.DataFrame(
            {
                "open": [100.0 + i * 0.02 for i in range(40)],
                "high": [100.3 + i * 0.02 for i in range(40)],
                "low": [99.7 + i * 0.02 for i in range(40)],
                "close": [100.0 + i * 0.02 for i in range(39)] + [101.5],
                "volume": [900.0] * 39 + [2000.0],
            }
        )

        decision = engine.analyze(
            {"5m": lower, "1h": higher},
            preferred_strategy="hybrid_crypto",
        )

        self.assertEqual(decision.signal, "HOLD")
        self.assertEqual(decision.metadata["regime_type"], "RANGING")
        self.assertEqual(decision.metadata["adjusted_confidence"], 0.0)

    def test_backtesting_engine_returns_equity_curve_and_metrics(self):
        frame = self._sample_frame()
        market_data = StubMarketData(frame)
        settings = Settings()
        engine = BacktestingEngine(
            settings=settings,
            market_data=market_data,
            feature_pipeline=None,
            ai_engine=None,
            strategy_engine=StrategyEngine(),
            risk_engine=RiskEngine(settings),
        )
        request = BacktestRequest(
            symbol="BTCUSDT",
            timeframe="5m",
            strategy="ema_crossover",
            starting_balance=10_000,
            start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        response = asyncio.run(engine.run(request))

        self.assertGreaterEqual(response.metrics.pnl, 0.0)
        self.assertGreaterEqual(response.metrics.win_rate, 0.0)
        self.assertGreaterEqual(response.metrics.max_drawdown, 0.0)
        self.assertGreater(len(response.equity_curve), 0)
        self.assertGreaterEqual(response.metrics.trades, 1)

    def test_strategy_optimization_returns_best_ranked_result(self):
        frame = self._sample_frame()
        market_data = StubMarketData(frame)
        settings = Settings()
        engine = BacktestingEngine(
            settings=settings,
            market_data=market_data,
            feature_pipeline=None,
            ai_engine=None,
            strategy_engine=StrategyEngine(),
            risk_engine=RiskEngine(settings),
        )
        request = StrategyOptimizationRequest(
            symbol="BTCUSDT",
            timeframe="5m",
            strategy="ema_crossover",
            starting_balance=10_000,
            start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ema_fast_periods=[8, 12],
            ema_slow_periods=[21, 30],
            max_parallelism=2,
        )

        response = asyncio.run(engine.optimize(request))

        self.assertEqual(response.best_result.rank, 1)
        self.assertEqual(response.total_runs, 4)
        self.assertEqual(len(response.rankings), 4)
        self.assertIn("ema_fast_period", response.best_parameters)

    def test_probability_engine_filters_low_probability_trade(self):
        settings = Settings(
            trade_probability_threshold=0.7,
            probability_min_training_samples=2,
            model_dir=str(Path.cwd() / "tmp-probability-tests"),
        )
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        probability_engine.train(
            [
                {
                    "probability_features": {
                        "trend_strength": 0.9,
                        "rsi": 52.0,
                        "breakout_strength": 0.8,
                        "volume": 7.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "probability_features": {
                        "trend_strength": 0.1,
                        "rsi": 49.0,
                        "breakout_strength": 0.1,
                        "volume": 4.0,
                    },
                    "outcome": 0.0,
                },
            ]
        )
        engine = StrategyEngine(probability_engine=probability_engine)
        frame = pd.DataFrame(
            {
                "open": [100.0 + i * 0.1 for i in range(24)],
                "high": [101.0 + i * 0.1 for i in range(24)],
                "low": [99.0 + i * 0.1 for i in range(24)],
                "close": [100.0 + i * 0.1 for i in range(23)] + [110.0],
                "volume": [40.0] * 24,
            }
        )

        decision = engine.analyze(frame, preferred_strategy="breakout")

        self.assertEqual(decision.signal, "HOLD")
        self.assertLess(decision.metadata["trade_success_probability"], 0.7)

    def test_probability_training_uses_rolling_window_and_promotes_versioned_model(self):
        settings = Settings(
            probability_min_training_samples=2,
            probability_min_validation_samples=2,
            probability_training_window_days=90,
            probability_validation_split=0.4,
        )
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        recent = datetime.now(timezone.utc)
        old = recent - timedelta(days=140)

        result = probability_engine.train(
            [
                {
                    "created_at": recent - timedelta(days=10),
                    "probability_features": {
                        "trend_strength": 0.9,
                        "rsi": 54.0,
                        "adx": 34.0,
                        "atr_ratio": 0.01,
                        "ema_distance": 0.02,
                        "price_return": 0.01,
                        "breakout_strength": 0.8,
                        "volume_spike": 1.8,
                        "candle_body_pct": 0.7,
                        "upper_wick_pct": 0.1,
                        "lower_wick_pct": 0.2,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.7,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": recent - timedelta(days=9),
                    "probability_features": {
                        "trend_strength": 0.2,
                        "rsi": 48.0,
                        "adx": 16.0,
                        "atr_ratio": 0.024,
                        "ema_distance": -0.01,
                        "price_return": -0.006,
                        "breakout_strength": 0.3,
                        "volume_spike": 0.8,
                        "candle_body_pct": 0.28,
                        "upper_wick_pct": 0.38,
                        "lower_wick_pct": 0.14,
                        "engulfing": 0.0,
                        "doji": 1.0,
                        "sentiment_score": 0.42,
                        "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
                {
                    "created_at": recent - timedelta(days=3),
                    "probability_features": {
                        "trend_strength": 0.82,
                        "rsi": 55.0,
                        "adx": 30.0,
                        "atr_ratio": 0.013,
                        "ema_distance": 0.016,
                        "price_return": 0.007,
                        "breakout_strength": 0.72,
                        "volume_spike": 1.4,
                        "candle_body_pct": 0.62,
                        "upper_wick_pct": 0.11,
                        "lower_wick_pct": 0.17,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.66,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": recent - timedelta(days=1),
                    "probability_features": {
                        "trend_strength": 0.2,
                        "rsi": 49.0,
                        "adx": 14.0,
                        "atr_ratio": 0.028,
                        "ema_distance": -0.008,
                        "price_return": -0.006,
                        "breakout_strength": 0.25,
                        "volume_spike": 0.8,
                        "candle_body_pct": 0.24,
                        "upper_wick_pct": 0.42,
                        "lower_wick_pct": 0.15,
                        "engulfing": 0.0,
                        "doji": 1.0,
                        "sentiment_score": 0.4,
                        "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
                {
                    "created_at": old,
                    "probability_features": {
                        "trend_strength": 0.99,
                        "rsi": 60.0,
                        "adx": 45.0,
                        "atr_ratio": 0.01,
                        "ema_distance": 0.03,
                        "price_return": 0.02,
                        "breakout_strength": 0.95,
                        "volume_spike": 2.5,
                        "candle_body_pct": 0.8,
                        "upper_wick_pct": 0.05,
                        "lower_wick_pct": 0.1,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.9,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
            ]
        )

        self.assertTrue(result["trained"])
        self.assertEqual(result["samples"], 4)
        self.assertIsNotNone(registry.model)
        self.assertEqual(registry.metadata["model_version"], "prob-v1")
        self.assertIn("analysis", result)
        self.assertIn("trade_intelligence", registry.metadata)
        self.assertIn("regime_performance", registry.metadata)

    def test_probability_promotion_rejects_candidate_worse_than_active_model(self):
        settings = Settings(
            probability_min_training_samples=4,
            probability_min_validation_samples=2,
            probability_validation_split=0.4,
        )
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)

        outperform = probability_engine._outperforms(
            {
                "precision": 0.74,
                "calibration_error": 0.09,
                "accuracy": 0.68,
            },
            {
                "precision": 0.88,
                "calibration_error": 0.04,
                "accuracy": 0.71,
            },
        )

        self.assertFalse(outperform)

    def test_probability_analysis_reports_data_quality_and_drift(self):
        settings = Settings(
            probability_training_window_days=120,
        )
        registry = StubProbabilityRegistry()
        firestore = StubProbabilityFirestore()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry, firestore=firestore)
        now = datetime.now(timezone.utc)

        report = probability_engine.analyze_training_data(
            [
                {
                    "created_at": now - timedelta(days=20),
                    "probability_features": {
                        "trend_strength": 0.8,
                        "rsi": 54.0,
                        "adx": 28.0,
                        "atr_ratio": 0.01,
                        "ema_distance": 0.012,
                        "price_return": 0.007,
                        "breakout_strength": 0.7,
                        "volume_spike": 1.4,
                        "candle_body_pct": 0.62,
                        "upper_wick_pct": 0.12,
                        "lower_wick_pct": 0.18,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.65,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": now - timedelta(days=10),
                    "probability_features": {
                        "trend_strength": 0.25,
                        "rsi": 47.0,
                        "adx": 16.0,
                        "atr_ratio": 0.024,
                        "ema_distance": -0.008,
                        "price_return": -0.006,
                        "breakout_strength": 0.28,
                        "volume_spike": 0.85,
                        "candle_body_pct": 0.26,
                        "upper_wick_pct": 0.4,
                        "lower_wick_pct": 0.14,
                        "engulfing": 0.0,
                        "doji": 1.0,
                        "sentiment_score": 0.38,
                        "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
            ]
        )

        self.assertEqual(report["sample_count"], 2)
        self.assertIn("drift", report)
        self.assertEqual(firestore.reports[0]["report_type"], "trade_probability_analysis")

    def test_probability_analysis_flags_distribution_drift(self):
        settings = Settings(probability_training_window_days=180)
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        now = datetime.now(timezone.utc)

        report = probability_engine.analyze_training_data(
            [
                {
                    "created_at": now - timedelta(days=30),
                    "probability_features": {
                        "trend_strength": 0.05,
                        "rsi": 41.0,
                        "adx": 8.0,
                        "atr_ratio": 0.04,
                        "ema_distance": -0.03,
                        "price_return": -0.02,
                        "breakout_strength": 0.1,
                        "volume_spike": 0.5,
                        "candle_body_pct": 0.18,
                        "upper_wick_pct": 0.55,
                        "lower_wick_pct": 0.07,
                        "engulfing": 0.0,
                        "doji": 1.0,
                        "sentiment_score": 0.2,
                        "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
                {
                    "created_at": now - timedelta(days=25),
                    "probability_features": {
                        "trend_strength": 0.08,
                        "rsi": 42.0,
                        "adx": 9.0,
                        "atr_ratio": 0.038,
                        "ema_distance": -0.028,
                        "price_return": -0.018,
                        "breakout_strength": 0.12,
                        "volume_spike": 0.55,
                        "candle_body_pct": 0.2,
                        "upper_wick_pct": 0.52,
                        "lower_wick_pct": 0.09,
                        "engulfing": 0.0,
                        "doji": 1.0,
                        "sentiment_score": 0.22,
                        "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
                {
                    "created_at": now - timedelta(days=2),
                    "probability_features": {
                        "trend_strength": 1.2,
                        "rsi": 63.0,
                        "adx": 42.0,
                        "atr_ratio": 0.008,
                        "ema_distance": 0.03,
                        "price_return": 0.02,
                        "breakout_strength": 0.95,
                        "volume_spike": 2.2,
                        "candle_body_pct": 0.84,
                        "upper_wick_pct": 0.05,
                        "lower_wick_pct": 0.1,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.85,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": now - timedelta(days=1),
                    "probability_features": {
                        "trend_strength": 1.15,
                        "rsi": 61.0,
                        "adx": 40.0,
                        "atr_ratio": 0.009,
                        "ema_distance": 0.028,
                        "price_return": 0.018,
                        "breakout_strength": 0.9,
                        "volume_spike": 2.0,
                        "candle_body_pct": 0.8,
                        "upper_wick_pct": 0.06,
                        "lower_wick_pct": 0.1,
                        "engulfing": 1.0,
                        "doji": 0.0,
                        "sentiment_score": 0.82,
                        "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
            ]
        )

        self.assertTrue(report["drift"]["drift_detected"])
        self.assertIn("distribution_drift_detected", report["issues_found"])

    def test_regime_specialized_model_marks_selected_regime_in_decision(self):
        settings = Settings(
            trade_probability_threshold=0.55,
            probability_min_training_samples=2,
            probability_min_validation_samples=2,
            probability_validation_split=0.4,
        )
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        now = datetime.now(timezone.utc)
        probability_engine.train(
            [
                {
                    "created_at": now - timedelta(days=12),
                    "probability_features": {
                        "trend_strength": 0.9, "rsi": 56.0, "adx": 33.0, "atr_ratio": 0.01,
                        "ema_distance": 0.018, "price_return": 0.009, "breakout_strength": 0.82,
                        "volume_spike": 1.8, "candle_body_pct": 0.7, "upper_wick_pct": 0.1,
                        "lower_wick_pct": 0.2, "engulfing": 1.0, "doji": 0.0,
                        "sentiment_score": 0.7, "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": now - timedelta(days=10),
                    "probability_features": {
                        "trend_strength": 0.15, "rsi": 46.0, "adx": 14.0, "atr_ratio": 0.012,
                        "ema_distance": -0.01, "price_return": -0.005, "breakout_strength": 0.2,
                        "volume_spike": 0.9, "candle_body_pct": 0.3, "upper_wick_pct": 0.35,
                        "lower_wick_pct": 0.15, "engulfing": 0.0, "doji": 1.0,
                        "sentiment_score": 0.4, "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
                {
                    "created_at": now - timedelta(days=3),
                    "probability_features": {
                        "trend_strength": 1.0, "rsi": 58.0, "adx": 36.0, "atr_ratio": 0.032,
                        "ema_distance": 0.025, "price_return": 0.014, "breakout_strength": 0.88,
                        "volume_spike": 2.2, "candle_body_pct": 0.78, "upper_wick_pct": 0.08,
                        "lower_wick_pct": 0.12, "engulfing": 1.0, "doji": 0.0,
                        "sentiment_score": 0.76, "regime_trending": 1.0,
                    },
                    "outcome": 1.0,
                },
                {
                    "created_at": now - timedelta(days=1),
                    "probability_features": {
                        "trend_strength": 0.12, "rsi": 43.0, "adx": 12.0, "atr_ratio": 0.03,
                        "ema_distance": -0.02, "price_return": -0.013, "breakout_strength": 0.18,
                        "volume_spike": 0.7, "candle_body_pct": 0.22, "upper_wick_pct": 0.45,
                        "lower_wick_pct": 0.1, "engulfing": 0.0, "doji": 1.0,
                        "sentiment_score": 0.3, "regime_trending": 0.0,
                    },
                    "outcome": 0.0,
                },
            ]
        )
        engine = StrategyEngine(probability_engine=probability_engine)
        frame = pd.DataFrame(
            {
                "open": [100.0 + i * 0.3 for i in range(24)],
                "high": [101.0 + i * 0.3 for i in range(24)],
                "low": [99.0 + i * 0.3 for i in range(24)],
                "close": [100.0 + i * 0.3 for i in range(23)] + [112.0],
                "volume": [1200.0] * 23 + [2600.0],
            }
        )

        decision = engine.analyze(frame, preferred_strategy="breakout")

        self.assertIn(decision.metadata["selected_regime_model"], {"trending", "high_vol", "ranging"})

    def test_meta_model_can_skip_negative_expectancy_regime(self):
        settings = Settings(
            trade_probability_threshold=0.55,
            probability_min_training_samples=2,
            probability_min_validation_samples=2,
            probability_validation_split=0.4,
        )
        registry = StubProbabilityRegistry()
        registry.metadata = {
            "model_version": "prob-v9",
            "calibration_error": 0.04,
            "trade_intelligence": {
                "RANGING": {
                    "win_rate": 0.44,
                    "avg_r_multiple": -0.12,
                    "avg_duration_hours": 1.5,
                    "avg_drawdown": 0.03,
                }
            },
            "positive_rate": 0.5,
        }
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        decision = probability_engine.enrich_decision(
            StrategyDecision(
                strategy="rsi",
                signal="BUY",
                confidence=0.9,
                metadata={"regime_type": "RANGING", "breakout_strength": 0.8},
            ),
            features=probability_engine._sanitize_features(
                {
                    "trend_strength": 0.2,
                    "rsi": 51.0,
                    "adx": 14.0,
                    "atr_ratio": 0.01,
                    "ema_distance": 0.001,
                    "price_return": 0.001,
                    "breakout_strength": 0.8,
                    "volume_spike": 1.1,
                    "candle_body_pct": 0.4,
                    "upper_wick_pct": 0.3,
                    "lower_wick_pct": 0.3,
                    "engulfing": 0.0,
                    "doji": 0.0,
                    "sentiment_score": 0.5,
                    "regime_trending": 0.0,
                }
            ),
        )

        self.assertEqual(decision.signal, "HOLD")
        self.assertEqual(decision.metadata["meta_model_reason"], "meta_model_low_regime_win_rate")

    def test_probability_ranking_boosts_strong_sleeve_and_cuts_weak_overweight_sleeve(self):
        settings = Settings(trade_probability_threshold=0.55)
        registry = StubProbabilityRegistry()
        probability_engine = TradeProbabilityEngine(settings=settings, registry=registry)
        base_features = probability_engine._sanitize_features(
            {
                "trend_strength": 0.45,
                "rsi": 56.0,
                "adx": 24.0,
                "atr_ratio": 0.012,
                "ema_distance": 0.004,
                "price_return": 0.002,
                "breakout_strength": 0.68,
                "volume_spike": 1.25,
                "candle_body_pct": 0.45,
                "upper_wick_pct": 0.22,
                "lower_wick_pct": 0.18,
                "engulfing": 0.0,
                "doji": 0.0,
                "sentiment_score": 0.55,
                "regime_trending": 1.0,
            }
        )

        strong = probability_engine.enrich_decision(
            StrategyDecision(
                strategy="breakout",
                signal="BUY",
                confidence=0.74,
                metadata={
                    "regime_type": "TRENDING",
                    "factor_sleeve_name": "SOLUSDT",
                    "factor_sleeve_budget_target": 0.34,
                    "factor_sleeve_budget_delta": 0.11,
                    "factor_sleeve_recent_win_rate": 0.64,
                    "factor_sleeve_recent_avg_pnl": 0.018,
                    "factor_sleeve_recent_closed_trades": 8,
                },
            ),
            features=base_features,
        )
        weak = probability_engine.enrich_decision(
            StrategyDecision(
                strategy="breakout",
                signal="BUY",
                confidence=0.74,
                metadata={
                    "regime_type": "TRENDING",
                    "factor_sleeve_name": "DOGEUSDT",
                    "factor_sleeve_budget_target": 0.12,
                    "factor_sleeve_budget_delta": -0.10,
                    "factor_sleeve_recent_win_rate": 0.38,
                    "factor_sleeve_recent_avg_pnl": -0.012,
                    "factor_sleeve_recent_closed_trades": 8,
                },
            ),
            features=base_features,
        )

        self.assertGreater(
            strong.metadata["trade_success_probability"],
            strong.metadata["raw_trade_success_probability"],
        )
        self.assertLess(
            weak.metadata["trade_success_probability"],
            weak.metadata["raw_trade_success_probability"],
        )
        self.assertGreater(
            strong.metadata["final_score"],
            weak.metadata["final_score"],
        )


if __name__ == "__main__":
    unittest.main()

