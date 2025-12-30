"""检索管理器

提供文档检索和排序功能
"""

from typing import List, Dict, Any, Optional
from loguru import logger


class RetrievalManager:
    """检索管理器
    
    负责文档检索和结果排序
    """

    def __init__(self):
        """初始化检索管理器"""
        pass

    async def search(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """搜索文档
        
        Args:
            documents: 文档列表（包含id, text, metadata等）
            query: 查询文本
            top_k: 返回前 K 个结果
            
        Returns:
            搜索结果列表
        """
        if not documents:
            return []
        
        # 简化的文本匹配搜索
        # 实际应该使用向量嵌入检索
        results = []
        
        query_lower = query.lower()
        
        for doc in documents:
            text = doc.get("text", "")
            doc_id = doc.get("id", "")
            metadata = doc.get("metadata", {})
            
            # 简单的关键词匹配
            score = self._calculate_score(text, query_lower)
            
            if score > 0:
                results.append({
                    "document_id": doc_id,
                    "text": text,
                    "score": score,
                    "metadata": metadata,
                })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # 只返回前 top_k 个结果
        return results[:top_k]

    def _calculate_score(self, text: str, query: str) -> float:
        """计算相似度分数
        
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
        
        # 包含查询词
        if query_lower in text_lower:
            return 0.8
        
        # 简单的关键词重叠
        query_words = set(query_lower.split())
        text_words = set(text_lower.split())
        
        overlap = len(query_words & text_words) / max(len(query_words), len(text_words))
        
        return overlap * 0.5

    async def rank_fusion(
        self,
        results_list: List[List[Dict[str, Any]]],
        weights: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """排序融合
        
        Args:
            results_list: 多个检索结果列表
            weights: 每个检索器的权重（可选）
            
        Returns:
            融合后的结果列表
        """
        if not results_list:
            return []
        
        if weights is None:
            # 默认等权重
            weights = [1.0 / len(results_list)] * len(results_list)
        
        # 收集所有文档ID和对应的分数
        doc_scores: {}  # doc_id -> [(weight1, score1), (weight2, score2), ...]
        
        for i, results in enumerate(results_list):
            weight = weights[i] if i < len(weights) else 0
            
            for result in results:
                doc_id = result.get("document_id")
                score = result.get("score", 0)
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = []
                
                doc_scores[doc_id].append((weight, score))
        
        # 融合分数（加权平均）
        ranked_results = []
        
        for doc_id in doc_scores:
            scores = doc_scores[doc_id]
            if not scores:
                continue
            
            # 计算加权平均分数
            total_weight = sum(w for w, _ in scores)
            if total_weight == 0:
                final_score = 0
            else:
                weighted_sum = sum(w * s for w, s in scores)
                final_score = weighted_sum / total_weight
            
            # 找到该文档的第一个结果
            first_result = next(
                (r for r in results if r.get("document_id") == doc_id),
                {"document_id": doc_id, "text": "", "score": final_score}
            )
            
            ranked_results.append(first_result)
        
        return ranked_results


# 创建全局检索管理器实例
retrieval_manager = RetrievalManager()