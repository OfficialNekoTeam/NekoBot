from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import yaml
from loguru import logger

from ..decorators.core import PLATFORM_SPEC_ATTR, PLUGIN_SPEC_ATTR

if TYPE_CHECKING:
    from ..app import NekoBotFramework


# ---------------------------------------------------------------------------
# Plugin metadata
# ---------------------------------------------------------------------------


@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    repository: str | None = None
    display_name: str | None = None
    tags: list[str] | None = None
    nekobot_version: str | None = None
    support_platforms: list[str] | None = None
    root_dir: str | None = None


def load_plugin_metadata(plugin_dir: Path) -> PluginMetadata | None:
    """从插件目录的 metadata.yaml 加载元信息，加载失败返回 None。"""
    path = plugin_dir / "metadata.yaml"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, object] = yaml.safe_load(f) or {}
        missing = [k for k in ("name", "version", "description", "author") if not data.get(k)]
        if missing:
            logger.warning("PluginMetadata: {} missing fields: {}", plugin_dir.name, missing)
            return None
        return PluginMetadata(
            name=str(data["name"]),
            version=str(data["version"]),
            description=str(data["description"]),
            author=str(data["author"]),
            repository=str(data["repository"]) if data.get("repository") else None,
            display_name=str(data["display_name"]) if data.get("display_name") else None,
            tags=list(data["tags"]) if isinstance(data.get("tags"), list) else None,
            nekobot_version=str(data["nekobot_version"]) if data.get("nekobot_version") else None,
            support_platforms=list(data["support_platforms"])
            if isinstance(data.get("support_platforms"), list)
            else None,
            root_dir=plugin_dir.name,
        )
    except Exception as exc:
        logger.warning("PluginMetadata: failed to load {}: {}", plugin_dir.name, exc)
        return None


# ---------------------------------------------------------------------------
# Dependency installer
# ---------------------------------------------------------------------------


async def install_plugin_dependencies(plugin_dir: Path) -> bool:
    """安装插件的 requirements.txt 依赖，无 requirements.txt 时直接返回 True。"""
    req = plugin_dir / "requirements.txt"
    if not req.exists():
        return True

    # 优先用 uv，回退到 pip
    for executable in ("uv", "pip"):
        cmd = (
            [executable, "pip", "install", "-r", str(req)]
            if executable == "uv"
            else [executable, "install", "-r", str(req)]
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode == 0:
                logger.info("PluginDeps: installed deps for {} via {}", plugin_dir.name, executable)
                return True
            logger.debug("PluginDeps: {} failed: {}", executable, stderr.decode(errors="ignore")[:200])
        except FileNotFoundError:
            continue
        except Exception as exc:
            logger.warning("PluginDeps: error running {}: {}", executable, exc)
            break

    logger.error("PluginDeps: failed to install deps for {}", plugin_dir.name)
    return False


# ---------------------------------------------------------------------------
# Reloader
# ---------------------------------------------------------------------------


class PluginReloader:
    """插件加载、热重载、目录扫描。

    用法：
        reloader = PluginReloader(framework)
        await reloader.load_directory("data/plugins")   # 扫描目录
        reloader.reload_plugin("my-plugin")             # 手动热重载
        await reloader.watch("data/plugins")            # 启动 watchfiles 自动热重载
    """

    def __init__(self, framework: NekoBotFramework) -> None:
        self.framework = framework
        # plugin_name → module dotted path
        self._source: dict[str, str] = {}
        # dir_name → PluginMetadata
        self._metadata: dict[str, PluginMetadata] = {}
        self._watch_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, module_path: str) -> list[str]:
        """首次导入并绑定模块，返回注册的插件名列表。"""
        module = importlib.import_module(module_path)
        return self._bind_module(module, module_path)

    def reload(self, module_path: str) -> list[str]:
        """热重载：卸载旧插件 → importlib.reload → 重新绑定。"""
        self._unregister_from_module(module_path)
        if module_path in sys.modules:
            module = importlib.reload(sys.modules[module_path])
        else:
            module = importlib.import_module(module_path)
        return self._bind_module(module, module_path)

    def reload_plugin(self, plugin_name: str) -> bool:
        """按插件名热重载，返回是否成功。"""
        module_path = self._source.get(plugin_name)
        if module_path is None:
            logger.warning("PluginReloader: unknown plugin {!r}", plugin_name)
            return False
        self.reload(module_path)
        return True

    async def load_directory(self, directory: str | Path) -> dict[str, list[str]]:
        """扫描插件目录，安装依赖并加载所有含 __init__.py 的子目录包。

        约定：
            __init__.py  — 框架发现入口（re-export 插件类）
            main.py      — 插件逻辑（@plugin / @command / @event_handler）
            metadata.yaml — 元信息
            requirements.txt — 可选依赖

        Returns:
            dict[dir_name, list[plugin_names]]
        """
        base = Path(directory).resolve()
        if not base.is_dir():
            logger.warning("PluginReloader: plugin directory not found: {}", base)
            return {}

        parent = str(base.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        results: dict[str, list[str]] = {}
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            if not (entry / "__init__.py").exists():
                logger.debug("PluginReloader: skipping {} (no __init__.py)", entry.name)
                continue

            # 加载元数据
            meta = load_plugin_metadata(entry)
            if meta:
                self._metadata[entry.name] = meta

            # 安装依赖
            dep_ok = await install_plugin_dependencies(entry)
            if not dep_ok:
                logger.error("PluginReloader: skipping {} due to dependency failure", entry.name)
                results[entry.name] = []
                continue

            module_path = f"{base.name}.{entry.name}"
            try:
                names = self.load(module_path)
                results[entry.name] = names
            except Exception as exc:
                logger.error("PluginReloader: failed to load {!r}: {}", entry.name, exc)
                results[entry.name] = []

        return results

    async def watch(self, directory: str | Path) -> None:
        """启动 watchfiles 监听，.py 文件变动时自动热重载对应插件。

        在后台 task 运行，调用 stop_watch() 停止。
        """
        try:
            from watchfiles import PythonFilter, awatch
        except ImportError:
            logger.warning("PluginReloader: watchfiles 未安装，无法启动文件监听")
            return

        base = Path(directory).resolve()

        async def _watch_loop() -> None:
            logger.info("PluginReloader: watching {}", base)
            try:
                async for changes in awatch(base, watch_filter=PythonFilter(), recursive=True):
                    affected = self._affected_plugins(changes, base)
                    for dir_name in affected:
                        module_path = f"{base.name}.{dir_name}"
                        if module_path not in {v for v in self._source.values()}:
                            continue
                        logger.info("PluginReloader: file change detected, reloading {!r}", dir_name)
                        try:
                            self.reload(module_path)
                        except Exception as exc:
                            logger.error("PluginReloader: reload failed for {!r}: {}", dir_name, exc)
            except asyncio.CancelledError:
                pass

        self._watch_task = asyncio.create_task(_watch_loop())

    def stop_watch(self) -> None:
        """停止 watchfiles 监听。"""
        if self._watch_task and not self._watch_task.done():
            self._watch_task.cancel()
            self._watch_task = None
            logger.info("PluginReloader: file watcher stopped")

    def unload(self, module_path: str) -> list[str]:
        """卸载模块内所有插件，返回被卸载的插件名列表。"""
        return self._unregister_from_module(module_path)

    def get_metadata(self, dir_name: str) -> PluginMetadata | None:
        return self._metadata.get(dir_name)

    def register_metadata(self, dir_name: str, meta: PluginMetadata) -> None:
        self._metadata[dir_name] = meta

    @property
    def loaded_plugins(self) -> dict[str, str]:
        """返回 {plugin_name: module_path} 映射（快照）。"""
        return dict(self._source)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bind_module(self, module: ModuleType, module_path: str) -> list[str]:
        loaded: list[str] = []
        for _, member in inspect.getmembers(module, inspect.isclass):
            # @platform 装饰器：注册平台类型
            platform_spec = getattr(member, PLATFORM_SPEC_ATTR, None)
            if platform_spec is not None:
                try:
                    self.framework.platform_registry.register_class(
                        platform_spec.platform_type, member
                    )
                    logger.info(
                        "PluginReloader: registered platform type {!r} from {}",
                        platform_spec.platform_type,
                        module_path,
                    )
                except ValueError as exc:
                    logger.warning("PluginReloader: platform register failed: {}", exc)
                continue

            # @plugin 装饰器：注册插件
            if getattr(member, PLUGIN_SPEC_ATTR, None) is None:
                continue
            try:
                registered = self.framework.binder.bind_plugin_class(member)
            except ValueError as exc:
                logger.warning("PluginReloader: bind failed for {}: {}", member.__name__, exc)
                continue
            name = registered.spec.name
            self._source[name] = module_path
            loaded.append(name)
            logger.info(
                "PluginReloader: loaded {!r} v{} from {}",
                name,
                registered.spec.version,
                module_path,
            )
        return loaded

    def _unregister_from_module(self, module_path: str) -> list[str]:
        names = [n for n, mp in self._source.items() if mp == module_path]
        for name in names:
            try:
                self.framework.runtime_registry.unregister_plugin(name)
            except Exception as exc:
                logger.warning("PluginReloader: runtime unregister failed for {!r}: {}", name, exc)
            try:
                self.framework.tool_registry.unregister_plugin(name)
            except Exception as exc:
                logger.warning("PluginReloader: tool unregister failed for {!r}: {}", name, exc)
            self._source.pop(name, None)
            logger.info("PluginReloader: unloaded {!r}", name)
        return names

    def _affected_plugins(self, changes: set[tuple[object, str]], base: Path) -> set[str]:
        """从 watchfiles 变更集合找出受影响的插件目录名。"""
        affected: set[str] = set()
        for _, file_path_str in changes:
            file_path = Path(file_path_str).resolve()
            # 向上找含 __init__.py 的直接子目录
            try:
                rel = file_path.relative_to(base)
                dir_name = rel.parts[0]
                if (base / dir_name / "__init__.py").exists():
                    affected.add(dir_name)
            except ValueError:
                continue
        return affected
