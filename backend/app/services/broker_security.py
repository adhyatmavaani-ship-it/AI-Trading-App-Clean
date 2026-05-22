from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings


FORBIDDEN_BROKER_PERMISSIONS = {"withdraw", "withdrawal", "transfer", "funding", "wallet"}


@dataclass
class BrokerCredentialVault:
    settings: Settings

    def encrypt_credentials(self, payload: dict) -> str:
        self._validate_permissions(payload.get("permissions", []))
        nonce = os.urandom(12)
        cipher = AESGCM(self._key())
        encrypted = cipher.encrypt(nonce, json.dumps(payload, sort_keys=True).encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    def decrypt_credentials(self, token: str) -> dict:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        nonce, encrypted = raw[:12], raw[12:]
        decrypted = AESGCM(self._key()).decrypt(nonce, encrypted, None)
        payload = json.loads(decrypted.decode("utf-8"))
        self._validate_permissions(payload.get("permissions", []))
        return payload

    def _key(self) -> bytes:
        raw = str(self.settings.broker_vault_master_key or "").strip()
        if not raw:
            raise ValueError("BROKER_VAULT_MASTER_KEY is required for encrypted broker credentials")
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
            if len(decoded) == 32:
                return decoded
        except Exception:
            pass
        return hashlib.sha256(raw.encode("utf-8")).digest()

    def _validate_permissions(self, permissions: object) -> None:
        normalized = {str(item).strip().lower() for item in (permissions or [])}
        forbidden = sorted(normalized & FORBIDDEN_BROKER_PERMISSIONS)
        if forbidden:
            raise ValueError(f"Broker API key rejected: withdrawal-style permissions are forbidden ({', '.join(forbidden)})")
