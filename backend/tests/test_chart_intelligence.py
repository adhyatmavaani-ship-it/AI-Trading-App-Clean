import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import (  # noqa: E402
    AIInference,
    AlphaContext,
    AlphaDecision,
    FeatureSnapshot,
    SignalResponse,
)
from app.services.chart_intelligence import (  # noqa: E402
    build_chart_intelligence,
    resample_ohlcv,
)


class ChartIntelligenceTest(unittest.TestCase):
    def _frame(self) -> pd.DataFrame:
        rows = []
        for index in range(18):
            rows.append(
                {
                    "open_time": 1714212000000 + (index * 60000),
                    "close_time": 1714212060000 + (index * 60000),
                    "open": 100.0 + (index * 0.2),
                    "high": 100.4 + (index * 0.22),
                    "low": 99.8 + (index * 0.18),
                    "close": 100.1 + (index * 0.24),
                    "volume": 1000 + (index * 75),
                }
            )
        return pd.DataFrame(rows)

    def _signal(self) -> SignalResponse:
        return SignalResponse(
            symbol="BTCUSDT",
            timeframe="multi",
            snapshot=FeatureSnapshot(
                symbol="BTCUSDT",
                price=104.2,
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
                regime="TRENDING",
                regime_confidence=0.82,
                volatility=0.018,
                atr=0.65,
                order_book_imbalance=0.18,
                features={"spread_bps": 6.5},
            ),
            inference=AIInference(
                price_forecast_return=0.012,
                expected_return=0.011,
                expected_risk=0.005,
                trade_probability=0.79,
                confidence_score=0.81,
                decision="BUY",
                model_version="test",
                reason="Momentum ignition",
            ),
            strategy="Momentum Ignition",
            risk_budget=0.01,
            rollout_capital_fraction=1.0,
            alpha=AlphaContext(),
            alpha_decision=AlphaDecision(
                final_score=84.0,
                expected_return=0.011,
                net_expected_return=0.009,
                risk_score=0.21,
                execution_cost_total=0.0008,
                allow_trade=True,
            ),
        )

    def test_resample_ohlcv_supports_three_minute_scalps(self):
        frame = self._frame()

        resampled = resample_ohlcv(frame, minutes=3)

        self.assertGreaterEqual(len(resampled), 5)
        first = resampled.iloc[0]
        self.assertIn("open", resampled.columns)
        self.assertIn("close_time", resampled.columns)
        self.assertGreater(float(first["high"]), float(first["low"]))

    def test_build_chart_intelligence_returns_professional_payload(self):
        payload = build_chart_intelligence(
            symbol="BTCUSDT",
            interval="3m",
            frame=self._frame(),
            signal=self._signal(),
            analytics_summary={"win_rate": 0.64, "best_regime": "TRENDING"},
            assistant_mode="semi_auto",
            learning_enabled=True,
        )

        self.assertEqual(payload["chart_engine"], "custom_canvas_pro")
        self.assertIn(
            payload["market_regime"]["state"],
            {"TRENDING", "HIGH_VOLATILITY"},
        )
        self.assertEqual(payload["active_assistant_mode"], "SEMI_AUTO")
        self.assertIn("Breakout Compression", [item["label"] for item in payload["overlays"]])
        self.assertGreater(payload["opportunity"]["expected_rr"], 1.0)
        self.assertTrue(payload["execution_guide"]["trailing_stop_path"])
        self.assertTrue(payload["strategy_state"]["micro_strategies"])
        self.assertTrue(payload["ai_feed"])
        self.assertIn("smc", payload)
        self.assertGreaterEqual(payload["smc"]["confluence_score"], 0)
        self.assertIn("ai_confidence_engine", payload)
        self.assertIn("smc_confluence", payload["ai_confidence_engine"]["factors"])
        self.assertIn("multi_timeframe_intelligence", payload)
        self.assertTrue(payload["render_hints"]["crosshair_repaint_isolated"])


if __name__ == "__main__":
    unittest.main()
