from __future__ import annotations

from pathlib import Path

import pytest

import packages.bootstrap.crypto as crypto_mod
from packages.bootstrap.crypto import (
    decrypt_secrets,
    decrypt_value,
    encrypt_secrets,
    encrypt_value,
)


@pytest.fixture(autouse=True)
def reset_fernet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect secret key file to tmp_path and reset cached Fernet instance."""
    monkeypatch.setattr(crypto_mod, "_SECRET_FILE", tmp_path / ".secret_key")
    monkeypatch.setattr(crypto_mod, "_FERNET", None)


# ---------------------------------------------------------------------------
# encrypt_value / decrypt_value
# ---------------------------------------------------------------------------

def test_encrypt_value_adds_enc_prefix() -> None:
    result = encrypt_value("my-api-key")
    assert result.startswith("ENC:")


def test_encrypt_value_is_not_plaintext() -> None:
    result = encrypt_value("my-api-key")
    assert "my-api-key" not in result


def test_decrypt_value_recovers_plaintext() -> None:
    encrypted = encrypt_value("hello-secret")
    assert decrypt_value(encrypted) == "hello-secret"


def test_decrypt_value_passthrough_without_prefix() -> None:
    assert decrypt_value("plain-text") == "plain-text"


def test_decrypt_value_returns_original_on_invalid_token() -> None:
    bad = "ENC:notvalidbase64!!"
    result = decrypt_value(bad)
    assert result == bad


def test_encrypt_decrypt_roundtrip_unicode() -> None:
    original = "密钥-🔑-secret"
    assert decrypt_value(encrypt_value(original)) == original


def test_same_plaintext_produces_different_ciphertext() -> None:
    a = encrypt_value("same")
    b = encrypt_value("same")
    assert a != b  # Fernet uses random IV


# ---------------------------------------------------------------------------
# encrypt_secrets / decrypt_secrets (recursive dict traversal)
# ---------------------------------------------------------------------------

def test_encrypt_secrets_encrypts_sensitive_keys() -> None:
    data = {"api_key": "sk-123", "name": "openai"}
    result = encrypt_secrets(data)
    assert isinstance(result, dict)
    assert str(result["api_key"]).startswith("ENC:")
    assert result["name"] == "openai"


@pytest.mark.parametrize("key", ["api_key", "secret", "password", "token"])
def test_encrypt_secrets_triggers_on_sensitive_key_names(key: str) -> None:
    result = encrypt_secrets({key: "value"})
    assert str(result[key]).startswith("ENC:")  # type: ignore[index]


def test_encrypt_secrets_skips_non_sensitive_keys() -> None:
    data = {"base_url": "https://api.openai.com", "model": "gpt-4"}
    result = encrypt_secrets(data)
    assert result == data


def test_encrypt_secrets_does_not_double_encrypt() -> None:
    already = encrypt_value("original")
    result = encrypt_secrets({"api_key": already})
    assert result["api_key"] == already  # type: ignore[index]


def test_decrypt_secrets_decrypts_nested_dict() -> None:
    data = {
        "provider": {
            "api_key": encrypt_value("real-key"),
            "model": "gpt-4",
        }
    }
    result = decrypt_secrets(data)
    assert isinstance(result, dict)
    assert result["provider"]["api_key"] == "real-key"  # type: ignore[index]
    assert result["provider"]["model"] == "gpt-4"  # type: ignore[index]


def test_decrypt_secrets_handles_list() -> None:
    data = [encrypt_value("a"), "plain", encrypt_value("b")]
    result = decrypt_secrets(data)
    assert result == ["a", "plain", "b"]


def test_encrypt_decrypt_full_config_roundtrip() -> None:
    config = {
        "framework_config": {"default_provider": "openai"},
        "provider_configs": {
            "openai": {"api_key": "sk-abc", "password": "pw123", "base_url": "https://x.com"}
        },
    }
    encrypted = encrypt_secrets(config)
    decrypted = decrypt_secrets(encrypted)
    assert decrypted == config


# ---------------------------------------------------------------------------
# Key file persistence
# ---------------------------------------------------------------------------

def test_secret_key_file_created_on_first_use(tmp_path: Path) -> None:
    key_path = tmp_path / ".secret_key"
    assert not key_path.exists()
    encrypt_value("test")
    assert key_path.exists()


def test_same_key_reused_across_calls(tmp_path: Path) -> None:
    encrypted = encrypt_value("data")
    # Reset cached instance to force re-read from file
    crypto_mod._FERNET = None
    assert decrypt_value(encrypted) == "data"
