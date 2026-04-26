from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys


REQUIRED_TOP_LEVEL = {
    "environment",
    "namespace",
    "release_name",
    "deployment",
    "service",
    "chart_path",
    "values_file",
    "ai_model_version",
    "strategy",
    "image",
    "signature",
}
REQUIRED_IMAGE_FIELDS = {"repository", "digest"}
REQUIRED_SIGNATURE_FIELDS = {"identity", "oidc_issuer"}
REQUIRED_STRATEGY_FIELDS = {"default", "enabled"}
ALLOWED_ENVIRONMENTS = {"staging", "production"}
ALLOWED_STRATEGIES = {"ensemble", "hybrid_crypto", "ema_crossover", "rsi", "breakout"}


def _load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    _validate_manifest(payload, path)
    return payload


def _validate_manifest(payload: dict, path: Path) -> None:
    missing = sorted(REQUIRED_TOP_LEVEL - set(payload))
    if missing:
        raise ValueError(f"{path}: missing required fields: {', '.join(missing)}")
    if payload["environment"] not in ALLOWED_ENVIRONMENTS:
        raise ValueError(f"{path}: environment must be one of {sorted(ALLOWED_ENVIRONMENTS)}")
    ai_model_version = str(payload["ai_model_version"]).strip()
    if not ai_model_version:
        raise ValueError(f"{path}: ai_model_version must not be empty")
    strategy = payload["strategy"]
    if not isinstance(strategy, dict):
        raise ValueError(f"{path}: strategy must be an object")
    strategy_missing = sorted(REQUIRED_STRATEGY_FIELDS - set(strategy))
    if strategy_missing:
        raise ValueError(f"{path}: strategy missing fields: {', '.join(strategy_missing)}")
    default_strategy = str(strategy["default"]).strip()
    enabled_strategies = strategy["enabled"]
    if default_strategy not in ALLOWED_STRATEGIES:
        raise ValueError(f"{path}: strategy.default must be one of {sorted(ALLOWED_STRATEGIES)}")
    if not isinstance(enabled_strategies, list) or not enabled_strategies:
        raise ValueError(f"{path}: strategy.enabled must be a non-empty list")
    normalized_enabled = [str(item).strip() for item in enabled_strategies]
    if any(item not in ALLOWED_STRATEGIES for item in normalized_enabled):
        raise ValueError(f"{path}: strategy.enabled contains unsupported strategies")
    if default_strategy not in normalized_enabled:
        raise ValueError(f"{path}: strategy.default must be included in strategy.enabled")
    image = payload["image"]
    if not isinstance(image, dict):
        raise ValueError(f"{path}: image must be an object")
    image_missing = sorted(REQUIRED_IMAGE_FIELDS - set(image))
    if image_missing:
        raise ValueError(f"{path}: image missing fields: {', '.join(image_missing)}")
    for key in ("namespace", "release_name", "deployment", "service", "chart_path", "values_file"):
        if not str(payload[key]).strip():
            raise ValueError(f"{path}: {key} must not be empty")
    for key in ("repository", "digest"):
        if not str(image[key]).strip():
            raise ValueError(f"{path}: image.{key} must not be empty")
    digest = str(image["digest"]).strip()
    if not digest.startswith("sha256:"):
        raise ValueError(f"{path}: image.digest must start with sha256:")
    digest_body = digest.split(":", 1)[1]
    if len(digest_body) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in digest_body):
        raise ValueError(f"{path}: image.digest must be a valid sha256 hex digest")
    signature = payload["signature"]
    if not isinstance(signature, dict):
        raise ValueError(f"{path}: signature must be an object")
    signature_missing = sorted(REQUIRED_SIGNATURE_FIELDS - set(signature))
    if signature_missing:
        raise ValueError(f"{path}: signature missing fields: {', '.join(signature_missing)}")
    for key in ("identity", "oidc_issuer"):
        if not str(signature[key]).strip():
            raise ValueError(f"{path}: signature.{key} must not be empty")


def _resolve(args: argparse.Namespace) -> int:
    manifest_path = Path(args.manifest).resolve()
    payload = _load_manifest(manifest_path)
    payload["manifest_path"] = str(manifest_path)
    if args.github_output:
        github_output = Path(args.github_output)
        lines = {
            "environment": payload["environment"],
            "namespace": payload["namespace"],
            "release_name": payload["release_name"],
            "deployment": payload["deployment"],
            "service": payload["service"],
            "chart_path": payload["chart_path"],
            "values_file": payload["values_file"],
            "ai_model_version": payload["ai_model_version"],
            "strategy_default": payload["strategy"]["default"],
            "strategy_enabled": ",".join(payload["strategy"]["enabled"]),
            "image_repository": payload["image"]["repository"],
            "image_registry": payload["image"]["repository"].split("/", 1)[0],
            "image_digest": payload["image"]["digest"],
            "signature_identity": payload["signature"]["identity"],
            "signature_oidc_issuer": payload["signature"]["oidc_issuer"],
            "context": payload.get("context", ""),
            "manifest_path": payload["manifest_path"],
        }
        with github_output.open("a", encoding="utf-8") as handle:
            for key, value in lines.items():
                handle.write(f"{key}={value}\n")
    else:
        print(json.dumps(payload, indent=2))
    return 0


def _promote(args: argparse.Namespace) -> int:
    source_path = Path(args.source).resolve()
    target_path = Path(args.target).resolve()
    source_payload = _load_manifest(source_path)
    target_payload = _load_manifest(target_path)

    target_payload["image"] = dict(source_payload["image"])
    target_payload["ai_model_version"] = source_payload["ai_model_version"]
    target_payload["strategy"] = dict(source_payload["strategy"])
    target_payload["signature"] = dict(source_payload["signature"])
    target_payload["promotion"] = {
        "source_manifest": str(source_path),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }

    with target_path.open("w", encoding="utf-8") as handle:
        json.dump(target_payload, handle, indent=2)
        handle.write("\n")

    print(f"Promoted artifact {source_payload['image']['repository']}@{source_payload['image']['digest']}")
    print(f"Updated {target_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve and promote release manifests.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve", help="Validate and emit manifest values.")
    resolve_parser.add_argument("--manifest", required=True)
    resolve_parser.add_argument("--github-output", default="")
    resolve_parser.set_defaults(handler=_resolve)

    promote_parser = subparsers.add_parser("promote", help="Promote image artifact from one manifest to another.")
    promote_parser.add_argument("--source", required=True)
    promote_parser.add_argument("--target", required=True)
    promote_parser.set_defaults(handler=_promote)

    args = parser.parse_args()
    try:
        return args.handler(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
