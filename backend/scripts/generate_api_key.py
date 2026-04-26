from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.api_key_auth import ApiKeyAuthService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and optionally persist an API key.")
    parser.add_argument("--user-id", required=True, help="User identifier that will own the key.")
    parser.add_argument("--key-id", help="Stable operator-facing ID for the key.")
    parser.add_argument(
        "--expires-in-days",
        type=int,
        default=0,
        help="Optional key lifetime in whole days. Omit or use 0 for no expiry.",
    )
    parser.add_argument(
        "--persist-firestore",
        action="store_true",
        help="Persist the hashed key record to Firestore using the configured project.",
    )
    parser.add_argument(
        "--metadata-json",
        default="",
        help="Optional JSON object stored alongside the key record.",
    )
    return parser.parse_args()


def _load_metadata(raw_json: str) -> dict:
    if not raw_json.strip():
        return {}
    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise ValueError("--metadata-json must decode to a JSON object")
    return payload


def main() -> int:
    args = _parse_args()
    settings = get_settings()
    service = ApiKeyAuthService(settings)
    expires_at = None
    if args.expires_in_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=args.expires_in_days)
    metadata = _load_metadata(args.metadata_json)
    provisioned = service.issue_api_key(
        args.user_id,
        key_id=args.key_id,
        expires_at=expires_at,
        persist_to_firestore=args.persist_firestore,
        metadata=metadata or None,
    )

    config_record = {
        "token_hash": provisioned.token_hash,
        "user_id": provisioned.record["user_id"],
        "key_id": provisioned.record["key_id"],
        "active": True,
    }
    if "expires_at" in provisioned.record:
        config_record["expires_at"] = provisioned.record["expires_at"].isoformat()
    if metadata:
        config_record["metadata"] = metadata

    print("API key generated successfully.")
    print(f"api_key={provisioned.api_key}")
    print(f"token_hash={provisioned.token_hash}")
    print(f"auth_source={'firestore' if args.persist_firestore else 'config'}")
    print("config_record=" + json.dumps(config_record, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
