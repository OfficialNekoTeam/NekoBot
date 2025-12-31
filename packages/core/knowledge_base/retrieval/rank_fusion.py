"""RankFusion 融合检索模块

参考 AstrBot 的 RankFusion 实现，提供多种检索结果融合算法
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger
import math



@dataclass
class RetrievalResult:
    """检索结果"""
    document_id: str
    text: str
    score: float
    metadata: Dict[str, Any]
    source: str
    """检索来源（如 sparse, dense 等）"""



class RankFusion:
    """排序融合工具类

    提供多种检索结果融合算法
    """

    @staticmethod
    def reciprocal_rank_fusion(
        results_list: List[List[RetrievalResult]],
        k: int = 60,
    ) -> List[RetrievalResult]:
        """倒排融合（Reciprocal Rank Fusion, RRF）

        RRF 是一种融合多个排序列表的算法，对每个结果根据排名计算分数。
        公式：score = sum(1 / (k + rank_i)) for all i

        Args:
            results_list: 多个检索结果列表
            k: RRF 常数，默认为 60

        Returns:
            融合后的结果列表
        """
        score_map: Dict[str, float] = {}
        result_map: Dict[str, RetrievalResult] = {}

        for results in results_list:
            for rank, result in enumerate(results):
                doc_id = result.document_id
                if doc_id not in result_map:
                    result_map[doc_id] = result
                    result_map[doc_id].score = 0
                score = 1 / (k + rank + 1)
                score_map[doc_id] = score_map.get(doc_id, 0) + score

        for doc_id, total_score in score_map.items():
            if doc_id in result_map:
                result_map[doc_id].score = total_score

        fused_results = sorted(
            result_map.values(),
            key=lambda x: x.score,
            reverse=True
        )

        return fused_results

    @staticmethod
    def weighted_fusion(
        results_list: List[List[RetrievalResult]],
        weights: Optional[List[float]] = None,
    ) -> List[RetrievalResult]:
        """加权融合

        对每个检索结果应用权重，然后加权平均融合。

        Args:
            results_list: 多个检索结果列表
            weights: 每个检索结果的权重列表

        Returns:
            融合后的结果列表
        """
        if weights is None:
            weights = [1.0] * len(results_list)

        if len(weights) != len(results_list):
            raise ValueError("weights 和 results_list 长度必须相同")

        score_map: Dict[str, List[tuple[float, float]]] = {}
        result_map: Dict[str, RetrievalResult] = {}

        for i, results in enumerate(results_list):
            weight = weights[i]
            for result in results:
                doc_id = result.document_id
                if doc_id not in result_map:
                    result_map[doc_id] = result
                    score_map[doc_id] = []
                score_map[doc_id].append((weight, result.score))

        for doc_id, scores in score_map.items():
            total_weight = sum(w for w, _ in scores)
            if total_weight > 0:
                weighted_score = sum(w * s for w, s in scores) / total_weight
                if doc_id in result_map:
                    result_map[doc_id].score = weighted_score

        fused_results = sorted(
            result_map.values(),
            key=lambda x: x.score,
            reverse=True
        )

        return fused_results

    @staticmethod
    def borda_fusion(
        results_list: List[List[RetrievalResult]],
    ) -> List[RetrievalResult]:
        """Borda 计数融合

        Borda 计数是一种投票方法，每个检索结果根据排名投票。

        Args:
            results_list: 多个检索结果列表

        Returns:
            融合后的结果列表
        """
        score_map: Dict[str, int] = {}
        result_map: Dict[str, RetrievalResult] = {}

        for results in results_list:
            num_results = len(results)
            for rank, result in enumerate(results):
                doc_id = result.document_id
                if doc_id not in result_map:
                    result_map[doc_id] = result
                    score_map[doc_id] = 0
                score_map[doc_id] += num_results - rank - 1

        for doc_id, score in score_map.items():
            if doc_id in result_map:
                result_map[doc_id].score = float(score)

        fused_results = sorted(
            result_map.values(),
            key=lambda x: x.score,
            reverse=True
        )

        return fused_results

    @staticmethod
    def condorcet_fusion(
        results_list: List[List[RetrievalResult]],
        top_k: int = 10,
    ) -> List[RetrievalResult]:
        """孔多塞融合（Condorcet）

        基于成对比较的融合方法，在每对比较中胜出更多的文档获得更高排名。

        Args:
            results_list: 多个检索结果列表
            top_k: 返回前 K 个结果

        Returns:
            融合后的结果列表
        """
        doc_ids = set()
        for results in results_list:
            for result in results:
                doc_ids.add(result.document_id)

        result_map: Dict[str, RetrievalResult] = {}
        wins: Dict[str, int] = {doc_id: 0 for doc_id in doc_ids}

        for results in results_list:
            for i in range(len(results)):
                for j in range(i + 1, len(results)):
                    doc_i = results[i].document_id
                    doc_j = results[j].document_id
                    wins[doc_i] += 1
                    if doc_i not in result_map:
                        result_map[doc_i] = results[i]

        for doc_id in result_map:
            result_map[doc_id].score = float(wins.get(doc_id, 0))

        fused_results = sorted(
            result_map.values(),
            key=lambda x: x.score,
            reverse=True
        )

        return fused_results[:top_k]

    @staticmethod
    def adaptive_fusion(
        results_list: List[List[RetrievalResult]],
        method: str = "rrf",
        **kwargs
    ) -> List[RetrievalResult]:
        """自适应融合

        根据输入自动选择融合方法。

        Args:
            results_list: 多个检索结果列表
            method: 融合方法（rrf, weighted, borda, condorcet）
            **kwargs: 其他参数

        Returns:
            融合后的结果列表
        """
        methods = {
            "rrf": RankFusion.reciprocal_rank_fusion,
            "weighted": RankFusion.weighted_fusion,
            "borda": RankFusion.borda_fusion,
            "condorcet": RankFusion.condorcet_fusion,
        }

        if method not in methods:
            logger.warning(f"未知的融合方法 {method}，使用 rrf")
            method = "rrf"

        fusion_func = methods[method]
        return fusion_func(results_list, **kwargs)

    @staticmethod
    def normalize_scores(
        results: List[RetrievalResult],
        method: str = "minmax"
    ) -> List[RetrievalResult]:
        """归一化分数

        Args:
            results: 检索结果列表
            method: 归一化方法（minmax, zscore, softmax）

        Returns:
            归一化后的结果列表
        """
        if not results:
            return results

        scores = [r.score for r in results]

        if method == "minmax":
            min_score = min(scores)
            max_score = max(scores)
            range_score = max_score - min_score
            if range_score == 0:
                return results

            for result in results:
                result.score = (result.score - min_score) / range_score

        elif method == "zscore":
            import statistics
            mean_score = statistics.mean(scores)
            stdev_score = statistics.stdev(scores) if len(scores) > 1 else 1
            if stdev_score == 0:
                return results

            for result in results:
                result.score = (result.score - mean_score) / stdev_score

        elif method == "softmax":
            import math
            exp_scores = [math.exp(s) for s in scores]
            sum_exp = sum(exp_scores)
            if sum_exp == 0:
                return results

            for i, result in enumerate(results):
                result.score = exp_scores[i] / sum_exp

        else:
            logger.warning(f"未知的归一化方法 {method}，使用 minmax")
            return RankFusion.normalize_scores(results, "minmax")

        return results
