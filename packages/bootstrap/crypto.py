from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet
from loguru import logger

_SECRET_FILE = Path("data/.secret_key")
_FERNET: Fernet | None = None

def _get_fernet() -> Fernet:
    global _FERNET
    if _FERNET is not None:
        return _FERNET
    
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if not _SECRET_FILE.exists():
        key = Fernet.generate_key()
        _SECRET_FILE.write_bytes(key)
        # 限制文件权限 (仅限Linux/Mac)
        if os.name != "nt":
            _SECRET_FILE.chmod(0o600)
        logger.info("Generated new secret key for configuration encryption.")
    else:
        key = _SECRET_FILE.read_bytes()
        
    _FERNET = Fernet(key)
    return _FERNET

def encrypt_value(value: str) -> str:
    """Encrypt a plaintext string and return it with 'ENC:' prefix."""
    f = _get_fernet()
    encrypted = f.encrypt(value.encode("utf-8")).decode("utf-8")
    return f"ENC:{encrypted}"

def decrypt_value(value: str) -> str:
    """Decrypt a string if it starts with 'ENC:', otherwise return as is."""
    if not value.startswith("ENC:"):
        return value
    f = _get_fernet()
    token = value[4:]
    try:
        decrypted = f.decrypt(token.encode("utf-8")).decode("utf-8")
        return decrypted
    except Exception as exc:
        logger.warning(f"Failed to decrypt configuration value: {exc}")
        return value

def decrypt_secrets(data: object) -> object:
    """Recursively traverse the configuration dictionary and decrypt values starting with 'ENC:'."""
    if isinstance(data, dict):
        return {k: decrypt_secrets(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [decrypt_secrets(item) for item in data]
    elif isinstance(data, str) and data.startswith("ENC:"):
        return decrypt_value(data)
    return data

def encrypt_secrets(data: object, key_name: str = "") -> object:
    """Recursively traverse and encrypt sensitive fields based on their keys."""
    if isinstance(data, dict):
        return {k: encrypt_secrets(v, str(k)) for k, v in data.items()}
    elif isinstance(data, list):
        return [encrypt_secrets(item, key_name) for item in data]
    elif isinstance(data, str):
        # 检查是否已经是密文，防止重复加密
        if data.startswith("ENC:"):
            return data
        # 如果 key 中包含如下敏感词，则执行加密
        lower_key = key_name.lower()
        if any(substr in lower_key for substr in ("api_key", "secret", "password", "token")):
            return encrypt_value(data)
    return data
