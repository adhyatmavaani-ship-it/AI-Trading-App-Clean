from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import Settings
from app.services.self_healing_ppo import SelfHealingPPOService


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python backend/scripts/self_healing_loop.py <loss-payload.json>")
        return 1

    payload_path = Path(sys.argv[1]).resolve()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    service = SelfHealingPPOService(settings=Settings())
    report = service.handle_trade_outcome(
        trade_id=payload["trade_id"],
        active_trade=payload["active_trade"],
        pnl=float(payload["pnl"]),
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
