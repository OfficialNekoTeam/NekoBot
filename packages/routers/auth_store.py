from __future__ import annotations

import secrets
from pathlib import Path

import aiosqlite
import bcrypt

_DEFAULT_DB = Path("data/auth.sqlite3")
_DEFAULT_USERNAME = "nekobot"
_DEFAULT_PASSWORD = "nekobot"
_JWT_SECRET_FILE = Path("data/jwt_secret.key")

# Module-level persistent connection and init flag
_conn: aiosqlite.Connection | None = None
_initialized: bool = False


def load_jwt_secret() -> str:
    """Load JWT secret from NEKOBOT_JWT_SECRET env var, persisted file, or generate one."""
    import os

    env_secret = os.environ.get("NEKOBOT_JWT_SECRET", "").strip()
    if env_secret:
        return env_secret
    if _JWT_SECRET_FILE.exists():
        return _JWT_SECRET_FILE.read_text().strip()
    secret = secrets.token_hex(32)
    _JWT_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _JWT_SECRET_FILE.write_text(secret)
    return secret


async def _get_conn(db_path: Path = _DEFAULT_DB) -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(db_path)
        _conn.row_factory = aiosqlite.Row
    return _conn


async def init_auth_db(db_path: Path = _DEFAULT_DB) -> None:
    """Create users table and seed default admin. Idempotent — safe to call at startup once."""
    global _initialized
    if _initialized:
        return
    db = await _get_conn(db_path)
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username      TEXT PRIMARY KEY,
            password_hash BLOB NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
        """
    )
    cursor = await db.execute(
        "SELECT 1 FROM users WHERE username = ?", (_DEFAULT_USERNAME,)
    )
    if await cursor.fetchone() is None:
        hashed = bcrypt.hashpw(_DEFAULT_PASSWORD.encode(), bcrypt.gensalt())
        await db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (_DEFAULT_USERNAME, hashed),
        )
    await db.commit()
    _initialized = True


async def verify_password(username: str, password: str, db_path: Path = _DEFAULT_DB) -> bool:
    await init_auth_db(db_path)
    db = await _get_conn(db_path)
    cursor = await db.execute(
        "SELECT password_hash FROM users WHERE username = ?", (username,)
    )
    row = await cursor.fetchone()
    if row is None:
        return False
    stored: bytes = bytes(row["password_hash"])
    return bcrypt.checkpw(password.encode(), stored)


async def update_password(
    username: str, new_password: str, db_path: Path = _DEFAULT_DB
) -> None:
    await init_auth_db(db_path)
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
    db = await _get_conn(db_path)
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE username = ?",
        (hashed, username),
    )
    await db.commit()
