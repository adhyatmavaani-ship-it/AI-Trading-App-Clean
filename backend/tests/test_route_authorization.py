import json
import sys
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.api.routes import frontend, meta, monitoring
from app.core.config import get_settings
from app.middleware.auth import AuthMiddleware
from app.services.container import get_container


class StubDrawdownProtection:
    class _Status:
        state = "ACTIVE"

    def __init__(self):
        self.last_user_id = None

    def load(self, user_id: str):
        self.last_user_id = user_id
        return self._Status()

    def capital_multiplier(self, user_id: str) -> float:
        return 1.0


class StubPortfolioLedger:
    def __init__(self):
        self.history = [
            {
                "updated_at": "2026-04-26T10:00:00+00:00",
                "gross_exposure_pct": 0.25,
                "symbol_exposure_pct": {"BTCUSDT": 0.15, "ETHUSDT": 0.10},
                "side_exposure_pct": {"BUY": 0.25},
                "theme_exposure_pct": {"STORE_OF_VALUE": 0.15, "L1": 0.10},
                "cluster_exposure_pct": {"CLUSTER_1": 0.15, "CLUSTER_2": 0.10},
                "beta_bucket_exposure_pct": {"BETA_HIGH": 0.15, "BETA_MID": 0.10},
                "gross_exposure_drift": 0.02,
                "cluster_concentration_drift": 0.01,
                "beta_bucket_concentration_drift": 0.01,
                "cluster_turnover": 0.10,
                "factor_regime": "TRENDING",
                "factor_model": "pca_covariance_regime_universe_v1",
                "factor_universe_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "factor_weights": {"BTCUSDT": 0.5, "ETHUSDT": 0.3, "SOLUSDT": 0.2},
                "factor_attribution": {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
                "factor_sleeve_performance": {"BTCUSDT": {"realized_pnl": 14.5, "wins": 2, "losses": 1}},
                "dominant_factor_sleeve": "BTCUSDT",
            },
            {
                "updated_at": "2026-04-18T10:00:00+00:00",
                "gross_exposure_pct": 0.18,
                "symbol_exposure_pct": {"BTCUSDT": 0.12},
                "side_exposure_pct": {"BUY": 0.18},
                "theme_exposure_pct": {"STORE_OF_VALUE": 0.12},
                "cluster_exposure_pct": {"CLUSTER_1": 0.12},
                "beta_bucket_exposure_pct": {"BETA_HIGH": 0.12},
                "gross_exposure_drift": 0.00,
                "cluster_concentration_drift": 0.00,
                "beta_bucket_concentration_drift": 0.00,
                "cluster_turnover": 0.00,
                "factor_regime": "RANGING",
                "factor_model": "pca_covariance_regime_universe_v1",
                "factor_universe_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
                "factor_weights": {"BTCUSDT": 0.6, "ETHUSDT": 0.25, "SOLUSDT": 0.15},
                "factor_attribution": {"BTCUSDT": 1.0},
                "factor_sleeve_performance": {"BTCUSDT": {"realized_pnl": 9.0, "wins": 1, "losses": 0}},
                "dominant_factor_sleeve": "BTCUSDT",
            },
        ]

    async def portfolio_snapshot(self, user_id: str) -> dict:
        return {
            "starting_equity": 1000.0,
            "realized_equity": 1020.0,
            "current_equity": 1030.0,
            "absolute_pnl": 30.0,
            "pnl_pct": 0.03,
            "realized_pnl": 20.0,
            "unrealized_pnl": 10.0,
            "peak_equity": 1050.0,
            "rolling_drawdown": 0.01,
            "active_trades": 1,
            "open_notional": 50.0,
            "gross_exposure": 0.05,
            "winning_trades": 2,
            "losing_trades": 1,
            "closed_trades": 3,
            "fees_paid": 1.0,
            "positions": [],
        }

    async def portfolio_concentration_profile(self, user_id: str) -> dict:
        return {
            "updated_at": "2026-04-26T11:00:00+00:00",
            "gross_exposure_pct": 0.3,
            "symbol_exposure_pct": {"BTCUSDT": 0.2, "ETHUSDT": 0.1},
            "side_exposure_pct": {"BUY": 0.3},
            "theme_exposure_pct": {"STORE_OF_VALUE": 0.2, "L1": 0.1},
            "cluster_exposure_pct": {"CLUSTER_1": 0.2, "CLUSTER_2": 0.1},
            "beta_bucket_exposure_pct": {"BETA_HIGH": 0.2, "BETA_MID": 0.1},
            "gross_exposure_drift": 0.03,
            "cluster_concentration_drift": 0.02,
            "beta_bucket_concentration_drift": 0.01,
            "cluster_turnover": 0.15,
            "factor_regime": "TRENDING",
            "factor_model": "pca_covariance_regime_universe_v1",
            "factor_universe_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "factor_weights": {"BTCUSDT": 0.55, "ETHUSDT": 0.30, "SOLUSDT": 0.15},
            "factor_attribution": {"BTCUSDT": 0.68, "ETHUSDT": 0.32},
            "factor_sleeve_performance": {"BTCUSDT": {"realized_pnl": 21.0, "wins": 3, "losses": 1}},
            "factor_sleeve_budget_targets": {"BTCUSDT": 0.58, "ETHUSDT": 0.42},
            "factor_sleeve_budget_deltas": {"BTCUSDT": -0.10, "ETHUSDT": 0.10},
            "factor_sleeve_budget_turnover": 0.12,
            "max_factor_sleeve_budget_gap_pct": 0.10,
            "dominant_over_budget_sleeve": "BTCUSDT",
            "dominant_under_budget_sleeve": "ETHUSDT",
            "dominant_factor_sleeve": "BTCUSDT",
        }

    def concentration_history(self, user_id: str) -> list[dict]:
        return list(self.history)


class StubRedisStateManager:
    def load_active_trade(self, trade_id: str):
        return {
            "trade_id": trade_id,
            "user_id": "alice",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "status": "SUBMITTED",
            "submitted_state": "ACCEPTED",
            "expected_return": 0.01,
        }

    def load_order(self, order_id: str):
        return None

    def restore_orders(self):
        return []


class StubCache:
    def __init__(self):
        self.payloads = {
            "subscription:alice": {
                "user_id": "alice",
                "tier": "free",
                "balance": 20.0,
                "risk_profile": "moderate",
            },
            "subscription:bob": {
                "user_id": "bob",
                "tier": "vip",
                "balance": 1000.0,
                "risk_profile": "aggressive",
            },
            "signal:latest:BTCUSDT": {
                "signal_id": "btc-1",
                "symbol": "BTCUSDT",
                "strategy": "TREND_FOLLOW",
                "alpha_score": 81.0,
                "regime": "TRENDING",
                "price": 65000.0,
                "signal_version": 1,
                "published_at": "2026-01-01T00:00:00+00:00",
                "decision_reason": "eligible free signal",
                "degraded_mode": False,
                "required_tier": "free",
                "min_balance": 0.0,
                "allowed_risk_profiles": ["moderate", "aggressive"],
            },
            "signal:latest:ETHUSDT": {
                "signal_id": "eth-1",
                "symbol": "ETHUSDT",
                "strategy": "TREND_FOLLOW",
                "alpha_score": 96.0,
                "regime": "TRENDING",
                "price": 3200.0,
                "signal_version": 2,
                "published_at": "2026-01-01T00:01:00+00:00",
                "decision_reason": "vip-only signal",
                "degraded_mode": False,
                "required_tier": "vip",
                "min_balance": 500.0,
                "allowed_risk_profiles": ["aggressive"],
            },
            "vom:aggregate:agg-alice": {
                "aggregate_id": "agg-alice",
                "exchange_order_id": "order-1",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "status": "FILLED",
                "requested_quantity": 1.0,
                "executed_quantity": 1.0,
                "remaining_quantity": 0.0,
                "intent_count": 1,
                "allocation_count": 1,
                "retry_count": 0,
                "fee_paid": 1.0,
                "executed_price": 65000.0,
                "participant_user_ids": ["alice"],
                "updated_at": "2026-01-01T00:02:00+00:00",
            },
            "vom:aggregate:agg-bob": {
                "aggregate_id": "agg-bob",
                "exchange_order_id": "order-2",
                "symbol": "ETHUSDT",
                "side": "SELL",
                "status": "FILLED",
                "requested_quantity": 2.0,
                "executed_quantity": 2.0,
                "remaining_quantity": 0.0,
                "intent_count": 1,
                "allocation_count": 1,
                "retry_count": 0,
                "fee_paid": 1.5,
                "executed_price": 3200.0,
                "participant_user_ids": ["bob"],
                "updated_at": "2026-01-01T00:03:00+00:00",
            },
            "vom:aggregate:legacy": {
                "aggregate_id": "legacy",
                "exchange_order_id": "order-3",
                "symbol": "SOLUSDT",
                "side": "BUY",
                "status": "FILLED",
                "requested_quantity": 5.0,
                "executed_quantity": 5.0,
                "remaining_quantity": 0.0,
                "intent_count": 2,
                "allocation_count": 2,
                "retry_count": 0,
                "fee_paid": 0.2,
                "executed_price": 150.0,
                "updated_at": "2026-01-01T00:04:00+00:00",
            },
        }

    def keys(self, pattern: str):
        if pattern == "signal:latest:*":
            return [key for key in self.payloads if key.startswith("signal:latest:")]
        if pattern == "vom:aggregate:*":
            return [key for key in self.payloads if key.startswith("vom:aggregate:")]
        return []

    def get_json(self, key: str):
        return self.payloads.get(key)


class StubSignalBroadcaster:
    def filter_subscriptions(self, signal: dict, subscriptions: list[dict]) -> list[dict]:
        required_tier = str(signal.get("required_tier", "free")).lower()
        min_balance = float(signal.get("min_balance", 0.0))
        allowed_profiles = {str(profile).lower() for profile in signal.get("allowed_risk_profiles", [])}
        tier_order = {"free": 0, "pro": 1, "vip": 2, "institutional": 3}
        eligible = []
        for subscription in subscriptions:
            tier = str(subscription.get("tier", "free")).lower()
            if tier_order.get(tier, 0) < tier_order.get(required_tier, 0):
                continue
            if float(subscription.get("balance", 0.0)) < min_balance:
                continue
            if allowed_profiles and str(subscription.get("risk_profile", "moderate")).lower() not in allowed_profiles:
                continue
            eligible.append(subscription)
        return eligible


class StubMetaController:
    def get_decision_log(self, trade_id: str):
        return {
            "trade_id": trade_id,
            "user_id": "alice",
            "symbol": "BTCUSDT",
            "decision": "APPROVED",
            "strategy": "TREND_FOLLOW",
            "confidence": 0.8,
            "signals": {},
            "conflicts": [],
            "risk_adjustments": {},
            "system_health_snapshot": {
                "healthy": True,
                "degraded": False,
                "reasons": [],
                "latency_ms": 0.0,
                "api_success_rate": 1.0,
                "redis_latency_ms": 0.0,
                "drawdown_state": "ACTIVE",
            },
            "reason": "ok",
            "created_at": "2026-01-01T00:00:00+00:00",
        }

    def analytics_snapshot(self):
        return {
            "blocked_trades": {"total": 0, "reasons": {}},
            "strategy_performance": {},
            "confidence_distribution": {},
            "updated_at": "2026-01-01T00:00:00+00:00",
        }


class StubSystemMonitor:
    def update_portfolio_concentration(self, profile: dict):
        return None

    def snapshot(self, **kwargs):
        return {
            "trading_mode": "paper",
            "api_status": "healthy",
            "latency_ms_p50": 0.0,
            "latency_ms_p95": 0.0,
            "active_trades": 0,
            "error_count": 0,
            "duplicate_signals_blocked": 0,
            "total_signals": 0,
            "whale_veto_blocked": 0,
            "blocked_profitable_signals": 0,
            "veto_efficiency_ratio": 0.0,
            "execution_latency_ms": 0.0,
            "execution_slippage_bps": 0.0,
            "failed_orders": 0,
            "partial_fills": 0,
            "slippage_spikes": 0,
            "degraded_mode": False,
            "drawdown": {
                "current_equity": 1000.0,
                "peak_equity": 1000.0,
                "rolling_drawdown": 0.0,
                "state": kwargs["drawdown"].state,
                "cooldown_until": None,
            },
            "rollout": {
                "stage_index": 1,
                "stage_name": kwargs["rollout"].stage_name,
                "capital_fraction": kwargs["rollout"].capital_fraction,
                "mode": "paper",
                "eligible_for_upgrade": False,
                "downgrade_flag": False,
            },
            "model_stability": {
                "active_model_version": kwargs["model_stability"].active_model_version,
                "fallback_model_version": None,
                "live_win_rate": 0.6,
                "training_win_rate": 0.6,
                "drift_score": 0.0,
                "concentration_drift_score": 0.0,
                "degraded": kwargs["model_stability"].degraded,
            },
            "portfolio_concentration": {
                "gross_exposure_pct": 0.3,
                "max_symbol_exposure_pct": 0.2,
                "max_side_exposure_pct": 0.3,
                "max_theme_exposure_pct": 0.2,
                "max_cluster_exposure_pct": 0.2,
                "max_beta_bucket_exposure_pct": 0.2,
                "max_factor_sleeve_budget_gap_pct": 0.1,
                "factor_sleeve_budget_turnover": 0.12,
                "dominant_symbol": "BTCUSDT",
                "dominant_side": "BUY",
                "dominant_theme": "STORE_OF_VALUE",
                "dominant_cluster": "CLUSTER_1",
                "dominant_beta_bucket": "BETA_HIGH",
                "dominant_over_budget_sleeve": "BTCUSDT",
                "dominant_under_budget_sleeve": "ETHUSDT",
                "symbol_count": 2,
                "theme_count": 2,
                "cluster_count": 2,
                "beta_bucket_count": 2,
            },
        }


class StubRolloutManager:
    class _Status:
        stage_name = "MICRO"
        capital_fraction = 0.01

    def status(self):
        return self._Status()


class StubModelStability:
    def __init__(self):
        self._history = []

    class _Status:
        active_model_version = "v1"
        fallback_model_version = "v0"
        live_win_rate = 0.61
        training_win_rate = 0.60
        drift_score = 0.02
        calibration_error = 0.01
        feature_drift_score = 0.01
        concept_drift_score = 0.01
        concentration_drift_score = 0.0
        retraining_triggered = False
        trading_frequency_multiplier = 1.0
        degraded = False

    def load_status(self):
        status = self._Status()
        if self._history:
            status.concentration_drift_score = self._history[-1]["score"]
            status.trading_frequency_multiplier = 0.85
        return status

    def update_concentration_state(self, profile: dict):
        entry = {
            "updated_at": "2026-04-26T11:05:00+00:00",
            "score": 0.15,
            "gross_exposure_drift": float(profile.get("gross_exposure_drift", 0.0) or 0.0),
            "cluster_concentration_drift": float(profile.get("cluster_concentration_drift", 0.0) or 0.0),
            "beta_bucket_concentration_drift": float(profile.get("beta_bucket_concentration_drift", 0.0) or 0.0),
            "cluster_turnover": float(profile.get("cluster_turnover", 0.0) or 0.0),
            "factor_sleeve_budget_turnover": float(profile.get("factor_sleeve_budget_turnover", 0.0) or 0.0),
            "max_factor_sleeve_budget_gap_pct": float(profile.get("max_factor_sleeve_budget_gap_pct", 0.0) or 0.0),
        }
        self._history.append(entry)
        return self.load_status()

    def concentration_history(self):
        return list(self._history)


class StubContainer:
    def __init__(self):
        self.cache = StubCache()
        self.portfolio_ledger = StubPortfolioLedger()
        self.drawdown_protection = StubDrawdownProtection()
        self.redis_state_manager = StubRedisStateManager()
        self.signal_broadcaster = StubSignalBroadcaster()
        self.meta_controller = StubMetaController()
        self.system_monitor = StubSystemMonitor()
        self.rollout_manager = StubRolloutManager()
        self.model_stability = StubModelStability()


class RouteAuthorizationTest(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        settings = get_settings()
        settings.auth_api_keys_json = json.dumps(
            [
                {"api_key": "alice-token", "user_id": "alice", "key_id": "alice-key"},
                {"api_key": "bob-token", "user_id": "bob", "key_id": "bob-key"},
            ]
        )
        settings.firestore_project_id = ""
        settings.auth_cache_ttl_seconds = 60

        app = FastAPI()
        app.add_middleware(AuthMiddleware)
        app.include_router(frontend.router, prefix="/v1")
        app.include_router(meta.router, prefix="/v1")
        app.include_router(monitoring.router, prefix="/v1")
        self.container = StubContainer()
        app.dependency_overrides[get_container] = lambda: self.container
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        get_settings.cache_clear()

    def test_user_pnl_rejects_cross_user_access(self):
        response = self.client.get(
            "/v1/user/pnl",
            headers={"X-API-Key": "bob-token"},
            params={"user_id": "alice"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error_code"],
            "UNAUTHORIZED_RESOURCE_ACCESS",
        )

    def test_live_signals_are_filtered_by_subscription_eligibility(self):
        response = self.client.get(
            "/v1/signals/live",
            headers={"X-API-Key": "alice-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "BTCUSDT")

    def test_vom_batches_are_filtered_to_authenticated_participant(self):
        response = self.client.get(
            "/v1/vom/batches",
            headers={"X-API-Key": "alice-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["aggregate_id"], "agg-alice")

    def test_trade_timeline_rejects_cross_user_access(self):
        response = self.client.get(
            "/v1/trade/trade-1/timeline",
            headers={"X-API-Key": "bob-token"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error_code"],
            "UNAUTHORIZED_RESOURCE_ACCESS",
        )

    def test_meta_decision_rejects_cross_user_access(self):
        response = self.client.get(
            "/v1/meta/decision/trade-1",
            headers={"X-API-Key": "bob-token"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["detail"]["error_code"],
            "UNAUTHORIZED_RESOURCE_ACCESS",
        )

    def test_monitoring_system_uses_authenticated_user(self):
        response = self.client.get(
            "/v1/monitoring/system",
            headers={"X-API-Key": "alice-token"},
            params={"user_id": "bob"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["drawdown"]["state"], "ACTIVE")
        self.assertEqual(response.json()["portfolio_concentration"]["dominant_symbol"], "BTCUSDT")
        self.assertAlmostEqual(
            response.json()["portfolio_concentration"]["max_factor_sleeve_budget_gap_pct"],
            0.10,
            places=6,
        )
        self.assertEqual(self.container.drawdown_protection.last_user_id, "alice")

    def test_monitoring_concentration_returns_recent_drift_history(self):
        response = self.client.get(
            "/v1/monitoring/concentration",
            headers={"X-API-Key": "alice-token"},
            params={"user_id": "bob"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["latest"]["dominant_symbol"], "BTCUSDT")
        self.assertAlmostEqual(payload["latest"]["gross_exposure_drift"], 0.03, places=6)
        self.assertEqual(payload["latest"]["severity"], "alert")
        self.assertEqual(payload["latest"]["factor_universe_symbols"][0], "BTCUSDT")
        self.assertEqual(payload["latest"]["dominant_factor_sleeve"], "BTCUSDT")
        self.assertEqual(payload["latest"]["factor_sleeve_performance"]["BTCUSDT"]["wins"], 3)
        self.assertEqual(payload["latest"]["factor_weights"]["BTCUSDT"], 0.55)
        self.assertAlmostEqual(payload["latest"]["factor_sleeve_budget_turnover"], 0.12, places=6)
        self.assertEqual(payload["latest"]["dominant_over_budget_sleeve"], "BTCUSDT")
        self.assertEqual(payload["latest"]["top_budget_gaining_sleeves"][0], "ETHUSDT")
        self.assertEqual(payload["latest"]["top_budget_losing_sleeves"][0], "BTCUSDT")
        self.assertEqual(len(payload["history"]), 1)
        self.assertAlmostEqual(payload["history"][0]["cluster_turnover"], 0.10, places=6)

    def test_monitoring_concentration_supports_window_filters(self):
        response = self.client.get(
            "/v1/monitoring/concentration",
            headers={"X-API-Key": "alice-token"},
            params={"window": "7d"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["history"]), 1)

    def test_model_stability_concentration_history_returns_latest_throttling_state(self):
        response = self.client.get(
            "/v1/monitoring/model-stability/concentration",
            headers={"X-API-Key": "alice-token"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["latest_status"]["active_model_version"], "v1")
        self.assertAlmostEqual(payload["latest_status"]["trading_frequency_multiplier"], 0.85, places=6)
        self.assertAlmostEqual(payload["latest_state"]["score"], 0.15, places=6)
        self.assertEqual(payload["latest_state"]["severity"], "alert")
        self.assertAlmostEqual(payload["latest_state"]["factor_sleeve_budget_turnover"], 0.12, places=6)
        self.assertEqual(len(payload["history"]), 1)


if __name__ == "__main__":
    unittest.main()
