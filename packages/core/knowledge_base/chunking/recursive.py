"""递归分块策略

按段落和标题智能分块
"""

from .base import BaseChunker
from typing import List


class RecursiveChunker(BaseChunker):
    """递归分块器

    按段落和标题智能分块文档
    """

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """初始化递归分块器

        Args:
            chunk_size: 最大分块大小（字符数）
            chunk_overlap: 分块重叠大小（字符数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def get_chunks(
        self,
        content: str,
    ) -> List[str]:
        """将内容按段落递归分块

        Args:
            content: 文档内容

        Returns:
            分块后的文本列表
        """
        chunks = []

        # 先按双换行和段落分割
        paragraphs = content.split("\n\n")

        for paragraph in paragraphs:
            if not paragraph.strip():
                continue

            # 如果段落太长，按句号或短语分割
            if len(paragraph) > self.chunk_size * 2:
                sentences = [s.strip() for s in paragraph.split("。") if s.strip()]

                if not sentences:
                    continue

                current_chunk = ""

                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 > self.chunk_size:
                        chunks.append(current_chunk.strip())
                        current_chunk = sentence
                    else:
                        current_chunk += sentence

                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                # 段落较短，直接作为一个分块
                chunks.append(paragraph.strip())

        # 添加重叠字符到每个分块
        if self.chunk_overlap > 0 and len(chunks) > 1:
            overlapped_chunks = []

            for i, chunk in enumerate(chunks):
                if i == 0:
                    # 第一个分块，添加原文内容作为前缀
                    if i > 0:
                        prefix = chunks[i - 1][-self.chunk_overlap:]
                    else:
                        prefix = ""
                    overlapped_chunks.append(prefix + chunk)
                else:
                    # 从前一个分块末尾添加重叠
                    prefix = overlapped_chunks[i - 1][-self.chunk_overlap:]
                    overlapped_chunks.append(prefix + chunk)

            return overlapped_chunks

        return chunks

    def get_config(self) -> dict:
        """获取分块配置

        Returns:
            分块配置字典
        """
        return {
            "type": "recursive",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }
