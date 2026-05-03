import sys
import tempfile
import unittest
from pathlib import Path
import os
import gc
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.firestore_repo import FirestoreRepository


class FirestoreTrainingBufferTest(unittest.TestCase):
    def test_local_training_buffer_persists_and_merges_samples_without_firestore(self):
        fd, sqlite_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        try:
            repo = FirestoreRepository(
                "",
                local_training_buffer_path=sqlite_path,
            )

            sample_id = repo.save_training_sample(
                {
                    "sample_id": "trade-1",
                    "trade_id": "trade-1",
                    "symbol": "BTCUSDT",
                    "features": {"rsi": 58.0, "volume_spike": 1.8},
                    "outcome": None,
                }
            )
            repo.update_training_sample(
                sample_id,
                {
                    "outcome": 1.0,
                    "realized_pnl": 12.5,
                    "close_reason": "take_profit",
                },
            )

            rows = repo.list_training_samples(limit=10)

            self.assertEqual(sample_id, "trade-1")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["sample_id"], "trade-1")
            self.assertEqual(rows[0]["features"]["rsi"], 58.0)
            self.assertEqual(rows[0]["outcome"], 1.0)
            self.assertEqual(rows[0]["realized_pnl"], 12.5)
            self.assertEqual(rows[0]["close_reason"], "take_profit")
            del repo
        finally:
            gc.collect()
            if os.path.exists(sqlite_path):
                os.remove(sqlite_path)

    @patch("app.services.firestore_repo.firestore.Client")
    @patch("app.services.firestore_repo.service_account.Credentials.from_service_account_info")
    def test_firestore_client_uses_explicit_credentials_json(self, credentials_factory, firestore_client):
        credentials_factory.return_value = object()

        repo = FirestoreRepository(
            "demo-project",
            raw_credentials_json='{"type":"service_account","project_id":"demo-project"}',
        )

        self.assertIs(repo.client, firestore_client.return_value)
        credentials_factory.assert_called_once_with(
            {"type": "service_account", "project_id": "demo-project"}
        )
        firestore_client.assert_called_once_with(
            project="demo-project",
            credentials=credentials_factory.return_value,
        )


if __name__ == "__main__":
    unittest.main()
