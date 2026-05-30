import pytest

from app.services.api_key_crypto import ApiKeyEncryptionService


def test_api_key_encryption_round_trip() -> None:
    service = ApiKeyEncryptionService(ApiKeyEncryptionService.generate_master_key())

    encrypted = service.encrypt("sk_live_test_crypto_key_123456", associated_data="user-1:binance")

    assert encrypted.key_preview == "sk_l...3456"
    assert encrypted.encrypted_key
    assert encrypted.encryption_iv
    assert encrypted.encryption_tag
    assert service.decrypt(
        encrypted_key=encrypted.encrypted_key,
        encryption_iv=encrypted.encryption_iv,
        encryption_tag=encrypted.encryption_tag,
        associated_data="user-1:binance",
    ) == "sk_live_test_crypto_key_123456"


def test_api_key_encryption_uses_unique_iv_with_stable_hash() -> None:
    service = ApiKeyEncryptionService(ApiKeyEncryptionService.generate_master_key())

    first = service.encrypt("same-user-key-material", associated_data="user-1:binance")
    second = service.encrypt("same-user-key-material", associated_data="user-1:binance")

    assert first.key_hash == second.key_hash
    assert first.encryption_iv != second.encryption_iv
    assert first.encrypted_key != second.encrypted_key


def test_api_key_decryption_rejects_wrong_context() -> None:
    service = ApiKeyEncryptionService(ApiKeyEncryptionService.generate_master_key())
    encrypted = service.encrypt("context-bound-key-material", associated_data="user-1:binance")

    with pytest.raises(Exception):
        service.decrypt(
            encrypted_key=encrypted.encrypted_key,
            encryption_iv=encrypted.encryption_iv,
            encryption_tag=encrypted.encryption_tag,
            associated_data="user-2:binance",
        )
