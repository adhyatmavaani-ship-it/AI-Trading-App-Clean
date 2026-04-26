from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "unittest",
        "backend.tests.test_chaos_resilience",
        "-v",
    ]
    print("[staging-chaos] running targeted chaos resilience suite")
    result = subprocess.run(command, cwd=repo_root)
    if result.returncode == 0:
        print("[staging-chaos] passed")
    else:
        print("[staging-chaos] failed", file=sys.stderr)
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
