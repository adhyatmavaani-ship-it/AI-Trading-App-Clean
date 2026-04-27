import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.portfolio_manager import PortfolioManager


class PortfolioManagerTest(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(redis_url="redis://unused")
        self.manager = PortfolioManager(self.settings)

    def test_compute_allocation_boosts_for_trend_symbol_and_confidence(self):
        allocation = self.manager.compute_allocation(
            confidence=0.85,
            regime="TRENDING",
            symbol_score=0.7,
            drawdown_pct=0.01,
        )

        self.assertGreater(allocation, self.settings.portfolio_base_risk_per_trade)
        self.assertLessEqual(allocation, self.settings.portfolio_max_risk_per_trade)

    def test_compute_allocation_reduces_for_high_vol_and_drawdown(self):
        allocation = self.manager.compute_allocation(
            confidence=0.75,
            regime="HIGH_VOL",
            symbol_score=0.4,
            drawdown_pct=0.12,
        )

        self.assertLess(allocation, self.settings.portfolio_base_risk_per_trade)

    def test_assess_new_trade_reduces_for_correlated_cluster(self):
        active_trades = [
            {"symbol": "BTCUSDT", "side": "BUY", "risk_fraction": 0.01},
            {"symbol": "ETHUSDT", "side": "BUY", "risk_fraction": 0.01},
        ]

        assessment = self.manager.assess_new_trade(
            active_trades=active_trades,
            symbol="SOLUSDT",
            side="BUY",
            proposed_risk_fraction=0.01,
            gross_exposure_pct=0.02,
            correlation_to_portfolio=0.8,
        )

        self.assertTrue(assessment["allow_trade"])
        self.assertLess(assessment["risk_fraction"], 0.01)
        self.assertGreaterEqual(assessment["correlated_count"], 2)

    def test_summary_reports_utilization_and_risk(self):
        summary = self.manager.summary(
            active_trades=[
                {"risk_fraction": 0.01, "portfolio_correlation_risk": 0.8},
                {"risk_fraction": 0.015, "portfolio_correlation_risk": 0.4},
            ],
            gross_exposure_pct=0.21,
        )

        self.assertGreater(summary["capital_utilization"], 0.0)
        self.assertAlmostEqual(summary["risk_exposure"], 0.025, places=6)
        self.assertAlmostEqual(summary["correlation_risk"], 0.6, places=6)


if __name__ == "__main__":
    unittest.main()
