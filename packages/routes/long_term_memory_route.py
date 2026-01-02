"""长期记忆管理 API

提供长期记忆的创建、查询、更新、删除和搜索功能
参考 AstrBot 的长期记忆功能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.database import db_manager


class LongTermMemoryRoute(Route):
    """长期记忆管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.routes = [
            ("/api/memories", "GET", self.list_memories),
            ("/api/memories", "POST", self.create_memory),
            ("/api/memories/<memory_id>", "GET", self.get_memory),
            ("/api/memories/<memory_id>", "PUT", self.update_memory),
            ("/api/memories/<memory_id>", "DELETE", self.delete_memory),
            ("/api/memories/search", "POST", self.search_memories),
            ("/api/memories/user/<user_id>", "GET", self.get_user_memories),
            ("/api/memories/user/<user_id>/summary", "GET", self.get_user_memory_summary),
            ("/api/memories/<memory_id>/tags", "PUT", self.update_memory_tags),
            ("/api/memories/tags", "GET", self.list_all_tags),
            ("/api/memories/tags/<tag_name>", "GET", self.get_memories_by_tag),
        ]
        
        # 初始化数据库表
        self._init_database()

    def _init_database(self) -> None:
        """初始化长期记忆数据库表"""
        try:
            # 检查表是否已存在
            conn = db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='long_term_memories'
            """)
            table_exists = cursor.fetchone() is not None
            
            conn.close()
            
            if not table_exists:
                self._create_tables()
                logger.info("长期记忆数据库表初始化完成")
        except Exception as e:
            logger.error(f"初始化长期记忆数据库失败: {e}")

    def _create_tables(self) -> None:
        """创建长期记忆相关表"""
        conn = db_manager._get_connection()
        cursor = conn.cursor()

        # 长期记忆表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_type TEXT DEFAULT 'general',
                tags TEXT,
                importance INTEGER DEFAULT 0,
                access_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_accessed_at TEXT
            )
        """)

        # 记忆标签表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag_name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#1976D2',
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 记忆与标签关联表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_tag_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                FOREIGN KEY (memory_id) REFERENCES long_term_memories(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES memory_tags(id) ON DELETE CASCADE,
                UNIQUE(memory_id, tag_id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON long_term_memories(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_platform ON long_term_memories(platform_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON long_term_memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON long_term_memories(importance DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_updated ON long_term_memories(updated_at DESC)")

        conn.commit()
        conn.close()

    async def list_memories(self) -> Dict[str, Any]:
        """列出所有长期记忆"""
        try:
            import quart
            user_id = quart.request.args.get("user_id")
            platform_id = quart.request.args.get("platform_id")
            memory_type = quart.request.args.get("type")
            limit = int(quart.request.args.get("limit", 50))
            offset = int(quart.request.args.get("offset", 0))
            sort_by = quart.request.args.get("sort_by", "updated_at")
            sort_order = quart.request.args.get("sort_order", "DESC")

            memories = self._query_memories(
                user_id=user_id,
                platform_id=platform_id,
                memory_type=memory_type,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order
            )

            return Response().ok(data=memories).to_dict()
        except Exception as e:
            logger.error(f"列出长期记忆失败: {e}")
            return Response().error(f"列出长期记忆失败: {str(e)}").to_dict()

    async def create_memory(self) -> Dict[str, Any]:
        """创建长期记忆"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["user_id", "platform_id", "content"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            user_id = data.get("user_id")
            platform_id = data.get("platform_id")
            content = data.get("content", "")
            memory_type = data.get("memory_type", "general")
            tags = data.get("tags", [])
            importance = data.get("importance", 0)

            # 验证重要性范围
            if not 0 <= importance <= 100:
                return Response().error("重要性必须在 0-100 之间").to_dict()

            # 创建记忆
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            now = datetime.utcnow().isoformat()
            cursor.execute(
                """INSERT INTO long_term_memories 
                   (user_id, platform_id, content, memory_type, importance, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, platform_id, content, memory_type, importance, now, now)
            )
            memory_id = cursor.lastrowid

            # 添加标签
            if tags:
                self._add_tags_to_memory(cursor, memory_id, tags)

            conn.commit()
            conn.close()

            # 记录操作日志
            self._add_operation_log(
                operation="create_memory",
                details={"memory_id": memory_id, "user_id": user_id},
            )

            logger.info(f"长期记忆 {memory_id} 创建成功")
            return Response().ok(data={"id": memory_id}, message="长期记忆创建成功").to_dict()
        except Exception as e:
            logger.error(f"创建长期记忆失败: {e}")
            return Response().error(f"创建长期记忆失败: {str(e)}").to_dict()

    async def get_memory(self, memory_id: int) -> Dict[str, Any]:
        """获取长期记忆详情"""
        try:
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """SELECT id, user_id, platform_id, content, memory_type, 
                          importance, access_count, created_at, updated_at, last_accessed_at 
                   FROM long_term_memories WHERE id = ?""",
                (memory_id,)
            )
            row = cursor.fetchone()

            if not row:
                conn.close()
                return Response().error("长期记忆不存在").to_dict()

            # 更新访问次数和最后访问时间
            cursor.execute(
                "UPDATE long_term_memories SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
                (datetime.utcnow().isoformat(), memory_id)
            )
            conn.commit()

            # 获取标签
            tags = self._get_memory_tags(cursor, memory_id)

            conn.close()

            return Response().ok(data={
                "id": row[0],
                "user_id": row[1],
                "platform_id": row[2],
                "content": row[3],
                "memory_type": row[4],
                "importance": row[5],
                "access_count": row[6],
                "created_at": row[7],
                "updated_at": row[8],
                "last_accessed_at": row[9],
                "tags": tags,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取长期记忆详情失败: {e}")
            return Response().error(f"获取长期记忆详情失败: {str(e)}").to_dict()

    async def update_memory(self, memory_id: int) -> Dict[str, Any]:
        """更新长期记忆"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            conn = db_manager._get_connection()
            cursor = conn.cursor()

            # 检查记忆是否存在
            cursor.execute("SELECT id FROM long_term_memories WHERE id = ?", (memory_id,))
            if not cursor.fetchone():
                conn.close()
                return Response().error("长期记忆不存在").to_dict()

            # 构建更新语句
            updates = []
            params = []
            allowed_fields = ["content", "memory_type", "importance"]

            for field in allowed_fields:
                if field in data:
                    updates.append(f"{field} = ?")
                    params.append(data[field])

            if not updates:
                conn.close()
                return Response().error("没有可更新的字段").to_dict()

            # 验证重要性范围
            if "importance" in data and not 0 <= data["importance"] <= 100:
                conn.close()
                return Response().error("重要性必须在 0-100 之间").to_dict()

            updates.append("updated_at = ?")
            params.append(datetime.utcnow().isoformat())
            params.append(memory_id)

            cursor.execute(
                f"UPDATE long_term_memories SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
            conn.close()

            # 记录操作日志
            self._add_operation_log(
                operation="update_memory",
                details={"memory_id": memory_id, "changes": data},
            )

            logger.info(f"长期记忆 {memory_id} 更新成功")
            return Response().ok(message="长期记忆更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新长期记忆失败: {e}")
            return Response().error(f"更新长期记忆失败: {str(e)}").to_dict()

    async def delete_memory(self, memory_id: int) -> Dict[str, Any]:
        """删除长期记忆"""
        try:
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            # 检查记忆是否存在
            cursor.execute("SELECT id FROM long_term_memories WHERE id = ?", (memory_id,))
            if not cursor.fetchone():
                conn.close()
                return Response().error("长期记忆不存在").to_dict()

            # 删除记忆（级联删除标签关联）
            cursor.execute("DELETE FROM long_term_memories WHERE id = ?", (memory_id,))
            conn.commit()
            conn.close()

            # 记录操作日志
            self._add_operation_log(
                operation="delete_memory",
                details={"memory_id": memory_id},
            )

            logger.info(f"长期记忆 {memory_id} 删除成功")
            return Response().ok(message="长期记忆删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除长期记忆失败: {e}")
            return Response().error(f"删除长期记忆失败: {str(e)}").to_dict()

    async def search_memories(self) -> Dict[str, Any]:
        """搜索长期记忆"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["query"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            query = data.get("query", "")
            user_id = data.get("user_id")
            platform_id = data.get("platform_id")
            memory_type = data.get("memory_type")
            limit = data.get("limit", 20)

            # 构建搜索查询
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            sql = "SELECT id, user_id, platform_id, content, memory_type, importance, created_at, updated_at FROM long_term_memories WHERE content LIKE ?"
            params = [f"%{query}%"]

            if user_id:
                sql += " AND user_id = ?"
                params.append(user_id)
            if platform_id:
                sql += " AND platform_id = ?"
                params.append(platform_id)
            if memory_type:
                sql += " AND memory_type = ?"
                params.append(memory_type)

            sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            conn.close()

            memories = []
            for row in rows:
                memories.append({
                    "id": row[0],
                    "user_id": row[1],
                    "platform_id": row[2],
                    "content": row[3],
                    "memory_type": row[4],
                    "importance": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                })

            return Response().ok(data={
                "query": query,
                "results": memories,
                "count": len(memories),
            }).to_dict()
        except Exception as e:
            logger.error(f"搜索长期记忆失败: {e}")
            return Response().error(f"搜索长期记忆失败: {str(e)}").to_dict()

    async def get_user_memories(self, user_id: str) -> Dict[str, Any]:
        """获取用户的所有长期记忆"""
        try:
            import quart
            platform_id = quart.request.args.get("platform_id")
            memory_type = quart.request.args.get("type")
            limit = int(quart.request.args.get("limit", 50))
            offset = int(quart.request.args.get("offset", 0))

            memories = self._query_memories(
                user_id=user_id,
                platform_id=platform_id,
                memory_type=memory_type,
                limit=limit,
                offset=offset
            )

            return Response().ok(data=memories).to_dict()
        except Exception as e:
            logger.error(f"获取用户长期记忆失败: {e}")
            return Response().error(f"获取用户长期记忆失败: {str(e)}").to_dict()

    async def get_user_memory_summary(self, user_id: str) -> Dict[str, Any]:
        """获取用户记忆摘要"""
        try:
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            # 统计各种类型的记忆数量
            cursor.execute(
                """SELECT memory_type, COUNT(*) as count, AVG(importance) as avg_importance 
                   FROM long_term_memories 
                   WHERE user_id = ? 
                   GROUP BY memory_type""",
                (user_id,)
            )
            type_stats = cursor.fetchall()

            # 获取最近创建的记忆
            cursor.execute(
                """SELECT id, content, memory_type, importance, created_at 
                   FROM long_term_memories 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT 10""",
                (user_id,)
            )
            recent_memories = cursor.fetchall()

            # 获取最重要的记忆
            cursor.execute(
                """SELECT id, content, memory_type, importance, created_at 
                   FROM long_term_memories 
                   WHERE user_id = ? 
                   ORDER BY importance DESC 
                   LIMIT 10""",
                (user_id,)
            )
            important_memories = cursor.fetchall()

            conn.close()

            summary = {
                "user_id": user_id,
                "type_stats": [
                    {
                        "type": row[0],
                        "count": row[1],
                        "avg_importance": round(row[2], 2) if row[2] else 0,
                    }
                    for row in type_stats
                ],
                "recent_memories": [
                    {
                        "id": row[0],
                        "content": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                        "memory_type": row[2],
                        "importance": row[3],
                        "created_at": row[4],
                    }
                    for row in recent_memories
                ],
                "important_memories": [
                    {
                        "id": row[0],
                        "content": row[1][:100] + "..." if len(row[1]) > 100 else row[1],
                        "memory_type": row[2],
                        "importance": row[3],
                        "created_at": row[4],
                    }
                    for row in important_memories
                ],
            }

            return Response().ok(data=summary).to_dict()
        except Exception as e:
            logger.error(f"获取用户记忆摘要失败: {e}")
            return Response().error(f"获取用户记忆摘要失败: {str(e)}").to_dict()

    async def update_memory_tags(self, memory_id: int) -> Dict[str, Any]:
        """更新记忆标签"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            tags = data.get("tags", [])

            conn = db_manager._get_connection()
            cursor = conn.cursor()

            # 检查记忆是否存在
            cursor.execute("SELECT id FROM long_term_memories WHERE id = ?", (memory_id,))
            if not cursor.fetchone():
                conn.close()
                return Response().error("长期记忆不存在").to_dict()

            # 删除旧的标签关联
            cursor.execute("DELETE FROM memory_tag_relations WHERE memory_id = ?", (memory_id,))

            # 添加新的标签
            if tags:
                self._add_tags_to_memory(cursor, memory_id, tags)

            conn.commit()
            conn.close()

            logger.info(f"长期记忆 {memory_id} 标签更新成功")
            return Response().ok(message="标签更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新记忆标签失败: {e}")
            return Response().error(f"更新记忆标签失败: {str(e)}").to_dict()

    async def list_all_tags(self) -> Dict[str, Any]:
        """列出所有标签"""
        try:
            conn = db_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """SELECT id, tag_name, color, description, created_at 
                   FROM memory_tags 
                   ORDER BY tag_name"""
            )
            rows = cursor.fetchall()

            # 获取每个标签的使用次数
            tags = []
            for row in rows:
                tag_id = row[0]
                cursor.execute(
                    "SELECT COUNT(*) FROM memory_tag_relations WHERE tag_id = ?",
                    (tag_id,)
                )
                count = cursor.fetchone()[0]

                tags.append({
                    "id": tag_id,
                    "name": row[1],
                    "color": row[2],
                    "description": row[3],
                    "created_at": row[4],
                    "usage_count": count,
                })

            conn.close()

            return Response().ok(data=tags).to_dict()
        except Exception as e:
            logger.error(f"列出标签失败: {e}")
            return Response().error(f"列出标签失败: {str(e)}").to_dict()

    async def get_memories_by_tag(self, tag_name: str) -> Dict[str, Any]:
        """按标签获取记忆"""
        try:
            import quart
            limit = int(quart.request.args.get("limit", 50))
            offset = int(quart.request.args.get("offset", 0))

            conn = db_manager._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """SELECT m.id, m.user_id, m.platform_id, m.content, m.memory_type, 
                          m.importance, m.created_at, m.updated_at
                   FROM long_term_memories m
                   INNER JOIN memory_tag_relations r ON m.id = r.memory_id
                   INNER JOIN memory_tags t ON r.tag_id = t.id
                   WHERE t.tag_name = ?
                   ORDER BY m.updated_at DESC
                   LIMIT ? OFFSET ?""",
                (tag_name, limit, offset)
            )
            rows = cursor.fetchall()
            conn.close()

            memories = []
            for row in rows:
                memories.append({
                    "id": row[0],
                    "user_id": row[1],
                    "platform_id": row[2],
                    "content": row[3],
                    "memory_type": row[4],
                    "importance": row[5],
                    "created_at": row[6],
                    "updated_at": row[7],
                })

            return Response().ok(data=memories).to_dict()
        except Exception as e:
            logger.error(f"按标签获取记忆失败: {e}")
            return Response().error(f"按标签获取记忆失败: {str(e)}").to_dict()

    def _query_memories(
        self,
        user_id: Optional[str] = None,
        platform_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "DESC"
    ) -> List[Dict[str, Any]]:
        """查询长期记忆"""
        conn = db_manager._get_connection()
        cursor = conn.cursor()

        sql = "SELECT id, user_id, platform_id, content, memory_type, importance, access_count, created_at, updated_at FROM long_term_memories WHERE 1=1"
        params = []

        if user_id:
            sql += " AND user_id = ?"
            params.append(user_id)
        if platform_id:
            sql += " AND platform_id = ?"
            params.append(platform_id)
        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)

        # 验证排序字段
        valid_sort_fields = ["updated_at", "created_at", "importance", "access_count"]
        if sort_by not in valid_sort_fields:
            sort_by = "updated_at"

        sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"
        sql += f" ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        memories = []
        for row in rows:
            memories.append({
                "id": row[0],
                "user_id": row[1],
                "platform_id": row[2],
                "content": row[3],
                "memory_type": row[4],
                "importance": row[5],
                "access_count": row[6],
                "created_at": row[7],
                "updated_at": row[8],
            })

        return memories

    def _add_tags_to_memory(self, cursor, memory_id: int, tags: List[str]) -> None:
        """添加标签到记忆"""
        for tag_name in tags:
            # 获取或创建标签
            cursor.execute(
                "SELECT id FROM memory_tags WHERE tag_name = ?",
                (tag_name,)
            )
            tag_row = cursor.fetchone()

            if tag_row:
                tag_id = tag_row[0]
            else:
                cursor.execute(
                    "INSERT INTO memory_tags (tag_name) VALUES (?)",
                    (tag_name,)
                )
                tag_id = cursor.lastrowid

            # 添加关联
            try:
                cursor.execute(
                    "INSERT INTO memory_tag_relations (memory_id, tag_id) VALUES (?, ?)",
                    (memory_id, tag_id)
                )
            except Exception:
                # 关联已存在，跳过
                pass

    def _get_memory_tags(self, cursor, memory_id: int) -> List[str]:
        """获取记忆的标签"""
        cursor.execute(
            """SELECT t.tag_name 
               FROM memory_tags t
               INNER JOIN memory_tag_relations r ON t.id = r.tag_id
               WHERE r.memory_id = ?""",
            (memory_id,)
        )
        return [row[0] for row in cursor.fetchall()]

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