#!/usr/bin/env python3
"""
独立脚本 - 运行导入检查器
"""
import sys
import os
from pathlib import Path

# 添加tests目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 删除可能的缓存文件
checker_pyc = Path(__file__).parent / 'import_checker.pyc'
if checker_pyc.exists():
    os.remove(checker_pyc)
    print(f"已删除: {checker_pyc}")

# 导入并运行
import import_checker

# 运行主函数
import_checker.main()