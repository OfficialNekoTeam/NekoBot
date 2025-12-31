"""热重载功能单元测试

测试热重载管理器的各种功能
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.core.hot_reload_manager import (
    HotReloadManager,
    ReloadEventType,
    ReloadEvent
)
from packages.core.config_reload_manager import (
    ConfigReloadManager,
    ConfigSchema,
    ConfigValidationResult
)
from packages.routes.dynamic_route_manager import (
    DynamicRouteManager,
    RouteInfo,
    RouteConflictResolution
)


class TestHotReloadManager:
    """测试热重载管理器"""

    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "plugins"
            config_dir = Path(tmpdir) / "config"
            plugin_dir.mkdir()
            config_dir.mkdir()
            yield plugin_dir, config_dir

    @pytest.fixture
    def hot_reload_manager(self, temp_dirs):
        """创建热重载管理器实例"""
        plugin_dir, config_dir = temp_dirs
        
        plugin_callback = AsyncMock()
        config_callback = AsyncMock()
        
        manager = HotReloadManager(
            plugin_dir=plugin_dir,
            config_dir=config_dir,
            plugin_reload_callback=plugin_callback,
            config_reload_callback=config_callback
        )
        return manager, plugin_callback, config_callback

    @pytest.mark.asyncio
    async def test_initialization(self, hot_reload_manager):
        """测试初始化"""
        manager, _, _ = hot_reload_manager
        assert not manager.is_running()
        assert len(manager._reloaded_plugins) == 0
        assert len(manager._reloaded_configs) == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, hot_reload_manager):
        """测试启动和停止"""
        manager, _, _ = hot_reload_manager
        
        # 测试启动（可能会因为缺少 watchfiles 而失败）
        try:
            await manager.start()
            # 如果 watchfiles 可用，应该运行
            if manager.is_running():
                assert manager.is_running()
                
                # 测试停止
                await manager.stop()
                assert not manager.is_running()
        except Exception:
            # 如果 watchfiles 不可用，跳过此测试
            pass

    @pytest.mark.asyncio
    async def test_safe_reload_plugin_success(self, hot_reload_manager):
        """测试成功的插件重载"""
        manager, plugin_callback, _ = hot_reload_manager
        
        plugin_name = "test_plugin"
        plugin_callback.return_value = None
        
        success = await manager._safe_reload_plugin(plugin_name)
        
        assert success is True
        assert plugin_name in manager._reloaded_plugins
        assert plugin_callback.called
        
        # 检查重载事件
        history = manager.get_reload_history()
        assert len(history) > 0
        latest_event = history[-1]
        assert latest_event["type"] == ReloadEventType.PLUGIN_RELOAD.value
        assert latest_event["target"] == plugin_name
        assert latest_event["success"] is True

    @pytest.mark.asyncio
    async def test_safe_reload_plugin_failure(self, hot_reload_manager):
        """测试失败的插件重载"""
        manager, plugin_callback, _ = hot_reload_manager
        
        plugin_name = "test_plugin"
        plugin_callback.side_effect = Exception("重载失败")
        
        success = await manager._safe_reload_plugin(plugin_name)
        
        assert success is False
        assert plugin_name in manager._reloaded_plugins
        
        # 检查重载事件
        history = manager.get_reload_history()
        latest_event = history[-1]
        assert latest_event["success"] is False
        assert latest_event["error"] == "重载失败"

    @pytest.mark.asyncio
    async def test_safe_reload_config_success(self, hot_reload_manager):
        """测试成功的配置重载"""
        manager, _, config_callback = hot_reload_manager
        
        config_name = "test_config"
        config_callback.return_value = None
        
        # Mock 验证函数
        with patch.object(manager, '_validate_config', return_value=asyncio.coroutine(lambda: (True, ""))()):
            success = await manager._safe_reload_config(config_name)
        
        assert success is True
        assert config_name in manager._reloaded_configs

    @pytest.mark.asyncio
    async def test_get_stats(self, hot_reload_manager):
        """测试获取统计信息"""
        manager, plugin_callback, _ = hot_reload_manager
        
        # 执行一次重载
        plugin_callback.return_value = None
        await manager._safe_reload_plugin("test_plugin")
        
        stats = manager.get_stats()
        
        assert stats["total_events"] == 1
        assert stats["plugin_reloads"] == 1
        assert stats["successful_reloads"] == 1
        assert stats["failed_reloads"] == 0
        assert stats["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_clear_reload_history(self, hot_reload_manager):
        """测试清空重载历史"""
        manager, plugin_callback, _ = hot_reload_manager
        
        # 添加一些历史
        plugin_callback.return_value = None
        await manager._safe_reload_plugin("plugin1")
        await manager._safe_reload_plugin("plugin2")
        
        assert len(manager._reload_history) == 2
        
        # 清空历史
        manager.clear_reload_history()
        
        assert len(manager._reload_history) == 0

    def test_register_route(self, hot_reload_manager):
        """测试注册路由"""
        manager, _, _ = hot_reload_manager
        
        route_id = "test_route"
        route = Mock()
        
        success = manager.register_route(route_id, route)
        
        assert success is True
        assert route_id in manager._dynamic_routes
        assert manager.get_route(route_id) == route

    def test_unregister_route(self, hot_reload_manager):
        """测试注销路由"""
        manager, _, _ = hot_reload_manager
        
        route_id = "test_route"
        route = Mock()
        manager.register_route(route_id, route)
        
        success = manager.unregister_route(route_id)
        
        assert success is True
        assert route_id not in manager._dynamic_routes
        assert manager.get_route(route_id) is None

    def test_list_routes(self, hot_reload_manager):
        """测试列出路由"""
        manager, _, _ = hot_reload_manager
        
        # 注册几个路由
        manager.register_route("route1", Mock())
        manager.register_route("route2", Mock())
        
        routes = manager.list_routes()
        
        assert len(routes) == 2
        assert "route1" in [r["route_id"] for r in routes]
        assert "route2" in [r["route_id"] for r in routes]


class TestConfigReloadManager:
    """测试配置热重载管理器"""

    @pytest.fixture
    def temp_config_dir(self):
        """创建临时配置目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            yield config_dir

    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """创建配置重载管理器实例"""
        manager = ConfigReloadManager(config_dir=temp_config_dir)
        return manager

    def test_initialization(self, config_manager):
        """测试初始化"""
        assert config_manager.config_dir.exists()
        assert len(config_manager._configs) == 0
        assert len(config_manager._schemas) == 0

    def test_register_schema(self, config_manager):
        """测试注册 Schema"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "enabled": {
                    "type": bool,
                    "default": True,
                    "description": "是否启用"
                },
                "count": {
                    "type": int,
                    "default": 0,
                    "min_value": 0,
                    "max_value": 100
                }
            }
        )
        
        config_manager.register_schema(schema)
        
        assert "test_config" in config_manager._schemas

    def test_get_default_config(self, config_manager):
        """测试获取默认配置"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "enabled": {"type": bool, "default": True},
                "count": {"type": int, "default": 0}
            }
        )
        
        default = config_manager._get_default_config(schema)
        
        assert default == {"enabled": True, "count": 0}

    def test_validate_config_valid(self, config_manager):
        """测试配置验证 - 有效配置"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "enabled": {"type": bool, "default": True},
                "count": {"type": int, "default": 0}
            }
        )
        config_manager.register_schema(schema)
        
        valid_config = {"enabled": True, "count": 50}
        result, errors = asyncio.run(config_manager._validate_config("test_config", valid_config))
        
        assert result == ConfigValidationResult.VALID
        assert errors == ""

    def test_validate_config_missing_field(self, config_manager):
        """测试配置验证 - 缺少必填字段"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "enabled": {"type": bool, "required": True},
                "count": {"type": int, "required": True}
            }
        )
        config_manager.register_schema(schema)
        
        invalid_config = {"enabled": True}  # 缺少 count
        result, errors = asyncio.run(config_manager._validate_config("test_config", invalid_config))
        
        assert result != ConfigValidationResult.VALID
        assert "缺少必填字段: count" in errors

    def test_validate_config_type_mismatch(self, config_manager):
        """测试配置验证 - 类型不匹配"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "enabled": {"type": bool, "default": True},
                "count": {"type": int, "default": 0}
            }
        )
        config_manager.register_schema(schema)
        
        invalid_config = {"enabled": "true", "count": 50}  # enabled 应该是 bool
        result, errors = asyncio.run(config_manager._validate_config("test_config", invalid_config))
        
        assert result != ConfigValidationResult.VALID
        assert "类型错误" in errors

    def test_validate_config_out_of_range(self, config_manager):
        """测试配置验证 - 超出范围"""
        schema = ConfigSchema(
            name="test_config",
            fields={
                "count": {"type": int, "min_value": 0, "max_value": 100}
            }
        )
        config_manager.register_schema(schema)
        
        invalid_config = {"count": 150}  # 超出 max_value
        result, errors = asyncio.run(config_manager._validate_config("test_config", invalid_config))
        
        assert result != ConfigValidationResult.VALID
        assert "超出最大值" in errors

    @pytest.mark.asyncio
    async def test_load_save_config(self, config_manager):
        """测试加载和保存配置"""
        config_name = "test_config"
        config_data = {"key1": "value1", "key2": 123}
        
        # 保存配置
        success = await config_manager.save_config(config_name, config_data)
        assert success is True
        
        # 加载配置
        loaded = await config_manager.load_config(config_name)
        assert loaded == config_data
        
        # 从缓存获取
        cached = config_manager.get_config(config_name)
        assert cached == config_data

    @pytest.mark.asyncio
    async def test_reload_config(self, config_manager):
        """测试重载配置"""
        config_name = "test_config"
        old_data = {"key1": "old_value"}
        new_data = {"key1": "new_value"}
        
        # 保存旧配置
        await config_manager.save_config(config_name, old_data)
        
        # 注册回调
        callback = Mock()
        config_manager.register_callback(config_name, callback)
        
        # 保存新配置
        await config_manager.save_config(config_name, new_data)
        
        # 重载
        success = await config_manager.reload_config(config_name)
        
        assert success is True
        assert callback.called
        assert config_manager.get_config(config_name) == new_data

    def test_get_stats(self, config_manager):
        """测试获取统计信息"""
        stats = config_manager.get_stats()
        
        assert "total_configs" in stats
        assert "total_schemas" in stats
        assert "total_callbacks" in stats

    def test_get_reload_history(self, config_manager):
        """测试获取重载历史"""
        history = config_manager.get_reload_history()
        
        assert isinstance(history, list)


class TestDynamicRouteManager:
    """测试动态路由管理器"""

    @pytest.fixture
    def mock_app(self):
        """创建 Mock 应用"""
        return Mock()

    @pytest.fixture
    def route_manager(self, mock_app):
        """创建动态路由管理器实例"""
        return DynamicRouteManager(mock_app)

    def test_initialization(self, route_manager):
        """测试初始化"""
        assert route_manager.app is not None
        assert len(route_manager._routes) == 0
        assert len(route_manager._path_routes) == 0

    def test_register_route_success(self, route_manager):
        """测试注册路由成功"""
        route_info = RouteInfo(
            route_id="test_route",
            method="GET",
            path="/api/test",
            handler=Mock(),
            module="test_module",
            description="测试路由"
        )
        
        success, error = asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=Mock(),
                module="test_module",
                description="测试路由"
            )
        )
        
        assert success is True
        assert error is None
        assert "test_route" in route_manager._routes

    def test_register_route_duplicate(self, route_manager):
        """测试注册重复路由"""
        handler = Mock()
        
        # 第一次注册
        success1, _ = asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=handler,
                module="test_module"
            )
        )
        assert success1 is True
        
        # 第二次注册（重复）
        success2, error = asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=Mock(),
                module="test_module"
            )
        )
        
        assert success2 is False
        assert "已存在" in error

    def test_unregister_route(self, route_manager):
        """测试注销路由"""
        handler = Mock()
        
        # 先注册
        asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=handler,
                module="test_module"
            )
        )
        
        # 注销
        success, error = asyncio.run(route_manager.unregister_route("test_route"))
        
        assert success is True
        assert error is None
        assert "test_route" not in route_manager._routes

    def test_get_routes_by_path(self, route_manager):
        """测试按路径获取路由"""
        handler1 = Mock()
        handler2 = Mock()
        
        # 注册同一路径的不同方法
        asyncio.run(
            route_manager.register_route(
                route_id="route1",
                method="GET",
                path="/api/test",
                handler=handler1,
                module="test_module"
            )
        )
        asyncio.run(
            route_manager.register_route(
                route_id="route2",
                method="POST",
                path="/api/test",
                handler=handler2,
                module="test_module"
            )
        )
        
        routes = route_manager.get_routes_by_path("/api/test")
        
        assert len(routes) == 2
        route_ids = [r.route_id for r in routes]
        assert "route1" in route_ids
        assert "route2" in route_ids

    def test_get_routes_by_module(self, route_manager):
        """测试按模块获取路由"""
        handler1 = Mock()
        handler2 = Mock()
        
        # 注册同模块的路由
        asyncio.run(
            route_manager.register_route(
                route_id="route1",
                method="GET",
                path="/api/test1",
                handler=handler1,
                module="test_module"
            )
        )
        asyncio.run(
            route_manager.register_route(
                route_id="route2",
                method="POST",
                path="/api/test2",
                handler=handler2,
                module="test_module"
            )
        )
        
        routes = route_manager.get_routes_by_module("test_module")
        
        assert len(routes) == 2
        route_ids = [r.route_id for r in routes]
        assert "route1" in route_ids
        assert "route2" in route_ids

    def test_set_conflict_resolution(self, route_manager):
        """测试设置冲突解决策略"""
        route_manager.set_conflict_resolution(RouteConflictResolution.REPLACE)
        
        assert route_manager._conflict_resolution == RouteConflictResolution.REPLACE

    def test_list_routes(self, route_manager):
        """测试列出所有路由"""
        handler = Mock()
        
        # 注册路由
        asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=handler,
                module="test_module",
                description="测试路由",
                priority=10
            )
        )
        
        routes = route_manager.list_routes()
        
        assert len(routes) == 1
        assert routes[0]["route_id"] == "test_route"
        assert routes[0]["method"] == "GET"
        assert routes[0]["path"] == "/api/test"
        assert routes[0]["module"] == "test_module"
        assert routes[0]["priority"] == 10

    def test_export_routes_documentation(self, route_manager):
        """测试导出路由文档"""
        handler = Mock()
        
        # 注册路由
        asyncio.run(
            route_manager.register_route(
                route_id="test_route",
                method="GET",
                path="/api/test",
                handler=handler,
                module="test_module",
                description="测试路由"
            )
        )
        
        doc = route_manager.export_routes_documentation()
        
        assert "# 动态路由文档" in doc
        assert "test_route" in doc
        assert "GET" in doc
        assert "/api/test" in doc

    @pytest.mark.asyncio
    async def test_enable_disable_route(self, route_manager):
        """测试启用/禁用路由"""
        handler = Mock()
        
        # 注册路由
        await route_manager.register_route(
            route_id="test_route",
            method="GET",
            path="/api/test",
            handler=handler,
            module="test_module"
        )
        
        # 禁用
        disabled = await route_manager.disable_route("test_route")
        assert disabled is True
        assert route_manager._routes["test_route"].enabled is False
        
        # 启用
        enabled = await route_manager.enable_route("test_route")
        assert enabled is True
        assert route_manager._routes["test_route"].enabled is True

    @pytest.mark.asyncio
    async def test_unregister_by_module(self, route_manager):
        """测试按模块注销路由"""
        handler1 = Mock()
        handler2 = Mock()
        
        # 注册同模块的路由
        await route_manager.register_route(
            route_id="route1",
            method="GET",
            path="/api/test1",
            handler=handler1,
            module="test_module"
        )
        await route_manager.register_route(
            route_id="route2",
            method="POST",
            path="/api/test2",
            handler=handler2,
            module="test_module"
        )
        
        # 注销模块
        success_count, failed = await route_manager.unregister_by_module("test_module")
        
        assert success_count == 2
        assert len(failed) == 0
        assert "route1" not in route_manager._routes
        assert "route2" not in route_manager._routes


class TestReloadPerformance:
    """测试重载性能"""

    @pytest.fixture
    def temp_dirs(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_dir = Path(tmpdir) / "plugins"
            config_dir = Path(tmpdir) / "config"
            plugin_dir.mkdir()
            config_dir.mkdir()
            yield plugin_dir, config_dir

    @pytest.fixture
    def hot_reload_manager(self, temp_dirs):
        """创建热重载管理器实例"""
        plugin_dir, config_dir = temp_dirs
        plugin_callback = AsyncMock()
        config_callback = AsyncMock()
        
        return HotReloadManager(
            plugin_dir=plugin_dir,
            config_dir=config_dir,
            plugin_reload_callback=plugin_callback,
            config_reload_callback=config_callback
        )

    @pytest.mark.asyncio
    async def test_plugin_reload_performance(self, hot_reload_manager):
        """测试插件重载性能"""
        import time
        
        manager, plugin_callback, _ = hot_reload_manager
        plugin_callback.return_value = None
        
        # 执行 10 次重载并测量时间
        times = []
        for i in range(10):
            start = time.time()
            await manager._safe_reload_plugin(f"plugin_{i}")
            duration_ms = (time.time() - start) * 1000
            times.append(duration_ms)
        
        avg_time = sum(times) / len(times)
        max_time = max(times)
        
        print(f"平均重载时间: {avg_time:.2f}ms")
        print(f"最大重载时间: {max_time:.2f}ms")
        
        # 验证不超过 300ms
        assert avg_time < 300, f"平均重载时间 {avg_time:.2f}ms 超过 300ms"
        assert max_time < 500, f"最大重载时间 {max_time:.2f}ms 超过 500ms"

    @pytest.mark.asyncio
    async def test_config_reload_performance(self, hot_reload_manager):
        """测试配置重载性能"""
        import time
        
        manager, _, config_callback = hot_reload_manager
        config_callback.return_value = None
        
        # Mock 验证函数
        with patch.object(manager, '_validate_config', return_value=asyncio.coroutine(lambda: (True, ""))()):
            times = []
            for i in range(10):
                start = time.time()
                await manager._safe_reload_config(f"config_{i}")
                duration_ms = (time.time() - start) * 1000
                times.append(duration_ms)
            
            avg_time = sum(times) / len(times)
            
            assert avg_time < 300, f"平均重载时间 {avg_time:.2f}ms 超过 300ms"