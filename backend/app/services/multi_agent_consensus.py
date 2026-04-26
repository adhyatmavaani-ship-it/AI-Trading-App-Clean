from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from app.schemas.trading import AIInference, FeatureSnapshot
from app.services.liquidity_slippage import LiquiditySlippageEngine
from app.services.sentiment_engine import SentimentEngine
from app.services.whale_tracker import WhaleTracker


@dataclass(frozen=True)
class AgentVote:
    agent: str
    signal: str
    confidence: float
    weight: float
    summary: str
    diagnostics: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ConsensusDecision:
    symbol: str
    approved: bool
    signal: str
    consensus_score: float
    consensus_threshold: float
    vetoed: bool
    veto_reason: str | None
    slippage_pct: float
    requested_notional: float
    votes: list[AgentVote]
    rationale: str


@dataclass
class MomentumSpecialist:
    weight: float = 0.40

    async def evaluate(
        self,
        snapshot: FeatureSnapshot,
        inference: AIInference,
    ) -> AgentVote:
        bullish_probability = max(
            inference.trade_probability if inference.decision == "BUY" else 0.0,
            float(inference.model_breakdown.get("calibrated_buy", 0.0)),
            float(inference.model_breakdown.get("forecast_buy", 0.0)),
        )
        bearish_probability = max(
            inference.trade_probability if inference.decision == "SELL" else 0.0,
            float(inference.model_breakdown.get("calibrated_sell", 0.0)),
            float(inference.model_breakdown.get("forecast_sell", 0.0)),
        )
        momentum_impulse = max(
            0.0,
            snapshot.features.get("1m_return", 0.0) * 25
            + snapshot.features.get("5m_return", 0.0) * 10
            + snapshot.order_book_imbalance * 1.5,
        )
        reversal_impulse = max(
            0.0,
            -snapshot.features.get("1m_return", 0.0) * 25
            - snapshot.features.get("5m_return", 0.0) * 10
            - snapshot.order_book_imbalance * 1.5,
        )
        long_score = min(1.0, bullish_probability * 0.70 + momentum_impulse * 0.30)
        short_score = min(1.0, bearish_probability * 0.70 + reversal_impulse * 0.30)
        signal, confidence = self._classify(long_score, short_score)
        return AgentVote(
            agent="momentum_specialist",
            signal=signal,
            confidence=confidence,
            weight=self.weight,
            summary=(
                f"Momentum ensemble={signal} from LSTM/Transformer forecast with "
                f"buy={long_score:.2f} sell={short_score:.2f}"
            ),
            diagnostics={
                "long_score": round(long_score, 4),
                "short_score": round(short_score, 4),
                "order_book_imbalance": round(snapshot.order_book_imbalance, 4),
            },
        )

    def _classify(self, long_score: float, short_score: float) -> tuple[str, float]:
        if max(long_score, short_score) < 0.55:
            hold_confidence = min(1.0, 1.0 - abs(long_score - short_score))
            return "HOLD", round(hold_confidence, 4)
        if long_score >= short_score:
            return "BUY", round(long_score, 4)
        return "SELL", round(short_score, 4)


@dataclass
class SentimentAnalyst:
    sentiment_engine: SentimentEngine
    weight: float = 0.30

    async def evaluate(
        self,
        symbol: str,
        market_features: dict[str, float],
        external_sentiment: dict | None = None,
    ) -> AgentVote:
        external_sentiment = external_sentiment or {}
        engine_sentiment = await self.sentiment_engine.analyze_token(symbol, market_features)
        x_score = float(external_sentiment.get("x_score", 0.0))
        telegram_score = float(external_sentiment.get("telegram_score", 0.0))
        news_score = float(external_sentiment.get("news_score", 0.0))
        relevance = float(external_sentiment.get("entity_relevance", 0.5))
        normalized_external = max(
            0.0,
            min(1.0, 0.5 + ((x_score + telegram_score + news_score) / 3) * 0.5 * max(relevance, 0.1)),
        )
        long_score = min(
            1.0,
            engine_sentiment["buzz_score"] * 0.20
            + min(1.0, engine_sentiment["hype_score"] / 1.5) * 0.35
            + engine_sentiment["volume_alignment"] * 0.15
            + normalized_external * 0.30,
        )
        short_score = min(
            1.0,
            max(0.0, 0.5 - normalized_external) * 0.50
            + max(0.0, 0.65 - engine_sentiment["volume_alignment"]) * 0.20
            + max(0.0, 0.55 - engine_sentiment["buzz_score"]) * 0.30,
        )
        signal, confidence = self._classify(long_score, short_score)
        return AgentVote(
            agent="sentiment_analyst",
            signal=signal,
            confidence=confidence,
            weight=self.weight,
            summary=(
                f"Sentiment NLP={signal} with narrative={engine_sentiment['narrative']} "
                f"and external composite={normalized_external:.2f}"
            ),
            diagnostics={
                "long_score": round(long_score, 4),
                "short_score": round(short_score, 4),
                "buzz_score": round(engine_sentiment["buzz_score"], 4),
                "hype_score": round(engine_sentiment["hype_score"], 4),
            },
        )

    def _classify(self, long_score: float, short_score: float) -> tuple[str, float]:
        if max(long_score, short_score) < 0.55:
            return "HOLD", round(min(1.0, 1.0 - abs(long_score - short_score)), 4)
        if long_score >= short_score:
            return "BUY", round(long_score, 4)
        return "SELL", round(short_score, 4)


@dataclass
class OnChainSentinel:
    whale_tracker: WhaleTracker
    slippage_engine: LiquiditySlippageEngine
    weight: float = 0.30

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
        onchain_metrics = onchain_metrics or {}
        whale_data = await self.whale_tracker.evaluate_token(symbol, chain, market_features)
        quantity = requested_notional / max(reference_price, 1e-8) if requested_notional > 0 else 0.0
        buy_impact = self.slippage_engine.estimate(order_book, "BUY", quantity) if quantity > 0 else {
            "estimated_slippage_bps": 0.0
        }
        sell_impact = self.slippage_engine.estimate(order_book, "SELL", quantity) if quantity > 0 else {
            "estimated_slippage_bps": 0.0
        }
        whale_flow_score = float(onchain_metrics.get("whale_flow_score", whale_data["accumulation_score"]))
        exchange_flow_score = float(onchain_metrics.get("exchange_flow_score", 0.5))
        stablecoin_flow_score = float(onchain_metrics.get("stablecoin_flow_score", 0.5))
        liquidity_bias = max(0.0, 1.0 - buy_impact["estimated_slippage_bps"] / 100)
        liquidation_risk = min(1.0, sell_impact["estimated_slippage_bps"] / 100)
        long_score = min(
            1.0,
            whale_data["score"] * 0.35
            + whale_flow_score * 0.25
            + exchange_flow_score * 0.15
            + stablecoin_flow_score * 0.10
            + liquidity_bias * 0.15,
        )
        short_score = min(
            1.0,
            whale_data["unusual_activity_score"] * 0.35
            + max(0.0, 0.5 - exchange_flow_score) * 0.20
            + max(0.0, 0.5 - stablecoin_flow_score) * 0.15
            + liquidation_risk * 0.30,
        )
        signal, confidence = self._classify(long_score, short_score)
        return AgentVote(
            agent="onchain_sentinel",
            signal=signal,
            confidence=confidence,
            weight=self.weight,
            summary=(
                f"On-chain={signal} with whale score={whale_data['score']:.2f} "
                f"and buy slippage={buy_impact['estimated_slippage_bps'] / 100:.2%}"
            ),
            diagnostics={
                "long_score": round(long_score, 4),
                "short_score": round(short_score, 4),
                "whale_score": round(whale_data["score"], 4),
                "buy_slippage_bps": round(float(buy_impact["estimated_slippage_bps"]), 4),
                "sell_slippage_bps": round(float(sell_impact["estimated_slippage_bps"]), 4),
            },
        )

    def _classify(self, long_score: float, short_score: float) -> tuple[str, float]:
        if max(long_score, short_score) < 0.55:
            return "HOLD", round(min(1.0, 1.0 - abs(long_score - short_score)), 4)
        if long_score >= short_score:
            return "BUY", round(long_score, 4)
        return "SELL", round(short_score, 4)


@dataclass
class RiskAgent:
    slippage_engine: LiquiditySlippageEngine
    max_slippage_pct: float = 0.005

    async def veto(
        self,
        signal: str,
        order_book: dict,
        reference_price: float,
        requested_notional: float,
    ) -> tuple[bool, float, str | None]:
        if signal == "HOLD":
            return False, 0.0, None
        quantity = requested_notional / max(reference_price, 1e-8) if requested_notional > 0 else 0.0
        if quantity <= 0:
            return False, 0.0, None
        side = "BUY" if signal == "BUY" else "SELL"
        slippage_bps = float(self.slippage_engine.estimate(order_book, side, quantity)["estimated_slippage_bps"])
        slippage_pct = slippage_bps / 10_000
        if slippage_pct > self.max_slippage_pct:
            return True, slippage_pct, f"Risk veto: estimated slippage {slippage_pct:.2%} exceeds 0.50%"
        return False, slippage_pct, None


@dataclass
class MultiAgentConsensusEngine:
    momentum_specialist: MomentumSpecialist
    sentiment_analyst: SentimentAnalyst
    onchain_sentinel: OnChainSentinel
    risk_agent: RiskAgent
    consensus_threshold: float = 0.75

    @classmethod
    def create_default(cls) -> "MultiAgentConsensusEngine":
        slippage_engine = LiquiditySlippageEngine()
        return cls(
            momentum_specialist=MomentumSpecialist(),
            sentiment_analyst=SentimentAnalyst(sentiment_engine=SentimentEngine()),
            onchain_sentinel=OnChainSentinel(
                whale_tracker=WhaleTracker.create_default(),
                slippage_engine=slippage_engine,
            ),
            risk_agent=RiskAgent(slippage_engine=slippage_engine),
        )

    async def evaluate_trade(
        self,
        *,
        symbol: str,
        chain: str,
        snapshot: FeatureSnapshot,
        inference: AIInference,
        order_book: dict,
        requested_notional: float,
        external_sentiment: dict | None = None,
        onchain_metrics: dict | None = None,
    ) -> ConsensusDecision:
        votes = await asyncio.gather(
            self.momentum_specialist.evaluate(snapshot, inference),
            self.sentiment_analyst.evaluate(symbol, snapshot.features, external_sentiment),
            self.onchain_sentinel.evaluate(
                symbol=symbol,
                chain=chain,
                market_features=snapshot.features,
                order_book=order_book,
                reference_price=snapshot.price,
                requested_notional=requested_notional,
                onchain_metrics=onchain_metrics,
            ),
        )
        signal, consensus_score = self._consensus(votes)
        approved = signal != "HOLD" and consensus_score >= self.consensus_threshold
        vetoed = False
        veto_reason = None
        slippage_pct = 0.0
        if approved:
            vetoed, slippage_pct, veto_reason = await self.risk_agent.veto(
                signal=signal,
                order_book=order_book,
                reference_price=snapshot.price,
                requested_notional=requested_notional,
            )
            approved = not vetoed
        rationale = self._rationale(signal, consensus_score, votes, veto_reason)
        return ConsensusDecision(
            symbol=symbol,
            approved=approved,
            signal=signal,
            consensus_score=round(consensus_score, 4),
            consensus_threshold=self.consensus_threshold,
            vetoed=vetoed,
            veto_reason=veto_reason,
            slippage_pct=round(slippage_pct, 6),
            requested_notional=requested_notional,
            votes=list(votes),
            rationale=rationale,
        )

    def _consensus(self, votes: list[AgentVote]) -> tuple[str, float]:
        signal_scores = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        total_weight = sum(vote.weight for vote in votes) or 1.0
        for vote in votes:
            signal_scores[vote.signal] += vote.confidence * vote.weight
        dominant_signal = max(signal_scores, key=signal_scores.get)
        consensus_score = signal_scores[dominant_signal] / total_weight
        return dominant_signal, consensus_score

    def _rationale(
        self,
        signal: str,
        consensus_score: float,
        votes: list[AgentVote],
        veto_reason: str | None,
    ) -> str:
        vote_summary = "; ".join(
            f"{vote.agent}={vote.signal}@{vote.confidence:.2f}" for vote in votes
        )
        if veto_reason:
            return f"{vote_summary}; consensus={signal}@{consensus_score:.2%}; {veto_reason}"
        if signal == "HOLD":
            return f"{vote_summary}; consensus resolved to HOLD"
        if consensus_score < self.consensus_threshold:
            return (
                f"{vote_summary}; consensus={signal}@{consensus_score:.2%} below "
                f"required {self.consensus_threshold:.0%}"
            )
        return f"{vote_summary}; consensus={signal}@{consensus_score:.2%} approved"
