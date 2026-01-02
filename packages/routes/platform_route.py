"""平台路由

提供平台统计信息和统一 Webhook 回调功能
"""

from typing import Dict, Any
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.server import platform_manager


class PlatformRoute(Route):
    """平台路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.platform_manager = platform_manager
        self.routes = [
            ("/api/platforms/list", "GET", self.get_platforms_list),
            ("/api/platforms/stats", "GET", self.get_platform_stats),
            ("/api/platforms/add", "POST", self.add_platform),
            ("/api/platforms/update", "POST", self.update_platform),
            ("/api/platforms/delete", "POST", self.delete_platform),
        ]
        
        # 为每个路由处理器添加唯一的endpoint名称，避免冲突
        self._method_name = type(self).__name__
        
        for path, method, handler in self.routes:
            # 给handler添加唯一的endpoint名称（通过__func__访问底层函数）
            handler.__func__.endpoint_name = f"{self._method_name}_{path.replace('/', '_')}"

    async def get_platforms_list(self) -> Dict[str, Any]:
        """获取所有平台适配器列表
        
        Returns:
            包含平台列表的响应
        """
        try:
            platforms = self.platform_manager.get_all_platforms()
            platforms_list = []
            for platform in platforms:
                platforms_list.append({
                    "type": platform.adapter_type,
                    "id": platform.id,
                    "name": platform.name,
                    "enabled": platform.enabled,
                    "connected": platform.status.value if platform.status else "disconnected"
                })
            return Response().ok(data={"platforms": platforms_list}).to_dict()
        except Exception as e:
            logger.error(f"获取平台列表失败: {e}")
            return Response().error(f"获取平台列表失败: {str(e)}").to_dict()
    
    async def get_platform_stats(self) -> Dict[str, Any]:
        """获取所有平台的统计信息
        
        Returns:
            包含平台统计信息的响应
        """
        try:
            stats = self.platform_manager.get_all_stats()
            return Response().ok(data=stats).to_dict()
        except Exception as e:
            logger.error(f"获取平台统计信息失败: {e}")
            return Response().error(f"获取统计信息失败: {str(e)}").to_dict()
    
    async def add_platform(self) -> Dict[str, Any]:
        """添加平台适配器
        
        Returns:
            添加结果的响应
        """
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            # 获取必需参数
            platform_type = data.get("type")
            adapter_id = data.get("id")
            name = data.get("name")
            
            if not platform_type or not adapter_id:
                return Response().error("缺少平台类型和ID").to_dict()
            
            # 检查平台是否已存在
            existing_platform = self.platform_manager.get_platform_adapter(platform_type)
            if existing_platform:
                return Response().error(f"平台 {platform_type} ({adapter_id}) 已存在").to_dict()
            
            # 添加到平台管理器
            self.platform_manager.add_platform(
                platform_type=platform_type,
                adapter_id=adapter_id,
                name=name
            )
            
            return Response().ok(message=f"平台适配器 {platform_type} ({adapter_id}) 已添加").to_dict()
        except Exception as e:
            logger.error(f"添加平台适配器失败: {e}")
            return Response().error(f"添加平台适配器失败: {str(e)}").to_dict()
    
    async def update_platform(self) -> Dict[str, Any]:
        """更新平台适配器配置
        
        Returns:
            更新结果的响应
        """
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            # 获取参数
            platform_type = data.get("type")
            adapter_id = data.get("id")
            updates = data.get("updates", {})
            
            if not platform_type or not adapter_id:
                return Response().error("缺少平台类型和ID").to_dict()
            
            # 检查平台是否存在
            existing_platform = self.platform_manager.get_platform_adapter(platform_type)
            if not existing_platform:
                return Response().error(f"平台 {platform_type} ({adapter_id}) 不存在").to_dict()
            
            # 更新配置
            # 合并更新到现有配置
            current_config = existing_platform.default_config_tmpl.copy()
            
            # 应用更新
            if "enable" in updates:
                current_config["enable"] = updates["enable"]
            if "id" in updates:
                current_config["id"] = updates["id"]
            if "name" in updates:
                current_config["name"] = updates["name"]
            
            # 更新平台
            self.platform_manager.update_platform(
                platform_type=platform_type,
                adapter_id=adapter_id,
                default_config_tmpl=current_config
            )
            
            return Response().ok(message=f"平台适配器 {platform_type} ({adapter_id}) 已更新").to_dict()
        except Exception as e:
            logger.error(f"更新平台适配器失败: {e}")
            return Response().error(f"更新平台适配器失败: {str(e)}").to_dict()
    
    async def delete_platform(self) -> Dict[str, Any]:
        """删除平台适配器
        
        Returns:
            删除结果的响应
        """
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("请求数据无效").to_dict()
            
            # 获取参数
            platform_type = data.get("type")
            adapter_id = data.get("id")
            
            if not platform_type or not adapter_id:
                return Response().error("缺少平台类型和ID").to_dict()
            
            # 检查平台是否存在
            existing_platform = self.platform_manager.get_platform_adapter(platform_type)
            if not existing_platform:
                return Response().error(f"平台 {platform_type} ({adapter_id}) 不存在").to_dict()
            
            # 删除平台
            self.platform_manager.remove_platform(platform_type)
            
            return Response().ok(message=f"平台适配器 {platform_type} ({adapter_id}) 已删除").to_dict()
        except Exception as e:
            logger.error(f"删除平台适配器失败: {e}")
            return Response().error(f"删除平台适配器失败: {str(e)}").to_dict()
