from __future__ import annotations

import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return payload


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    render_path = REPO_ROOT / "render.yaml"
    render = _load_yaml(render_path)
    services = render.get("services")
    if not isinstance(services, list) or not services:
        errors.append("render.yaml must define at least one service")
    else:
        backend_service = services[0]
        start_command = str(backend_service.get("startCommand", "")).strip()
        health_path = str(backend_service.get("healthCheckPath", "")).strip()
        if "uvicorn app.main:app" not in start_command:
            errors.append("render.yaml startCommand must boot the production FastAPI app via uvicorn app.main:app")
        if health_path != "/health":
            warnings.append("render.yaml healthCheckPath differs from /health; confirm the host expects this probe")

        env_vars = backend_service.get("envVars", [])
        env_map = {
            str(item.get("key", "")).strip(): item
            for item in env_vars
            if isinstance(item, dict)
        }
        trading_mode = str(env_map.get("TRADING_MODE", {}).get("value", "")).strip().lower()
        if trading_mode != "paper":
            errors.append("render.yaml must default TRADING_MODE to paper")

    gitignore_path = REPO_ROOT / ".gitignore"
    gitignore_text = gitignore_path.read_text(encoding="utf-8")
    for pattern in ("trades.db", "*.sqlite3", "artifacts/"):
        if pattern not in gitignore_text:
            errors.append(f".gitignore missing required runtime-artifact rule: {pattern}")

    if (REPO_ROOT / "trades.db").exists():
        errors.append("repo root contains trades.db; remove runtime database before release")

    checklist_path = REPO_ROOT / "PRODUCTION_CHECKLIST.md"
    if not checklist_path.exists():
        warnings.append("PRODUCTION_CHECKLIST.md is missing")

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        return 1

    print("Production readiness preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
