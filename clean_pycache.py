"""
清理 Python 缓存文件
删除所有 __pycache__ 目录和 .pyc 文件
"""
import os
import shutil
from pathlib import Path

def clean_pycache(root_dir="."):
    """清理指定目录下的所有 Python 缓存文件"""
    root_path = Path(root_dir).absolute()
    count = 0
    
    print(f"开始清理 {root_path} 下的 Python 缓存文件...")
    
    # 删除所有 __pycache__ 目录
    for pycache_dir in root_path.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
            print(f"已删除: {pycache_dir}")
            count += 1
        except Exception as e:
            print(f"删除失败: {pycache_dir} - {e}")
    
    # 删除所有 .pyc 文件
    for pyc_file in root_path.rglob("*.pyc"):
        try:
            pyc_file.unlink()
            print(f"已删除: {pyc_file}")
            count += 1
        except Exception as e:
            print(f"删除失败: {pyc_file} - {e}")
    
    print(f"\n清理完成！共删除 {count} 个文件/目录")

if __name__ == "__main__":
    clean_pycache()