"""简化的BM25稀疏检索器

基于BM25算法的文档检索实现
"""

from typing import List, Dict, Any, Optional
from loguru import logger
import re


class BM25Retriever:
    """BM25稀疏检索器
    
    使用BM25算法计算文档相似度
    """

    def __init__(self):
        """初始化BM25检索器"""
        # 中文停止词列表
        self.stopwords = {
            "的", "了", "是", "在", "我", "我们", "你", "他", "她", "它",
            "这", "那", "哪", "吗", "呢", "吧", "啊", "哦", "嗯", "哈",
            "嘿", "呀", "哇", "嗯", "噢", "哎", "唉", "好", "行", "对", "不对",
            "就", "都", "也", "还", "再", "又", "很", "挺", "真", "假",
            "和", "或", "但", "不", "没", "有", "没有", "吧", "啦", "咯",
            "嘛", "咩", "哼", "嚏", "啦", "嗷", "哦呵", "哎哟",
            "唔", "噢啦", "啊啦", "嗯哪", "好吧", "行呀", "对的",
        }

    async def retrieve(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """检索相关文档
        
        Args:
            documents: 文档列表（包含id, text, metadata等）
            query: 查询文本
            top_k: 返回前 K 个结果
            min_score: 最小分数阈值
            
        Returns:
            检索结果列表
        """
        if not documents:
            logger.warning("文档列表为空，返回空结果")
            return []
        
        results = []
        query_lower = query.lower()
        
        for doc in documents:
            text = doc.get("text", "")
            doc_id = doc.get("id", "")
            metadata = doc.get("metadata", {})
            
            # 简单的文本匹配检索（计算相似度）
            score = self._calculate_text_score(text, query_lower)
            
            if score >= min_score:
                results.append({
                    "document_id": doc_id,
                    "text": text,
                    "score": score,
                    "metadata": metadata,
                })
        
        # 按分数排序（降序）
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # 只返回前 top_k 个结果
        results = results[:top_k]
        
        logger.info(f"BM25检索完成，查询: '{query}'，返回 {len(results)} 个结果")
        return results

    def _calculate_text_score(self, text: str, query: str) -> float:
        """计算文本相似度分数
        
        Args:
            text: 文档文本
            query: 查询文本
            
        Returns:
            相似度分数（0-1）
        """
        text_lower = text.lower()
        query_lower = query.lower()
        
        # 完全匹配
        if text_lower == query_lower:
            return 1.0
        
        # 计算查询词和文档文本的重叠
        query_words = set(query_lower.split())
        text_words = set(text_lower.split())
        
        # 计算重叠词数
        overlap = len(query_words & text_words)
        
        if len(query_words) == 0:
            return 0.0
        
        # 简化的相似度计算：重叠率 * 0.7
        return (overlap / len(query_words)) * 0.7

    def add_stopword(self, word: str):
        """添加停止词
        
        Args:
            word: 停止词
        """
        if word:
            self.stopwords.add(word.lower())
            logger.debug(f"已添加停止词: {word}")

    def remove_stopword(self, word: str):
        """移除停止词
        
        Args:
            word: 停止词
        """
        word_lower = word.lower()
        if word_lower in self.stopwords:
            self.stopwords.remove(word_lower)
            logger.debug(f"已移除停止词: {word}")

    def get_stopwords(self) -> set[str]:
        """获取停止词集合
        
        Returns:
            停止词集合
        """
        return self.stopwords.copy()