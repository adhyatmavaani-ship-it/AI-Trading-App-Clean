from __future__ import annotations

import argparse
import base64
import os
import secrets
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.api_key_crypto import ApiKeyEncryptionService


WORKER_ENV_BLOCK = {
    "ML_SIGNAL_PIPELINE_ENABLED": "true",
    "ML_SIGNAL_PIPELINE_INTERVAL_SECONDS": "5.0",
    "CHART_EXECUTION_BRIDGE_ENABLED": "true",
    "CHART_EXECUTION_BRIDGE_INTERVAL_SECONDS": "1.0",
    "CHART_EXECUTION_BRIDGE_MODE": "mock",
}


def generate_secret() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(path)
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def validate_values(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    secret = values.get("USER_API_KEY_ENCRYPTION_SECRET", "")
    try:
        ApiKeyEncryptionService(secret)
    except Exception as exc:
        errors.append(f"USER_API_KEY_ENCRYPTION_SECRET invalid: {exc}")

    mode = values.get("CHART_EXECUTION_BRIDGE_MODE", "mock").lower()
    if mode not in {"mock", "testnet"}:
        errors.append("CHART_EXECUTION_BRIDGE_MODE must be mock or testnet")

    for key in (
        "ML_SIGNAL_PIPELINE_ENABLED",
        "CHART_EXECUTION_BRIDGE_ENABLED",
    ):
        value = values.get(key, "false").lower()
        if value not in {"true", "false", "1", "0", "yes", "no"}:
            errors.append(f"{key} must be boolean-like")

    for key in (
        "ML_SIGNAL_PIPELINE_INTERVAL_SECONDS",
        "CHART_EXECUTION_BRIDGE_INTERVAL_SECONDS",
    ):
        try:
            if float(values.get(key, "1")) <= 0:
                errors.append(f"{key} must be > 0")
        except ValueError:
            errors.append(f"{key} must be numeric")
    return errors


def render_env_block(secret: str) -> str:
    lines = [f"USER_API_KEY_ENCRYPTION_SECRET={secret}"]
    lines.extend(f"{key}={value}" for key, value in WORKER_ENV_BLOCK.items())
    return "\n".join(lines)


def write_missing_values(path: Path, values: dict[str, str]) -> None:
    existing = parse_env_file(path) if path.exists() else {}
    missing = {key: value for key, value in values.items() if key not in existing or not existing[key]}
    if not missing:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n# Advanced advisory trading workspace\n")
        for key, value in missing.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and verify advanced trading workspace environment settings.")
    parser.add_argument("--env-block", action="store_true", help="Print a staging-safe environment block.")
    parser.add_argument("--check-env", type=Path, help="Validate an existing env file.")
    parser.add_argument("--write-missing", type=Path, help="Append missing advanced settings to an env file.")
    args = parser.parse_args()

    secret = generate_secret()
    values = {"USER_API_KEY_ENCRYPTION_SECRET": secret, **WORKER_ENV_BLOCK}

    if args.write_missing:
        write_missing_values(args.write_missing, values)
        print(f"Advanced trading env settings present in {args.write_missing}")

    if args.check_env:
        env_values = parse_env_file(args.check_env)
        errors = validate_values(env_values)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Advanced trading env validation passed: {args.check_env}")

    if args.env_block or not (args.write_missing or args.check_env):
        print(render_env_block(secret))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
