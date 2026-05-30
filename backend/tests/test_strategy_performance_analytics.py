from app.services.strategy_performance_analytics import StrategyPerformanceAnalyticsProcessor


def test_strategy_performance_snapshot_is_replay_safe_and_advisory_only() -> None:
    processor = StrategyPerformanceAnalyticsProcessor()
    actions = [
        {
            "action_id": "a1",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 100.0,
            "quantity": 1.0,
            "is_ai_trailing": False,
            "created_at": "2026-05-30T10:00:00Z",
            "action_payload": {"accepted": True, "live_broker_submission": False},
        },
        {
            "action_id": "a2",
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 105.0,
            "quantity": 1.0,
            "is_ai_trailing": True,
            "created_at": "2026-05-30T10:01:00Z",
            "action_payload": {"accepted": True, "live_broker_submission": False},
        },
        {
            "action_id": "a3",
            "symbol": "ETHUSDT",
            "side": "SELL",
            "price": 99.0,
            "quantity": 2.0,
            "is_ai_trailing": False,
            "created_at": "2026-05-30T10:02:00Z",
            "action_payload": {"accepted": False, "live_broker_submission": False},
        },
    ]

    first = processor.snapshot(user_id="alice", actions=actions)
    second = processor.snapshot(user_id="alice", actions=list(reversed(actions)))

    for snapshot in (first, second):
        assert snapshot["event"] == "strategy_performance_update"
        assert snapshot["advisory_only"] is True
        assert snapshot["simulation_only"] is True
        assert snapshot["live_broker_submission"] is False
        assert snapshot["action_count"] == 3
        assert snapshot["accepted_count"] == 2
        assert snapshot["rejected_count"] == 1
        assert "BTCUSDT" in snapshot["symbol_breakdown"]
        assert snapshot["stress_simulation"]["advisory_only"] is True
        assert snapshot["stress_simulation"]["simulation_only"] is True

    comparable_first = {k: v for k, v in first.items() if k != "timestamp"}
    comparable_second = {k: v for k, v in second.items() if k != "timestamp"}
    assert comparable_first == comparable_second


def test_empty_strategy_performance_snapshot_has_safe_defaults() -> None:
    snapshot = StrategyPerformanceAnalyticsProcessor().snapshot(user_id="alice", actions=[])

    assert snapshot["rolling_window"] == 0
    assert snapshot["advisory_only"] is True
    assert snapshot["simulation_only"] is True
    assert snapshot["stress_simulation"]["scenario_count"] == 0
