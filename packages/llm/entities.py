"""LLM 实体类

参考 AstrBot 的实现
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TokenUsage:
    """Token 使用情况"""

    input_other: int = 0
    """输入 token 数量（不包括缓存的）"""

    input_cached: int = 0
    """缓存的输入 token 数量"""

    output: int = 0
    """输出 token 数量"""

    @property
    def total(self) -> int:
        """总 token 数量"""
        return self.input_other + self.input_cached + self.output

    @property
    def input(self) -> int:
        """输入 token 数量（包括缓存）"""
        return self.input_other + self.input_cached

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_other=self.input_other + other.input_other,
            input_cached=self.input_cached + other.input_cached,
            output=self.output + other.output,
        )


@dataclass
class LLMResponse:
    """LLM 响应"""

    completion_text: str = ""
    """返回的结果文本"""

    role: str = "assistant"
    """角色，assistant, tool, err"""

    tools_call_args: list[dict[str, Any]] = field(default_factory=list)
    """工具调用参数"""

    tools_call_name: list[str] = field(default_factory=list)
    """工具调用名称"""

    tools_call_ids: list[str] = field(default_factory=list)
    """工具调用 ID"""

    raw_completion: Any = None
    """原始响应"""

    is_chunk: bool = False
    """是否为流式响应的分块"""

    usage: Optional[TokenUsage] = None
    """token 使用情况"""

    @property
    def content(self) -> str:
        """兼容性属性，返回 completion_text"""
        return self.completion_text
