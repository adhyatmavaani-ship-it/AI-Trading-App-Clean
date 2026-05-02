from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

__all__ = ["app", "create_app"]

_PACKAGE_DIR = Path(__file__).resolve().parent
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))


def __getattr__(name: str) -> Any:
    if name in {"app", "create_app"}:
        from main import app, create_app

        return {"app": app, "create_app": create_app}[name]
    raise AttributeError(name)
