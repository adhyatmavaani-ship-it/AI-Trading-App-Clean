import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import AIInference, FeatureSnapshot, SignalResponse  # noqa: E402
from app.services.advanced_risk_intelligence import AdvancedRiskIntelligence  # noqa: E402
from app.services.broker_abstraction import (  # noqa: E402
    BrokerCapabilityRegistry,
    UnifiedOrderRequest,
)
from app.services.chart_intelligence import build_chart_intelligence  # noqa: E402
from app.services.multi_agent_intelligence import MultiAgentIntelligenceEngine  # noqa: E402
from app.services.orderflow_engine import InstitutionalOrderflowEngine  # noqa: E402
from app.services.predictive_intelligence import PredictiveIntelligenceEngine  # noqa: E402
from app.services.replay_engine import HistoricalReplayEngine  # noqa: E402
from app.services.realtime_integrity import RealtimeIntegritySequencer  # noqa: E402


class Phase4InfrastructureTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        rows = []
        for index in range(40):
            rows.append(
                {
                    "open_time": 1714212000000 + (index * 60000),
                    "close_time": 1714212060000 + (index * 60000),
                    "open": 100.0 + index * 0.20,
                    "high": 100.7 + index * 0.24,
                    "low": 99.8 + index * 0.18,
                    "close": 100.35 + index * 0.22,
                    "volume": 1000 + index * 55,
                }
            )
        return pd.DataFrame(rows)

    def test_orderflow_generates_execution_quality(self):
        snapshot = InstitutionalOrderflowEngine().analyze(
            self._frame(),
            spread_bps=7.5,
        )

        payload = snapshot.as_dict()
        self.assertIn("liquidity_pressure_score", payload)
        self.assertIn(payload["execution_quality"]["state"], {"NORMAL", "DEGRADED"})
        self.assertGreaterEqual(payload["trap_probability"], 0.0)

    def test_chart_intelligence_exposes_phase4_payloads(self):
        payload = build_chart_intelligence(
            symbol="BTCUSDT",
            interval="5m",
            frame=self._frame(),
            signal=SignalResponse(
                symbol="BTCUSDT",
                timeframe="multi",
                strategy="Momentum Ignition",
                risk_budget=0.01,
                snapshot=FeatureSnapshot(
                    symbol="BTCUSDT",
                    price=108.0,
                    timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    regime="TRENDING",
                    volatility=0.018,
                    atr=0.72,
                    order_book_imbalance=0.12,
                    features={"spread_bps": 5.5},
                ),
                inference=AIInference(
                    price_forecast_return=0.012,
                    confidence_score=0.76,
                    trade_probability=0.72,
                    decision="BUY",
                    expected_return=0.01,
                    expected_risk=0.004,
                    model_version="phase4-test",
                    reason="test",
                ),
            ),
        )

        self.assertIn("orderflow", payload)
        self.assertIn("multi_agent_intelligence", payload)
        self.assertIn("predictive_intelligence", payload)
        self.assertIn("advanced_risk_intelligence", payload)
        self.assertTrue(payload["liquidity_heatmap"]["heatmap_zones"])
        self.assertTrue(payload["render_hints"]["heatmap_layer"])

    def test_multi_agent_and_predictive_outputs_are_replay_safe(self):
        agents = MultiAgentIntelligenceEngine().evaluate(
            side="BUY",
            confidence=0.7,
            smc_confluence=0.65,
            liquidity_pressure=0.62,
            regime_confidence=0.72,
            trap_probability=0.20,
            momentum_score=0.66,
            risk_score=0.25,
        )
        prediction = PredictiveIntelligenceEngine().predict(
            current_price=100.0,
            atr=1.2,
            confidence=0.7,
            trend_strength=0.68,
            momentum_score=0.64,
            trap_probability=0.20,
            regime="TRENDING",
            side="BUY",
        )

        self.assertEqual(len(agents["votes"]), 6)
        self.assertGreater(agents["consensus_score"], 0)
        self.assertEqual(len(prediction["confidence_cones"]), 3)

    def test_advanced_risk_is_advisory_only(self):
        payload = AdvancedRiskIntelligence().evaluate(
            volatility=0.04,
            spread_bps=20,
            trap_probability=0.70,
            liquidity_pressure=0.15,
            confidence=0.55,
            regime="COMPRESSION",
        )

        self.assertEqual(payload["risk_state"], "BLOCK_CANDIDATE")
        self.assertIn("Advisory only", payload["execution_note"])

    def test_replay_validation_detects_integrity_mismatch(self):
        envelope = RealtimeIntegritySequencer().envelope(
            {"type": "chart_snapshot", "symbol": "BTCUSDT", "latest_price": 100.0}
        )
        self.assertIsNotNone(envelope)
        corrupted = dict(envelope)
        corrupted["latest_price"] = 101.0
        result = HistoricalReplayEngine().validate([corrupted])

        self.assertFalse(result.valid)
        self.assertEqual(result.mismatch_count, 1)

    def test_broker_registry_normalizes_paper_order_without_execution(self):
        registry = BrokerCapabilityRegistry()
        normalized = registry.normalize(
            "paper",
            UnifiedOrderRequest(
                symbol="btcusdt",
                side="buy",
                quantity=0.01,
                stop_loss=99.0,
                take_profit=104.0,
                client_order_id="test-1",
                paper=True,
            ),
        )

        self.assertEqual(normalized["broker"], "paper")
        self.assertEqual(normalized["symbol"], "BTCUSDT")
        self.assertTrue(registry.capability("paper").supports_bracket_orders)


if __name__ == "__main__":
    unittest.main()
