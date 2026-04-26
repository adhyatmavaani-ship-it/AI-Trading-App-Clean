import asyncio
import unittest
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.portfolio_ledger import PortfolioLedgerService
from app.services.redis_state_manager import RedisStateManager


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl):
        self.store[key] = value

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)


class StubMarketData:
    def __init__(self):
        self.calls = []
        self.frames = {
            "BTCUSDT": pd.DataFrame({"close": [100 + (index * 0.5) for index in range(40)]}),
            "ETHUSDT": pd.DataFrame({"close": [(100 + (index * 0.5)) * 0.5 for index in range(40)]}),
            "SOLUSDT": pd.DataFrame({"close": [40 - (index * 0.2) for index in range(40)]}),
        }

    def latest_stream_price(self, symbol: str):
        return None

    async def fetch_latest_price(self, symbol: str) -> float:
        self.calls.append(symbol)
        prices = {"BTCUSDT": 110.0, "ETHUSDT": 90.0}
        return prices[symbol]

    async def fetch_multi_timeframe_ohlcv(self, symbol: str, intervals=("15m",)) -> dict:
        return {"15m": self.frames[symbol]}


class StubFirestore:
    def __init__(self):
        self.snapshots = []
        self.factor_snapshots = []
        self.factor_performance = []

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots.append((user_id, payload))

    def save_factor_attribution_snapshot(self, user_id, payload):
        self.factor_snapshots.append((user_id, payload))

    def save_factor_sleeve_performance(self, user_id, payload):
        self.factor_performance.append((user_id, payload))


class PortfolioLedgerTest(unittest.TestCase):
    def test_snapshot_tracks_realized_and_unrealized_pnl(self):
        cache = InMemoryCache()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0, portfolio_snapshot_cache_ttl_seconds=2)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager, StubFirestore())

        state_manager.save_active_trade(
            "t1",
            {
                "trade_id": "t1",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 2.0,
                "fees": 1.0,
            },
        )
        ledger.record_trade_open(
            user_id="u1",
            trade_id="t1",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=2.0,
            notional=200.0,
            fee_paid=1.0,
        )

        snapshot = asyncio.run(ledger.portfolio_snapshot("u1"))

        self.assertEqual(snapshot["realized_pnl"], 0.0)
        self.assertAlmostEqual(snapshot["unrealized_pnl"], 19.0, places=6)
        self.assertAlmostEqual(snapshot["current_equity"], 1019.0, places=6)
        self.assertEqual(snapshot["active_trades"], 1)
        self.assertEqual(snapshot["positions"][0]["symbol"], "BTCUSDT")

        ledger.record_trade_close(user_id="u1", trade_id="t1", pnl=25.0)
        state_manager.clear_active_trade("t1")
        closed_snapshot = asyncio.run(ledger.portfolio_snapshot("u1"))

        self.assertAlmostEqual(closed_snapshot["realized_pnl"], 25.0, places=6)
        self.assertAlmostEqual(closed_snapshot["unrealized_pnl"], 0.0, places=6)
        self.assertEqual(closed_snapshot["active_trades"], 0)

    def test_snapshot_fetches_one_price_per_unique_symbol(self):
        cache = InMemoryCache()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0, portfolio_snapshot_cache_ttl_seconds=2)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        for trade_id in ("t1", "t2"):
            state_manager.save_active_trade(
                trade_id,
                {
                    "trade_id": trade_id,
                    "user_id": "u1",
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "entry": 100.0,
                    "executed_quantity": 1.0,
                    "fees": 0.0,
                },
            )
            ledger.record_trade_open(
                user_id="u1",
                trade_id=trade_id,
                symbol="BTCUSDT",
                side="BUY",
                entry_price=100.0,
                executed_quantity=1.0,
                notional=100.0,
                fee_paid=0.0,
            )

        asyncio.run(ledger.portfolio_snapshot("u1"))

        self.assertEqual(market_data.calls, ["BTCUSDT"])

    def test_portfolio_risk_summary_tracks_gross_and_symbol_exposure(self):
        cache = InMemoryCache()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0, portfolio_snapshot_cache_ttl_seconds=2)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        state_manager.save_active_trade(
            "t1",
            {
                "trade_id": "t1",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 2.0,
                "notional": 200.0,
                "fees": 0.0,
            },
        )
        state_manager.save_active_trade(
            "t2",
            {
                "trade_id": "t2",
                "user_id": "u1",
                "symbol": "ETHUSDT",
                "side": "SELL",
                "entry": 50.0,
                "executed_quantity": 4.0,
                "notional": 200.0,
                "fees": 0.0,
            },
        )
        ledger.record_trade_open(
            user_id="u1",
            trade_id="t1",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=2.0,
            notional=200.0,
            fee_paid=0.0,
        )
        ledger.record_trade_open(
            user_id="u1",
            trade_id="t2",
            symbol="ETHUSDT",
            side="SELL",
            entry_price=50.0,
            executed_quantity=4.0,
            notional=200.0,
            fee_paid=0.0,
        )

        summary = ledger.portfolio_risk_summary("u1")

        self.assertEqual(summary["active_trades"], 2)
        self.assertAlmostEqual(summary["gross_exposure"], 400.0, places=6)
        self.assertAlmostEqual(summary["gross_exposure_pct"], 0.4, places=6)
        self.assertEqual(summary["symbol_exposures"]["BTCUSDT"], 200.0)
        self.assertEqual(summary["symbol_exposures"]["ETHUSDT"], 200.0)
        self.assertAlmostEqual(summary["symbol_exposure_pct"]["BTCUSDT"], 0.2, places=6)
        self.assertAlmostEqual(summary["side_exposure_pct"]["BUY"], 0.2, places=6)
        self.assertAlmostEqual(summary["side_exposure_pct"]["SELL"], 0.2, places=6)
        self.assertAlmostEqual(summary["theme_exposure_pct"]["STORE_OF_VALUE"], 0.2, places=6)
        self.assertAlmostEqual(summary["theme_exposure_pct"]["L1"], 0.2, places=6)

    def test_portfolio_concentration_profile_builds_clusters_and_beta_buckets(self):
        cache = InMemoryCache()
        settings = Settings(
            redis_url="redis://unused",
            default_portfolio_balance=1000.0,
            portfolio_snapshot_cache_ttl_seconds=2,
            portfolio_correlation_min_overlap=10,
        )
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        for trade_id, symbol in (("t1", "BTCUSDT"), ("t2", "ETHUSDT")):
            state_manager.save_active_trade(
                trade_id,
                {
                    "trade_id": trade_id,
                    "user_id": "u1",
                    "symbol": symbol,
                    "side": "BUY",
                    "entry": 100.0,
                    "executed_quantity": 2.0,
                    "notional": 200.0,
                    "fees": 0.0,
                },
            )
            ledger.record_trade_open(
                user_id="u1",
                trade_id=trade_id,
                symbol=symbol,
                side="BUY",
                entry_price=100.0,
                executed_quantity=2.0,
                notional=200.0,
                fee_paid=0.0,
            )

        profile = asyncio.run(ledger.portfolio_concentration_profile("u1", candidate_symbol="SOLUSDT"))

        self.assertEqual(profile["cluster_assignments"]["BTCUSDT"], profile["cluster_assignments"]["ETHUSDT"])
        self.assertIn("candidate_cluster_exposure_pct", profile)
        self.assertIn(profile["beta_bucket_assignments"]["BTCUSDT"], {"BETA_HIGH", "BETA_MID", "BETA_LOW"})
        self.assertIn("candidate_beta_bucket_exposure_pct", profile)
        self.assertEqual(profile["factor_model"], "pca_covariance_regime_universe_v1")
        self.assertAlmostEqual(sum(profile["factor_weights"].values()), 1.0, places=5)

    def test_portfolio_concentration_profile_learns_non_uniform_factor_weights(self):
        cache = InMemoryCache()
        settings = Settings(
            redis_url="redis://unused",
            default_portfolio_balance=1000.0,
            portfolio_snapshot_cache_ttl_seconds=2,
            portfolio_correlation_min_overlap=10,
        )
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        market_data.frames["BTCUSDT"] = pd.DataFrame({"close": [100, 101, 102, 104, 107, 111, 116, 122, 129, 137, 146, 156]})
        market_data.frames["ETHUSDT"] = pd.DataFrame({"close": [80, 81, 81.5, 82, 84, 87, 91, 96, 102, 109, 117, 126]})
        market_data.frames["SOLUSDT"] = pd.DataFrame({"close": [50, 50.2, 49.8, 50.5, 49.6, 50.7, 49.4, 51.0, 49.2, 51.3, 49.0, 51.7]})
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        state_manager.save_active_trade(
            "t1",
            {
                "trade_id": "t1",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 2.0,
                "notional": 200.0,
                "fees": 0.0,
            },
        )
        ledger.record_trade_open(
            user_id="u1",
            trade_id="t1",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=2.0,
            notional=200.0,
            fee_paid=0.0,
        )

        profile = asyncio.run(ledger.portfolio_concentration_profile("u1", candidate_symbol="ETHUSDT"))

        weights = profile["factor_weights"]
        self.assertEqual(set(weights.keys()), {"BTCUSDT", "ETHUSDT", "SOLUSDT"})
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=5)
        self.assertNotAlmostEqual(weights["BTCUSDT"], weights["SOLUSDT"], places=3)

    def test_portfolio_concentration_profile_adapts_factor_universe_to_active_book(self):
        cache = InMemoryCache()
        settings = Settings(
            redis_url="redis://unused",
            default_portfolio_balance=1000.0,
            portfolio_snapshot_cache_ttl_seconds=2,
            portfolio_correlation_min_overlap=10,
            portfolio_factor_active_symbol_limit=4,
        )
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        market_data.frames["DOGEUSDT"] = pd.DataFrame({"close": [10, 10.1, 10.4, 10.8, 11.1, 11.6, 12.2, 12.9, 13.7, 14.6, 15.6, 16.7]})
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        for trade_id, symbol, notional in (
            ("t1", "BTCUSDT", 200.0),
            ("t2", "DOGEUSDT", 350.0),
        ):
            state_manager.save_active_trade(
                trade_id,
                {
                    "trade_id": trade_id,
                    "user_id": "u1",
                    "symbol": symbol,
                    "side": "BUY",
                    "entry": 100.0,
                    "executed_quantity": 2.0,
                    "notional": notional,
                    "fees": 0.0,
                },
            )
            ledger.record_trade_open(
                user_id="u1",
                trade_id=trade_id,
                symbol=symbol,
                side="BUY",
                entry_price=100.0,
                executed_quantity=2.0,
                notional=notional,
                fee_paid=0.0,
            )

        profile = asyncio.run(ledger.portfolio_concentration_profile("u1"))

        self.assertIn("DOGEUSDT", profile["factor_weights"])
        self.assertIn("DOGEUSDT", profile["factor_universe_symbols"])
        self.assertIn("DOGEUSDT", profile["factor_attribution"])
        self.assertIn("DOGEUSDT", profile["factor_sleeve_budget_targets"])
        self.assertIn("DOGEUSDT", profile["factor_sleeve_budget_deltas"])
        self.assertAlmostEqual(sum(profile["factor_sleeve_budget_targets"].values()), 1.0, places=5)
        effective_cap = max(
            settings.portfolio_factor_sleeve_budget_cap,
            1.0 / len(profile["factor_sleeve_budget_targets"]),
        )
        self.assertTrue(
            all(
                settings.portfolio_factor_sleeve_budget_floor - 1e-6
                <= value
                <= effective_cap + 1e-6
                for value in profile["factor_sleeve_budget_targets"].values()
            )
        )
        self.assertEqual(profile["dominant_factor_sleeve"], "DOGEUSDT")
        self.assertEqual(profile["factor_model"], "pca_covariance_regime_universe_v1")

    def test_concentration_history_keeps_recent_snapshots(self):
        cache = InMemoryCache()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0, portfolio_snapshot_cache_ttl_seconds=2)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        first = {"updated_at": "2026-01-01T00:00:00+00:00", "gross_exposure_pct": 0.2}
        second = {"updated_at": "2026-01-01T00:05:00+00:00", "gross_exposure_pct": 0.3}
        ledger._persist_concentration_profile("u1", first)
        ledger._persist_concentration_profile("u1", second)

        history = ledger.concentration_history("u1")

        self.assertEqual(len(history), 2)
        self.assertEqual(history[-1]["updated_at"], "2026-01-01T00:05:00+00:00")

    def test_concentration_drift_tracks_sleeve_budget_turnover(self):
        cache = InMemoryCache()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        drift = ledger._concentration_drift(
            {
                "gross_exposure_pct": 0.3,
                "cluster_exposure_pct": {"CLUSTER_1": 0.2},
                "beta_bucket_exposure_pct": {"BETA_HIGH": 0.2},
                "cluster_assignments": {"BTCUSDT": "CLUSTER_1"},
                "factor_sleeve_budget_targets": {"BTCUSDT": 0.60, "ETHUSDT": 0.40},
            },
            {
                "gross_exposure_pct": 0.2,
                "cluster_exposure_pct": {"CLUSTER_1": 0.1},
                "beta_bucket_exposure_pct": {"BETA_HIGH": 0.1},
                "cluster_assignments": {"BTCUSDT": "CLUSTER_1"},
                "factor_sleeve_budget_targets": {"BTCUSDT": 0.50, "ETHUSDT": 0.50},
            },
        )

        self.assertAlmostEqual(drift["factor_sleeve_budget_turnover"], 0.10, places=6)

    def test_factor_history_and_sleeve_performance_are_persisted(self):
        cache = InMemoryCache()
        firestore = StubFirestore()
        settings = Settings(redis_url="redis://unused", default_portfolio_balance=1000.0, portfolio_snapshot_cache_ttl_seconds=2)
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager, firestore)

        state_manager.save_active_trade(
            "t1",
            {
                "trade_id": "t1",
                "user_id": "u1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "entry": 100.0,
                "executed_quantity": 2.0,
                "notional": 200.0,
                "fees": 0.0,
            },
        )
        ledger.record_trade_open(
            user_id="u1",
            trade_id="t1",
            symbol="BTCUSDT",
            side="BUY",
            entry_price=100.0,
            executed_quantity=2.0,
            notional=200.0,
            fee_paid=0.0,
        )
        asyncio.run(ledger.portfolio_concentration_profile("u1"))
        ledger.record_trade_close(user_id="u1", trade_id="t1", pnl=12.5)

        factor_history = ledger.factor_attribution_history("u1")
        sleeve_performance = ledger.sleeve_performance_summary("u1")

        self.assertGreaterEqual(len(factor_history), 1)
        self.assertIn("BTCUSDT", factor_history[-1]["factor_attribution"])
        self.assertIn("factor_sleeve_budget_targets", factor_history[-1])
        self.assertAlmostEqual(sleeve_performance["BTCUSDT"]["realized_pnl"], 12.5, places=6)
        self.assertEqual(sleeve_performance["BTCUSDT"]["wins"], 1)
        self.assertAlmostEqual(sleeve_performance["BTCUSDT"]["recent_realized_pnl"], 12.5, places=6)
        self.assertAlmostEqual(sleeve_performance["BTCUSDT"]["recent_win_rate"], 1.0, places=6)
        self.assertTrue(firestore.factor_snapshots)
        self.assertTrue(firestore.factor_performance)

    def test_sleeve_performance_uses_rolling_recent_window(self):
        cache = InMemoryCache()
        settings = Settings(
            redis_url="redis://unused",
            default_portfolio_balance=1000.0,
            portfolio_snapshot_cache_ttl_seconds=2,
            portfolio_factor_performance_window_trades=3,
        )
        state_manager = RedisStateManager(settings, cache)
        market_data = StubMarketData()
        ledger = PortfolioLedgerService(settings, cache, market_data, state_manager)

        ledger._record_factor_sleeve_outcome(user_id="u1", symbol="BTCUSDT", pnl=10.0)
        ledger._record_factor_sleeve_outcome(user_id="u1", symbol="BTCUSDT", pnl=-4.0)
        ledger._record_factor_sleeve_outcome(user_id="u1", symbol="BTCUSDT", pnl=6.0)
        ledger._record_factor_sleeve_outcome(user_id="u1", symbol="BTCUSDT", pnl=8.0)

        summary = ledger.sleeve_performance_summary("u1")["BTCUSDT"]

        self.assertAlmostEqual(summary["realized_pnl"], 20.0, places=6)
        self.assertAlmostEqual(summary["recent_realized_pnl"], 10.0, places=6)
        self.assertEqual(summary["recent_closed_trades"], 3)
        self.assertAlmostEqual(summary["recent_win_rate"], 0.66666667, places=6)
