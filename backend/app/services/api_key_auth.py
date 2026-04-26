from __future__ import annotations

import hashlib
import json
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

try:
    from google.cloud import firestore
except ModuleNotFoundError:  # pragma: no cover - exercised in lightweight local environments
    firestore = None

from app.core.config import Settings, get_settings
from app.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: str
    auth_source: str
    key_id: str | None = None
    expires_at: datetime | None = None
    principal_type: str = "user"
    can_execute_for_users: bool = False


@dataclass(frozen=True)
class ProvisionedApiKey:
    api_key: str
    token_hash: str
    record: dict[str, Any]


@dataclass
class _CacheEntry:
    principal: AuthPrincipal | None
    cached_until: datetime


class ApiKeyAuthService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._cache_ttl_seconds = max(int(settings.auth_cache_ttl_seconds), 1)
        self._cache: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._config_records = self._load_config_records(settings.auth_api_keys_json)
        if settings.firestore_project_id:
            if firestore is None:
                raise ConfigurationError(
                    "google-cloud-firestore is required when firestore_project_id is configured",
                    error_code="INVALID_AUTH_CONFIG",
                )
            self._firestore_client = firestore.Client(project=settings.firestore_project_id)
        else:
            self._firestore_client = None

    def authenticate(self, api_key: str) -> AuthPrincipal | None:
        normalized = api_key.strip()
        if not normalized:
            return None

        token_hash = self._hash_api_key(normalized)
        now = datetime.now(timezone.utc)
        cached = self._cache_get(token_hash, now)
        if cached is not _Missing:
            return cached

        principal = self._lookup_config(token_hash, now)
        if principal is None:
            principal = self._lookup_firestore(token_hash, now)
        self._cache_set(token_hash, principal, now)
        return principal

    def issue_api_key(
        self,
        user_id: str,
        *,
        key_id: str | None = None,
        expires_at: datetime | str | None = None,
        persist_to_firestore: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ProvisionedApiKey:
        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ConfigurationError(
                "user_id is required to issue an API key",
                error_code="INVALID_AUTH_CONFIG",
            )

        parsed_expiry = self._parse_expiry(expires_at)
        plaintext_key = self._generate_api_key()
        token_hash = self._hash_api_key(plaintext_key)
        record = {
            "user_id": normalized_user_id,
            "key_id": str(key_id or token_hash[:12]),
            "token_hash": token_hash,
            "active": True,
            "revoked": False,
            "created_at": datetime.now(timezone.utc),
        }
        if parsed_expiry is not None:
            record["expires_at"] = parsed_expiry
        if metadata:
            record["metadata"] = metadata

        if persist_to_firestore:
            self._persist_record_to_firestore(token_hash, record)

        return ProvisionedApiKey(api_key=plaintext_key, token_hash=token_hash, record=record)

    def _lookup_config(self, token_hash: str, now: datetime) -> AuthPrincipal | None:
        record = self._config_records.get(token_hash)
        if record is None:
            return None
        expires_at = self._parse_expiry(record.get("expires_at"))
        if expires_at is not None and expires_at <= now:
            return None
        if record.get("active", True) is False:
            return None
        user_id = str(record.get("user_id", "")).strip()
        if not user_id:
            return None
        return AuthPrincipal(
            user_id=user_id,
            auth_source="config",
            key_id=record.get("key_id"),
            expires_at=expires_at,
            principal_type=str(record.get("principal_type") or "user"),
            can_execute_for_users=bool(record.get("can_execute_for_users", False)),
        )

    def _lookup_firestore(self, token_hash: str, now: datetime) -> AuthPrincipal | None:
        if self._firestore_client is None:
            return None
        collection = self._firestore_client.collection(self.settings.auth_api_keys_collection)

        snapshot = collection.document(token_hash).get()
        payload = snapshot.to_dict() if snapshot.exists else None

        if payload is None:
            query = (
                collection.where("token_hash", "==", token_hash)
                .limit(1)
                .stream()
            )
            payload = next((doc.to_dict() for doc in query), None)

        if payload is None:
            return None
        if payload.get("revoked", False) or payload.get("active", True) is False:
            return None

        expires_at = self._parse_expiry(payload.get("expires_at"))
        if expires_at is not None and expires_at <= now:
            return None

        user_id = str(payload.get("user_id", "")).strip()
        if not user_id:
            return None

        return AuthPrincipal(
            user_id=user_id,
            auth_source="firestore",
            key_id=str(payload.get("key_id") or payload.get("name") or token_hash[:12]),
            expires_at=expires_at,
            principal_type=str(payload.get("principal_type") or "user"),
            can_execute_for_users=bool(payload.get("can_execute_for_users", False)),
        )

    def _cache_get(self, token_hash: str, now: datetime) -> AuthPrincipal | None | _MissingType:
        with self._lock:
            entry = self._cache.get(token_hash)
            if entry is None:
                return _Missing
            if entry.cached_until <= now:
                self._cache.pop(token_hash, None)
                return _Missing
            return entry.principal

    def _cache_set(self, token_hash: str, principal: AuthPrincipal | None, now: datetime) -> None:
        ttl_seconds = self._cache_ttl_seconds
        if principal is not None and principal.expires_at is not None:
            remaining = max(int((principal.expires_at - now).total_seconds()), 1)
            ttl_seconds = min(ttl_seconds, remaining)
        with self._lock:
            self._cache[token_hash] = _CacheEntry(
                principal=principal,
                cached_until=now + timedelta(seconds=ttl_seconds),
            )

    def _persist_record_to_firestore(self, token_hash: str, record: dict[str, Any]) -> None:
        if self._firestore_client is None:
            raise ConfigurationError(
                "firestore_project_id must be configured to persist API keys",
                error_code="INVALID_AUTH_CONFIG",
            )
        collection = self._firestore_client.collection(self.settings.auth_api_keys_collection)
        collection.document(token_hash).set(record, merge=True)
        with self._lock:
            self._cache.pop(token_hash, None)

    def _load_config_records(self, raw_json: str) -> dict[str, dict[str, Any]]:
        if not raw_json.strip():
            return {}
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                "AUTH_API_KEYS_JSON must be valid JSON",
                error_code="INVALID_AUTH_CONFIG",
                details={"error": str(exc)},
            ) from exc

        entries: list[dict[str, Any]]
        if isinstance(parsed, dict):
            entries = []
            for key, value in parsed.items():
                if isinstance(value, dict):
                    entries.append({"api_key": key, **value})
                else:
                    entries.append({"api_key": key, "user_id": value})
        elif isinstance(parsed, list):
            entries = [entry for entry in parsed if isinstance(entry, dict)]
        else:
            raise ConfigurationError(
                "AUTH_API_KEYS_JSON must be a JSON object or array",
                error_code="INVALID_AUTH_CONFIG",
            )

        records: dict[str, dict[str, Any]] = {}
        for index, entry in enumerate(entries):
            api_key = str(entry.get("api_key") or entry.get("token") or "").strip()
            user_id = str(entry.get("user_id") or "").strip()
            token_hash = str(entry.get("token_hash") or "").strip().lower()
            if not token_hash:
                if not api_key or not user_id:
                    raise ConfigurationError(
                        "Each API key config entry must include api_key and user_id, or token_hash and user_id",
                        error_code="INVALID_AUTH_CONFIG",
                        details={"index": index},
                    )
                token_hash = self._hash_api_key(api_key)
            elif not user_id:
                raise ConfigurationError(
                    "Each API key config entry must include user_id",
                    error_code="INVALID_AUTH_CONFIG",
                    details={"index": index},
                )
            records[token_hash] = {
                "user_id": user_id,
                "key_id": str(entry.get("key_id") or token_hash[:12]),
                "expires_at": entry.get("expires_at"),
                "active": entry.get("active", True),
                "principal_type": self._principal_type(entry),
                "can_execute_for_users": self._can_execute_for_users(entry),
            }
        return records

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_api_key() -> str:
        return f"atk_{secrets.token_urlsafe(32)}"

    @staticmethod
    def _principal_type(record: dict[str, Any]) -> str:
        metadata = record.get("metadata")
        if isinstance(metadata, dict) and metadata.get("principal_type"):
            return str(metadata.get("principal_type"))
        return str(record.get("principal_type") or "user")

    @staticmethod
    def _can_execute_for_users(record: dict[str, Any]) -> bool:
        metadata = record.get("metadata")
        metadata_flag = metadata.get("can_execute_for_users") if isinstance(metadata, dict) else None
        if metadata_flag is not None:
            return bool(metadata_flag)
        if record.get("can_execute_for_users") is not None:
            return bool(record.get("can_execute_for_users"))
        return ApiKeyAuthService._principal_type(record) == "system_executor"

    @staticmethod
    def _parse_expiry(value: Any) -> datetime | None:
        if value in (None, "", 0):
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if hasattr(value, "to_datetime"):
            converted = value.to_datetime()
            return converted.astimezone(timezone.utc) if converted.tzinfo else converted.replace(tzinfo=timezone.utc)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            parsed = datetime.fromisoformat(normalized)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        raise ConfigurationError(
            "expires_at must be an ISO-8601 string or datetime",
            error_code="INVALID_AUTH_CONFIG",
            details={"value_type": type(value).__name__},
        )


class _MissingType:
    pass


_Missing = _MissingType()


@lru_cache
def get_api_key_auth_service() -> ApiKeyAuthService:
    return ApiKeyAuthService(get_settings())

