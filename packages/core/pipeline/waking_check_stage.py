"""唤醒检查阶段

参考 AstrBot 的实现，支持：
1. 艾特机器人
2. 引用机器人消息
3. 唤醒前缀（如 /、. 等）
4. 私聊消息自动唤醒（可选）
"""

from typing import AsyncGenerator, Optional
from loguru import logger

from .stage import Stage, register_stage
from .context import PipelineContext


@register_stage
class WakingCheckStage(Stage):
    """唤醒检查阶段
    
    此阶段检查是否需要唤醒机器人。如果消息满足以下任一条件，则允许通过：
    1. 消息中包含艾特机器人
    2. 消息引用了机器人的消息
    3. 消息以唤醒前缀开头
    4. 私聊消息（根据配置）
    """

    async def initialize(self, ctx: PipelineContext) -> None:
        """初始化阶段"""
        self.ctx = ctx
        # 加载配置
        self.config = ctx.config
        
        # 唤醒前缀配置
        self.wake_prefixes = self.config.get("wake_prefix", ["/", "."])
        
        # 私聊是否需要唤醒前缀
        self.private_needs_wake_prefix = self.config.get(
            "private_message_needs_wake_prefix", False
        )
        
        # 是否忽略艾特全体成员
        self.ignore_at_all = self.config.get("ignore_at_all", False)
        
        # 启用唤醒检查
        self.waking_enabled = self.config.get("waking", {}).get("enabled", False)
        self.waking_prefixes = self.config.get("waking", {}).get("prefixes", [])

        logger.debug(f"唤醒检查初始化: wake_prefixes={self.wake_prefixes}, "
                    f"private_needs_wake_prefix={self.private_needs_wake_prefix}, "
                    f"ignore_at_all={self.ignore_at_all}")

    async def process(
        self, event: dict, ctx: PipelineContext
    ) -> Optional[AsyncGenerator[None, None]]:
        """检查唤醒前缀

        Args:
            event: 事件数据
            ctx: Pipeline 上下文

        Returns:
            None
        """
        post_type = event.get("post_type")

        if post_type != "message":
            return None

        # 检查是否被艾特、使用唤醒前缀或私聊自动唤醒
        # 注意：这里调用 process_stage._check_if_at_me 的逻辑
        # 但由于这是独立阶段，我们需要重新实现或使用共享方法
        
        # 获取消息内容
        message = event.get("message", "")
        self_id = event.get("self_id")
        message_type = event.get("message_type", "")
        
        if not message or not self_id:
            # 如果没有消息或 self_id，允许通过（可能由其他阶段处理）
            return None

        # 将 self_id 转换为字符串集合，方便比较
        self_id_set = {
            str(self_id),
            int(self_id) if str(self_id).isdigit() else None
        }.difference({None})

        should_wake = False

        if isinstance(message, list):
            first_seg_is_at = False
            at_qq_first = None
            
            # 首先检查是否有艾特或引用
            for i, msg_seg in enumerate(message):
                seg_type = msg_seg.get("type", "")
                seg_data = msg_seg.get("data", {})
                
                # 检查 at 消息段
                if seg_type == "at":
                    at_qq = seg_data.get("qq", "")
                    
                    # 记录第一个 at 消息段的 QQ 号
                    if i == 0:
                        first_seg_is_at = True
                        at_qq_first = at_qq
                    
                    # 检查是否艾特全体成员
                    if str(at_qq) == "all":
                        if self.ignore_at_all:
                            continue
                        should_wake = True
                        break
                    
                    # 检查是否艾特机器人
                    at_qq_formats = {
                        str(at_qq),
                        int(at_qq) if str(at_qq).isdigit() else None
                    }.difference({None})
                    
                    if self_id_set & at_qq_formats:
                        should_wake = True
                        break
                
                # 检查 reply 消息段（引用消息）
                elif seg_type == "reply":
                    reply_sender_id = seg_data.get("sender_id", "")
                    if reply_sender_id:
                        reply_sender_formats = {
                            str(reply_sender_id),
                            int(reply_sender_id) if str(reply_sender_id).isdigit() else None
                        }.difference({None})
                        
                        if self_id_set & reply_sender_formats:
                            should_wake = True
                            break

            # 检查唤醒前缀
            if not should_wake:
                for msg_seg in message:
                    if msg_seg.get("type") == "text":
                        text = msg_seg.get("data", {}).get("text", "")
                        text_stripped = text.strip()
                        
                        # 检查是否以唤醒前缀开头
                        for prefix in self.wake_prefixes:
                            if text_stripped.startswith(prefix):
                                # 如果是群聊且第一个消息段是艾特，需要检查是否艾特机器人
                                if message_type == "group" and first_seg_is_at:
                                    if at_qq_first is not None and str(at_qq_first) != "all":
                                        # 第一个艾特不是机器人也不是全体成员，不唤醒
                                        break
                                should_wake = True
                                break
                        
                        if should_wake:
                            break

            # 检查私聊消息
            if not should_wake and message_type == "private" and not self.private_needs_wake_prefix:
                should_wake = True

        elif isinstance(message, str):
            # 纯字符串消息（兼容性处理）
            text_stripped = message.strip()
            
            # 检查是否以唤醒前缀开头
            for prefix in self.wake_prefixes:
                if text_stripped.startswith(prefix):
                    should_wake = True
                    break
            
            # 检查私聊消息
            if not should_wake and message_type == "private" and not self.private_needs_wake_prefix:
                should_wake = True

        # 如果需要唤醒，允许通过
        if should_wake:
            return None

        # 如果启用了旧的唤醒检查配置，使用旧逻辑
        if self.waking_enabled and self.waking_prefixes:
            text_content = self._extract_text_content(message)
            if not any(text_content.startswith(prefix) for prefix in self.waking_prefixes):
                event["_stopped"] = True
                return None
            return None

        # 否则停止事件处理
        event["_stopped"] = True
        return None

    def _extract_text_content(self, message) -> str:
        """提取消息中的文本内容"""
        if isinstance(message, list):
            text = ""
            for seg in message:
                if seg.get("type") == "text":
                    text += seg.get("data", {}).get("text", "")
            return text
        elif isinstance(message, str):
            return message
        return ""
