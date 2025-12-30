"""处理消息阶段

处理消息（Agent/LLM 请求）
"""

import asyncio
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
            try:
                return s if len(s) <= n else s[: n - 3] + "..."
            except UnicodeEncodeError:
                # 如果遇到无法编码的字符，先使用 replace 过滤掉
                safe_chars = []
                for c in s:
                    try:
                        c.encode("gbk")
                        safe_chars.append(c)
                    except UnicodeEncodeError:
                        pass
                s_safe = "".join(safe_chars)
                return s_safe if len(s_safe) <= n else s_safe[: n - 3] + "..."
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

        message_type = event.get("message_type", "")
        message = event.get("message", "")
        
        # 获取 LLM 回复模式配置
        from ..config import load_config
        config = load_config()
        llm_reply_mode = config.get("llm_reply_mode", "active")
        
        # 检查是否被艾特
        is_at_me = self._check_if_at_me(event, ctx)
        
        # 检查是否是命令
        is_command = self._check_if_command(event, ctx)
        
        # 私聊消息处理
        if message_type == "private":
            await ctx.plugin_manager.handle_message(event)
            # passive 模式下私聊也不触发 LLM
            if llm_reply_mode != "passive":
                asyncio.create_task(self._trigger_llm_response(event, ctx))
            return
        
        # 群聊消息根据模式决定是否触发 LLM
        should_trigger_llm = False
        
        if llm_reply_mode == "active":
            # 主动模式：所有消息都触发
            should_trigger_llm = True
        elif llm_reply_mode == "passive":
            # 被动模式：不主动回复，只响应命令
            should_trigger_llm = False
        elif llm_reply_mode == "at":
            # 艾特模式：只有被艾特时触发
            should_trigger_llm = is_at_me
        elif llm_reply_mode == "command":
            # 命令模式：只有使用命令前缀时触发
            should_trigger_llm = is_command
        
        # 处理消息
        await ctx.plugin_manager.handle_message(event)
        
        # 如果是命令，先尝试处理命令
        if is_command:
            command_handled = await self._process_command(event, ctx)
            if not command_handled and should_trigger_llm:
                asyncio.create_task(self._trigger_llm_response(event, ctx))
        elif should_trigger_llm:
            asyncio.create_task(self._trigger_llm_response(event, ctx))

    async def _process_command(self, event: dict, ctx: PipelineContext) -> bool:
        """处理命令"""
        from ..server import format_message

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
                command_aliases = {
                    "plugin": "plugins",
                }
                command = command_aliases.get(command, command)

                if command == "help":
                    await self._handle_help_command(event, ctx)
                    return True
                elif command == "ping":
                    await self._handle_ping_command(event, ctx)
                    return True
                elif command == "sid":
                    await self._handle_sid_command(event, ctx)
                    return True
                elif command == "plugins":
                    await self._handle_plugins_command(event, ctx, args)
                    return True
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

                handled = await ctx.plugin_manager.execute_command(command, args, event)
                if handled:
                    return True
                logger.warning(f"未找到命令处理器: {command}")
        return False

    async def _process_notice(self, event: dict, ctx: PipelineContext) -> None:
        """处理通知事件"""
        notice_type = event.get("notice_type", "unknown")
        logger.info(f"收到通知事件: {notice_type}")

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
        await ctx.plugin_manager.handle_message(event)

    async def _trigger_llm_response(self, event: dict, ctx: PipelineContext) -> None:
        """触发 LLM 回复"""
        try:
            from packages.llm import (
                ContextManager,
                ContextConfig,
                ContextCompressionStrategy,
                LLMResponse,
            )
            from ..config import load_config

            message_text = self._format_message(event, simple=False)
            config = load_config()
            llm_providers = config.get("llm_providers", {})
            
            # 记录 LLM 提供商状态（不暴露敏感信息）
            provider_names = [p.get("name", "未命名") for p in llm_providers.values()]
            enabled_count = sum(1 for p in llm_providers.values() if p.get("enabled", False))
            logger.debug(f"LLM 提供商: 共 {len(llm_providers)} 个，已启用 {enabled_count} 个: {', '.join(provider_names)}")

            provider_config = None
            for provider in llm_providers.values():
                if provider.get("enabled", False):
                    provider_config = provider
                    break

            if not provider_config:
                logger.warning(f"未找到启用的 LLM 提供商")
                return

            provider_type = provider_config.get("type", "unknown")
            from ...llm.register import llm_provider_cls_map

            provider_meta = llm_provider_cls_map.get(provider_type)
            if not provider_meta:
                logger.warning(f"未找到 LLM 提供商类型: {provider_type}")
                return

            provider = provider_meta.cls_type(provider_config, {})

            user_id = event.get("user_id", "unknown")
            group_id = event.get("group_id", "private")
            session_id = f"{group_id}_{user_id}"

            compression_strategy_name = provider_config.get("compression_strategy", "fifo").lower()
            # 确保策略名称有效
            valid_strategies = ["none", "fifo", "lru", "summary", "chat_summary"]
            if compression_strategy_name not in valid_strategies:
                compression_strategy_name = "fifo"

            context_config = ContextConfig(
                max_messages=provider_config.get("max_messages", 20),
                compression_strategy=ContextCompressionStrategy(compression_strategy_name),
            )
            context_manager = ContextManager(context_config)

            response: LLMResponse = await provider.text_chat(
                prompt=message_text,
                session_id=session_id,
                contexts=await context_manager.get_context(session_id),
            )

            response_text = response.completion_text or response.content
            if not response_text:
                logger.warning("LLM 返回空响应")
                return

            await self._send_message(event, ctx, response_text)

            await context_manager.add_message(session_id, "user", message_text)
            await context_manager.add_message(session_id, "assistant", response_text)

        except Exception as e:
            logger.error(f"触发 LLM 回复失败: {e}")

    async def _handle_help_command(self, event: dict, ctx: PipelineContext) -> None:
        """处理 help 命令"""
        platform_id = event.get("platform_id", "onebot")
        platform = ctx.platform_manager.get_platform(platform_id)
        command_prefix = platform.get_config("command_prefix", "/") if platform else "/"
        from ..server import get_full_version

        help_text = f"NekoBot {get_full_version()}\n"
        help_text += "[System]\n"
        help_text += f"  {command_prefix}help: 查看、插件帮助\n"
        help_text += f"  {command_prefix}ping: 检查机器人状态\n"
        help_text += f"  {command_prefix}sid: 获取会话 ID\n"
        help_text += f"  {command_prefix}op: 管理员\n"
        help_text += f"  {command_prefix}wl: 白名单\n"
        help_text += f"  {command_prefix}dashboard_update: 更新管理面板\n"
        help_text += f"  {command_prefix}alter_cmd: 设置指令权限\n"
        help_text += "\n[Plugin]\n"
        help_text += f"  {command_prefix}plugins list: 显示已加载的插件\n"
        help_text += f"  {command_prefix}plugins enable <插件名>: 启用插件\n"
        help_text += f"  {command_prefix}plugins disable <插件名>: 禁用插件\n"
        help_text += f"  {command_prefix}plugins reload <插件名>: 重载插件\n"
        help_text += f"  {command_prefix}plugins install <URL>: 从 URL 安装插件\n"
        help_text += f"  {command_prefix}plugins uninstall <插件名>: 卸载插件\n"
        help_text += f"  {command_prefix}plugins help <插件名>: 查看插件帮助"

        await self._send_message(event, ctx, help_text)

    async def _handle_ping_command(self, event: dict, ctx: PipelineContext) -> None:
        """处理 ping 命令"""
        await self._send_message(event, ctx, "Pong!")

    async def _handle_plugins_command(self, event: dict, ctx: PipelineContext, args: list) -> None:
        """处理 plugins 命令"""
        if not args:
            plugins_info = ctx.plugin_manager.get_all_plugins_info()
            text = "已加载的插件:\n"
            for name, info in plugins_info.items():
                status = "已启用" if info.get("enabled") else "已禁用"
                text += f"  {name} ({info.get('version', '未知版本')}) - {status}\n"
            text += "\n使用 /plugins help <插件名> 查看插件帮助和加载的指令。\n"
            text += "使用 /plugins enable/disable <插件名> 启用或禁用插件。"
            await self._send_message(event, ctx, text)
        else:
            action = args[0]
            if action == "list":
                plugins_info = ctx.plugin_manager.get_all_plugins_info()
                text = "已加载的插件:\n"
                for name, info in plugins_info.items():
                    status = "已启用" if info.get("enabled") else "已禁用"
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
                            event, ctx, f"插件 {args[1]} 已启用"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"插件 {args[1]} 启用失败"
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
                            event, ctx, f"插件 {args[1]} 已禁用"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"插件 {args[1]} 禁用失败"
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
                            event, ctx, f"插件 {args[1]} 已重载"
                        )
                    else:
                        await self._send_message(
                            event, ctx, f"插件 {args[1]} 重载失败"
                        )
            elif action == "install":
                if len(args) < 2:
                    await self._send_message(event, ctx, "用法: /plugins install <URL>")
                else:
                    try:
                        await ctx.plugin_manager.install_plugin_from_url(args[1])
                        await self._send_message(event, ctx, "插件安装成功")
                    except Exception as e:
                        await self._send_message(event, ctx, f"插件安装失败: {e}")
            elif action == "uninstall":
                if len(args) < 2:
                    await self._send_message(
                        event, ctx, "用法: /plugins uninstall <插件名>"
                    )
                else:
                    try:
                        await ctx.plugin_manager.delete_plugin(args[1])
                        await self._send_message(
                            event, ctx, f"插件 {args[1]} 已卸载"
                        )
                    except Exception as e:
                        await self._send_message(event, ctx, f"插件卸载失败: {e}")
            elif action == "help":
                if len(args) < 2:
                    await self._send_message(event, ctx, "用法: /plugins help <插件名>")
                else:
                    await self._handle_plugin_help_command(event, ctx, args[1])
            else:
                await self._send_message(
                    event,
                    ctx,
                    f"未知的子命令: {action}\n可用子命令: list, enable, disable, reload, install, uninstall, help",
                )

    async def _handle_plugin_help_command(self, event: dict, ctx: PipelineContext, plugin_name: str) -> None:
        """处理插件帮助命令"""
        plugin = ctx.plugin_manager.plugins.get(plugin_name)
        if plugin is None:
            await self._send_message(event, ctx, "未找到此插件。")
            return

        help_msg = f"插件 {plugin_name} 帮助信息：\n\n"
        help_msg += f"作者: {getattr(plugin, 'author', '未知')}\n"
        help_msg += f"版本: {getattr(plugin, 'version', '未知')}\n"
        help_msg += f"描述: {getattr(plugin, 'desc', '无描述')}\n"

        command_handlers = []
        command_names = []
        for cmd_name, cmd_func in plugin.commands.items():
            cmd_info = getattr(cmd_func, "_nekobot_command", None)
            command_handlers.append(cmd_func)
            command_names.append(cmd_name)

        if len(command_handlers) > 0:
            help_msg += "\n指令列表：\n"
            for i in range(len(command_handlers)):
                line = f"  {command_names[i]}"
                cmd_info = getattr(command_handlers[i], "_nekobot_command", None)
                if cmd_info and cmd_info.description:
                    line += f": {cmd_info.description}"
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

        sid_text = "会话 ID 信息:\n"
        sid_text += f"  平台 ID: {platform_id}\n"
        sid_text += f"  用户 ID: {user_id}\n"
        sid_text += f"  消息类型: {message_type}\n"
        if message_type == "group":
            sid_text += f"  群组 ID: {group_id}\n"
        sid_text += f"  统一会话 ID: {group_id}_{user_id}"

        await self._send_message(event, ctx, sid_text)

    async def _handle_op_command(self, event: dict, ctx: PipelineContext, args: list) -> None:
        """处理 op 命令 - 授权管理员"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /op <用户ID> 授权管理员；可通过 /sid 获取 ID。"
            )
            return

        admin_id = args[0]
        from ..config import load_config

        config = load_config()
        admins = config.get("admins_id", [])
        if admin_id not in admins:
            admins.append(str(admin_id))
            config["admins_id"] = admins
            config.save_config()
            await self._send_message(event, ctx, f"用户 {admin_id} 已授权为管理员。")
        else:
            await self._send_message(event, ctx, f"用户 {admin_id} 已经是管理员。")

    async def _handle_deop_command(self, event: dict, ctx: PipelineContext, args: list) -> None:
        """处理 deop 命令 - 取消管理员授权"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /deop <用户ID> 取消管理员；可通过 /sid 获取 ID。"
            )
            return

        admin_id = args[0]
        from ..config import load_config

        config = load_config()
        admins = config.get("admins_id", [])
        if admin_id in admins:
            admins.remove(str(admin_id))
            config["admins_id"] = admins
            config.save_config()
            await self._send_message(
                event, ctx, f"用户 {admin_id} 已取消管理员授权。"
            )
        else:
            await self._send_message(
                event, ctx, f"用户 {admin_id} 不在管理员名单内。"
            )

    async def _handle_wl_command(self, event: dict, ctx: PipelineContext, args: list) -> None:
        """处理 wl 命令 - 添加白名单"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /wl <会话ID> 添加白名单；可通过 /sid 获取 ID。"
            )
            return

        sid = args[0]
        from ..config import load_config

        config = load_config()
        whitelist = config.get("id_whitelist", [])
        if sid not in whitelist:
            whitelist.append(str(sid))
            config["id_whitelist"] = whitelist
            config.save_config()
            await self._send_message(event, ctx, f"会话 {sid} 已添加到白名单。")
        else:
            await self._send_message(event, ctx, f"会话 {sid} 已经在白名单内。")

    async def _handle_dwl_command(self, event: dict, ctx: PipelineContext, args: list) -> None:
        """处理 dwl 命令 - 删除白名单"""
        if not args:
            await self._send_message(
                event, ctx, "用法: /dwl <会话ID> 删除白名单；可通过 /sid 获取 ID。"
            )
            return

        sid = args[0]
        from ..config import load_config

        config = load_config()
        whitelist = config.get("id_whitelist", [])
        if sid in whitelist:
            whitelist.remove(str(sid))
            config["id_whitelist"] = whitelist
            config.save_config()
            await self._send_message(event, ctx, f"会话 {sid} 已从白名单删除。")
        else:
            await self._send_message(event, ctx, f"会话 {sid} 不在白名单内。")

    def _check_if_at_me(self, event: dict, ctx: PipelineContext) -> bool:
        """检查消息中是否艾特了机器人"""
        message = event.get("message", "")
        self_id = event.get("self_id")
        
        if not message or not self_id:
            return False
        
        if isinstance(message, list):
            for msg_seg in message:
                if msg_seg.get("type") == "at" and msg_seg.get("data", {}).get("qq") == self_id:
                    return True
        return False
    
    def _check_if_command(self, event: dict, ctx: PipelineContext) -> bool:
        """检查是否是命令消息"""
        message = event.get("message", "")
        
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
                        return True
        elif isinstance(message, str) and message.startswith("/"):
            return True
        
        return False
    
    def _format_message(self, event: dict, simple: bool = True) -> str:
        """格式化消息内容"""
        import re

        if not simple:
            # 始终使用解析后的消息而不是 raw_message，避免 CQ 码传入 LLM
            msg = event.get("message")
            if isinstance(msg, list):
                parts = []
                for seg in msg:
                    if not isinstance(seg, dict):
                        continue
                    t = seg.get("type")
                    data = seg.get("data", {}) if isinstance(seg.get("data"), dict) else {}
                    if t == "text":
                        parts.append(data.get("text", ""))
                return "".join(parts)
            
            # 如果是字符串，过滤 CQ 码
            raw = event.get("raw_message")
            if isinstance(raw, str):
                raw = re.sub(r"\[CQ:[^\]]+\]", "", raw)
                return raw.strip()

        msg = event.get("message")

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

        raw = event.get("raw_message")
        if isinstance(raw, str):
            if simple:
                raw = re.sub(r"\[CQ:image,[^\]]+\]", "[图片]", raw)
                raw = re.sub(r"\[CQ:face,[^\]]+\]", "[表情]", raw)
                raw = re.sub(r"\[CQ:record,[^\]]+\]", "[语音]", raw)
                raw = re.sub(r"\[CQ:video,[^\]]+\]", "[视频]", raw)
                raw = re.sub(r"\[CQ:at,qq=(\d+)[^\]]*\]", r"[@\1]", raw)
                raw = re.sub(r"\[CQ:([^,]+),[^\]]+\]", r"[\1]", raw)
            return raw

        return ""

    async def _send_message(self, event: dict, ctx: PipelineContext, text: str) -> None:
        """发送消息"""
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
