"""示例插件

演示如何使用平台服务器发送消息
"""

from .base import (
    BasePlugin,
    register,
    on_message,
    on_private_message,
    on_group_message,
)
from loguru import logger


class ExamplePlugin(BasePlugin):
    """示例插件"""

    def __init__(self):
        super().__init__()
        self.name = "example_plugin"
        self.version = "1.0.0"
        self.description = "示例插件，演示如何发送消息"
        self.author = "NekoBot"

    async def on_load(self):
        """插件加载时调用"""
        logger.info(f"示例插件已加载: {self.name}")

    async def on_unload(self):
        """插件卸载时调用"""
        logger.info(f"示例插件已卸载: {self.name}")

    async def on_enable(self):
        """插件启用时调用"""
        logger.info(f"示例插件已启用: {self.name}")

    async def on_disable(self):
        """插件禁用时调用"""
        logger.info(f"示例插件已禁用: {self.name}")

    @register("test_send_private", "测试发送私聊消息")
    async def test_send_private(self, args, message):
        """测试发送私聊消息"""
        if not self.platform_server:
            await self.send_private_message(message.user_id, "错误：平台服务器未连接")
            return

        test_user_id = 123456789  # 测试用户ID
        success = await self.send_private_message(
            test_user_id, "这是一条测试私聊消息，来自示例插件！"
        )

        if success:
            await self.send_private_message(
                message.user_id, f"已向用户 {test_user_id} 发送测试消息"
            )
        else:
            await self.send_private_message(message.user_id, "发送消息失败")

    @register("test_send_group", "测试发送群消息")
    async def test_send_group(self, args, message):
        """测试发送群消息"""
        if not self.platform_server:
            await self.send_private_message(message.user_id, "错误：平台服务器未连接")
            return

        test_group_id = 123456789  # 测试群ID
        test_user_id = 987654321  # 测试用户ID
        success = await self.send_group_message(
            test_group_id, test_user_id, "这是一条测试群消息，来自示例插件！"
        )

        if success:
            await self.send_private_message(
                message.user_id, f"已向群 {test_group_id} 发送测试消息"
            )
        else:
            await self.send_private_message(message.user_id, "发送消息失败")

    @on_message
    async def handle_all_messages(self, message):
        """处理所有消息"""
        logger.debug(f"收到消息: {message}")

    @on_private_message
    async def handle_private_message(self, message):
        """处理私聊消息"""
        if hasattr(message, "message") and message.message:
            logger.info(f"收到私聊消息: {message.message}")

    @on_group_message
    async def handle_group_message(self, message):
        """处理群消息"""
        if hasattr(message, "message") and message.message:
            logger.info(f"收到群消息: {message.message}")


# 创建插件实例
plugin = ExamplePlugin()
