"""Tests for PluginManager — install, uninstall, update, list_installed."""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.app import NekoBotFramework
from packages.plugins import PluginReloader
from packages.plugins.manager import PluginManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_plugin_zip(plugin_name: str, *, nested: bool = False) -> bytes:
    """Build an in-memory ZIP that looks like a valid nekobot plugin.

    If ``nested=True`` the zip has a GitHub-style top-level directory
    (repo-main/<files>) to exercise the strip logic.
    """
    buf = io.BytesIO()
    prefix = f"{plugin_name}-main/" if nested else ""
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{prefix}__init__.py", "from .main import *\n")
        zf.writestr(
            f"{prefix}main.py",
            "from packages.decorators import plugin\n"
            "from packages.plugins import BasePlugin\n\n"
            "@plugin(name='test-plugin', version='0.1.0')\n"
            "class TestPlugin(BasePlugin):\n"
            "    pass\n",
        )
        zf.writestr(
            f"{prefix}metadata.yaml",
            "name: test-plugin\n"
            "version: 0.1.0\n"
            "description: test\n"
            "author: tester\n"
            f"repository: https://github.com/tester/{plugin_name}\n",
        )
    return buf.getvalue()


def _make_framework() -> NekoBotFramework:
    return NekoBotFramework()


def _make_manager(tmp_path: Path) -> tuple[PluginManager, PluginReloader]:
    fw = _make_framework()
    reloader = PluginReloader(fw)
    manager = PluginManager(reloader, plugin_dir=tmp_path)
    return manager, reloader


# ---------------------------------------------------------------------------
# _parse_github_url
# ---------------------------------------------------------------------------


def test_parse_github_url_plain() -> None:
    author, repo, branch = PluginManager._parse_github_url(
        "https://github.com/someone/my_plugin"
    )
    assert author == "someone"
    assert repo == "my_plugin"
    assert branch is None


def test_parse_github_url_branch() -> None:
    author, repo, branch = PluginManager._parse_github_url(
        "https://github.com/someone/my_plugin/tree/dev"
    )
    assert author == "someone"
    assert repo == "my_plugin"
    assert branch == "dev"


def test_infer_dir_name_github() -> None:
    assert PluginManager._infer_dir_name("https://github.com/x/my_plugin") == "my_plugin"


def test_infer_dir_name_zip() -> None:
    assert PluginManager._infer_dir_name("https://example.com/plugin.zip") == "plugin"


# ---------------------------------------------------------------------------
# _extract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_flat(tmp_path: Path) -> None:
    """Flat zip (no top-level nesting) extracts directly."""
    manager, _ = _make_manager(tmp_path)
    zip_bytes = _make_plugin_zip("my_plugin", nested=False)
    zip_file = tmp_path / "_dl.zip"
    zip_file.write_bytes(zip_bytes)

    result = await manager._extract(zip_file, dir_name="my_plugin")
    assert result is not None
    assert (result / "__init__.py").exists()
    assert (result / "main.py").exists()


@pytest.mark.asyncio
async def test_extract_nested(tmp_path: Path) -> None:
    """GitHub-style nested zip strips the top-level directory."""
    manager, _ = _make_manager(tmp_path)
    zip_bytes = _make_plugin_zip("my_plugin", nested=True)
    zip_file = tmp_path / "_dl.zip"
    zip_file.write_bytes(zip_bytes)

    result = await manager._extract(zip_file, dir_name="my_plugin")
    assert result is not None
    assert (result / "__init__.py").exists()


@pytest.mark.asyncio
async def test_extract_overwrites_existing(tmp_path: Path) -> None:
    """Extracting over an existing directory removes the old one first."""
    manager, _ = _make_manager(tmp_path)
    existing = tmp_path / "my_plugin"
    existing.mkdir()
    (existing / "stale.txt").write_text("old")

    zip_bytes = _make_plugin_zip("my_plugin", nested=False)
    zip_file = tmp_path / "_dl.zip"
    zip_file.write_bytes(zip_bytes)

    result = await manager._extract(zip_file, dir_name="my_plugin")
    assert result is not None
    assert not (result / "stale.txt").exists()
    assert (result / "__init__.py").exists()


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_success(tmp_path: Path) -> None:
    zip_bytes = _make_plugin_zip("test_plugin", nested=True)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content.iter_chunked = MagicMock(return_value=_async_iter([zip_bytes]))
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Add plugin dir to sys.path so the plugin module can be imported
    sys.path.insert(0, str(tmp_path.parent))

    with (
        patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session),
        patch.object(PluginManager, "_resolve_download_url", new_callable=AsyncMock,
                     return_value="https://example.com/test_plugin.zip"),
        patch("packages.plugins.reloader.install_plugin_dependencies",
              new_callable=AsyncMock, return_value=True),
    ):
        manager, reloader = _make_manager(tmp_path)
        result = await manager.install(
            "https://github.com/tester/test_plugin",
            dir_name="test_plugin",
        )

    assert result is True
    assert (tmp_path / "test_plugin" / "__init__.py").exists()


@pytest.mark.asyncio
async def test_install_no_init_py_rolls_back(tmp_path: Path) -> None:
    """If extracted dir has no __init__.py the directory is removed."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("only_main.py", "# no __init__")
    zip_bytes = buf.getvalue()

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content.iter_chunked = MagicMock(return_value=_async_iter([zip_bytes]))
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session),
        patch.object(PluginManager, "_resolve_download_url", new_callable=AsyncMock,
                     return_value="https://example.com/bad.zip"),
    ):
        manager, _ = _make_manager(tmp_path)
        result = await manager.install(
            "https://example.com/bad.zip",
            dir_name="bad_plugin",
        )

    assert result is False
    assert not (tmp_path / "bad_plugin").exists()


@pytest.mark.asyncio
async def test_install_download_failure(tmp_path: Path) -> None:
    """All download attempts fail → install returns False."""
    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session),
        patch.object(PluginManager, "_resolve_download_url", new_callable=AsyncMock,
                     return_value="https://example.com/plugin.zip"),
    ):
        manager, _ = _make_manager(tmp_path)
        result = await manager.install("https://example.com/plugin.zip")

    assert result is False


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uninstall_removes_files(tmp_path: Path) -> None:
    manager, reloader = _make_manager(tmp_path)

    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")

    # Fake an already-loaded plugin in the reloader
    reloader._source["my-plugin"] = f"{tmp_path.name}.my_plugin"

    result = await manager.uninstall("my-plugin", remove_files=True)
    assert result is True
    assert not plugin_dir.exists()
    assert "my-plugin" not in reloader.loaded_plugins


@pytest.mark.asyncio
async def test_uninstall_unknown_plugin(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)
    result = await manager.uninstall("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_uninstall_keep_files(tmp_path: Path) -> None:
    manager, reloader = _make_manager(tmp_path)

    plugin_dir = tmp_path / "my_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("")
    reloader._source["my-plugin"] = f"{tmp_path.name}.my_plugin"

    result = await manager.uninstall("my-plugin", remove_files=False)
    assert result is True
    assert plugin_dir.exists()  # files kept


# ---------------------------------------------------------------------------
# list_installed
# ---------------------------------------------------------------------------


def test_list_installed(tmp_path: Path) -> None:
    manager, reloader = _make_manager(tmp_path)

    p1 = tmp_path / "plugin_a"
    p1.mkdir()
    (p1 / "__init__.py").write_text("")
    (p1 / "metadata.yaml").write_text(
        "name: plugin-a\nversion: 1.0\ndescription: A\nauthor: dev\n"
    )

    p2 = tmp_path / "plugin_b"
    p2.mkdir()
    (p2 / "__init__.py").write_text("")
    (p2 / "metadata.yaml").write_text(
        "name: plugin-b\nversion: 2.0\ndescription: B\nauthor: dev\n"
    )

    # directory without __init__.py — should be excluded
    p3 = tmp_path / "not_a_plugin"
    p3.mkdir()

    installed = manager.list_installed()
    names = [m.name for m in installed]
    assert "plugin-a" in names
    assert "plugin-b" in names
    assert len(installed) == 2


def test_list_installed_empty(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)
    assert manager.list_installed() == []


# ---------------------------------------------------------------------------
# _resolve_download_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_zip_url_passthrough(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)
    url = "https://example.com/plugin.zip"
    result = await manager._resolve_download_url(url)
    assert result == url


@pytest.mark.asyncio
async def test_resolve_github_branch_url(tmp_path: Path) -> None:
    manager, _ = _make_manager(tmp_path)
    url = "https://github.com/user/repo/tree/develop"
    result = await manager._resolve_download_url(url)
    assert result is not None
    assert "develop" in result


@pytest.mark.asyncio
async def test_resolve_github_uses_release(tmp_path: Path) -> None:
    """When GitHub Releases API returns a zipball_url, use it."""
    manager, _ = _make_manager(tmp_path)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={
        "zipball_url": "https://api.github.com/repos/user/repo/zipball/v1.0",
        "tag_name": "v1.0",
    })
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session):
        result = await manager._resolve_download_url("https://github.com/user/repo")

    assert result == "https://api.github.com/repos/user/repo/zipball/v1.0"


@pytest.mark.asyncio
async def test_resolve_github_falls_back_to_main(tmp_path: Path) -> None:
    """When Releases API fails, fall back to /archive/refs/heads/main.zip."""
    manager, _ = _make_manager(tmp_path)

    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session):
        result = await manager._resolve_download_url("https://github.com/user/repo")

    assert result is not None
    assert "main.zip" in result


# ---------------------------------------------------------------------------
# _download with proxy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_uses_proxy_first(tmp_path: Path) -> None:
    """When proxy is specified, the proxy URL is tried before the direct URL."""
    manager, _ = _make_manager(tmp_path)
    tried: list[str] = []

    def fake_get(url: str, **kwargs: object) -> AsyncMock:
        tried.append(url)
        resp = AsyncMock()
        resp.status = 200
        resp.content.iter_chunked = MagicMock(
            return_value=_async_iter([b"PK\x03\x04" + b"\x00" * 100])
        )
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=False)
        return resp

    mock_session = AsyncMock()
    mock_session.get = MagicMock(side_effect=fake_get)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("packages.plugins.manager.aiohttp.ClientSession", return_value=mock_session):
        await manager._download(
            "https://github.com/user/repo/archive/main.zip",
            proxy="https://myproxy.example.com",
        )

    assert tried[0].startswith("https://myproxy.example.com")


# ---------------------------------------------------------------------------
# Async helper
# ---------------------------------------------------------------------------


async def _async_iter_impl(items: list[bytes]):  # type: ignore[return]
    for item in items:
        yield item


def _async_iter(items: list[bytes]):
    return _async_iter_impl(items)
