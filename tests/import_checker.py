#!/usr/bin/env python3
"""
导入检查器 - 系统地检查项目中所有模块的导入语句
"""
import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ImportIssue:
    """导入问题"""
    file_path: str
    line: int
    issue_type: str
    message: str
    severity: str = "error"  # error, warning, info
    suggestion: str = ""  # 建议的修正


@dataclass
class ModuleExport:
    """模块导出信息"""
    file_path: str
    has_default_export: bool = False
    default_exports: Set[str] = field(default_factory=set)
    named_exports: Set[str] = field(default_factory=set)
    classes: Set[str] = field(default_factory=set)
    functions: Set[str] = field(default_factory=set)
    variables: Set[str] = field(default_factory=set)
    __all__: Set[str] = field(default_factory=set)  # 明确的__all__定义


@dataclass
class ImportStatement:
    """导入语句"""
    file_path: str
    line: int
    module: str
    names: List[str]
    is_from_import: bool
    is_relative: bool
    level: int = 0  # 相对导入的层级
    alias_map: Dict[str, str] = field(default_factory=dict)


# Python标准库列表（常见模块）
STANDARD_LIBS = {
    'abc', 'aifc', 'argparse', 'array', 'ast', 'asynchat', 'asyncio',
    'asyncore', 'atexit', 'audioop', 'base64', 'bdb', 'binascii',
    'binhex', 'bisect', 'builtins', 'bz2', 'calendar', 'cgi', 'cgitb',
    'chunk', 'cmath', 'cmd', 'code', 'codecs', 'codeop', 'collections',
    'colorsys', 'compileall', 'complex', 'configparser', 'contextlib',
    'contextvars', 'copy', 'copyreg', 'cProfile', 'crypt', 'csv',
    'ctypes', 'curses', 'dataclasses', 'datetime', 'dbm', 'decimal',
    'difflib', 'dis', 'distutils', 'doctest', 'email', 'encodings',
    'enum', 'errno', 'faulthandler', 'fcntl', 'filecmp', 'fileinput',
    'fnmatch', 'formatter', 'fractions', 'ftplib', 'functools',
    'gc', 'getopt', 'getpass', 'gettext', 'glob', 'graphlib',
    'grp', 'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http',
    'imaplib', 'imghdr', 'imp', 'importlib', 'inspect', 'io',
    'ipaddress', 'itertools', 'json', 'keyword', 'lib2to3', 'linecache',
    'locale', 'logging', 'lzma', 'mailbox', 'mailcap', 'marshal',
    'math', 'mimetypes', 'mmap', 'modulefinder', 'msilib', 'msvcrt',
    'multiprocessing', 'netrc', 'nis', 'nntplib', 'numbers', 'operator',
    'optparse', 'os', 'ossaudiodev', 'pathlib', 'pdb', 'pickle',
    'pickletools', 'pipes', 'pkgutil', 'platform', 'plistlib',
    'poplib', 'posix', 'posixpath', 'pprint', 'profile', 'pstats',
    'pty', 'pwd', 'py_compile', 'pyclbr', 'pydoc', 'queue',
    'quopri', 'random', 're', 'readline', 'reprlib', 'resource',
    'rlcompleter', 'runpy', 'sched', 'secrets', 'select', 'selectors',
    'shelve', 'shelve', 'shutil', 'signal', 'site', 'smtpd',
    'smtplib', 'sndhdr', 'socket', 'socketserver', 'spwd', 'sqlite3',
    'ssl', 'stat', 'statistics', 'string', 'stringprep', 'struct',
    'subprocess', 'sunau', 'symbol', 'symtable', 'sys', 'sysconfig',
    'syslog', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile',
    'termios', 'test', 'textwrap', 'threading', 'time', 'timeit',
    'tkinter', 'token', 'tokenize', 'tomllib', 'trace', 'traceback',
    'tracemalloc', 'tty', 'turtle', 'turtledemo', 'types',
    'typing', 'typing_extensions', 'unicodedata', 'unittest', 'urllib',
    'uu', 'uuid', 'venv', 'warnings', 'wave', 'weakref',
    'webbrowser', 'winreg', 'winsound', 'wsgiref', 'xdrlib', 'xml',
    'xmlrpc', 'zipapp', 'zipfile', 'zipimport', 'zlib',
    # 标准库子模块
    'abc.abc', 'asyncio.abc', 'collections.abc', 'contextlib',
    'email.message', 'email.mime', 'encodings.aliases', 'importlib.abc',
    'importlib.metadata', 'importlib.resources', 'importlib.util',
    'os.path', 'pathlib.Path', 'queue.Queue', 'typing.Generic',
    'typing.Protocol', 'typing.TypeVar', 'typing.dataclass',
    'typing_extensions', 'unittest.mock', 'urllib.parse', 'urllib.request',
    # 常用第三方库（通过pip安装）
    'anthropic', 'aiohttp', 'bcrypt', 'certifi', 'dashscope',
    'dataclasses', 'functools', 'google', 'google.genai',
    'google.genai.errors', 'httpx', 'jose', 'loguru', 'openai',
    'pathlib', 'pypdf', 'pydantic', 'psutil', 'quart', 'quart_cors',
    'slack_sdk', 'ssl', 'statistics', 'tomli', 'unittest',
    'watchfiles', 'werobot', 'werkzeug', 'zhipuai', 'lark_oapi',
    'lark_oapi.api.im.v1', 'pytest', 'yaml', 'anthropic.types.usage',
    'anthropic.types', 'openai', 'contextlib', 'abc', 'collections',
    'datetime', 'enum', 'functools', 'inspect', 'json', 'os',
    'pathlib', 're', 'shutil', 'sqlite3', 'sys', 'tempfile',
    'time', 'traceback', 'typing', 'uuid', 'websockets',
    'werkzeug.exceptions', 'anthropic', 'loguru', 'pytest', 'yaml',
    'base64', 'certifi', 'inspect', 'logging', 'math', 'random',
    'ssl', 'traceback', 'unittest.mock'
}


class ImportChecker:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.issues: List[ImportIssue] = []
        self.exports: Dict[str, ModuleExport] = {}
        self.imports: List[ImportStatement] = []
        self.scanned_files: Set[str] = set()
    
    def is_standard_or_third_party_lib(self, module_name: str) -> bool:
        """检查是否是标准库或已安装的第三方库"""
        # 检查标准库
        if module_name in STANDARD_LIBS:
            return True
        
        # 检查是否是标准库的子模块
        base_name = module_name.split('.')[0]
        if base_name in STANDARD_LIBS:
            return True
        
        # 尝试导入检查是否是已安装的第三方库
        try:
            __import__(module_name)
            return True
        except ImportError:
            return False
        
    def collect_all_python_files(self) -> List[Path]:
        """收集所有Python文件"""
        python_files = []
        for root, dirs, files in os.walk(self.project_root):
            # 跳过虚拟环境、缓存等目录
            dirs[:] = [d for d in dirs if d not in {
                '__pycache__', '.git', '.venv', 'venv',
                'node_modules', '.pytest_cache', 'dist', 'build'
            }]
             
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        return python_files
    
    def parse_module_exports(self, file_path: Path) -> ModuleExport:
        """解析模块的导出内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"警告: 无法读取文件 {file_path}: {e}")
            return ModuleExport(file_path=str(file_path))
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"警告: 文件 {file_path} 存在语法错误: {e}")
            return ModuleExport(file_path=str(file_path))
        
        export = ModuleExport(file_path=str(file_path))
        
        # 只遍历模块级别的节点
        for node in tree.body:
            # 收集类定义
            if isinstance(node, ast.ClassDef):
                export.classes.add(node.name)
                export.named_exports.add(node.name)
             
            # 收集函数定义
            elif isinstance(node, ast.FunctionDef):
                export.functions.add(node.name)
                export.named_exports.add(node.name)
             
            # 收集变量赋值（模块级别）
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        export.variables.add(target.id)
                        export.named_exports.add(target.id)
                        
                        # 检查是否是 __all__ 定义
                        if target.id == '__all__':
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant):
                                        export.__all__.add(elt.value)
                                        export.named_exports.add(elt.value)
        
        return export
    
    def parse_imports(self, file_path: Path) -> List[ImportStatement]:
        """解析文件中的导入语句"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"警告: 无法读取文件 {file_path}: {e}")
            return []
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            print(f"警告: 文件 {file_path} 存在语法错误: {e}")
            return []
        
        imports = []
        
        for node in ast.walk(tree):
            # 直接导入：import module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportStatement(
                        file_path=str(file_path),
                        line=node.lineno,
                        module=alias.name,
                        names=[alias.asname if alias.asname else alias.name],
                        is_from_import=False,
                        is_relative=not alias.name.startswith('.')
                    ))
             
            # from导入：from module import name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                level = node.level  # 相对导入的层级
                
                for alias in node.names:
                    alias_map = {}
                    if alias.asname:
                        alias_map[alias.asname] = alias.name
                     
                    imports.append(ImportStatement(
                        file_path=str(file_path),
                        line=node.lineno,
                        module=module,
                        names=[alias.name],
                        is_from_import=True,
                        is_relative=level > 0,
                        level=level,
                        alias_map=alias_map
                    ))
        
        return imports
    
    def resolve_module_path(self, import_stmt: ImportStatement, current_file: Path) -> str:
        """解析导入模块的绝对路径"""
        if not import_stmt.is_relative:
            # 绝对导入，直接从项目根目录查找
            module_parts = import_stmt.module.split('.')
            possible_paths = []
             
            # 尝试从项目根目录查找
            base_path = self.project_root
            for i in range(len(module_parts)):
                test_path = base_path.joinpath(*module_parts[:i+1]) / '__init__.py'
                if test_path.exists():
                    possible_paths.append(str(test_path))
                     
                test_py = base_path.joinpath(*module_parts[:i+1]).with_suffix('.py')
                if test_py.exists():
                    possible_paths.append(str(test_py))
             
            # 尝试packages目录
            base_path = self.project_root / 'packages'
            for i in range(len(module_parts)):
                test_path = base_path.joinpath(*module_parts[:i+1]) / '__init__.py'
                if test_path.exists():
                    possible_paths.append(str(test_path))
                     
                test_py = base_path.joinpath(*module_parts[:i+1]).with_suffix('.py')
                if test_py.exists():
                    possible_paths.append(str(test_py))
             
            return possible_paths[0] if possible_paths else import_stmt.module
        else:
            # 相对导入
            level = import_stmt.level
            current_dir = current_file.parent
             
            # 向上查找level个目录
            for _ in range(level - 1):
                current_dir = current_dir.parent
             
            module_parts = import_stmt.module.split('.') if import_stmt.module else []
            target_path = current_dir
             
            for part in module_parts:
                target_path = target_path / part
             
            # 查找__init__.py或.py文件
            init_path = target_path / '__init__.py'
            py_path = target_path.with_suffix('.py') if target_path.suffix == '' else target_path
             
            if init_path.exists():
                return str(init_path)
            elif py_path.exists():
                return str(py_path)
             
            return str(target_path)
     
    def find_similar_names(self, name: str, available_names: Set[str]) -> List[str]:
        """查找相似的名称（用于拼写检查）"""
        similar = []
        for available in available_names:
            # 检查大小写不匹配
            if name.lower() == available.lower() and name != available:
                similar.append(available)
            # 检查简单的拼写错误（编辑距离1）
            elif self._levenshtein_distance(name, available) <= 2:
                similar.append(available)
        return sorted(similar)
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """计算两个字符串的编辑距离"""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def check_import_validity(self, import_stmt: ImportStatement) -> List[ImportIssue]:
        """检查导入的有效性"""
        issues = []
        current_file = Path(import_stmt.file_path)
        
        # 解析目标模块路径
        target_path = self.resolve_module_path(import_stmt, current_file)
        
        # 检查模块是否存在
        if not os.path.exists(target_path):
            # 检查是否是标准库或第三方库
            if self.is_standard_or_third_party_lib(import_stmt.module):
                return issues  # 标准库或第三方库，跳过检查
            
            issues.append(ImportIssue(
                file_path=import_stmt.file_path,
                line=import_stmt.line,
                issue_type="MODULE_NOT_FOUND",
                message=f"模块 '{import_stmt.module}' 不存在，解析路径为: {target_path}",
                severity="error"
            ))
            return issues
        
        # 获取目标模块的导出
        if target_path in self.exports:
            export = self.exports[target_path]
        else:
            export = self.parse_module_exports(Path(target_path))
            self.exports[target_path] = export
        
        # 检查导入的名称是否存在
        if import_stmt.is_from_import:
            for name in import_stmt.names:
                if name == '*':
                    continue
                
                # 收集所有可用的名称
                all_available = set()
                all_available.update(export.named_exports)
                all_available.update(export.classes)
                all_available.update(export.functions)
                all_available.update(export.variables)
                
                if name not in all_available:
                    # 查找相似的名称
                    similar_names = self.find_similar_names(name, all_available)
                    suggestion = f"建议使用: {', '.join(similar_names)}" if similar_names else ""
                    
                    issues.append(ImportIssue(
                        file_path=import_stmt.file_path,
                        line=import_stmt.line,
                        issue_type="NAME_NOT_FOUND",
                        message=f"在模块 '{import_stmt.module}' 中未找到名称 '{name}'",
                        severity="error",
                        suggestion=suggestion
                    ))
                else:
                    # 检查大小写一致性
                    if name in export.named_exports:
                        # 名称在命名导出中找到，检查是否有大小写不匹配的情况
                        for export_name in export.named_exports:
                            if name.lower() == export_name.lower() and name != export_name:
                                issues.append(ImportIssue(
                                    file_path=import_stmt.file_path,
                                    line=import_stmt.line,
                                    issue_type="CASE_MISMATCH",
                                    message=f"大小写不匹配: 导入 '{name}' 但模块中定义为 '{export_name}'",
                                    severity="warning",
                                    suggestion=f"建议改为: {export_name}"
                                ))
                                break
        else:
            # 检查import语句的别名
            for alias in import_stmt.names:
                # 这里可以添加对import语句的额外检查
                pass
        
        return issues
    
    def scan_project(self) -> None:
        """扫描整个项目"""
        print("正在扫描Python文件...")
        python_files = self.collect_all_python_files()
        print(f"找到 {len(python_files)} 个Python文件")
        
        # 首先解析所有模块的导出
        print("正在解析模块导出...")
        for file_path in python_files:
            export = self.parse_module_exports(file_path)
            self.exports[str(file_path)] = export
            self.scanned_files.add(str(file_path))
        
        # 解析所有导入语句
        print("正在解析导入语句...")
        for file_path in python_files:
            imports = self.parse_imports(file_path)
            self.imports.extend(imports)
        
        print(f"找到 {len(self.imports)} 个导入语句")
        
        # 检查导入有效性
        print("正在检查导入有效性...")
        for import_stmt in self.imports:
            issues = self.check_import_validity(import_stmt)
            self.issues.extend(issues)
    
    def generate_report(self) -> str:
        """生成导入状态报告"""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("导入状态报告")
        report_lines.append("=" * 80)
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"项目根目录: {self.project_root}")
        report_lines.append("")
        
        # 统计信息
        report_lines.append("## 统计信息")
        report_lines.append("-" * 80)
        report_lines.append(f"扫描的Python文件数: {len(self.scanned_files)}")
        report_lines.append(f"导入语句总数: {len(self.imports)}")
        report_lines.append(f"发现的导出模块数: {len(self.exports)}")
        report_lines.append("")
        
        report_lines.append("发现的问题:")
        error_count = sum(1 for i in self.issues if i.severity == "error")
        warning_count = sum(1 for i in self.issues if i.severity == "warning")
        report_lines.append(f"  - 错误: {error_count}")
        report_lines.append(f"  - 警告: {warning_count}")
        report_lines.append("")
        
        # 导入语句详情
        report_lines.append("## 导入语句详情")
        report_lines.append("-" * 80)
        
        # 按文件分组
        imports_by_file: Dict[str, List[ImportStatement]] = {}
        for imp in self.imports:
            if imp.file_path not in imports_by_file:
                imports_by_file[imp.file_path] = []
            imports_by_file[imp.file_path].append(imp)
        
        for file_path, imports in sorted(imports_by_file.items()):
            rel_path = Path(file_path).relative_to(self.project_root)
            report_lines.append(f"\n### {rel_path}")
            for imp in sorted(imports, key=lambda x: x.line):
                imp_type = "from导入" if imp.is_from_import else "import导入"
                relative = " (相对)" if imp.is_relative else " (绝对)"
                alias_info = ""
                if imp.alias_map:
                    alias_info = f" [别名: {imp.alias_map}]"
                report_lines.append(f" 行 {imp.line}: {imp_type}{relative} - {imp.module}{alias_info}")
        
        # 问题详情
        if self.issues:
            report_lines.append("")
            report_lines.append("## 发现的问题")
            report_lines.append("-" * 80)
            
            # 按类型分组
            issues_by_type: Dict[str, List[ImportIssue]] = {}
            for issue in self.issues:
                if issue.issue_type not in issues_by_type:
                    issues_by_type[issue.issue_type] = []
                issues_by_type[issue.issue_type].append(issue)
            
            for issue_type, issues in sorted(issues_by_type.items()):
                report_lines.append(f"\n### {issue_type} ({len(issues)}个)")
                for issue in sorted(issues, key=lambda x: (x.file_path, x.line)):
                    rel_path = Path(issue.file_path).relative_to(self.project_root)
                    severity_icon = "❌" if issue.severity == "error" else "⚠️"
                    report_lines.append(f"  {severity_icon} {rel_path}:{issue.line}")
                    report_lines.append(f"     {issue.message}")
                    if issue.suggestion:
                        report_lines.append(f"     💡 {issue.suggestion}")
        else:
            report_lines.append("")
            report_lines.append("## 发现的问题")
            report_lines.append("-" * 80)
            report_lines.append("✅ 未发现任何导入问题！")
        
        # 模块导出摘要
        report_lines.append("")
        report_lines.append("## 模块导出摘要")
        report_lines.append("-" * 80)
        
        exports_by_package: Dict[str, List[ModuleExport]] = {}
        for file_path, export in self.exports.items():
            rel_path = Path(file_path).relative_to(self.project_root)
            if rel_path.parts[0] == 'packages':
                package = '/'.join(rel_path.parts[:3]) if len(rel_path.parts) > 2 else str(rel_path.parent)
            else:
                package = str(rel_path.parent)
             
            if package not in exports_by_package:
                exports_by_package[package] = []
            exports_by_package[package].append(export)
        
        for package, exports in sorted(exports_by_package.items()):
            total_classes = sum(len(e.classes) for e in exports)
            total_functions = sum(len(e.functions) for e in exports)
            report_lines.append(f"\n### {package}/")
            report_lines.append(f"  文件数: {len(exports)}")
            report_lines.append(f"  导出类: {total_classes}")
            report_lines.append(f"  导出函数: {total_functions}")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append("报告结束")
        report_lines.append("=" * 80)
        
        return '\n'.join(report_lines)
    
    def save_report(self, output_file: str) -> None:
        """保存报告到文件"""
        # 确保输出目录存在
        output_dir = Path(output_file).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        report = self.generate_report()
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"报告已保存到: {output_file}")


def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    print(f"项目根目录: {project_root}")
    print("=" * 80)
    
    # 创建输出目录 (tests/outputs)
    output_dir = script_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建检查器并扫描项目
    checker = ImportChecker(str(project_root))
    checker.scan_project()
    
    # 生成并保存报告（带时间戳）
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = output_dir / f"import_status_report_{timestamp}.txt"
    checker.save_report(str(report_file))
    
    # 同时输出到控制台（使用UTF-8编码）
    try:
        print("\n" + checker.generate_report())
    except UnicodeEncodeError:
        # 如果控制台不支持UTF-8，只输出摘要
        print("\n报告已生成，请查看文件: " + str(report_file))
        print(f"扫描文件数: {len(checker.scanned_files)}")
        print(f"导入语句数: {len(checker.imports)}")
        print(f"发现问题数: {len(checker.issues)}")


if __name__ == "__main__":
    main()