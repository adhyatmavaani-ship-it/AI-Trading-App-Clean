import asyncio
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.liquidity_monitor import LiquidityMonitor
from app.services.security_scanner import SecurityScanner
from app.services.sentiment_engine import SentimentEngine
from app.services.whale_tracker import WhaleTracker


class AlphaModulesTest(unittest.TestCase):
    def test_whale_tracker_scores_wallets(self):
        tracker = WhaleTracker.create_default()
        scorecard = tracker.wallet_scorecard("ethereum")
        self.assertGreaterEqual(len(scorecard), 30)
        self.assertGreaterEqual(scorecard[0]["score"], scorecard[-1]["score"])

    def test_liquidity_and_security_flag_risk(self):
        liquidity = asyncio.run(
            LiquidityMonitor().assess_token(
                "TEST",
                "ethereum",
                {"volatility": 0.10, "order_book_imbalance": 0.7, "5m_volume": 2_000_000, "15m_volume": 900_000},
            )
        )
        security = asyncio.run(
            SecurityScanner().scan_token(
                "TEST",
                "ethereum",
                {"volatility": 0.10, "order_book_imbalance": 0.7, "1m_return": 0.06},
            )
        )
        self.assertGreater(liquidity["rug_pull_risk"], 0.4)
        self.assertGreater(security["honeypot_risk"], 0.5)

    def test_sentiment_engine_generates_narrative_and_hype(self):
        sentiment = asyncio.run(
            SentimentEngine().analyze_token(
                "AIUSDT",
                {"1m_return": 0.03, "5m_volume": 1_200_000, "15m_volume": 800_000, "order_book_imbalance": 0.2},
            )
        )
        self.assertIn("narrative", sentiment)
        self.assertGreater(sentiment["hype_score"], 0.0)


if __name__ == "__main__":
    unittest.main()
