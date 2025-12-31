#!/usr/bin/env python3
"""
包装脚本 - 强制重新运行导入检查器
"""
import sys
import os
import shutil
from pathlib import Path

# 清除所有 __pycache__ 目录
print("正在清除Python缓存...")
for root, dirs, files in os.walk('.'):
    for d in dirs:
        if d == '__pycache__':
            cache_path = os.path.join(root, d)
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path, ignore_errors=True)
                print(f"  已删除: {cache_path}")

# 删除特定模块的缓存
if 'import_checker' in sys.modules:
    del sys.modules['import_checker']

# 删除import_checker的pyc文件
checker_pyc = Path('tests/import_checker.py')
if checker_pyc.with_suffix('.pyc').exists():
    pyc_path = checker_pyc.with_suffix('.pyc')
    os.remove(pyc_path)
    print(f"已删除: {pyc_path}")

print("正在运行导入检查器...")
exec(open('tests/import_checker.py').read())