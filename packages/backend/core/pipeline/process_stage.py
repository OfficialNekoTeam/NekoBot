"""处理消息阶段

处理消息（Agent/LLM 请求）
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class ProcessStage(Stage):
    """处理消息阶段"""

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        logger.debug("ProcessStage 初始化")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """处理消息事件

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type == "message":
            await self._process_message(event, ctx)
        elif post_type == "notice":
            await self._process_notice(event, ctx)
        elif post_type == "request":
            await self._process_request(event, ctx)

        return None

    async def _process_message(self, event: dict, ctx: PipelineContext) -> None:
        """处理消息事件"""
        message_type = event.get("message_type", "unknown")
        user_id = event.get("user_id", "unknown")
        group_id = event.get("group_id", "N/A")

        text_content = self._format_message(event)

        def _trim_text(t: str, n: int = 120) -> str:
            s = " ".join(t.splitlines())
            return s if len(s) <= n else s[: n - 3] + "..."

        text_log = _trim_text(text_content)
        sender = (
            event.get("sender", {}) if isinstance(event.get("sender"), dict) else {}
        )
        nickname = sender.get("card") or sender.get("nickname") or str(user_id)
        user_disp = f"{nickname}({user_id})"
        group_name = event.get("group_name")
        group_disp = f"{group_name}({group_id})" if group_name else f"{group_id}"

        if message_type == "group":
            logger.info(f"猫猫 | 接收 <- 群聊 [{group_disp}] [{user_disp}] {text_log}")
        else:
            logger.info(f"猫猫 | 接收 <- 私聊 [{user_disp}] {text_log}")

        # 检查是否是命令消息
        message = event.get("message", "")
        is_command = False

        if isinstance(message, list):
            for msg_seg in message:
                if msg_seg.get("type") == "text":
                    text = msg_seg.get("data", {}).get("text", "")
                    platform_id = event.get("platform_id", "onebot")
                    platform = ctx.platform_manager.get_platform(platform_id)
                    command_prefix = (
                        platform.get_config("command_prefix", "/") if platform else "/"
                    )
                    if text.startswith(command_prefix):
                        is_command = True
                        break
        elif isinstance(message, str) and message.startswith("/"):
            is_command = True

        # 处理命令消息
        if is_command:
            await ctx.plugin_manager.handle_message(event)
            command_handled = await self._process_command(event, ctx)
            # 如果命令未被处理，则触发 LLM 回复
            if not command_handled:
                await self._trigger_llm_response(event, ctx)
        else:
            # 非命令消息，直接触发 LLM 回复
            await self._trigger_llm_response(event, ctx)

    async def _process_command(self, event: dict, ctx: PipelineContext) -> bool:
        """处理命令

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            是否成功处理命令
        """
        from packages.backend.core.server import format_message

        normalized_text = format_message(event, simple=False)
        platform_id = event.get("platform_id", "onebot")
        platform = ctx.platform_manager.get_platform(platform_id)
        command_prefix = platform.get_config("command_prefix", "/") if platform else "/"
        if isinstance(normalized_text, str) and normalized_text.startswith(
            command_prefix
        ):
            command_text = normalized_text[len(command_prefix) :]
            parts = command_text.split()
            command = parts[0] if parts else ""
            args = parts[1:] if len(parts) > 1 else []
            if command:
                # 命令别名映射
                command_aliases = {
                    "plugin": "plugins",
                }
                command = command_aliases.get(command, command)

                # 基础命令
                if command == "help":
                    await self._handle_help_command(event, ctx)
                    return True
                elif command == "ping":
                    await self._handle_ping_command(event, ctx)
                    return True
                elif command == "sid":
                    await self._handle_sid_command(event, ctx)
                    return True
                # 插件管理命令
                elif command == "plugins":
                    await self._handle_plugins_command(event, ctx, args)
                    return True
                # 管理员命令
                elif command == "op":
                    await self._handle_op_command(event, ctx, args)
                    return True
                elif command == "deop":
                    await self._handle_deop_command(event, ctx, args)
                    return True
                elif command == "wl":
                    await self._handle_wl_command(event, ctx, args)
                    return True
                elif command == "dwl":
                    await self._handle_dwl_command(event, ctx, args)
                    return True
                # 插件命令
                handled = await ctx.plugin_manager.execute_command(command, args, event)
                if handled:
                    return True
                logger.warning(f"未找到命令处理器: {command}")
        return False

    async def _process_notice(self, event: dict, ctx: PipelineContext) -> None:
        """处理通知事件"""
        notice_type = event.get("notice_type", "unknown")
        logger.info(f"收到通知事件: {notice_type}")

        # 只转发部分通知事件到插件系统
        if notice_type in [
            "group_increase",
            "group_decrease",
            "group_ban",
            "friend_add",
        ]:
            await ctx.plugin_manager.handle_message(event)

    async def _process_request(self, event: dict, ctx: PipelineContext) -> None:
        """处理请求事件"""
        request_type = event.get("request_type", "unknown")
        logger.info(f"收到请求事件: {request_type}")

        # 转发请求事件到插件系统
        await ctx.plugin_manager.handle_message(event)

    async def _trigger_llm_response(self, event: dict, ctx: PipelineContext) -> None:
        """触发 LLM 回复

        Args:
            event: 事件数据
            ctx: Pipeline 上下文
        """
        try:
            from packages.backend.llm import (
                ContextManager,
                ContextConfig,
                ContextCompressionStrategy,
            )
            from packages.backend.llm.base import BaseLLMProvider
            from packages.backend.core.config import load_config

            # 获取消息内容
            message_text = self._format_message(event, simple=False)

            # 加载配置
            config = load_config()
            llm_providers = config.get("llm_providers", {})

            # 查找启用的 LLM 提供商
            provider_config = None
            for provider in llm_providers.values():
                if provider.get("enabled", False):
                    provider_config = provider
                    break

            if not provider_config:
                logger.warning("未找到启用的 LLM 提供商")
                return

            # 创建 LLM 提供商实例
            provider_type = provider_config.get("type", "unknown")
            from packages.backend.llm.register import llm_provider_cls_map

            provider_cls = llm_provider_cls_map.get(provider_type)
            if not provider_cls:
                logger.warning(f"未找到 LLM 提供商类型: {provider_type}")
                return

            provider = provider_cls(provider_config, {})

            # 创建会话 ID（基于用户 ID 和群组 ID）
            user_id = event.get("user_id", "unknown")
            group_id = event.get("group_id", "private")
            session_id = f"{group_id}_{user_id}"

            # 创建上下文管理器
            context_config = ContextConfig(
                max_messages=provider_config.get("max_messages", 20),
                compression_strategy=ContextCompressionStrategy(
                    provider_config.get("compression_strategy", "FIFO")
                ),
            )
            context_manager = ContextManager(context_config)

            # 调用 LLM
            response = await provider.text_chat(
                prompt=message_text,
                session_id=session_id,
                contexts=context_manager.get_context(session_id),
            )

            # 获取响应文本
            response_text = response.get("content", "")
            if not response_text:
                logger.warning("LLM 返回空响应")
                return

            # 发送回复
            await self._send_message(event, ctx, response_text)

            # 更新上下文
            context_manager.add_message(session_id, "user", message_text)
            context_manager.add_message(session_id, "assistant", response_text)

        except Exception as e:
            logger.error(f"触发 LLM 回复失败: {e}")

    async def _handle_help_command(self, event: dict, ctx: PipelineContext) -> None:
        """处理 help 命令"""
        platform_id = event.get("platform_id", "onebot")
        platform = ctx.platform_manager.get_platform(platform_id)
        command_prefix = platform.get_config("command_prefix", "/") if platform else "/"

        from packages.backend.core.server import get_full_version

        help_text = f"🐱 NekoBot 帮助\n{get_full_version()}\n\n"
        help_text += "📋 基础命令:\n"
        help_text += f"  {command_prefix}help - 显示此帮助信息\n"
        help_text += f"  {command_prefix}ping - 检查机器人状态\n"
        help_text += f"  {command_prefix}sid - 获取当前会话 ID\n\n"
        help_text += "🔌 插件管理:\n"
        help_text += f"  {command_prefix}plugins list - 显示已加载的插件\n"
        help_text += f"  {command_prefix}plugins enable <插件名> - 启用插件\n"
        help_text += f"  {command_prefix}plugins disable <插件名> - 禁用插件\n"
        help_text += f"  {command_prefix}plugins reload <插件名> - 重载插件\n"
        help_text += f"  {command_prefix}plugins install <URL> - 从 URL 安装插件\n"
        help_text += f"  {command_prefix}plugins uninstall <插件名> - 卸载插件\n"
        help_text += f"  {command_prefix}plugins help <插件名> - 查看插件帮助\n\n"
        help_text += "👑 管理员命令:\n"
        help_text += f"  {command_prefix}op <用户ID> - 授权管理员\n"
        help_text += f"  {command_prefix}deop <用户ID> - 取消管理员授权\n"
        help_text += f"  {command_prefix}wl <会话ID> - 添加白名单\n"
        help_text += f"  {command_prefix}dwl <会话ID> - 删除白名单\n\n"
        help_text += "🎯 插件命令:\n"

        # 获取所有已启用插件的命令
        plugin_commands = {}
        for plugin_name in ctx.plugin_manager.enabled_plugins:
            plugin = ctx.plugin_manager.plugins.get(plugin_name)
            if plugin:
                for cmd_name, cmd_func in plugin.commands.items():
                    cmd_info = getattr(cmd_func, "_nekobot_command", {})
                    description = cmd_info.get("description", "无描述")
                    if plugin_name not in plugin_commands:
                        plugin_commands[plugin_name] = []
                    plugin_commands[plugin_name].append((cmd_name, description))

        # 按插件分组显示命令
        for plugin_name, commands in plugin_commands.items():
            help_text += f"  [{plugin_name}]\n"
            for cmd_name, description in commands:
                help_text += f"    {command_prefix}{cmd_name} - {description}\n"

        # 发送帮助信息
        await self._send_message(event, ctx, help_text)

    async def _handle_ping_command(self, event: dict, ctx: PipelineContext) -> None:
        """处理 ping 命令"""
        await self._send_message(event, ctx, "Pong!")

    async def _handle_plugins_command(
        self, event: dict, ctx: PipelineContext, args: list
    ) -> None:
        """处理 plugins 命令"""
        if not args:
            # 默认显示插件列表
            plugins_info = ctx.plugin_manager.get_all_plugins_info()
            text = "🔌 已加载的插件:\n"
            for name, info in plugins_info.items():
                status = "✅ 已启用" if info.get("enabled") else "❌ 已禁用"
                text += f"  {name} ({info.get('version', '未知版本')}) - {status}\n"
            text += "\n使用 /plugins help <插件名> 查看插件帮助和加载的指令。\n"
            text += "使用 /plugins enable/disable <插件名> 启用或禁用插件。"
            await self._send_message(event, ctx, text)
        else:
            action = args[0]
            if action == "list":
                plugins_info = ctx.plugin_manager.get_all_plugins_info()
                text = "🔌 已加载的插件:\n"
                for name, info in plugins_info.items():
                    status = "✅ 已启用" if info.get("enabled") else "❌ 已禁用"
                    text += f"  {name} ({info.get('version', '未知版本')}) - {status}\n"
                await self._send_message(event, ctx, text)
            elif action == "enable":
                if len(args) < 2:
                    await self._send_message(
                        event, ctx, "用法: /plugins enable <插件名>"
                    )
                else:
                    success = await ctx.plugin_manager.enable_plugin(args[1])
                    if success:
                        await self._send_message(
                            event, ctx, f"✅ 插件 {args[1]} 已启用"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"❌ 插件 {args[1]} 启用失败"
                        )
            elif action == "disable":
                if len(args) < 2:
                    await self._send_message(
                        event, ctx, "用法: /plugins disable <插件名>"
                    )
                else:
                    success = await ctx.plugin_manager.disable_plugin(args[1])
                    if success:
                        await self._send_message(
                            event, ctx, f"✅ 插件 {args[1]} 已禁用"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"❌ 插件 {args[1]} 禁用失败"
                        )
            elif action == "reload":
                if len(args) < 2:
                    await self._send_message(
                        event, ctx, "用法: /plugins reload <插件名>"
                    )
                else:
                    success = await ctx.plugin_manager.reload_plugin(args[1])
                    if success:
                        await self._send_message(
                            event, ctx, f"✅ 插件 {args[1]} 已重载"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"❌ 插件 {args[1]} 重载失败"
                        )
            elif action == "install":
                if len(args) < 2:
                    await self._send_message(event, ctx, "用法: /plugins install <URL>")
                else:
                    try:
                        await ctx.plugin_manager.install_plugin_from_url(args[1])
                        await self._send_message(event, ctx, f"✅ 插件安装成功")
                    except Exception as e:
                        await self._send_message(event, ctx, f"❌ 插件安装失败: {e}")
            elif action == "uninstall":
                if len(args) < 2:
                    await self._send_message(
                        event, ctx, "用法: /plugins uninstall <插件名>"
                    )
                else:
                    try:
                        await ctx.plugin_manager.delete_plugin(args[1])
                        await self._send_message(
                            event, ctx, f"✅ 插件 {args[1]} 已卸载"
                        )
                    except Exception as e:
                        await self._send_message(event, ctx, f"❌ 插件卸载失败: {e}")
            elif action == "help":
                if len(args) < 2:
                    await self._send_message(event, ctx, "用法: /plugins help <插件名>")
                else:
                    await self._handle_plugin_help_command(event, ctx, args[1])
            else:
                await self._send_message(
                    event,
                    ctx,
                    f"❌ 未知的子命令: {action}\n可用子命令: list, enable, disable, reload, install, uninstall, help",
                )

    async def _handle_plugin_help_command(
        self, event: dict, ctx: PipelineContext, plugin_name: str
    ) -> None:
        """处理插件帮助命令"""
        plugin = ctx.plugin_manager.plugins.get(plugin_name)
        if plugin is None:
            await self._send_message(event, ctx, "❌ 未找到此插件。")
            return

        help_msg = f"🧩 插件 {plugin_name} 帮助信息：\n\n"
        help_msg += f"✨ 作者: {getattr(plugin, 'author', '未知')}\n"
        help_msg += f"✨ 版本: {getattr(plugin, 'version', '未知')}\n"
        help_msg += f"✨ 描述: {getattr(plugin, 'desc', '无描述')}\n"

        # 获取插件的命令
        command_handlers = []
        command_names = []
        for cmd_name, cmd_func in plugin.commands.items():
            cmd_info = getattr(cmd_func, "_nekobot_command", {})
            command_handlers.append(cmd_func)
            command_names.append(cmd_name)

        if len(command_handlers) > 0:
            help_msg += "\n🔧 指令列表：\n"
            for i in range(len(command_handlers)):
                line = f"  {command_names[i]}"
                cmd_info = getattr(command_handlers[i], "_nekobot_command", {})
                if cmd_info.get("description"):
                    line += f": {cmd_info['description']}"
                help_msg += line + "\n"
            help_msg += "\nTip: 指令的触发需要添加唤醒前缀，默认为 /。"

        help_msg += "\n更多帮助信息请查看插件仓库 README。"
        await self._send_message(event, ctx, help_msg)

    async def _handle_sid_command(self, event: dict, ctx: PipelineContext) -> None:
        """处理 sid 命令 - 获取会话 ID"""
        user_id = event.get("user_id", "unknown")
        group_id = event.get("group_id", "private")
        message_type = event.get("message_type", "unknown")
        platform_id = event.get("platform_id", "unknown")

        sid_text = f"📋 会话 ID 信息:\n"
        sid_text += f"  平台 ID: {platform_id}\n"
        sid_text += f"  用户 ID: {user_id}\n"
        sid_text += f"  消息类型: {message_type}\n"
        if message_type == "group":
            sid_text += f"  群组 ID: {group_id}\n"
        sid_text += f"  统一会话 ID: {group_id}_{user_id}"

        await self._send_message(event, ctx, sid_text)

    async def _handle_op_command(
        self, event: dict, ctx: PipelineContext, args: list
    ) -> None:
        """处理 op 命令 - 授权管理员"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /op <用户ID> 授权管理员；可通过 /sid 获取 ID。"
            )
            return

        admin_id = args[0]
        from packages.backend.core.config import load_config

        config = load_config()
        admins = config.get("admins_id", [])
        if admin_id not in admins:
            admins.append(str(admin_id))
            config["admins_id"] = admins
            config.save_config()
            await self._send_message(event, ctx, f"✅ 用户 {admin_id} 已授权为管理员。")
        else:
            await self._send_message(event, ctx, f"⚠️ 用户 {admin_id} 已经是管理员。")

    async def _handle_deop_command(
        self, event: dict, ctx: PipelineContext, args: list
    ) -> None:
        """处理 deop 命令 - 取消管理员授权"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /deop <用户ID> 取消管理员；可通过 /sid 获取 ID。"
            )
            return

        admin_id = args[0]
        from packages.backend.core.config import load_config

        config = load_config()
        admins = config.get("admins_id", [])
        if admin_id in admins:
            admins.remove(str(admin_id))
            config["admins_id"] = admins
            config.save_config()
            await self._send_message(
                event, ctx, f"✅ 用户 {admin_id} 已取消管理员授权。"
            )
        else:
            await self._send_message(
                event, ctx, f"⚠️ 用户 {admin_id} 不在管理员名单内。"
            )

    async def _handle_wl_command(
        self, event: dict, ctx: PipelineContext, args: list
    ) -> None:
        """处理 wl 命令 - 添加白名单"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /wl <会话ID> 添加白名单；可通过 /sid 获取 ID。"
            )
            return

        sid = args[0]
        from packages.backend.core.config import load_config

        config = load_config()
        whitelist = config.get("id_whitelist", [])
        if sid not in whitelist:
            whitelist.append(str(sid))
            config["id_whitelist"] = whitelist
            config.save_config()
            await self._send_message(event, ctx, f"✅ 会话 {sid} 已添加到白名单。")
        else:
            await self._send_message(event, ctx, f"⚠️ 会话 {sid} 已经在白名单内。")

    async def _handle_dwl_command(
        self, event: dict, ctx: PipelineContext, args: list
    ) -> None:
        """处理 dwl 命令 - 删除白名单"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /dwl <会话ID> 删除白名单；可通过 /sid 获取 ID。"
            )
            return

        sid = args[0]
        from packages.backend.core.config import load_config

        config = load_config()
        whitelist = config.get("id_whitelist", [])
        if sid in whitelist:
            whitelist.remove(str(sid))
            config["id_whitelist"] = whitelist
            config.save_config()
            await self._send_message(event, ctx, f"✅ 会话 {sid} 已从白名单删除。")
        else:
            await self._send_message(event, ctx, f"⚠️ 会话 {sid} 不在白名单内。")

    def _format_message(self, event: dict, simple: bool = True) -> str:
        """格式化消息内容，将 CQ 码转换为简短描述

        Args:
            event: 事件数据
            simple: 是否简化 CQ 码 (True 用于日志显示, False 用于命令解析)

        Returns:
            格式化后的消息
        """
        import re

        # 非简化模式下，优先返回 raw_message
        if not simple:
            raw = event.get("raw_message")
            if isinstance(raw, str) and raw:
                return raw

        msg = event.get("message")

        # 优先解析 message 数组 (结构化数据)
        if isinstance(msg, list):
            parts = []
            for seg in msg:
                if not isinstance(seg, dict):
                    continue
                t = seg.get("type")
                data = seg.get("data", {}) if isinstance(seg.get("data"), dict) else {}

                if t == "text":
                    parts.append(data.get("text", ""))
                elif t == "at":
                    parts.append(f"[@{data.get('qq', 'User')}]")
                elif t == "image":
                    parts.append("[图片]")
                elif t == "face":
                    parts.append("[表情]")
                elif t == "record":
                    parts.append("[语音]")
                elif t == "video":
                    parts.append("[视频]")
                elif t == "share":
                    parts.append(f"[分享: {data.get('title', '链接')}]")
                elif t == "xml":
                    parts.append("[XML卡片]")
                elif t == "json":
                    parts.append("[JSON卡片]")
                elif t == "reply":
                    parts.append(f"[回复: {data.get('id', 'Unknown')}]")
                else:
                    parts.append(f"[{t}]")
            return "".join(parts)

        # 如果没有 message 数组，回退到 raw_message
        raw = event.get("raw_message")
        if isinstance(raw, str):
            if simple:
                # 简化 raw_message 中的 CQ 码
                raw = re.sub(r"\[CQ:image,[^\]]+\]", "[图片]", raw)
                raw = re.sub(r"\[CQ:face,[^\]]+\]", "[表情]", raw)
                raw = re.sub(r"\[CQ:record,[^\]]+\]", "[语音]", raw)
                raw = re.sub(r"\[CQ:video,[^\]]+\]", "[视频]", raw)
                raw = re.sub(r"\[CQ:at,qq=(\d+)[^\]]*\]", r"[@\1]", raw)
                # 通用匹配其他 CQ 码
                raw = re.sub(r"\[CQ:([^,]+),[^\]]+\]", r"[\1]", raw)
            return raw

        return ""

    async def _send_message(self, event: dict, ctx: PipelineContext, text: str) -> None:
        """发送消息

        Args:
            event: 事件数据
            ctx: Pipeline 上下文
            text: 消息内容
        """
        platform_id = event.get("platform_id", "onebot")
        message_type = event.get("message_type", "")
        target_id = None

        if message_type == "private":
            target_id = event.get("user_id")
        elif message_type == "group":
            target_id = event.get("group_id")

        if target_id:
            chat_type = "群聊" if message_type == "group" else "私聊"
            group_id = event.get("group_id", "N/A")
            group_name = event.get("group_name")
            group_disp = (
                f"{group_name}({group_id})"
                if (message_type == "group" and group_id)
                else ""
            )
            bot_id = event.get("self_id")
            bot_disp = f"猫猫({bot_id})" if bot_id else "猫猫"

            def _trim_text(t: str, n: int = 120) -> str:
                s = " ".join(t.splitlines())
                return s if len(s) <= n else s[: n - 3] + "..."

            log_text = _trim_text(text)
            if message_type == "group":
                logger.info(
                    f"猫猫 | 发送 -> {chat_type} [{group_disp}] [{bot_disp}] {log_text}"
                )
            else:
                logger.info(f"猫猫 | 发送 -> {chat_type} [{bot_disp}] {log_text}")
            await ctx.platform_manager.send_message(
                platform_id, message_type, target_id, text
            )
