from __future__ import annotations

import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from loguru import logger

from .reloader import PluginReloader, install_plugin_dependencies, load_plugin_metadata

if TYPE_CHECKING:
    from .reloader import PluginMetadata

# GitHub 加速代理（国内环境回退用）
_GITHUB_PROXIES = [
    "https://ghproxy.com",
    "https://hk.gh-proxy.com",
    "https://gh.llkk.cc",
]


class PluginManager:
    """插件生命周期管理：安装、卸载、更新、列表。

    安装方式：
        - GitHub 仓库 URL：优先取 latest Release zipball，无 Release 则用 main.zip archive
        - 直链 ZIP：直接下载解压
        - 支持 GitHub 代理（ghproxy 等）用于国内加速

    用法：
        manager = PluginManager(reloader, plugin_dir="data/plugins")
        await manager.install("https://github.com/someone/nekobot_weather")
        await manager.uninstall("weather")
        await manager.update("weather")
    """

    def __init__(
        self,
        reloader: PluginReloader,
        plugin_dir: str | Path = "data/plugins",
    ) -> None:
        self.reloader = reloader
        self.plugin_dir = Path(plugin_dir).resolve()
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def install(
        self,
        url: str,
        *,
        dir_name: str | None = None,
        use_proxy: bool = False,
        proxy: str | None = None,
    ) -> bool:
        """从 URL 安装插件。

        支持格式：
            https://github.com/user/repo          → 优先 latest Release，回退 main.zip
            https://github.com/user/repo/tree/dev → 指定分支 archive
            https://example.com/plugin.zip        → 直链 ZIP

        Args:
            url:       插件来源 URL
            dir_name:  目标目录名，不填则从 URL 推断
            use_proxy: 是否尝试 GitHub 代理列表（国内加速）
            proxy:     指定代理前缀，优先于 use_proxy
        """
        download_url = await self._resolve_download_url(url)
        if download_url is None:
            logger.error("PluginManager: cannot resolve download URL from {}", url)
            return False

        zip_path = await self._download(download_url, proxy=proxy, use_proxy=use_proxy)
        if zip_path is None:
            return False

        try:
            plugin_dir = await self._extract(zip_path, dir_name=dir_name or self._infer_dir_name(url))
        finally:
            zip_path.unlink(missing_ok=True)

        if plugin_dir is None:
            return False

        if not (plugin_dir / "__init__.py").exists():
            logger.error("PluginManager: {} has no __init__.py, not a valid plugin", plugin_dir.name)
            shutil.rmtree(plugin_dir, ignore_errors=True)
            return False

        dep_ok = await install_plugin_dependencies(plugin_dir)
        if not dep_ok:
            logger.error("PluginManager: dependency install failed for {}, rolling back", plugin_dir.name)
            shutil.rmtree(plugin_dir, ignore_errors=True)
            return False

        parent = str(self.plugin_dir.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        module_path = f"{self.plugin_dir.name}.{plugin_dir.name}"
        try:
            names = self.reloader.load(module_path)
        except Exception as exc:
            logger.error("PluginManager: load failed for {}: {}", plugin_dir.name, exc)
            shutil.rmtree(plugin_dir, ignore_errors=True)
            return False

        meta = load_plugin_metadata(plugin_dir)
        if meta:
            self.reloader.register_metadata(plugin_dir.name, meta)

        logger.info("PluginManager: installed {} (plugins: {})", plugin_dir.name, names)
        return True

    async def uninstall(self, plugin_name: str, *, remove_files: bool = True) -> bool:
        """卸载插件。"""
        module_path = self.reloader.loaded_plugins.get(plugin_name)
        if module_path is None:
            logger.warning("PluginManager: plugin {!r} not loaded", plugin_name)
            return False

        self.reloader.unload(module_path)

        if remove_files:
            dir_name = module_path.split(".")[-1]
            target = self.plugin_dir / dir_name
            if target.exists():
                shutil.rmtree(target)
                logger.info("PluginManager: removed {}", target)

        logger.info("PluginManager: uninstalled {!r}", plugin_name)
        return True

    async def update(self, plugin_name: str, *, use_proxy: bool = False, proxy: str | None = None) -> bool:
        """重新下载最新版本并热重载。"""
        module_path = self.reloader.loaded_plugins.get(plugin_name)
        if module_path is None:
            logger.warning("PluginManager: plugin {!r} not loaded", plugin_name)
            return False

        dir_name = module_path.split(".")[-1]
        target = self.plugin_dir / dir_name
        meta = self.reloader.get_metadata(dir_name) or load_plugin_metadata(target)

        if meta is None or meta.repository is None:
            logger.warning("PluginManager: no repository URL found for {!r}, cannot update", plugin_name)
            return False

        # 卸载但保留文件，稍后覆盖
        self.reloader.unload(module_path)
        if target.exists():
            shutil.rmtree(target)

        return await self.install(meta.repository, dir_name=dir_name, use_proxy=use_proxy, proxy=proxy)

    def list_installed(self) -> list[PluginMetadata]:
        """返回所有已安装插件的元数据列表。"""
        result = []
        for entry in sorted(self.plugin_dir.iterdir()):
            if entry.is_dir() and (entry / "__init__.py").exists():
                meta = self.reloader.get_metadata(entry.name) or load_plugin_metadata(entry)
                if meta:
                    result.append(meta)
        return result

    # ------------------------------------------------------------------
    # URL resolution
    # ------------------------------------------------------------------

    async def _resolve_download_url(self, url: str) -> str | None:
        """将仓库 URL 解析为可下载的 ZIP 地址。"""
        url = url.rstrip("/")

        if url.endswith(".zip"):
            return url

        if "github.com" in url:
            return await self._resolve_github_url(url)

        if "gitee.com" in url:
            # Gitee archive 格式
            parts = url.replace("https://gitee.com/", "").split("/")
            if len(parts) >= 2:
                author, repo = parts[0], parts[1]
                return f"https://gitee.com/{author}/{repo}/repository/archive/master.zip"

        return url  # 未知格式直接尝试

    async def _resolve_github_url(self, url: str) -> str:
        """GitHub URL → 优先 latest Release zipball，回退 main.zip。"""
        author, repo, branch = self._parse_github_url(url)

        if branch:
            return f"https://github.com/{author}/{repo}/archive/refs/heads/{branch}.zip"

        # 尝试 latest Release
        try:
            api = f"https://api.github.com/repos/{author}/{repo}/releases/latest"
            async with aiohttp.ClientSession() as session:
                async with session.get(api, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        zipball = data.get("zipball_url")
                        tag = data.get("tag_name", "")
                        if zipball:
                            logger.info("PluginManager: using release {} for {}/{}", tag, author, repo)
                            return str(zipball)
        except Exception as exc:
            logger.debug("PluginManager: GitHub Releases API failed ({}), falling back to main.zip", exc)

        return f"https://github.com/{author}/{repo}/archive/refs/heads/main.zip"

    @staticmethod
    def _parse_github_url(url: str) -> tuple[str, str, str | None]:
        """返回 (author, repo, branch|None)。"""
        # https://github.com/author/repo/tree/branch
        url = url.replace("https://github.com/", "").rstrip("/")
        parts = url.split("/")
        author = parts[0]
        repo = parts[1] if len(parts) > 1 else ""
        branch = parts[3] if len(parts) > 3 and parts[2] == "tree" else None
        return author, repo, branch

    @staticmethod
    def _infer_dir_name(url: str) -> str:
        return url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git").removesuffix(".zip")

    # ------------------------------------------------------------------
    # Download & extract
    # ------------------------------------------------------------------

    async def _download(
        self, url: str, *, proxy: str | None = None, use_proxy: bool = False
    ) -> Path | None:
        tmp = Path(tempfile.mkdtemp()) / "plugin.zip"
        urls_to_try: list[str] = []

        if proxy:
            urls_to_try.append(f"{proxy.rstrip('/')}/{url}")
        elif use_proxy and "github.com" in url:
            for p in _GITHUB_PROXIES:
                urls_to_try.append(f"{p.rstrip('/')}/{url}")

        urls_to_try.append(url)  # 直连作为最后手段

        for attempt_url in urls_to_try:
            try:
                logger.info("PluginManager: downloading {}", attempt_url)
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        attempt_url, timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        if resp.status != 200:
                            logger.debug("PluginManager: HTTP {} from {}", resp.status, attempt_url)
                            continue
                        with open(tmp, "wb") as f:
                            async for chunk in resp.content.iter_chunked(65536):
                                f.write(chunk)
                logger.info("PluginManager: download complete ({} bytes)", tmp.stat().st_size)
                return tmp
            except Exception as exc:
                logger.debug("PluginManager: download failed from {}: {}", attempt_url, exc)

        logger.error("PluginManager: all download attempts failed for {}", url)
        return None

    async def _extract(self, zip_path: Path, *, dir_name: str) -> Path | None:
        """解压 ZIP 到插件目录，处理 GitHub archive 的顶层嵌套目录。"""
        # 防止 Path Traversal 地址遍历漏洞
        safe_dir_name = Path(dir_name).name
        if not safe_dir_name or safe_dir_name in (".", ".."):
            logger.error("PluginManager: Invalid directory name {!r}", dir_name)
            return None
            
        target = self.plugin_dir / safe_dir_name

        if target.exists():
            logger.warning("PluginManager: {} already exists, overwriting", dir_name)
            shutil.rmtree(target)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                names = zf.namelist()
                # GitHub archive 有顶层目录 repo-branch/，需要剥掉
                top_dirs = {n.split("/")[0] for n in names if "/" in n}
                single_top = next(iter(top_dirs)) if len(top_dirs) == 1 else None

                with tempfile.TemporaryDirectory() as tmp_extract:
                    zf.extractall(tmp_extract)
                    extracted = Path(tmp_extract)
                    src = extracted / single_top if single_top else extracted
                    shutil.copytree(src, target)

            logger.info("PluginManager: extracted to {}", target)
            return target
        except Exception as exc:
            logger.error("PluginManager: extraction failed: {}", exc)
            shutil.rmtree(target, ignore_errors=True)
            return None
