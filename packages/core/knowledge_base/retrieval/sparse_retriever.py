"""BM25稀疏检索器

基于BM25算法的文档检索
"""

from typing import List, Dict, Any, Optional
from loguru import logger
from collections import Counter
import re


class BM25Retriever:
    """BM25稀疏检索器
    
    使用BM25算法计算文档相似度
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75, k2: float = 0.25):
        """初始化BM25检索器
        
        Args:
            k1: 查询词的参数
            b: 文档长度的参数
            k2: 文档长度的参数
        """
        self.k1 = k1
        self.b = b
        self.k2 = k2
        self.stopwords: set[str] = set()
        
        # 加载停止词
        self._load_stopwords()

    def _load_stopwords(self):
        """加载停止词"""
        self.stopwords = {
            "的", "了", "是", "在", "我", "我们", "你", "他", "她", "它",
            "这", "那", "哪", "吗", "呢", "吧", "啊", "哦", "嗯", "哈", "嘿",
            "呀", "哇", "嗯", "噢", "哎", "唉", "好", "行", "对", "不对",
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
        
        # 预处理查询
        query_lower = query.lower()
        query_tokens = self._tokenize(query_lower)
        
        # 计算每个文档的BM25分数
        doc_scores = []
        
        for doc in documents:
            doc_id = doc.get("id", "")
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            
            # 预处理文档文本
            doc_lower = text.lower()
            doc_tokens = self._tokenize(doc_lower)
            
            # 过滤停止词
            doc_tokens = [t for t in doc_tokens if t not in self.stopwords]
            
            if not doc_tokens:
                logger.debug(f"文档 {doc_id} 被过滤为空，跳过")
                continue
            
            # 计算BM25分数
            score = self._calculate_bm25_score(query_tokens, doc_tokens)
            
            if score >= min_score:
                doc_scores.append({
                    "document_id": doc_id,
                    "text": text,
                    "score": score,
                    "metadata": metadata,
                })
        
        # 按分数排序（降序）
        doc_scores.sort(key=lambda x: x["score"], reverse=True)
        
        # 只返回前 top_k 个结果
        results = doc_scores[:top_k]
        
        logger.info(f"BM25检索完成，查询: '{query}'，返回 {len(results)} 个结果")
        return results

    def _calculate_bm25_score(self, query_tokens: list, doc_tokens: list) -> float:
        """计算BM25分数
        
        Args:
            query_tokens: 查询分词列表
            doc_tokens: 文档分词列表
            
        Returns:
            BM25分数
        """
        # 计算查询分词的IDF
        qid = self._calculate_idf(query_tokens)
        
        # 计算文档分词的平均IDF
        avg_idf = self._calculate_avg_idf(doc_tokens)
        
        # 计算文档分词的平均IDF
        avg_idf_doc = self._calculate_avg_idf(doc_tokens)
        
        # BM25公式: IDF部分 + TF部分
        # IDF = log((N - df + 0.5) / (df + 0.5))
        # 这里简化：使用文档长度作为df的近似
        N = len(doc_tokens)
        df = 1.0  # 简化，假设平均每篇文档的频率
        
        idf_part = 0.0
        if qid in doc_tokens:
            # 查询词存在于文档中
            # IDF = log((N - df + 0.5) / (df + 0.5))
            # 简化：减少IDF（文档包含查询词）
            # N = N (包含查询词的文档数）
            # df = 1.0 (默认文档频率）
            # idf_part = 1.0 / N
            pass
        else:
            # 查询词不存在于文档中
            # IDF = log((N - df + 0.5) / (df + 0.5))
            # 简化：使用较大的N值
            # idf_part = 1.0
            pass
        
        # TF部分：词频
        # 对于查询词，TF = 1
        tf_query = 1.0
        
        # 计算文档中查询词的TF
        tf_doc = 0
        if qid in doc_tokens:
            # 统计文档中查询词的出现次数
            count = sum(1 for t in doc_tokens if t == qid)
            # TF = count / 文档长度
            tf_doc = count / max(len(doc_tokens), 1)
        
        # BM25分数 = IDF * TF
        score = idf_part * ((k1 + 1) * tf_query / (k1 * tf_query + 1)) + (
                   k2 * tf_doc / (k2 * tf_doc + 1))
        
        return max(score, 0.0)

    def _calculate_idf(self, tokens: list, token: str) -> float:
        """计算词的逆文档频率（IDF）
        
        Args:
            tokens: 分词列表
            token: 要计算的词
            
        Returns:
            IDF值
        """
        # 计算包含该词的文档数
        N = sum(1 for t in tokens if t == token)
        
        if N == 0:
            return 0.0
        
        # IDF = log((N - df + 0.5) / (df + 0.5))
        # 这里简化：使用文档数量作为df
        df = len(tokens)  # 简化：假设平均每篇文档的频率
        idf = 1.0
        if N > 0:
            idf = (len(tokens) / N + 0.5) / (df + 0.5)
            idf = max(idf, 0.01)  # 最小IDF
        
        return idf

    def _calculate_avg_idf(self, tokens: list) -> float:
        """计算文档分词的平均IDF
        
        Args:
            tokens: 分词列表
            
        Returns:
            平均IDF值
        """
        if not tokens:
            return 0.0
        
        # 计算所有词的IDF总和
        total_idf = sum(self._calculate_idf(tokens, t) for t in set(tokens))
        
        # 平均IDF
        avg_idf = total_idf / max(len(tokens), 1)
        
        return avg_idf

    def _tokenize(self, text: str) -> list[str]:
        """分词
        
        Args:
            text: 文本内容
            
        Returns:
            分词列表
        """
        # 简化的中文分词（按空格和标点符号）
        tokens = re.findall(r"[\w\u4e00-\u9fa5]+", text.lower())
        return tokens

    def add_stopword(self, word: str):
        """添加停止词
        
        Args:
            word: 停止词
        """
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