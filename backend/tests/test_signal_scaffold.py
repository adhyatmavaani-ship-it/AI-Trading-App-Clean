from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import mkdtemp
import unittest

from fastapi.testclient import TestClient

from main import create_app
from models.trade import TradeRecord
from services.broker_adapter import BrokerAdapter


class SignalScaffoldTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(mkdtemp())
        self.db_path = self.temp_dir / "scaffold.db"
        self.app = create_app(db_path=self.db_path)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        for path in sorted(self.temp_dir.glob("**/*"), reverse=True):
            try:
                if path.is_file():
                    path.unlink()
                else:
                    path.rmdir()
            except OSError:
                pass
        try:
            self.temp_dir.rmdir()
        except OSError:
            pass

    def _seed_closed_trade(self, *, strategy: str, pnl: float, symbol: str) -> None:
        now = datetime.now(timezone.utc) - timedelta(days=1)
        self.app.state.trading.db.log_trade(
            TradeRecord(
                strategy=strategy,
                signal="BUY",
                symbol=symbol,
                entry_price=100.0,
                stop_loss=99.0,
                take_profit=102.0,
                exit_price=100.0 + pnl,
                pnl=pnl,
                approved_by_meta=True,
                approved_by_risk=True,
                status="closed",
                created_at=now,
                closed_at=now,
            )
        )

    def _install_stub_price_service(
        self,
        results: dict[str, tuple[float | None, str]],
    ) -> None:
        class StubPriceService:
            def __init__(self, seeded: dict[str, tuple[float | None, str]]) -> None:
                self._results = {
                    key.upper(): (
                        None if value[0] is None else float(value[0]),
                        str(value[1]),
                    )
                    for key, value in seeded.items()
                }

            async def get_prices(self, symbols):
                return {
                    symbol.upper(): self._results[symbol.upper()]
                    for symbol in symbols
                    if symbol.upper() in self._results
                }

        stub = StubPriceService(results)
        self.app.state.trading.price_service = stub
        self.app.state.trading.lifecycle_loop._price_service = stub

    def _install_stub_broker(
        self,
        *,
        response: dict[str, object],
        is_live: bool = False,
    ):
        class StubBroker(BrokerAdapter):
            def __init__(self, seeded_response: dict[str, object]) -> None:
                self._response = dict(seeded_response)
                self.calls: list[dict[str, object]] = []
                self.open_positions: dict[str, dict[str, object]] = {}
                self.open_orders: dict[str, dict[str, object]] = {}
                self.orders: dict[str, dict[str, object]] = {}

            def place_order(self, *, symbol: str, side: str, quantity: float, sl: float, tp: float) -> dict[str, object]:
                self.calls.append(
                    {
                        "symbol": symbol,
                        "side": side,
                        "quantity": quantity,
                        "sl": sl,
                        "tp": tp,
                    }
                )
                response = dict(self._response)
                broker_order_id = str(response.get("broker_order_id", ""))
                if broker_order_id:
                    self.orders[broker_order_id] = dict(response)
                    self.open_positions[symbol.upper()] = {
                        "symbol": symbol.upper(),
                        "side": side.upper(),
                        "qty": float(quantity),
                        "avgPrice": float(response.get("avgPrice", 0.0)),
                        "status": "OPEN",
                        "broker_order_id": broker_order_id,
                    }
                return response

            def get_position(self, symbol: str) -> dict[str, object]:
                return dict(self.open_positions.get(symbol.upper(), {"status": "flat", "symbol": symbol}))

            def close_position(self, symbol: str) -> dict[str, object]:
                self.open_positions.pop(symbol.upper(), None)
                return {"status": "closed", "symbol": symbol}

            def get_open_positions(self) -> dict[str, dict[str, object]]:
                return {symbol: dict(payload) for symbol, payload in self.open_positions.items()}

            def get_open_orders(self) -> dict[str, dict[str, object]]:
                return {order_id: dict(payload) for order_id, payload in self.open_orders.items()}

            def get_order(self, order_id: str) -> dict[str, object] | None:
                payload = self.orders.get(str(order_id))
                return dict(payload) if payload is not None else None

        StubBroker.name = "stub-live" if is_live else "stub-paper"
        StubBroker.is_live = is_live
        stub = StubBroker(response)
        self.app.state.trading.execution_engine._broker = stub
        self.app.state.trading.broker = stub
        self.app.state.trading.sync_engine._broker = stub
        return stub

    def test_signal_execution_and_rejection_flow_is_persisted(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")
            self._seed_closed_trade(strategy="range", pnl=-8.0, symbol=f"ETHUSDT{index}")

        first = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertEqual(first_body["status"], "executed")
        self.assertTrue(first_body["executed"])
        self.assertEqual(first_body["selected_strategy"], "trend")
        self.assertGreater(first_body["confidence"], 0.2)
        self.assertTrue(first_body["meta"]["approved"])
        self.assertEqual(first_body["meta"]["selected_strategy"], "trend")
        self.assertTrue(first_body["risk"]["approved"])
        self.assertEqual(first_body["trade"]["status"], "open")
        self.assertEqual(first_body["trade"]["exchange_status"], "filled")
        self.assertTrue(first_body["trade"]["broker_order_id"].startswith("paper-"))
        self.assertAlmostEqual(first_body["trade"]["stop_loss"], 98.5)
        self.assertAlmostEqual(first_body["trade"]["take_profit"], 103.0)
        self.assertAlmostEqual(first_body["trade"]["position_size"], 133.3333333333)
        self.assertAlmostEqual(first_body["trade"]["atr"], 1.0)

        second = self.client.post(
            "/api/signal",
            json={
                "strategy": "range",
                "signal": "BUY",
                "symbol": "ETHUSDT",
                "price": 200.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(second.status_code, 200)
        second_body = second.json()
        self.assertEqual(second_body["status"], "rejected")
        self.assertFalse(second_body["executed"])
        self.assertEqual(second_body["selected_strategy"], "trend")
        self.assertFalse(second_body["meta"]["approved"])
        self.assertEqual(second_body["trade"]["rejection_reason"], "strategy_disabled_by_kill_switch")
        self.assertEqual(second_body["meta"]["selected_strategy"], "trend")
        self.assertLessEqual(second_body["confidence"], 1.0)

        state = self.client.get("/api/state")
        self.assertEqual(state.status_code, 200)
        state_body = state.json()
        self.assertEqual(state_body["summary"]["total_trades"], 8)
        self.assertEqual(state_body["summary"]["open_trades"], 1)
        self.assertEqual(state_body["summary"]["rejected_trades"], 1)
        self.assertEqual(state_body["summary"]["closed_trades"], 6)
        self.assertEqual(len(state_body["recent_trades"]), 8)
        self.assertEqual(state_body["strategy_performance"][0]["strategy"], "breakout")
        trend = next(item for item in state_body["strategy_performance"] if item["strategy"] == "trend")
        ranged = next(item for item in state_body["strategy_performance"] if item["strategy"] == "range")
        self.assertGreater(trend["recent_win_rate"], ranged["recent_win_rate"])
        self.assertGreater(trend["score"], ranged["score"])
        self.assertFalse(trend["disabled"])
        self.assertTrue(ranged["disabled"])

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")

    def test_low_confidence_trade_is_rejected_by_execution_policy(self) -> None:
        response = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["trade"]["rejection_reason"], "low_confidence")
        self.assertTrue(payload["meta"]["approved"])
        self.assertEqual(payload["confidence"], 0.0)

    def test_live_broker_dry_run_executes_without_sending_order(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "sent",
                "exchange_status": "sent",
                "broker_order_id": "binance-live-1",
            },
            is_live=True,
        )
        self.app.state.trading.execution_engine._dry_run = True

        response = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["executed"])
        self.assertEqual(payload["trade"]["exchange_status"], "dry_run")
        self.assertTrue(payload["trade"]["broker_order_id"].startswith("dryrun-"))
        self.assertEqual(stub.calls, [])
        self.app.state.trading.execution_engine._dry_run = False

    def test_broker_rejection_is_persisted(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_broker(
            response={
                "status": "sent",
                "exchange_status": "sent",
                "broker_order_id": "binance-order-123",
            },
            is_live=False,
        )

        response = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["trade"]["rejection_reason"], "broker_reject")
        self.assertEqual(payload["trade"]["exchange_status"], "sent")
        self.assertEqual(payload["trade"]["broker_order_id"], "binance-order-123")

    def test_kill_switch_blocks_execution(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self.app.state.trading.execution_engine._kill_switch = True
        response = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["trade"]["rejection_reason"], "broker_kill_switch_active")
        self.app.state.trading.execution_engine._kill_switch = False

    def test_max_exposure_blocks_new_execution(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        engine = self.app.state.trading.execution_engine
        engine._cooldown_window = timedelta(0)
        engine._max_open_trades = 10
        engine._max_total_exposure_pct = 1.5

        first = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["executed"])

        second = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "ETHUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["executed"])
        self.assertEqual(second.json()["trade"]["rejection_reason"], "max_exposure_reached")

    def test_cooldown_blocks_immediate_reentry(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        first = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["executed"])

        second = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "ETHUSDT",
                "price": 101.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["executed"])
        self.assertEqual(second.json()["trade"]["rejection_reason"], "cooldown_active")

    def test_max_open_trades_blocks_new_execution(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self.app.state.trading.execution_engine._cooldown_window = timedelta(0)

        for symbol in ("BTCUSDT", "ETHUSDT"):
            response = self.client.post(
                "/api/signal",
                json={
                    "strategy": "trend",
                    "signal": "BUY",
                    "symbol": symbol,
                    "price": 100.0,
                    "atr": 1.0,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["executed"])

        blocked = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "SOLUSDT",
                "price": 102.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(blocked.status_code, 200)
        blocked_body = blocked.json()
        self.assertFalse(blocked_body["executed"])
        self.assertEqual(blocked_body["trade"]["rejection_reason"], "max_open_trades_reached")

    def test_monitor_loop_closes_trade_and_persists_pnl(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        opened_body = opened.json()
        self.assertTrue(opened_body["executed"])
        trade_id = opened_body["trade"]["trade_id"]

        price_push = self.client.post(
            "/api/price",
            json={
                "symbol": "BTCUSDT",
                "price": 103.0,
                "run_monitor": True,
            },
        )
        self.assertEqual(price_push.status_code, 200)
        closed_trades = price_push.json()["closed_trades"]
        self.assertEqual(len(closed_trades), 1)
        self.assertEqual(closed_trades[0]["trade_id"], trade_id)
        self.assertEqual(closed_trades[0]["status"], "closed")
        self.assertEqual(closed_trades[0]["close_reason"], "tp")
        self.assertEqual(closed_trades[0]["price_source"], "manual")
        self.assertAlmostEqual(closed_trades[0]["exit_price"], 102.94)
        self.assertAlmostEqual(closed_trades[0]["pnl"], 2.94)

        state = self.client.get("/api/state")
        self.assertEqual(state.status_code, 200)
        state_body = state.json()
        self.assertEqual(state_body["summary"]["open_trades"], 0)
        self.assertEqual(state_body["summary"]["closed_trades"], 4)

        stored = next(item for item in state_body["recent_trades"] if item["trade_id"] == trade_id)
        self.assertEqual(stored["status"], "closed")
        self.assertEqual(stored["close_reason"], "tp")
        self.assertEqual(stored["price_source"], "manual")
        self.assertAlmostEqual(stored["pnl"], 2.94)

    def test_monitor_run_polls_remote_price_service(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_price_service({"BTCUSDT": (98.5, "live")})

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        monitored = self.client.post("/api/monitor/run")
        self.assertEqual(monitored.status_code, 200)
        payload = monitored.json()
        self.assertEqual(payload["closed_count"], 1)
        closed = payload["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["close_reason"], "sl")
        self.assertEqual(closed["price_source"], "live")
        self.assertAlmostEqual(closed["exit_price"], 98.4)
        self.assertAlmostEqual(closed["pnl"], -1.6)

    def test_cache_price_does_not_close_trade_when_not_close_enough_to_trigger(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_price_service({"BTCUSDT": (98.7, "cache")})

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        monitored = self.client.post("/api/monitor/run")
        self.assertEqual(monitored.status_code, 200)
        payload = monitored.json()
        self.assertEqual(payload["closed_count"], 0)

        state = self.client.get("/api/state")
        self.assertEqual(state.status_code, 200)
        stored = next(item for item in state.json()["recent_trades"] if item["trade_id"] == trade_id)
        self.assertEqual(stored["status"], "open")
        self.assertIsNone(stored["price_source"])

    def test_secondary_source_closes_trade_with_slippage(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_price_service({"BTCUSDT": (98.5, "secondary")})

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        monitored = self.client.post("/api/monitor/run")
        self.assertEqual(monitored.status_code, 200)
        payload = monitored.json()
        self.assertEqual(payload["closed_count"], 1)
        closed = payload["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["price_source"], "secondary")
        self.assertAlmostEqual(closed["exit_price"], 98.4)
        self.assertAlmostEqual(closed["pnl"], -1.6)

    def test_price_mismatch_skips_close(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_price_service({"BTCUSDT": (98.5, "mismatch")})

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        monitored = self.client.post("/api/monitor/run")
        self.assertEqual(monitored.status_code, 200)
        self.assertEqual(monitored.json()["closed_count"], 0)

        state = self.client.get("/api/state")
        stored = next(item for item in state.json()["recent_trades"] if item["trade_id"] == trade_id)
        self.assertEqual(stored["status"], "open")
        self.assertIsNone(stored["price_source"])

    def test_sell_exit_applies_buy_side_slippage(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "SELL",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        price_push = self.client.post(
            "/api/price",
            json={
                "symbol": "BTCUSDT",
                "price": 101.5,
                "run_monitor": True,
            },
        )
        self.assertEqual(price_push.status_code, 200)
        closed = price_push.json()["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["price_source"], "manual")
        self.assertAlmostEqual(closed["exit_price"], 101.56)
        self.assertAlmostEqual(closed["pnl"], -1.56)

    def test_cache_price_can_close_when_near_trigger_with_slippage(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        self._install_stub_price_service({"BTCUSDT": (98.49, "cache")})

        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        monitored = self.client.post("/api/monitor/run")
        self.assertEqual(monitored.status_code, 200)
        payload = monitored.json()
        self.assertEqual(payload["closed_count"], 1)
        closed = payload["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["price_source"], "cache")
        self.assertAlmostEqual(closed["exit_price"], 98.44)
        self.assertAlmostEqual(closed["pnl"], -1.56)

    def test_sync_engine_closes_trade_from_broker_fill(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "filled",
                "exchange_status": "filled",
                "broker_order_id": "sync-fill-1",
                "avgPrice": 100.0,
            },
        )
        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        stub.open_positions.pop("BTCUSDT", None)
        stub.orders["sync-fill-1"] = {
            "status": "FILLED",
            "avgPrice": 103.25,
            "executedQty": 133.3333333333,
        }

        synced = self.client.post("/api/sync/run")
        self.assertEqual(synced.status_code, 200)
        payload = synced.json()
        self.assertEqual(len(payload["closed_trades"]), 1)
        closed = payload["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["price_source"], "broker")
        self.assertEqual(closed["close_reason"], "broker_fill")
        self.assertEqual(closed["exchange_status"], "filled")
        self.assertAlmostEqual(closed["exit_price"], 103.25)
        self.assertAlmostEqual(closed["avg_fill_price"], 103.25)

    def test_sync_engine_updates_partial_fill(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "filled",
                "exchange_status": "filled",
                "broker_order_id": "sync-partial-1",
                "avgPrice": 100.0,
            },
        )
        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        stub.open_orders["sync-partial-1"] = {
            "status": "PARTIALLY_FILLED",
            "executedQty": 60.0,
            "avgPrice": 100.5,
        }

        synced = self.client.post("/api/sync/run")
        self.assertEqual(synced.status_code, 200)
        payload = synced.json()
        self.assertEqual(len(payload["updated_trades"]), 1)
        updated = payload["updated_trades"][0]
        self.assertEqual(updated["trade_id"], trade_id)
        self.assertEqual(updated["exchange_status"], "partial")
        self.assertAlmostEqual(updated["filled_qty"], 60.0)
        self.assertAlmostEqual(updated["avg_fill_price"], 100.5)
        self.assertEqual(updated["status"], "open")

    def test_sync_engine_marks_missing_order_unknown(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "filled",
                "exchange_status": "filled",
                "broker_order_id": "sync-missing-1",
            },
        )
        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        stub.open_positions.clear()
        stub.orders.clear()

        synced = self.client.post("/api/sync/run")
        self.assertEqual(synced.status_code, 200)
        payload = synced.json()
        self.assertEqual(len(payload["unknown_trades"]), 1)
        unknown = payload["unknown_trades"][0]
        self.assertEqual(unknown["trade_id"], trade_id)
        self.assertEqual(unknown["exchange_status"], "unknown")
        self.assertIsNotNone(unknown["last_sync_at"])
        self.assertEqual(unknown["status"], "open")

    def test_sync_engine_is_idempotent_on_duplicate_fill(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "filled",
                "exchange_status": "filled",
                "broker_order_id": "sync-idempotent-1",
            },
        )
        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)

        stub.open_positions.clear()
        stub.orders["sync-idempotent-1"] = {
            "status": "FILLED",
            "avgPrice": 103.0,
            "executedQty": 133.3333333333,
        }

        first = self.client.post("/api/sync/run")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.json()["closed_trades"]), 1)

        second = self.client.post("/api/sync/run")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.json()["closed_trades"]), 0)

    def test_sync_engine_reflects_manual_broker_close(self) -> None:
        for index in range(3):
            self._seed_closed_trade(strategy="trend", pnl=12.0, symbol=f"BTCUSDT{index}")

        stub = self._install_stub_broker(
            response={
                "status": "filled",
                "exchange_status": "filled",
                "broker_order_id": "sync-manual-1",
                "avgPrice": 100.0,
            },
        )
        opened = self.client.post(
            "/api/signal",
            json={
                "strategy": "trend",
                "signal": "BUY",
                "symbol": "BTCUSDT",
                "price": 100.0,
                "atr": 1.0,
            },
        )
        self.assertEqual(opened.status_code, 200)
        trade_id = opened.json()["trade"]["trade_id"]

        stub.close_position("BTCUSDT")
        stub.orders["sync-manual-1"] = {
            "status": "FILLED",
            "avgPrice": 101.75,
            "executedQty": 133.3333333333,
        }

        synced = self.client.post("/api/sync/run")
        self.assertEqual(synced.status_code, 200)
        closed = synced.json()["closed_trades"][0]
        self.assertEqual(closed["trade_id"], trade_id)
        self.assertEqual(closed["price_source"], "broker")
        self.assertAlmostEqual(closed["exit_price"], 101.75)


if __name__ == "__main__":
    unittest.main()
