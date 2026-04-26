import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.drawdown_protection import DrawdownProtectionService


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def publish(self, channel, message):
        self.store[f"pub:{channel}"] = message
        return 1


class DrawdownProtectionTest(unittest.TestCase):
    def test_drawdown_reduces_then_pauses_trading(self):
        cache = InMemoryCache()
        settings = Settings(
            rolling_drawdown_limit=0.05,
            pause_drawdown_limit=0.10,
            default_portfolio_balance=10_000,
        )
        service = DrawdownProtectionService(settings, cache)

        reduced = service.update("u1", 9_400)
        paused = service.update("u1", 8_800)

        self.assertEqual(reduced.state, "REDUCED")
        self.assertEqual(paused.state, "PAUSED")
        self.assertEqual(service.capital_multiplier("u1"), 0.0)

    def test_manual_emergency_stop_blocks_capital_multiplier(self):
        cache = InMemoryCache()
        service = DrawdownProtectionService(Settings(default_portfolio_balance=10_000), cache)

        controls = service.activate_emergency_stop("u1", reason="manual_kill_switch", manual=True)

        self.assertTrue(controls.emergency_stop_manual)
        self.assertTrue(service.load_controls("u1").emergency_stop_active)
        self.assertEqual(service.capital_multiplier("u1"), 0.0)

    def test_daily_loss_limit_triggers_auto_emergency_stop(self):
        cache = InMemoryCache()
        settings = Settings(default_portfolio_balance=10_000, daily_loss_limit=0.05)
        service = DrawdownProtectionService(settings, cache)

        service.update("u1", 10_000)
        service.update("u1", 9_400)
        controls = service.load_controls("u1")

        self.assertTrue(controls.emergency_stop_auto)
        self.assertIn("daily_loss_limit_exceeded", controls.emergency_stop_reason)
        self.assertEqual(service.capital_multiplier("u1"), 0.0)


if __name__ == "__main__":
    unittest.main()
