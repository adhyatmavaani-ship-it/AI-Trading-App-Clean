from app.core.config import Settings
from app.schemas.risk_coach import RiskEvaluationRequest, TradeCloseRequest, TradeCreateRequest
from app.services.risk_coach_market import RiskCoachMarketService
from app.services.risk_coach_service import RiskCoachService


def test_risk_engine_blocks_high_risk_and_low_rr():
    service = RiskCoachService(Settings(), RiskCoachMarketService())
    result = service.evaluate(
        RiskEvaluationRequest(
            account_equity=1_000,
            risk_amount=50,
            entry=100,
            stop_loss=98,
            take_profit=101,
            reliability=0.8,
            confidence=0.6,
        )
    )
    assert result.allowed is False
    assert any("3%" in item for item in result.blockers)
    assert any("1.2" in item for item in result.blockers)


def test_post_mortem_returns_structured_insights():
    market = RiskCoachMarketService()
    market._seed_synthetic_buffer()
    service = RiskCoachService(Settings(), market)
    trade = service.create_trade(
        TradeCreateRequest(
            symbol="BTCUSDT",
            side="long",
            account_equity=10_000,
            risk_amount=100,
            entry=100,
            stop_loss=95,
            take_profit=112,
            p_win=0.82,
            reliability=0.76,
        )
    )
    report = service.close_trade(trade.trade_id, TradeCloseRequest(exit_price=94))
    assert report.trade.trade_id == trade.trade_id
    assert report.insights
    assert report.realized_rr < 0
