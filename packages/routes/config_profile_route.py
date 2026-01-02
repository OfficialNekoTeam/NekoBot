"""配置文件管理 API

提供多配置文件的创建、切换、删除和查询功能
参考 AstrBot 的多配置文件功能
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from loguru import logger

from .route import Route, Response, RouteContext
from ..core.config import load_config

# 配置文件目录
CONFIG_DIR = Path(__file__).parent.parent.parent / "data" / "config_profiles"
# 活动配置文件路径
ACTIVE_PROFILE_PATH = Path(__file__).parent.parent.parent / "data" / "active_profile.json"
# 基础配置文件
BASE_CONFIG_FILES = [
    "cmd_config.json",
    "platforms_sources.json",
    "llm_providers.json",
]


class ConfigProfileRoute(Route):
    """配置文件管理路由"""

    def __init__(self, context: RouteContext) -> None:
        super().__init__(context)
        self.config_dir = CONFIG_DIR
        self.active_profile_path = ACTIVE_PROFILE_PATH
        self.routes = [
            ("/api/config/abconfs", "GET", self.list_abconfs),
            ("/api/config/abconf", "GET", self.get_abconf),
            ("/api/config/abconf/new", "POST", self.create_abconf),
            ("/api/config/abconf/update", "POST", self.update_abconf_metadata),
            ("/api/config/abconf/delete", "POST", self.delete_abconf),
            ("/api/config/astrbot/update", "POST", self.update_astrbot_config),
            ("/api/config/switch", "POST", self.switch_profile),
            ("/api/config/active", "GET", self.get_active_profile),
        ]
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_active_profile(self) -> Optional[str]:
        """获取当前活动的配置文件ID"""
        if not self.active_profile_path.exists():
            # 默认返回 "default"
            return "default"
        
        try:
            with open(self.active_profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("active_profile", "default")
        except Exception as e:
            logger.error(f"读取活动配置文件失败: {e}")
            return "default"

    def _set_active_profile(self, profile_id: str) -> bool:
        """设置活动配置文件"""
        try:
            with open(self.active_profile_path, "w", encoding="utf-8") as f:
                json.dump({"active_profile": profile_id, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"设置活动配置文件失败: {e}")
            return False

    def _get_profile_dir(self, profile_id: str) -> Path:
        """获取配置文件目录"""
        return self.config_dir / profile_id

    def _get_base_config_dir(self) -> Path:
        """获取基础配置目录"""
        return Path(__file__).parent.parent.parent / "data"

    def _validate_profile_id(self, profile_id: str) -> tuple[bool, str]:
        """验证配置文件ID"""
        if not profile_id:
            return False, "配置文件ID不能为空"
        if len(profile_id) > 50:
            return False, "配置文件ID长度不能超过50个字符"
        if not profile_id.replace("_", "").replace("-", "").isalnum():
            return False, "配置文件ID只能包含字母、数字、下划线和连字符"
        return True, ""

    async def list_abconfs(self) -> Dict[str, Any]:
        """获取所有配置文件列表 (AstrBot 规范)"""
        try:
            profiles = []
            active_profile = self._get_active_profile()

            # 检查是否有 default 配置
            profile_dirs = sorted([d for d in self.config_dir.iterdir() if d.is_dir()])
            
            for profile_dir in profile_dirs:
                profile_id = profile_dir.name
                metadata_path = profile_dir / "metadata.json"
                
                # 获取元数据
                metadata = {}
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass

                # 检查配置文件完整性
                has_configs = all((profile_dir / config_file).exists() for config_file in BASE_CONFIG_FILES)

                profiles.append({
                    "id": profile_id,
                    "name": metadata.get("name", profile_id),
                    "description": metadata.get("description", ""),
                    "created_at": metadata.get("created_at", ""),
                    "updated_at": metadata.get("updated_at", ""),
                    "is_active": profile_id == active_profile,
                    "has_configs": has_configs,
                })

            return Response().ok(data=profiles).to_dict()
        except Exception as e:
            logger.error(f"列出配置文件失败: {e}")
            return Response().error(f"列出配置文件失败: {str(e)}").to_dict()

    async def get_abconf(self) -> Dict[str, Any]:
        """获取指定配置文件内容 (AstrBot 规范)"""
        try:
            from quart import request
            
            profile_id = request.args.get("id")
            if not profile_id:
                return Response().error("缺少 id 参数").to_dict()

            profile_dir = self._get_profile_dir(profile_id)
            if not profile_dir.exists():
                return Response().error("配置文件不存在").to_dict()

            metadata_path = profile_dir / "metadata.json"
            metadata = {}
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except Exception:
                    pass

            # 获取配置文件内容
            configs = {}
            for config_file in BASE_CONFIG_FILES:
                config_path = profile_dir / config_file
                if config_path.exists():
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            configs[config_file] = json.load(f)
                    except Exception:
                        configs[config_file] = {}

            return Response().ok(data={
                "id": profile_id,
                "name": metadata.get("name", profile_id),
                "description": metadata.get("description", ""),
                "created_at": metadata.get("created_at", ""),
                "updated_at": metadata.get("updated_at", ""),
                "configs": configs,
            }).to_dict()
        except Exception as e:
            logger.error(f"获取配置文件失败: {e}")
            return Response().error(f"获取配置文件失败: {str(e)}").to_dict()

    async def create_abconf(self) -> Dict[str, Any]:
        """创建新配置文件 (AstrBot 规范)"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            profile_id = data.get("id")
            name = data.get("name")
            description = data.get("description", "")

            # 验证必填字段
            is_valid, error_msg = await self.validate_required_fields(data, ["id", "name"])
            if not is_valid:
                return Response().error(error_msg).to_dict()

            # 验证配置文件ID
            is_valid, error_msg = self._validate_profile_id(profile_id)
            if not is_valid:
                return Response().error(error_msg).to_dict()

            # 检查是否已存在
            profile_dir = self._get_profile_dir(profile_id)
            if profile_dir.exists():
                return Response().error("配置文件已存在").to_dict()

            # 创建配置文件目录
            profile_dir.mkdir(parents=True, exist_ok=True)

            # 从当前配置复制配置文件
            base_config_dir = self._get_base_config_dir()
            for config_file in BASE_CONFIG_FILES:
                src = base_config_dir / config_file
                dst = profile_dir / config_file
                if src.exists():
                    shutil.copy2(src, dst)
                else:
                    # 创建空配置文件
                    dst.write_text("{}", encoding="utf-8")

            # 保存元数据
            now = datetime.utcnow().isoformat()
            metadata = {
                "name": name,
                "description": description,
                "created_at": now,
                "updated_at": now,
            }
            metadata_path = profile_dir / "metadata.json"
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"配置文件 {profile_id} 创建成功")
            return Response().ok(data={"id": profile_id}, message="配置文件创建成功").to_dict()
        except Exception as e:
            logger.error(f"创建配置文件失败: {e}")
            return Response().error(f"创建配置文件失败: {str(e)}").to_dict()

    async def update_abconf_metadata(self) -> Dict[str, Any]:
        """更新配置文件元数据 (AstrBot 规范)"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            profile_id = data.get("id")
            if not profile_id:
                return Response().error("缺少 id 参数").to_dict()

            profile_dir = self._get_profile_dir(profile_id)
            if not profile_dir.exists():
                return Response().error("配置文件不存在").to_dict()

            # 更新元数据
            metadata_path = profile_dir / "metadata.json"
            metadata = {}
            if metadata_path.exists():
                try:
                    with open(metadata_path, "r", encoding="utf-8") as f:
                        metadata = json.load(f)
                except Exception:
                    pass

            # 更新可修改的字段
            if "name" in data:
                metadata["name"] = data["name"]
            if "description" in data:
                metadata["description"] = data["description"]
            metadata["updated_at"] = datetime.utcnow().isoformat()

            # 保存元数据
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"配置文件 {profile_id} 元数据更新成功")
            return Response().ok(message="配置文件元数据更新成功").to_dict()
        except Exception as e:
            logger.error(f"更新配置文件元数据失败: {e}")
            return Response().error(f"更新配置文件元数据失败: {str(e)}").to_dict()

    async def delete_abconf(self) -> Dict[str, Any]:
        """删除配置文件 (AstrBot 规范)"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            profile_id = data.get("id")
            if not profile_id:
                return Response().error("缺少 id 参数").to_dict()

            # 检查是否为活动配置文件
            active_profile = self._get_active_profile()
            if profile_id == active_profile:
                return Response().error("不能删除当前活动的配置文件").to_dict()

            profile_dir = self._get_profile_dir(profile_id)
            if not profile_dir.exists():
                return Response().error("配置文件不存在").to_dict()

            # 删除配置文件目录
            shutil.rmtree(profile_dir)

            logger.info(f"配置文件 {profile_id} 删除成功")
            return Response().ok(message="配置文件删除成功").to_dict()
        except Exception as e:
            logger.error(f"删除配置文件失败: {e}")
            return Response().error(f"删除配置文件失败: {str(e)}").to_dict()

    async def update_astrbot_config(self) -> Dict[str, Any]:
        """更新指定配置文件内容 (AstrBot 规范)"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            profile_id = data.get("id")
            if not profile_id:
                return Response().error("缺少 id 参数").to_dict()

            profile_dir = self._get_profile_dir(profile_id)
            if not profile_dir.exists():
                return Response().error("配置文件不存在").to_dict()

            # 更新配置文件内容
            if "configs" in data and isinstance(data["configs"], dict):
                for config_file, config_content in data["configs"].items():
                    if config_file in BASE_CONFIG_FILES:
                        config_path = profile_dir / config_file
                        with open(config_path, "w", encoding="utf-8") as f:
                            json.dump(config_content, f, indent=2, ensure_ascii=False)

                # 更新元数据时间
                metadata_path = profile_dir / "metadata.json"
                metadata = {}
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass
                metadata["updated_at"] = datetime.utcnow().isoformat()
                with open(metadata_path, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)

                logger.info(f"配置文件 {profile_id} 内容更新成功")
                return Response().ok(message="配置文件内容更新成功").to_dict()
            else:
                return Response().error("缺少 configs 参数").to_dict()
        except Exception as e:
            logger.error(f"更新配置文件内容失败: {e}")
            return Response().error(f"更新配置文件内容失败: {str(e)}").to_dict()

    async def switch_profile(self) -> Dict[str, Any]:
        """切换配置文件"""
        try:
            data = await self.get_request_data()
            if not data:
                return Response().error("缺少请求数据").to_dict()

            profile_id = data.get("id")
            if not profile_id:
                return Response().error("缺少 id 参数").to_dict()

            profile_dir = self._get_profile_dir(profile_id)
            if not profile_dir.exists():
                return Response().error("配置文件不存在").to_dict()

            # 检查配置文件完整性
            for config_file in BASE_CONFIG_FILES:
                if not (profile_dir / config_file).exists():
                    return Response().error(f"配置文件不完整，缺少 {config_file}").to_dict()

            # 备份当前配置
            base_config_dir = self._get_base_config_dir()
            backup_dir = base_config_dir / "backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"backup_{backup_timestamp}"
            backup_path.mkdir(parents=True, exist_ok=True)

            for config_file in BASE_CONFIG_FILES:
                src = base_config_dir / config_file
                if src.exists():
                    shutil.copy2(src, backup_path / config_file)

            # 复制新配置文件到基础目录
            for config_file in BASE_CONFIG_FILES:
                src = profile_dir / config_file
                dst = base_config_dir / config_file
                shutil.copy2(src, dst)

            # 设置活动配置文件
            if not self._set_active_profile(profile_id):
                return Response().error("设置活动配置文件失败").to_dict()

            logger.info(f"已切换到配置文件 {profile_id}")
            return Response().ok(message="配置文件切换成功，请重启应用以生效").to_dict()
        except Exception as e:
            logger.error(f"切换配置文件失败: {e}")
            return Response().error(f"切换配置文件失败: {str(e)}").to_dict()

    async def get_active_profile(self) -> Dict[str, Any]:
        """获取当前活动的配置文件"""
        try:
            active_profile = self._get_active_profile()
            profile_dir = self._get_profile_dir(active_profile)

            metadata = {}
            if profile_dir.exists():
                metadata_path = profile_dir / "metadata.json"
                if metadata_path.exists():
                    try:
                        with open(metadata_path, "r", encoding="utf-8") as f:
                            metadata = json.load(f)
                    except Exception:
                        pass

            return Response().ok(data={
                "id": active_profile,
                "name": metadata.get("name", active_profile),
                "description": metadata.get("description", ""),
            }).to_dict()
        except Exception as e:
            logger.error(f"获取活动配置文件失败: {e}")
            return Response().error(f"获取活动配置文件失败: {str(e)}").to_dict()