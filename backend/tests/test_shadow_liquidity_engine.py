import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.shadow_liquidity_engine import ShadowLiquiditySentinel


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl=None):
        self.store[key] = value


class StubFirestore:
    def __init__(self):
        self.snapshots = {}

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots[user_id] = payload


class ShadowLiquiditySentinelTest(unittest.TestCase):
    def test_shadow_liquidity_alert_fires_for_hidden_whale_flow(self):
        settings = Settings(model_dir=str(Path.cwd() / "tmp-shadow"), redis_url="redis://unused")
        sentinel = ShadowLiquiditySentinel(settings=settings, cache=InMemoryCache(), firestore=StubFirestore())

        report = asyncio.run(
            sentinel.analyze_cross_chain_shadow_liquidity(
                symbol="SOLUSDT",
                chain_payloads={
                    "solana": {
                        "pending_transactions": [
                            {"value_usd": 32_000_000, "private_relay": False},
                            {"value_usd": 18_000_000, "private_relay": False},
                        ],
                        "dust_transfers": [
                            {"cluster_id": "c1", "wallet": f"w{idx}", "token": "SOL", "amount_usd": 25.0}
                            for idx in range(80)
                        ],
                        "token_buys": [{"cluster_id": "c1"} for _ in range(60)],
                        "venue_flows": [
                            {"direction": "DEX_TO_CEX", "amount_usd": 14_000_000},
                            {"direction": "CEX_TO_DEX", "amount_usd": 3_000_000},
                        ],
                    }
                },
            )
        )

        self.assertTrue(report["entry_signal"])
        self.assertGreaterEqual(report["shadow_liquidity_score"], 0.7)
        self.assertIn("Whale alert", report["headline"])


if __name__ == "__main__":
    unittest.main()
