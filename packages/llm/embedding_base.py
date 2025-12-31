"""Embedding（嵌入向量）Provider 基类

参考 AstrBot 的 Embedding Provider 实现
"""

import abc
from typing import Optional, List


class EmbeddingProvider(abc.ABC):
    """嵌入向量服务提供商基类"""

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
    async def get_embedding(self, text: str) -> List[float]:
        """获取文本的向量

        Args:
            text: 输入文本

        Returns:
            向量列表
        """
        raise NotImplementedError

    @abc.abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """批量获取文本的向量

        Args:
            texts: 输入文本列表

        Returns:
            向量列表
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_dim(self) -> int:
        """获取向量的维度

        Returns:
            向量维度
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
        await self.get_embedding("nekobot")

    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 16,
        tasks_limit: int = 3,
        max_retries: int = 3,
    ) -> List[List[float]]:
        """批量获取文本的向量，分批处理以节省内存

        Args:
            texts: 文本列表
            batch_size: 每批处理的文本数量
            tasks_limit: 并发任务数量限制
            max_retries: 失败时的最大重试次数

        Returns:
            向量列表
        """
        import asyncio

        semaphore = asyncio.Semaphore(tasks_limit)
        all_embeddings: List[List[float]] = []
        failed_batches: List[tuple[int, List[str]]] = []

        async def process_batch(batch_idx: int, batch_texts: List[str]):
            async with semaphore:
                for attempt in range(max_retries):
                    try:
                        batch_embeddings = await self.get_embeddings(batch_texts)
                        all_embeddings.extend(batch_embeddings)
                        return
                    except Exception as e:
                        if attempt == max_retries - 1:
                            failed_batches.append((batch_idx, batch_texts))
                            raise Exception(
                                f"批次 {batch_idx} 处理失败，已重试 {max_retries} 次: {e}",
                            )
                        await asyncio.sleep(2 ** attempt)

        tasks = []
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_idx = i // batch_size
            tasks.append(process_batch(batch_idx, batch_texts))

        await asyncio.gather(*tasks)

        if failed_batches:
            errors = [f"批次 {idx} 处理失败" for idx, _ in failed_batches]
            raise Exception(f"有 {len(failed_batches)} 个批次处理失败: {'; '.join(errors)}")

        return all_embeddings
