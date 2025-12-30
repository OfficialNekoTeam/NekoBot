"""PDF文档解析器

使用PyPDF库解析PDF文档内容
"""

from typing import Optional
from pathlib import Path
from loguru import logger

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    logger.warning("未安装 pypdf，无法解析PDF文档")


class PDFParser:
    """PDF文档解析器"""

    def __init__(self):
        pass

    def supports(self, file_path: Path) -> bool:
        """检查是否支持PDF文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否支持
        """
        return PYPDF_AVAILABLE and file_path.suffix.lower() == ".pdf"

    async def parse(self, file_path: Path) -> Optional[str]:
        """解析PDF文档内容
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            解析后的文本内容，如果失败则返回 None
        """
        if not PYPDF_AVAILABLE:
            logger.error("pypdf 库未安装，无法解析PDF文档")
            return None
        
        try:
            # 读取PDF文件
            import pypdf
            
            pdf_reader = pypdf.PdfReader(str(file_path))
            
            # 提取所有页面的文本
            text_content = ""
            
            for page_num, page in enumerate(pdf_reader.pages, start=1):
                try:
                    text = page.extract_text()
                    text_content += f"\n\n--- 页面 {page_num} ---\n{text}"
                except Exception as e:
                    logger.warning(f"解析PDF第 {page_num} 页时出错: {e}")
                    continue
            
            logger.info(f"成功解析PDF文档 {file_path.name}，共 {len(pdf_reader.pages)} 页，{len(text_content)} 字符")
            return text_content
            
        except Exception as e:
            logger.error(f"解析PDF文档 {file_path} 失败: {e}")
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
            chunk_size: 分块大小（字符数）
            chunk_overlap: 重叠大小（字符数）
            
        Returns:
            分块后的文本列表
        """
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            chunks.append(chunk)
            start = end - chunk_overlap
        
        return chunks