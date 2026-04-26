from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path


def _load_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_digest(digest: str) -> None:
    if not digest.startswith("sha256:"):
        raise ValueError("image digest must start with sha256:")
    body = digest.split(":", 1)[1]
    if len(body) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in body):
        raise ValueError("image digest must be a valid sha256 hex digest")


def _verify(
    *,
    cosign_bin: str,
    image_repository: str,
    image_digest: str,
    identity: str,
    oidc_issuer: str,
) -> int:
    _validate_digest(image_digest)
    image_ref = f"{image_repository}@{image_digest}"
    command = [
        *shlex.split(cosign_bin),
        "verify",
        image_ref,
        "--certificate-identity",
        identity,
        "--certificate-oidc-issuer",
        oidc_issuer,
        "--output",
        "json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "cosign verify failed"
        raise RuntimeError(stderr)
    payload = json.loads(result.stdout or "[]")
    if not payload:
        raise RuntimeError("cosign verify returned no signatures")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a container image signature with cosign.")
    parser.add_argument("--manifest", default="")
    parser.add_argument("--repository", default="")
    parser.add_argument("--digest", default="")
    parser.add_argument("--identity", default="")
    parser.add_argument("--oidc-issuer", default="")
    parser.add_argument("--cosign-bin", default="cosign")
    args = parser.parse_args()

    try:
        if args.manifest:
            manifest = _load_manifest(Path(args.manifest).resolve())
            repository = manifest["image"]["repository"]
            digest = manifest["image"]["digest"]
            identity = manifest["signature"]["identity"]
            oidc_issuer = manifest["signature"]["oidc_issuer"]
        else:
            repository = args.repository
            digest = args.digest
            identity = args.identity
            oidc_issuer = args.oidc_issuer

        if not all([repository, digest, identity, oidc_issuer]):
            raise ValueError(
                "repository, digest, identity, and oidc issuer are required unless --manifest is provided"
            )

        _verify(
            cosign_bin=args.cosign_bin,
            image_repository=repository,
            image_digest=digest,
            identity=identity,
            oidc_issuer=oidc_issuer,
        )
        print(f"Verified signature for {repository}@{digest}")
        return 0
    except Exception as exc:
        print(f"Signature verification failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
