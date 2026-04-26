import unittest
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.allocation_engine import AllocationEngine


class AllocationEngineTest(unittest.TestCase):
    def test_allocates_proportionally_and_preserves_total(self):
        engine = AllocationEngine(precision=4)
        allocations = engine.allocate(
            intents=[
                {"intent_id": "a", "user_id": "u1", "requested_quantity": 1.0},
                {"intent_id": "b", "user_id": "u2", "requested_quantity": 2.0},
                {"intent_id": "c", "user_id": "u3", "requested_quantity": 3.0},
            ],
            executed_quantity=3.0,
            fee_paid=0.06,
            executed_price=100.0,
            aggregate_order_id="agg-1",
            aggregate_status="PARTIALLY_FILLED",
        )

        self.assertEqual(len(allocations), 3)
        self.assertAlmostEqual(sum(item["allocated_quantity"] for item in allocations), 3.0, places=4)
        self.assertAlmostEqual(sum(item["fee_paid"] for item in allocations), 0.06, places=4)
        self.assertEqual(allocations[0]["allocation_status"], "PARTIALLY_FILLED")
        self.assertGreater(allocations[2]["allocated_quantity"], allocations[0]["allocated_quantity"])


if __name__ == "__main__":
    unittest.main()
