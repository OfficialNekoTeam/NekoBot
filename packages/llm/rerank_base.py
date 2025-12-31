"""Rerank（重排序）Provider 基类

参考 AstrBot 的 Rerank Provider 实现
"""

import abc
from dataclasses import dataclass
from typing import List, Optional



@dataclass
class RerankResult:
    """重排序结果"""
    index: int
    """文档在原始列表中的索引"""
    score: float
    """重排序分数"""
    document: str
    """文档内容"""



class RerankProvider(abc.ABC):
    """重排序服务提供商基类"""

    def __init__(self, provider_config: dict, provider_settings: dict) -> None:
        super().__init__()
        self.provider_config = provider_config
        self.provider_settings = provider_settings

    def get_current_key(self) -> str:
        """获取当前 API Key"""
        keys = self.provider_config.get("api_key", [""])
        if keys:
            return keys[0]
        return ""

    def get_keys(self) -> list[str]:
        """获取所有 API Key"""
        keys = self.provider_config.get("api_key", [""])
        return keys or [""]

    @abc.abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None,
    ) -> List[RerankResult]:
        """获取查询和文档的重排序分数

        Args:
            query: 查询文本
            documents: 文档列表
            top_n: 返回前 N 个结果，None 表示返回全部

        Returns:
            重排序结果列表
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_models(self) -> list[str]:
        """获取支持的模型列表"""
        raise NotImplementedError

    async def test(self) -> None:
        """测试服务提供商是否可用

        Raises:
            Exception: 如果服务提供商不可用
        """
        result = await self.rerank(query="Apple", documents=["apple", "banana"])
        if not result:
            raise Exception("Rerank provider test failed, no results returned")
