import sys
import tempfile
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.backtest_jobs import BacktestJobService


class _StubBacktestingEngine:
    optimizer = None


class _StubHistoricalData:
    pass


class BacktestJobServiceTest(unittest.TestCase):
    def test_prunes_old_job_files_to_history_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(backtest_data_dir=temp_dir)
            settings.backtest_job_history_limit = 2
            service = BacktestJobService(
                settings=settings,
                backtesting_engine=_StubBacktestingEngine(),
                historical_data=_StubHistoricalData(),
            )

            for index in range(4):
                payload = {
                    "job_id": f"job-{index}",
                    "user_id": "alice",
                    "status": "COMPLETED",
                    "progress_pct": 100.0,
                    "current_stage": "completed",
                    "trades_found": 1,
                    "net_profit": 1.0,
                    "logs": [],
                    "request": {},
                    "result": None,
                    "comparison_profiles": [],
                }
                service._persist(payload)

            job_files = sorted(service.jobs_dir.glob("*.json"))
            self.assertEqual(len(job_files), 2)


if __name__ == "__main__":
    unittest.main()
