"""平台适配器单元测试

测试新增的平台适配器功能
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.platform import BasePlatform
from packages.platform.base import PlatformStatus
from packages.platform.sources import (
    lark,
    kook,
    qqchannel,
)


class TestLarkPlatform:
    """飞书平台适配器测试"""

    @pytest.fixture
    def platform_config(self):
        return {
            "type": "lark",
            "enable": True,
            "id": "test_lark",
            "name": "TestBot",
            "app_id": "test_app_id",
            "app_secret": "test_secret",
            "domain": "https://open.feishu.cn",
            "connection_mode": "socket",
            "lark_bot_name": "TestBot",
        }

    @pytest.fixture
    def platform_settings(self):
        return {}

    @pytest.fixture
    def event_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def platform(self, platform_config, platform_settings, event_queue):
        return lark.LarkPlatform(platform_config, platform_settings, event_queue)

    def test_initialization(self, platform, platform_config):
        """测试初始化"""
        assert platform.name == "lark"
        assert platform.enabled == platform_config["enable"]
        assert platform.id == platform_config["id"]
        assert platform.display_name == platform_config["name"]

    def test_get_config(self, platform, platform_config):
        """测试获取配置"""
        assert platform.get_config("app_id") == platform_config["app_id"]
        assert platform.get_config("app_secret") == platform_config["app_secret"]
        assert platform.get_config("invalid_key", "default") == "default"

    def test_is_enabled(self, platform):
        """测试是否启用"""
        assert platform.is_enabled() is True

    def test_status(self, platform):
        """测试状态"""
        assert platform.status == PlatformStatus.PENDING

    def test_duplicate_event_check(self, platform):
        """测试重复事件检查"""
        # 首次检查应返回 False
        assert platform._is_duplicate_event("test_event_1") is False
        # 第二次检查应返回 True
        assert platform._is_duplicate_event("test_event_1") is True
        # 第三次检查应返回 True
        assert platform._is_duplicate_event("test_event_1") is True


class TestKookPlatform:
    """KOOK 平台适配器测试"""

    @pytest.fixture
    def platform_config(self):
        return {
            "type": "kook",
            "enable": True,
            "id": "test_kook",
            "name": "TestBot",
            "token": "test_token",
            "verify_token": "",
            "encrypt_key": "",
        }

    @pytest.fixture
    def platform_settings(self):
        return {}

    @pytest.fixture
    def event_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def platform(self, platform_config, platform_settings, event_queue):
        return kook.KookPlatform(platform_config, platform_settings, event_queue)

    def test_initialization(self, platform, platform_config):
        """测试初始化"""
        assert platform.name == "kook"
        assert platform.enabled == platform_config["enable"]
        assert platform.id == platform_config["id"]
        assert platform.token == platform_config["token"]

    def test_get_config(self, platform, platform_config):
        """测试获取配置"""
        assert platform.get_config("token") == platform_config["token"]
        assert platform.get_config("invalid_key", "default") == "default"


class TestQQChannelPlatform:
    """QQ 频道平台适配器测试"""

    @pytest.fixture
    def platform_config(self):
        return {
            "type": "qqchannel",
            "enable": True,
            "id": "test_qqchannel",
            "name": "TestBot",
            "app_id": "test_app_id",
            "token": "test_token",
            "sandbox": False,
        }

    @pytest.fixture
    def platform_settings(self):
        return {}

    @pytest.fixture
    def event_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def platform(self, platform_config, platform_settings, event_queue):
        return qqchannel.QQChannelPlatform(platform_config, platform_settings, event_queue)

    def test_initialization(self, platform, platform_config):
        """测试初始化"""
        assert platform.name == "qqchannel"
        assert platform.enabled == platform_config["enable"]
        assert platform.id == platform_config["id"]
        assert platform.app_id == platform_config["app_id"]
        assert platform.token == platform_config["token"]

    def test_get_config(self, platform, platform_config):
        """测试获取配置"""
        assert platform.get_config("app_id") == platform_config["app_id"]
        assert platform.get_config("token") == platform_config["token"]

    def test_api_base(self, platform):
        """测试 API 基础 URL"""
        assert platform.api_base == "https://api.sgroup.qq.com"

    def test_sandbox_api_base(self, platform):
        """测试沙箱 API 基础 URL"""
        sandbox_config = {
            **self.platform_config,
            "sandbox": True,
        }
        platform_sandbox = qqchannel.QQChannelPlatform(
            sandbox_config, {}, asyncio.Queue()
        )
        assert platform_sandbox.api_base == "https://sandbox.api.sgroup.qq.com"


class TestPlatformBase:
    """平台基类测试"""

    @pytest.fixture
    def platform_config(self):
        return {
            "type": "test",
            "enable": True,
            "id": "test_id",
            "name": "TestBot",
        }

    @pytest.fixture
    def platform_settings(self):
        return {}

    @pytest.fixture
    def event_queue(self):
        return asyncio.Queue()

    @pytest.fixture
    def platform(self, platform_config, platform_settings, event_queue):
        # 创建一个简单的测试平台
        class TestPlatform(BasePlatform):
            async def start(self):
                self.status = PlatformStatus.RUNNING
            async def stop(self):
                self.status = PlatformStatus.STOPPED
            async def send_message(self, message_type, target_id, message, **kwargs):
                return {"status": "success"}

        return TestPlatform(platform_config, platform_settings, event_queue)

    def test_initial_status(self, platform):
        """测试初始状态"""
        assert platform.status == PlatformStatus.PENDING

    def test_error_recording(self, platform):
        """测试错误记录"""
        platform.record_error("Test error", "Test traceback")
        assert len(platform.errors) == 1
        assert platform.errors[0].message == "Test error"
        assert platform.errors[0].traceback == "Test traceback"

    def test_error_status(self, platform):
        """测试错误状态"""
        platform.record_error("Test error")
        assert platform.status == PlatformStatus.ERROR

    def test_clear_errors(self, platform):
        """测试清除错误"""
        platform.record_error("Test error")
        assert len(platform.errors) == 1
        platform.clear_errors()
        assert len(platform.errors) == 0
        assert platform.status == PlatformStatus.RUNNING

    def test_message_count(self, platform):
        """测试消息计数"""
        assert platform.get_message_count() == 0
        platform.increment_message_count()
        assert platform.get_message_count() == 1
        platform.increment_message_count()
        platform.increment_message_count()
        assert platform.get_message_count() == 3

    def test_reset_message_count(self, platform):
        """测试重置消息计数"""
        platform.increment_message_count()
        platform.increment_message_count()
        assert platform.get_message_count() == 2
        assert platform.get_previous_message_count() == 0
        platform.reset_message_count()
        assert platform.get_message_count() == 0
        assert platform.get_previous_message_count() == 2

    def test_stats(self, platform):
        """测试统计信息"""
        platform.status = PlatformStatus.RUNNING
        stats = platform.get_stats()
        assert "id" in stats
        assert "type" in stats
        assert "status" in stats
        assert stats["status"] == "running"