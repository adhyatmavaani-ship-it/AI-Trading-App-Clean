from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


@dataclass(frozen=True)
class EncryptedApiKey:
    key_hash: str
    encrypted_key: str
    encryption_iv: str
    encryption_tag: str
    key_preview: str


class ApiKeyEncryptionService:
    """Encrypt user exchange credentials without touching broker execution flow."""

    def __init__(self, master_key: str) -> None:
        self._key = self._decode_master_key(master_key)

    @staticmethod
    def generate_master_key() -> str:
        return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")

    @staticmethod
    def hash_key(raw_api_key: str) -> str:
        return hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def preview(raw_api_key: str) -> str:
        normalized = raw_api_key.strip()
        if len(normalized) <= 8:
            return "*" * len(normalized)
        return f"{normalized[:4]}...{normalized[-4:]}"

    def encrypt(self, raw_api_key: str, *, associated_data: str = "") -> EncryptedApiKey:
        normalized = raw_api_key.strip()
        if not normalized:
            raise ValueError("api key is required")
        iv = os.urandom(12)
        ciphertext_with_tag = AESGCM(self._key).encrypt(
            iv,
            normalized.encode("utf-8"),
            associated_data.encode("utf-8") if associated_data else None,
        )
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]
        return EncryptedApiKey(
            key_hash=self.hash_key(normalized),
            encrypted_key=self._b64encode(ciphertext),
            encryption_iv=self._b64encode(iv),
            encryption_tag=self._b64encode(tag),
            key_preview=self.preview(normalized),
        )

    def decrypt(
        self,
        *,
        encrypted_key: str,
        encryption_iv: str,
        encryption_tag: str,
        associated_data: str = "",
    ) -> str:
        payload = self._b64decode(encrypted_key) + self._b64decode(encryption_tag)
        plaintext = AESGCM(self._key).decrypt(
            self._b64decode(encryption_iv),
            payload,
            associated_data.encode("utf-8") if associated_data else None,
        )
        return plaintext.decode("utf-8")

    @classmethod
    def _decode_master_key(cls, value: str) -> bytes:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("USER_API_KEY_ENCRYPTION_SECRET is required")
        for decoder in (cls._b64decode, bytes.fromhex):
            try:
                decoded = decoder(normalized)
            except Exception:
                continue
            if len(decoded) in {16, 24, 32}:
                return decoded
        if len(normalized) >= 32:
            return hashlib.sha256(normalized.encode("utf-8")).digest()
        raise ValueError("USER_API_KEY_ENCRYPTION_SECRET must resolve to at least 32 bytes")

    @staticmethod
    def _b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _b64decode(value: str) -> bytes:
        normalized = str(value).strip()
        padding = "=" * (-len(normalized) % 4)
        return base64.urlsafe_b64decode((normalized + padding).encode("ascii"))
