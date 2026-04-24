from __future__ import annotations

from pathlib import Path

import pytest

import packages.routers.auth_store as auth_store_mod
from packages.routers.auth_store import (
    close_auth_db,
    init_auth_db,
    update_password,
    verify_password,
)


@pytest.fixture(autouse=True)
async def reset_auth_state():
    """Reset module-level connection state before and after each test."""
    await close_auth_db()
    yield
    await close_auth_db()


async def test_default_credentials_accepted(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    assert await verify_password("nekobot", "nekobot", db_path=db) is True


async def test_wrong_password_rejected(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    await init_auth_db(db_path=db)
    assert await verify_password("nekobot", "wrongpass", db_path=db) is False


async def test_unknown_user_rejected(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    await init_auth_db(db_path=db)
    assert await verify_password("nobody", "nekobot", db_path=db) is False


async def test_update_password_changes_credentials(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    await init_auth_db(db_path=db)

    await update_password("nekobot", "newpass123", db_path=db)

    assert await verify_password("nekobot", "newpass123", db_path=db) is True
    assert await verify_password("nekobot", "nekobot", db_path=db) is False


async def test_init_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    await init_auth_db(db_path=db)
    await init_auth_db(db_path=db)  # second call must not raise or duplicate rows
    assert await verify_password("nekobot", "nekobot", db_path=db) is True


async def test_close_resets_connection_state(tmp_path: Path) -> None:
    db = tmp_path / "auth.sqlite3"
    await init_auth_db(db_path=db)
    await close_auth_db()

    assert auth_store_mod._conn is None
    assert auth_store_mod._initialized is False

    # Should be usable again after close
    assert await verify_password("nekobot", "nekobot", db_path=db) is True
