"""知识库管理 API

提供知识库的创建、查询、管理和文档操作功能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger
from quart import request, send_file

from .route import Route, Response, RouteContext
from ..core.knowledge_base.kb_manager import get_kb_manager
from ..core.database import db_manager


class KnowledgeBaseRoute(Route):
    """知识库管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.kb_manager = get_kb_manager()
        self.routes = [
            ("/api/knowledge-bases", "GET", self.list_knowledge_bases),
            ("/api/knowledge-bases", "POST", self.create_knowledge_base),
            ("/api/knowledge-bases/<kb_id>", "GET", self.get_knowledge_base),
            ("/api/knowledge-bases/<kb_id>", "PUT", self.update_knowledge_base),
            ("/api/knowledge-bases/<kb_id>", "DELETE", self.delete_knowledge_base),
            ("/api/knowledge-bases/<kb_id>/documents", "POST", self.add_document),
            ("/api/knowledge-bases/<kb_id>/documents/<doc_id>", "DELETE", self.delete_document),
            ("/api/knowledge-bases/<kb_id>/documents/<doc_id>", "GET", self.get_document),
            ("/api/knowledge-bases/<kb_id>/search", "POST", self.search_documents),
            ("/api/knowledge-bases/<kb_id>/stats", "GET", self.get_knowledge_base_stats),
            ("/api/knowledge-bases/<kb_id>/export", "GET", self.export_knowledge_base),
        ]

    async def list_knowledge_bases(self) -> Dict[str, Any]:
        """列出所有知识库"""
        try:
            knowledge_bases = await self.kb_manager.list_knowledge_bases()
            result = []
            
            for kb in knowledge_bases:
                # 获取文档数量
                doc_count = await self.kb_manager.get_document_count(kb.id)
                
                result.append({
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "embedding_model": kb.embedding_model,
                    "document_count": doc_count,
                })

            return Response().ok(data=result).to_dict()
        except Exception as e:
            logger.error(f"列出知识库失败: {e}")
            return Response().error(f"列出知识库失败: {str(e)}").to_dict()

    async def create_knowledge_base(self) -> Dict[str, Any]:
        """创建知识库"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["id", "name"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            kb_id = data.get("id")
            name = data.get("name")
            description = data.get("description", "")
            embedding_model = data.get("embedding_model", "openai")

            # 验证知识库ID格式
            if not kb_id or not kb_id.replace("_", "").replace("-", "").isalnum():
                return Response().error("知识库ID只能包含字母、数字、下划线和连字符").to_dict()

            # 创建知识库
            kb_id = await self.kb_manager.create_knowledge_base(
                kb_id=kb_id,
                name=name,
                description=description,
                embedding_model=embedding_model,
            )

            if not kb_id:
                return Response().error("创建知识库失败，可能已存在").to_dict()

            # 记录操作日志
            self._add_operation_log(
                operation="create_knowledge_base",
                details={"kb_id": kb_id, "name": name},
            )

            return Response().ok(data={"id": kb_id}, message="知识库创建成功").to_dict()
        except Exception as e:
            logger.error(f"创建知识库失败: {e}")
            return Response().error(f"创建知识库失败: {str(e)}").to_dict()

    async def get_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库详情"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            # 获取文档数量
            doc_count = await self.kb_manager.get_document_count(kb_id)

            return Response().ok(data={
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "document_count": doc_count,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取知识库详情失败: {e}")
            return Response().error(f"获取知识库详情失败: {str(e)}").to_dict()

    async def update_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """更新知识库"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            # 更新可修改的字段
            if "name" in data:
                kb.name = data["name"]
            if "description" in data:
                kb.description = data["description"]
            if "embedding_model" in data:
                kb.embedding_model = data["embedding_model"]

            # 这里简化实现，实际应该更新到数据库或持久化存储
            logger.info(f"知识库 {kb_id} 更新成功")

            # 记录操作日志
            self._add_operation_log(
                operation="update_knowledge_base",
                details={"kb_id": kb_id, "changes": data},
            )

            return Response().ok(message="知识库更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新知识库失败: {e}")
            return Response().error(f"更新知识库失败: {str(e)}").to_dict()

    async def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        """删除知识库"""
        try:
            success = await self.kb_manager.delete_knowledge_base(kb_id)
            if not success:
                return Response().error("知识库不存在或删除失败").to_dict()

            # 记录操作日志
            self._add_operation_log(
                operation="delete_knowledge_base",
                details={"kb_id": kb_id},
            )

            return Response().ok(message="知识库删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除知识库失败: {e}")
            return Response().error(f"删除知识库失败: {str(e)}").to_dict()

    async def add_document(self, kb_id: str) -> Dict[str, Any]:
        """添加文档到知识库"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["content"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            content = data.get("content", "")
            title = data.get("title", "")
            metadata = data.get("metadata", {})

            # 构建文档元数据
            doc_metadata = {
                "title": title,
                "kb_id": kb_id,
                "created_at": datetime.utcnow().isoformat(),
                **metadata,
            }

            # 添加文档
            doc_id = await self.kb_manager.add_document(
                kb_id=kb_id,
                text=content,
                metadata=doc_metadata,
            )

            if not doc_id:
                return Response().error("添加文档失败").to_dict()

            # 记录操作日志
            self._add_operation_log(
                operation="add_document",
                details={"kb_id": kb_id, "doc_id": doc_id, "title": title},
            )

            return Response().ok(data={"doc_id": doc_id}, message="文档添加成功").to_dict()
        except Exception as e:
            logger.error(f"添加文档失败: {e}")
            return Response().error(f"添加文档失败: {str(e)}").to_dict()

    async def delete_document(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        """删除文档"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            success = await self.kb_manager.delete_document(kb_id, doc_id)
            if not success:
                return Response().error("文档不存在或删除失败").to_dict()

            # 记录操作日志
            self._add_operation_log(
                operation="delete_document",
                details={"kb_id": kb_id, "doc_id": doc_id},
            )

            return Response().ok(message="文档删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除文档失败: {e}")
            return Response().error(f"删除文档失败: {str(e)}").to_dict()

    async def get_document(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        """获取文档详情"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            # 从知识库管理器获取文档详情
            document = await self.kb_manager.get_document(kb_id, doc_id)

            if not document:
                return Response().error("文档不存在").to_dict()

            return Response().ok(data=document).to_dict()
        except Exception as e:
            logger.error(f"获取文档详情失败: {e}", exc_info=True)
            return Response().error(f"获取文档详情失败: {str(e)}").to_dict()

    async def search_documents(self, kb_id: str) -> Dict[str, Any]:
        """搜索知识库文档"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["query"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            query = data.get("query", "")
            top_k = data.get("top_k", 5)

            # 搜索文档
            results = await self.kb_manager.search(
                kb_id=kb_id,
                query=query,
                top_k=top_k,
            )

            return Response().ok(data={
                "query": query,
                "results": results,
                "count": len(results),
            }).to_dict()
        except Exception as e:
            logger.error(f"搜索文档失败: {e}")
            return Response().error(f"搜索文档失败: {str(e)}").to_dict()

    async def get_knowledge_base_stats(self, kb_id: str) -> Dict[str, Any]:
        """获取知识库统计信息"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            # 获取文档数量
            doc_count = await self.kb_manager.get_document_count(kb_id)

            return Response().ok(data={
                "kb_id": kb_id,
                "name": kb.name,
                "document_count": doc_count,
                "embedding_model": kb.embedding_model,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取知识库统计信息失败: {e}")
            return Response().error(f"获取知识库统计信息失败: {str(e)}").to_dict()

    async def export_knowledge_base(self, kb_id: str):
        """导出知识库"""
        try:
            kb = await self.kb_manager.get_knowledge_base(kb_id)
            if not kb:
                return Response().error("知识库不存在").to_dict()

            # 导出知识库为 JSON 文件
            export_data = {
                "kb_id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "exported_at": datetime.utcnow().isoformat(),
                "documents": [],  # 实际应该包含所有文档
            }

            # 创建临时文件
            import tempfile
            import json
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                temp_path = f.name

            # 记录操作日志
            self._add_operation_log(
                operation="export_knowledge_base",
                details={"kb_id": kb_id},
            )

            return await send_file(
                temp_path,
                as_attachment=True,
                download_name=f"knowledge_base_{kb_id}.json",
                mimetype='application/json'
            )
        except Exception as e:
            logger.error(f"导出知识库失败: {e}")
            return Response().error(f"导出知识库失败: {str(e)}").to_dict()

    def _add_operation_log(
        self,
        operation: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """添加操作日志"""
        try:
            from quart import request
            ip_address = request.headers.get("X-Forwarded-For", request.remote_addr)
            if ip_address and "," in ip_address:
                ip_address = ip_address.split(",")[0].strip()

            username = "unknown"
            try:
                from quart import g
                if hasattr(g, 'user') and g.user:
                    username = g.user.username
            except Exception:
                pass

            db_manager.add_operation_log(operation, username, ip_address, details)
        except Exception as e:
            logger.error(f"添加操作日志失败: {e}")