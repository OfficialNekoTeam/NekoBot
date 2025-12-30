"""URL文档解析器

从URL获取文档内容
"""

import aiohttp
import asyncio
from typing import Optional
from loguru import logger
from pathlib import Path

from ..base import BaseParser
from ..models import Document


class URLParser(BaseParser):
    """URL文档解析器
    
    从URL获取文档内容
    """

    def supports(self, file_path: Path) -> bool:
        """检查是否支持URL
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否是URL文件
        """
        return file_path.suffix.lower() in [".txt", ".md"]

    async def parse(self, file_path: Path) -> Optional[str]:
        """从URL获取文档内容
        
        Args:
            file_path: 文件路径（URL）
            
        Returns:
            文档内容，如果失败则返回 None
        """
        if not file_path.suffix.lower() in [".txt", ".md"]:
            logger.warning(f"文件 {file_path} 不是文本文件")
            return None
        
        try:
            # 使用 aiohttp 获取内容
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession() as session:
                async with session.get(str(file_path), timeout=timeout) as response:
                    if response.status != 200:
                        logger.error(f"无法从 URL {file_path} 获取内容: {response.status}")
                        return None
                    
                    content = await response.text()
                    
                    # 尝试检测编码
                    try:
                        content.encode("utf-8")
                    except UnicodeDecodeError:
                        try:
                            content.encode("gbk")
                            content = content.decode("gbk")
                        except:
                            content = content.decode("utf-8", errors="ignore")
                    
                    logger.info(f"成功从 URL {file_path} 获取文档: {len(content)} 字符")
                    return content
                    
        except asyncio.TimeoutError:
            logger.error(f"获取 URL {file_path} 超时: 30秒")
            return None
        except Exception as e:
            logger.error(f"解析 URL {file_path} 时出错: {e}")
            return None

    async def get_chunks(
        self,
        content: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> list[str]:
        """将内容分块
        
        Args:
            content: 文档内容
            chunk_size: 分块大小
            chunk_overlap: 重叠大小
            
        Returns:
            分块后的文本列表
        """
        # 简化实现，直接按字符数分块
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
        
        return chunks

    def get_title(self, content: str) -> str:
        """从内容提取标题
        
        Args:
            content: 文档内容
            
        Returns:
            文档标题
        """
        lines = content.strip().split("\n")
        
        if not lines:
            return "无标题"
        
        # 取第一行作为标题
        title = lines[0].strip()
        
        # 限制标题长度
        if len(title) > 100:
            title = title[:97] + "..."
        
        return title