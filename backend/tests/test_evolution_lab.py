import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings
from app.services.evolution_lab import EvolutionLab


class InMemoryCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl=None):
        self.store[key] = value


class StubFirestore:
    def __init__(self):
        self.snapshots = {}

    def save_performance_snapshot(self, user_id, payload):
        self.snapshots[user_id] = payload


class EvolutionLabTest(unittest.TestCase):
    def test_stages_promotion_candidate_but_requires_approval(self):
        cache = InMemoryCache()
        lab = EvolutionLab(
            settings=Settings(model_dir=str(Path.cwd() / "tmp-evolution"), redis_url="redis://unused"),
            cache=cache,
            firestore=StubFirestore(),
        )

        children = lab.breed_child_bots({"bot_id": "master", "stop_loss_pct": 0.02, "rsi_length": 14})
        result = lab.evaluate_children(
            children,
            [{"profit_factor": 1.3, "win_rate": 0.58, "max_drawdown": 0.08} for _ in children],
        )

        self.assertEqual(len(children), 10)
        self.assertTrue(result["promotion_candidate"]["approval_required"])
        self.assertIn("disabled", result["promotion_candidate"]["reason"])


if __name__ == "__main__":
    unittest.main()
