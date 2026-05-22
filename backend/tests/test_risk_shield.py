from datetime import datetime, timezone
import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.risk_shield import RiskShieldBracket, RiskShieldService, UserRiskState


class RiskShieldServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = RiskShieldService(Settings())

    def test_auto_position_size_caps_user_notional(self):
        decision = self.service.evaluate_order(
            side="BUY",
            requested_notional=20_001.0,
            bracket=RiskShieldBracket(entry_price=100.0, stop_loss=95.0, take_profit=110.0),
            user_state=UserRiskState(account_balance=100_000.0),
            now=datetime(2026, 5, 23, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "POSITION_SIZE_EXCEEDS_RISK_LIMIT")
        self.assertEqual(decision.auto_quantity, 200.0)
        self.assertEqual(decision.max_notional, 20_000.0)

    def test_daily_loss_freezes_until_midnight(self):
        decision = self.service.evaluate_order(
            side="BUY",
            requested_notional=1_000.0,
            bracket=RiskShieldBracket(entry_price=100.0, stop_loss=95.0, take_profit=110.0),
            user_state=UserRiskState(account_balance=100_000.0, daily_realized_pnl=-3_000.0),
            now=datetime(2026, 5, 23, 12, 30, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "DAILY_LOSS_LIMIT_REACHED")
        self.assertEqual(decision.locked_until, "2026-05-24T00:00:00+00:00")

    def test_three_consecutive_losses_triggers_cooldown(self):
        decision = self.service.evaluate_order(
            side="SELL",
            requested_notional=1_000.0,
            bracket=RiskShieldBracket(entry_price=100.0, stop_loss=105.0, take_profit=90.0),
            user_state=UserRiskState(account_balance=100_000.0, consecutive_losses=3),
            now=datetime(2026, 5, 23, 12, 30, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.approved)
        self.assertEqual(decision.reason_code, "CONSECUTIVE_LOSS_LOCK")
        self.assertEqual(decision.locked_until, "2026-05-23T14:30:00+00:00")

    def test_rookie_challenge_unlocks_live_status(self):
        decision = self.service.evaluate_order(
            side="BUY",
            requested_notional=1_000.0,
            bracket=RiskShieldBracket(entry_price=100.0, stop_loss=95.0, take_profit=110.0),
            user_state=UserRiskState(
                account_balance=100_000.0,
                closed_trades=10,
                winning_trades=5,
                average_risk_reward=1.5,
            ),
            now=datetime(2026, 5, 23, tzinfo=timezone.utc),
        )

        self.assertTrue(decision.approved)
        self.assertEqual(decision.license_status, "Live Trade Ready")
        self.assertTrue(decision.live_unlocked)


if __name__ == "__main__":
    unittest.main()
