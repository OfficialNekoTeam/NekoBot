"""插件依赖管理器

自动检查和安装插件依赖
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import List, Optional
from loguru import logger


class DependencyManager:
    """插件依赖管理器
    
    负责检查和安装插件依赖（requirements.txt）
    """

    def __init__(self, pip_executable: Optional[str] = None):
        """初始化依赖管理器
        
        Args:
            pip_executable: pip 可执行文件路径（可选）
        """
        self.pip_executable = pip_executable or "pip"

    async def check_and_install(
        self,
        plugin_dir: Path,
        proxy: Optional[str] = None,
    ) -> bool:
        """检查并安装插件依赖
        
        Args:
            plugin_dir: 插件目录
            proxy: 代理地址（可选）
            
        Returns:
            是否成功安装依赖
        """
        requirements_path = plugin_dir / "requirements.txt"
        
        if not requirements_path.exists():
            logger.debug(f"插件 {plugin_dir.name} 没有 requirements.txt，跳过依赖安装")
            return True
        
        logger.info(f"开始检查插件 {plugin_dir.name} 的依赖...")
        
        try:
            # 读取 requirements.txt
            with open(requirements_path, "r", encoding="utf-8") as f:
                requirements = [
                    line.strip()
                    for line in f.readlines()
                    if line.strip() and not line.startswith("#")
                ]
            
            if not requirements:
                logger.debug(f"插件 {plugin_dir.name} 的 requirements.txt 为空，跳过")
                return True
            
            logger.info(f"发现 {len(requirements)} 个依赖包")
            
            # 构建 pip 命令
            cmd = [self.pip_executable, "install", "-r", str(requirements_path)]
            
            # 添加代理
            if proxy:
                cmd.extend(["--proxy", proxy])
            
            # 异步执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(
                    f"安装插件 {plugin_dir.name} 的依赖失败: {stderr.decode('utf-8', errors='ignore')}"
                )
                return False
            
            logger.info(f"插件 {plugin_dir.name} 的依赖安装成功")
            return True
            
        except Exception as e:
            logger.error(f"检查插件 {plugin_dir.name} 的依赖时出错: {e}")
            return False

    async def check_installed(
        self,
        package_name: str,
    ) -> bool:
        """检查包是否已安装
        
        Args:
            package_name: 包名
            
        Returns:
            是否已安装
        """
        try:
            process = await asyncio.create_subprocess_exec(
                self.pip_executable, "show", package_name
            )
            await process.wait()
            return process.returncode == 0
        except Exception as e:
            logger.debug(f"检查包 {package_name} 时出错: {e}")
            return False

    async def get_installed_version(
        self,
        package_name: str,
    ) -> Optional[str]:
        """获取已安装包的版本
        
        Args:
            package_name: 包名
            
        Returns:
            版本号，如果未安装则返回 None
        """
        try:
            process = await asyncio.create_subprocess_exec(
                self.pip_executable, "show", package_name
            )
            stdout, _ = await process.communicate()
            
            # 解析版本号
            if process.returncode == 0:
                output = stdout.decode("utf-8", errors="ignore")
                for line in output.split("\n"):
                    if "Version:" in line:
                        version = line.split("Version:")[1].strip()
                        return version
            
            return None
        except Exception as e:
            logger.debug(f"获取包 {package_name} 版本时出错: {e}")
            return None

    async def uninstall(
        self,
        package_name: str,
    ) -> bool:
        """卸载包
        
        Args:
            package_name: 包名
            
        Returns:
            是否成功卸载
        """
        try:
            process = await asyncio.create_subprocess_exec(
                self.pip_executable, "uninstall", "-y", package_name
            )
            await process.wait()
            
            if process.returncode == 0:
                logger.info(f"已卸载包: {package_name}")
                return True
            else:
                logger.warning(f"卸载包 {package_name} 失败")
                return False
        except Exception as e:
            logger.error(f"卸载包 {package_name} 时出错: {e}")
            return False

    def parse_requirements(self, requirements_path: Path) -> List[str]:
        """解析 requirements.txt 文件
        
        Args:
            requirements_path: requirements.txt 文件路径
            
        Returns:
            依赖包列表
        """
        if not requirements_path.exists():
            return []
        
        requirements = []
        
        try:
            with open(requirements_path, "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    
                    # 跳过注释和空行
                    if not line or line.startswith("#"):
                        continue
                    
                    # 处理版本约束
                    # 简化处理：只取包名
                    package = line.split(">=")[0].split("==")[0].split(">")[0].split("<")[0].split("~=")[0].strip()
                    
                    if package:
                        requirements.append(package)
        
        return requirements


# 创建全局依赖管理器实例
dependency_manager = DependencyManager()