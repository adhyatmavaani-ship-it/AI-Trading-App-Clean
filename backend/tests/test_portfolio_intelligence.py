import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.portfolio_intelligence import PortfolioIntelligenceService


class PortfolioIntelligenceTest(unittest.TestCase):
    def test_profit_factor_drawdown_and_concentration_cards(self):
        service = PortfolioIntelligenceService(Settings())
        payload = service.build(
            ledger_snapshot={
                "gross_profit": 300.0,
                "gross_loss": 100.0,
                "rolling_drawdown": 0.052,
                "current_equity": 1000.0,
                "positions": [
                    {"symbol": "BTCUSDT", "market_value": 550.0},
                    {"symbol": "ETHUSDT", "market_value": 120.0},
                ],
            },
            strategy_performance={
                "Breakout": {"trades": 20, "wins": 13, "pnl": 240.0},
                "Mean Reversion": {"trades": 8, "wins": 2, "pnl": -120.0},
            },
        )

        self.assertEqual(payload["profit_factor"], 3.0)
        self.assertEqual(payload["strategy_health_tag"], "Healthy Strategy")
        self.assertTrue(payload["drawdown_alert"])
        self.assertEqual(payload["risk_profile_mode"], "conservative")
        self.assertIn("Over-Concentration Risk", payload["concentration_warning"])
        self.assertIn("Breakout", payload["strategy_score_summary"])
        self.assertEqual(payload["strategy_scores"]["Mean Reversion"]["tag"], "Losing Money")


if __name__ == "__main__":
    unittest.main()
