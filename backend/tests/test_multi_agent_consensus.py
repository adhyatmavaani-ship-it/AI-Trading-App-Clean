import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.liquidity_slippage import LiquiditySlippageEngine
from app.services.multi_agent_consensus import (
    AgentVote,
    ConsensusDecision,
    MomentumSpecialist,
    MultiAgentConsensusEngine,
    OnChainSentinel,
    RiskAgent,
    SentimentAnalyst,
)
from app.services.sentiment_engine import SentimentEngine
from app.services.whale_tracker import WhaleTracker


class StubMomentumSpecialist:
    def __init__(self, vote: AgentVote):
        self.vote = vote

    async def evaluate(self, snapshot: FeatureSnapshot, inference: AIInference) -> AgentVote:
        return self.vote


class StubSentimentAnalyst:
    def __init__(self, vote: AgentVote):
        self.vote = vote

    async def evaluate(self, symbol: str, market_features: dict[str, float], external_sentiment: dict | None = None) -> AgentVote:
        return self.vote


class StubOnChainSentinel:
    def __init__(self, vote: AgentVote):
        self.vote = vote

    async def evaluate(
        self,
        symbol: str,
        chain: str,
        market_features: dict[str, float],
        order_book: dict,
        reference_price: float,
        requested_notional: float,
        onchain_metrics: dict | None = None,
    ) -> AgentVote:
        return self.vote


class StubRiskAgent:
    def __init__(self, *, veto: bool = False, slippage_pct: float = 0.0, reason: str | None = None):
        self._veto = veto
        self._slippage_pct = slippage_pct
        self._reason = reason

    async def veto(
        self,
        signal: str,
        order_book: dict,
        reference_price: float,
        requested_notional: float,
    ) -> tuple[bool, float, str | None]:
        return self._veto, self._slippage_pct, self._reason


class MultiAgentConsensusEngineTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.snapshot = FeatureSnapshot(
            symbol="BTCUSDT",
            price=100_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.84,
            volatility=0.014,
            atr=450,
            order_book_imbalance=0.22,
            features={
                "1m_return": 0.006,
                "5m_return": 0.012,
                "15m_volume": 2_400_000,
                "5m_volume": 1_200_000,
            },
        )
        self.inference = AIInference(
            price_forecast_return=0.013,
            expected_return=0.010,
            expected_risk=0.012,
            trade_probability=0.82,
            confidence_score=0.82,
            decision="BUY",
            model_version="v1",
            model_breakdown={
                "calibrated_buy": 0.82,
                "calibrated_sell": 0.18,
                "forecast_buy": 0.79,
                "forecast_sell": 0.21,
            },
            reason="consensus test",
        )
        self.order_book = {
            "bids": [{"price": 99_990.0, "qty": 2.0}, {"price": 99_980.0, "qty": 2.0}],
            "asks": [{"price": 100_010.0, "qty": 2.0}, {"price": 100_020.0, "qty": 2.0}],
        }

    async def test_trade_is_approved_when_weighted_consensus_reaches_75_percent(self):
        engine = MultiAgentConsensusEngine(
            momentum_specialist=StubMomentumSpecialist(
                AgentVote("momentum_specialist", "BUY", 0.95, 0.40, "momentum buy")
            ),
            sentiment_analyst=StubSentimentAnalyst(
                AgentVote("sentiment_analyst", "BUY", 0.90, 0.30, "sentiment buy")
            ),
            onchain_sentinel=StubOnChainSentinel(
                AgentVote("onchain_sentinel", "BUY", 0.40, 0.30, "onchain buy")
            ),
            risk_agent=StubRiskAgent(),
        )

        decision = await engine.evaluate_trade(
            symbol="BTCUSDT",
            chain="ethereum",
            snapshot=self.snapshot,
            inference=self.inference,
            order_book=self.order_book,
            requested_notional=20_000,
        )

        self.assertTrue(decision.approved)
        self.assertEqual(decision.signal, "BUY")
        self.assertGreaterEqual(decision.consensus_score, 0.75)
        self.assertFalse(decision.vetoed)

    async def test_trade_is_blocked_when_consensus_is_below_threshold(self):
        engine = MultiAgentConsensusEngine(
            momentum_specialist=StubMomentumSpecialist(
                AgentVote("momentum_specialist", "BUY", 0.70, 0.40, "momentum buy")
            ),
            sentiment_analyst=StubSentimentAnalyst(
                AgentVote("sentiment_analyst", "HOLD", 0.90, 0.30, "sentiment hold")
            ),
            onchain_sentinel=StubOnChainSentinel(
                AgentVote("onchain_sentinel", "BUY", 0.60, 0.30, "onchain buy")
            ),
            risk_agent=StubRiskAgent(),
        )

        decision = await engine.evaluate_trade(
            symbol="BTCUSDT",
            chain="ethereum",
            snapshot=self.snapshot,
            inference=self.inference,
            order_book=self.order_book,
            requested_notional=20_000,
        )

        self.assertFalse(decision.approved)
        self.assertEqual(decision.signal, "BUY")
        self.assertLess(decision.consensus_score, 0.75)
        self.assertFalse(decision.vetoed)

    async def test_risk_agent_can_veto_after_consensus_passes(self):
        engine = MultiAgentConsensusEngine(
            momentum_specialist=StubMomentumSpecialist(
                AgentVote("momentum_specialist", "BUY", 0.95, 0.40, "momentum buy")
            ),
            sentiment_analyst=StubSentimentAnalyst(
                AgentVote("sentiment_analyst", "BUY", 0.92, 0.30, "sentiment buy")
            ),
            onchain_sentinel=StubOnChainSentinel(
                AgentVote("onchain_sentinel", "BUY", 0.88, 0.30, "onchain buy")
            ),
            risk_agent=StubRiskAgent(
                veto=True,
                slippage_pct=0.0062,
                reason="Risk veto: estimated slippage 0.62% exceeds 0.50%",
            ),
        )

        decision = await engine.evaluate_trade(
            symbol="BTCUSDT",
            chain="ethereum",
            snapshot=self.snapshot,
            inference=self.inference,
            order_book=self.order_book,
            requested_notional=80_000,
        )

        self.assertFalse(decision.approved)
        self.assertTrue(decision.vetoed)
        self.assertAlmostEqual(decision.slippage_pct, 0.0062, places=6)
        self.assertIn("0.50%", decision.veto_reason or "")

    async def test_default_engine_smoke_test_returns_structured_decision(self):
        engine = MultiAgentConsensusEngine.create_default()

        decision = await engine.evaluate_trade(
            symbol="BTCUSDT",
            chain="ethereum",
            snapshot=self.snapshot,
            inference=self.inference,
            order_book=self.order_book,
            requested_notional=10_000,
            external_sentiment={"x_score": 0.7, "telegram_score": 0.5, "news_score": 0.4, "entity_relevance": 0.9},
            onchain_metrics={"whale_flow_score": 0.8, "exchange_flow_score": 0.7, "stablecoin_flow_score": 0.72},
        )

        self.assertIsInstance(decision, ConsensusDecision)
        self.assertEqual(len(decision.votes), 3)
        self.assertIn(decision.signal, {"BUY", "SELL", "HOLD"})


class RiskAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_veto_triggers_when_slippage_exceeds_half_percent(self):
        order_book = {
            "bids": [{"price": 99.0, "qty": 1.0}],
            "asks": [{"price": 100.0, "qty": 0.1}, {"price": 101.0, "qty": 2.0}],
        }
        risk_agent = RiskAgent(slippage_engine=LiquiditySlippageEngine(), max_slippage_pct=0.005)

        vetoed, slippage_pct, reason = await risk_agent.veto(
            signal="BUY",
            order_book=order_book,
            reference_price=100.0,
            requested_notional=100.0,
        )

        self.assertTrue(vetoed)
        self.assertGreater(slippage_pct, 0.005)
        self.assertIn("exceeds 0.50%", reason or "")


class SpecialistSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_specialists_emit_valid_votes(self):
        snapshot = FeatureSnapshot(
            symbol="ETHUSDT",
            price=2_000,
            timestamp="2026-01-01T00:00:00Z",
            regime="TRENDING",
            regime_confidence=0.75,
            volatility=0.018,
            atr=40,
            order_book_imbalance=0.15,
            features={
                "1m_return": 0.004,
                "5m_return": 0.009,
                "15m_volume": 2_800_000,
                "5m_volume": 1_600_000,
            },
        )
        inference = AIInference(
            price_forecast_return=0.008,
            expected_return=0.007,
            expected_risk=0.011,
            trade_probability=0.74,
            confidence_score=0.74,
            decision="BUY",
            model_version="v1",
            model_breakdown={
                "calibrated_buy": 0.76,
                "calibrated_sell": 0.24,
                "forecast_buy": 0.72,
                "forecast_sell": 0.28,
            },
            reason="specialist smoke",
        )
        order_book = {
            "bids": [{"price": 1999.0, "qty": 10.0}],
            "asks": [{"price": 2001.0, "qty": 10.0}],
        }

        momentum = await MomentumSpecialist().evaluate(snapshot, inference)
        sentiment = await SentimentAnalyst(SentimentEngine()).evaluate(
            "ETHUSDT",
            snapshot.features,
            {"x_score": 0.4, "telegram_score": 0.5, "news_score": 0.3, "entity_relevance": 0.8},
        )
        onchain = await OnChainSentinel(
            whale_tracker=WhaleTracker.create_default(),
            slippage_engine=LiquiditySlippageEngine(),
        ).evaluate(
            symbol="ETHUSDT",
            chain="ethereum",
            market_features=snapshot.features,
            order_book=order_book,
            reference_price=snapshot.price,
            requested_notional=5_000,
            onchain_metrics={"whale_flow_score": 0.7, "exchange_flow_score": 0.65, "stablecoin_flow_score": 0.62},
        )

        self.assertIn(momentum.signal, {"BUY", "SELL", "HOLD"})
        self.assertIn(sentiment.signal, {"BUY", "SELL", "HOLD"})
        self.assertIn(onchain.signal, {"BUY", "SELL", "HOLD"})


if __name__ == "__main__":
    unittest.main()
