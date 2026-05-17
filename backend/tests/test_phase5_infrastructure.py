import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import AIInference, FeatureSnapshot, SignalResponse  # noqa: E402
from app.services.autonomous_assistant_engine import AutonomousAssistantEngine  # noqa: E402
from app.services.chart_intelligence import build_chart_intelligence  # noqa: E402
from app.services.event_sourced_replay import EventSourcedReplayStore  # noqa: E402
from app.services.gpu_inference_queue import GPUInferenceQueue  # noqa: E402
from app.services.high_availability import HighAvailabilityPlanner  # noqa: E402
from app.services.orderbook_depth_engine import FullDepthOrderbookEngine  # noqa: E402
from app.services.quant_analytics_engine import QuantAnalyticsEngine  # noqa: E402
from app.services.redis_cache import RedisCache  # noqa: E402
from app.services.strategy_sandbox import StrategySandbox  # noqa: E402
from app.services.time_series_store import TimeSeriesStore  # noqa: E402
from app.services.trade_journal_intelligence import TradeJournalIntelligence  # noqa: E402


class Phase5InfrastructureTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "open_time": 1714212000000 + index * 60000,
                    "close_time": 1714212060000 + index * 60000,
                    "open": 100 + index * 0.16,
                    "high": 100.5 + index * 0.20,
                    "low": 99.7 + index * 0.12,
                    "close": 100.2 + index * 0.18,
                    "volume": 1000 + index * 50,
                }
                for index in range(36)
            ]
        )

    def _signal(self) -> SignalResponse:
        return SignalResponse(
            symbol="BTCUSDT",
            timeframe="multi",
            strategy="Momentum Ignition",
            risk_budget=0.01,
            snapshot=FeatureSnapshot(
                symbol="BTCUSDT",
                price=105.0,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                regime="TRENDING",
                volatility=0.018,
                atr=0.7,
                order_book_imbalance=0.18,
                features={"spread_bps": 5.5},
            ),
            inference=AIInference(
                price_forecast_return=0.012,
                confidence_score=0.78,
                trade_probability=0.75,
                decision="BUY",
                expected_return=0.01,
                expected_risk=0.004,
                model_version="phase5-test",
                reason="test",
            ),
        )

    def test_orderbook_depth_engine_builds_ladder_and_detects_pressure(self):
        engine = FullDepthOrderbookEngine()
        analytics = engine.apply_snapshot(
            bids=[(100.0, 10.0), (99.9, 8.0), (99.8, 7.0)],
            asks=[(100.1, 4.0), (100.2, 3.0), (100.3, 2.0)],
            sequence_id=10,
        ).as_dict()

        self.assertEqual(analytics["sequence_id"], 10)
        self.assertTrue(analytics["liquidity_ladder"])
        self.assertGreater(analytics["pressure_score"], 0)
        self.assertIn("execution_quality", analytics)

    def test_event_sourced_replay_store_appends_and_validates(self):
        cache = RedisCache("")
        replay = EventSourcedReplayStore(TimeSeriesStore(cache))

        stream_id = replay.append_event(
            symbol="BTCUSDT",
            event_type="market_event",
            payload={"latest_price": 100.0, "state_hash": "bad"},
        )
        timeline = replay.timeline(symbol="BTCUSDT")

        self.assertIsNotNone(stream_id)
        self.assertEqual(len(timeline), 1)
        self.assertIn("valid", replay.validate(symbol="BTCUSDT"))

    def test_quant_analytics_generates_strategy_diagnostics(self):
        diagnostics = QuantAnalyticsEngine().analyze(
            [
                {"return_pct": 0.01},
                {"return_pct": -0.004},
                {"return_pct": 0.008},
                {"return_pct": -0.003},
                {"return_pct": 0.012},
                {"return_pct": 0.004},
            ]
        )

        self.assertEqual(diagnostics["trade_count"], 6)
        self.assertIn("sharpe_ratio", diagnostics)
        self.assertIn("monte_carlo", diagnostics)

    def test_gpu_queue_batches_jobs_without_gpu_requirement(self):
        queue = GPUInferenceQueue(RedisCache(""))
        queue.enqueue(model="heatmap-v1", symbol="BTCUSDT", payload={"window": 128})

        jobs = queue.dequeue_batch(limit=4)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].runtime, "onnx")

    def test_assistant_sandbox_ha_and_journal_are_advisory(self):
        assistant = AutonomousAssistantEngine().summarize(
            symbol="BTCUSDT",
            orderbook={"pressure_score": 65.0},
            orderflow={"trap_probability": 20.0},
            predictive={"breakout_probability": 72.0},
            risk={"warnings": []},
            regime={"state": "TRENDING"},
        )
        sandbox = StrategySandbox().simulate(
            strategy_name="test",
            replay_events=[
                {"payload": {"decision": "BUY", "latest_price": 100}},
                {"payload": {"decision": "EXIT", "latest_price": 102}},
            ],
        )
        ha = HighAvailabilityPlanner().plan(
            redis_fallback=True,
            queue_depth=600,
            websocket_gaps=4,
            stale_feeds=2,
        )
        journal = TradeJournalIntelligence(RedisCache("")).record(
            user_id="user-1",
            event={
                "type": "trade_decision",
                "symbol": "BTCUSDT",
                "setup_quality": 42,
                "risk_state": "DEGRADED",
                "followed_plan": False,
            },
        )

        self.assertTrue(assistant["replay_safe"])
        self.assertEqual(sandbox["execution_mode"], "SIMULATED_ONLY")
        self.assertEqual(ha["mode"], "DEGRADED")
        self.assertGreater(journal["behavioral_risk_score"], 0)

    def test_chart_payload_exposes_phase5_dom_and_assistant(self):
        payload = build_chart_intelligence(
            symbol="BTCUSDT",
            interval="5m",
            frame=self._frame(),
            signal=self._signal(),
        )

        self.assertIn("orderbook_depth", payload)
        self.assertTrue(payload["orderbook_depth"]["liquidity_ladder"])
        self.assertIn("autonomous_assistant", payload)
        self.assertTrue(payload["render_hints"]["dom_ladder_layer"])
        self.assertIn("shader_pipeline", payload["render_hints"])


if __name__ == "__main__":
    unittest.main()
