#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后端领域拆分的机械检查。只读代码，不修改任何文件。

一条命令判定三件事：

1. 领域路由模块之间没有 import 边；
2. 共享层模块不 import 领域路由模块；
3. 单个领域路由文件不超过 600 行。

规则全部由扫描目录自动发现，仓库里没有内置的文件清单，新建领域目录后自动纳入检查：

- 领域路由目录：含 Flask Blueprint 定义文件的目录。一个领域一个蓝图（见
  docs/adr/0001-backend-domain-split.md），所以「有没有蓝图」就是「是不是路由层」的判据。
  同一目录下出现多个蓝图文件时，该目录按容器处理，每个蓝图文件各自成为一个领域，
  避免把平铺的同级领域误并成一个。
- 领域路由模块：领域路由目录下的全部 .py 文件，含 __init__.py。包的 __init__.py
  同样能 import 别的领域、同样能写到 600 行以上，把它算进来才不会漏判。
- 共享层模块：路径上带有共享层名字且不在任何领域路由目录下的 .py 文件。名字取自
  GLOSSARY.md 对「共享层」的定义（只有 core、ai、shared 三类），可用 --shared 增补。

import 边用 ast 解析，覆盖 `import x`、`import x.y`、`from x import y`、`from x.y import z`
以及各级相对导入；标准库与第三方导入自动忽略。无法解析的文件单独报为一类违规，
避免语法错误被静默跳过。

用法：
    python tools/check_architecture.py
    python tools/check_architecture.py --root . --max-lines 600
    python tools/check_architecture.py --shared shared,core,ai,platform

退出码：0 合规，1 有违规，2 用法或环境错误。
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# 扫描根是 backend/：后端代码整体迁入 backend/ 后，领域路由目录（domains/）、
# 共享层（core / ai / shared）都在它下面。这个脚本本身留在 tools/ 不动，
# 所以从 __file__ 上跳一级到仓库根、再进 backend/。
REPO_ROOT = Path(__file__).resolve().parents[1] / "backend"

DEFAULT_MAX_LINES = 600
DEFAULT_SHARED_NAMES = ("shared", "core", "ai")

EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".idea",
        ".vscode",
        ".scratch",
        "build",
        "dist",
        "tools",
        "tests",
        "e2e",
    }
)

KIND_CROSS_DOMAIN = "cross-domain-import"
KIND_SHARED_TO_DOMAIN = "shared-imports-domain"
KIND_TOO_LONG = "file-too-long"
KIND_UNPARSABLE = "unparsable-file"

KIND_ORDER = {
    KIND_CROSS_DOMAIN: 0,
    KIND_SHARED_TO_DOMAIN: 1,
    KIND_TOO_LONG: 2,
    KIND_UNPARSABLE: 3,
}


@dataclass
class ModuleInfo:
    relative: str
    module: str
    is_package: bool
    is_blueprint: bool = False
    line_count: int = 0
    tree: object = None
    error: str = ""


@dataclass
class Domain:
    key: str
    name: str
    modules: list = field(default_factory=list)

    @property
    def files(self):
        return [module.relative for module in self.modules]


@dataclass
class Violation:
    kind: str
    source: str
    message: str
    line: int = 0
    target: str = ""
    detail: str = ""


@dataclass
class Report:
    root: Path
    domains: list
    shared_modules: list
    violations: list
    max_lines: int

    @property
    def ok(self):
        return not self.violations


def iter_python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if filename.endswith(".py"):
                yield Path(dirpath) / filename


def read_source(path):
    try:
        with tokenize.open(path) as handle:
            return handle.read()
    except (SyntaxError, UnicodeDecodeError, LookupError, ValueError):
        return path.read_bytes().decode("utf-8", errors="replace")


def module_name(relative):
    parts = list(PurePosixPath(relative).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def parent_dir(relative):
    return relative.rpartition("/")[0]


def domain_name(key):
    name = key.rsplit("/", 1)[-1]
    return name[:-3] if name.endswith(".py") else name


def callee_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        parts.reverse()
        return ".".join(parts)
    return ""


def defines_blueprint(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = callee_name(node.func)
            if name and name.rsplit(".", 1)[-1] == "Blueprint":
                return True
    return False


def import_from_head(info, node):
    if not node.level:
        return node.module or ""
    parts = info.module.split(".") if info.module else []
    package = parts if info.is_package else parts[:-1]
    keep = len(package) - (node.level - 1)
    if keep < 0:
        return ""
    base = ".".join(package[:keep])
    module = node.module or ""
    if base and module:
        return base + "." + module
    return base or module


def imported_targets(info):
    """返回 (行号, 候选模块名) 列表，候选按 Python 的解析优先级排列。"""
    if info.tree is None:
        return []
    targets = []
    for node in ast.walk(info.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    targets.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            head = import_from_head(info, node)
            if not head:
                continue
            for alias in node.names:
                if alias.name != "*":
                    targets.append((node.lineno, head + "." + alias.name))
            targets.append((node.lineno, head))
    return targets


class Layout:
    """仓库的领域路由目录、共享层模块与模块名到文件的映射。"""

    def __init__(self, root, shared_names):
        self.root = root
        self.shared_names = frozenset(shared_names)
        self.modules = []
        self.domains = []
        self.shared_modules = []
        self._by_module = {}
        self._by_relative = {}
        self._blueprint_count = {}
        self._domain_key = {}
        self._load()
        self._classify()

    def _load(self):
        for path in iter_python_files(self.root):
            relative = path.relative_to(self.root).as_posix()
            module = module_name(relative)
            if not module:
                continue
            info = ModuleInfo(
                relative=relative,
                module=module,
                is_package=relative.endswith("__init__.py"),
            )
            source = read_source(path)
            info.line_count = len(source.splitlines())
            try:
                info.tree = ast.parse(source, filename=relative)
            except SyntaxError as exc:
                info.error = "第 %s 行 %s" % (exc.lineno, exc.msg)
            else:
                info.is_blueprint = defines_blueprint(info.tree)
            self.modules.append(info)
            self._by_module[module] = info
            self._by_relative[relative] = info

    def _classify(self):
        for info in self.modules:
            directory = parent_dir(info.relative)
            if info.is_blueprint:
                self._blueprint_count[directory] = self._blueprint_count.get(directory, 0) + 1

        groups = {}
        for info in self.modules:
            key = self._domain_key_of(info)
            self._domain_key[info.relative] = key
            if key is not None:
                groups.setdefault(key, []).append(info)

        self.domains = [
            Domain(key=key, name=domain_name(key), modules=members)
            for key, members in sorted(groups.items())
        ]
        self.shared_modules = [info for info in self.modules if self.is_shared(info)]

    def _is_container(self, directory):
        if self._blueprint_count.get(directory, 0) < 2:
            return False
        init = "%s/__init__.py" % directory if directory else "__init__.py"
        info = self._by_relative.get(init)
        return not (info is not None and info.is_blueprint)

    def _domain_key_of(self, info):
        directory = parent_dir(info.relative)
        if info.is_blueprint:
            return info.relative if self._is_container(directory) else directory
        current = directory
        while current:
            if self._blueprint_count.get(current, 0) and not self._is_container(current):
                return current
            current = parent_dir(current)
        return None

    def is_domain(self, relative):
        return self._domain_key.get(relative) is not None

    def domain_key(self, relative):
        return self._domain_key.get(relative)

    def domain_of(self, relative):
        key = self._domain_key.get(relative)
        return domain_name(key) if key else ""

    def is_shared(self, info):
        if self.is_domain(info.relative):
            return False
        parts = PurePosixPath(info.relative).with_suffix("").parts
        return any(part in self.shared_names for part in parts)

    def resolve(self, name):
        return self._by_module.get(name)


def check(root=None, max_lines=DEFAULT_MAX_LINES, shared_names=DEFAULT_SHARED_NAMES):
    root = Path(root).resolve() if root else REPO_ROOT
    layout = Layout(root, shared_names)
    violations = []
    seen = set()

    def add(kind, source, message, line=0, target="", detail=""):
        signature = (kind, source, target)
        if signature in seen:
            return
        seen.add(signature)
        violations.append(
            Violation(kind=kind, source=source, message=message, line=line, target=target, detail=detail)
        )

    for domain in layout.domains:
        for info in domain.modules:
            if info.tree is None:
                add(
                    KIND_UNPARSABLE,
                    info.relative,
                    "无法解析 %s：%s" % (info.relative, info.error),
                    detail=info.error,
                )
                continue
            if info.line_count > max_lines:
                over = info.line_count - max_lines
                add(
                    KIND_TOO_LONG,
                    info.relative,
                    "文件超长：%s 共 %d 行，超过 %d 行上限 %d 行"
                    % (info.relative, info.line_count, max_lines, over),
                    detail="%d 行，上限 %d 行" % (info.line_count, max_lines),
                )
            for line, candidate in imported_targets(info):
                target = layout.resolve(candidate)
                if target is None or not layout.is_domain(target.relative):
                    continue
                if layout.domain_key(target.relative) == domain.key:
                    continue
                add(
                    KIND_CROSS_DOMAIN,
                    info.relative,
                    "领域间 import：%s:%d import 了 %s（领域 %s 不得依赖领域 %s）"
                    % (
                        info.relative,
                        line,
                        target.relative,
                        domain.name,
                        layout.domain_of(target.relative),
                    ),
                    line=line,
                    target=target.relative,
                )

    for info in layout.shared_modules:
        if info.tree is None:
            add(
                KIND_UNPARSABLE,
                info.relative,
                "无法解析 %s：%s" % (info.relative, info.error),
                detail=info.error,
            )
            continue
        for line, candidate in imported_targets(info):
            target = layout.resolve(candidate)
            if target is None or not layout.is_domain(target.relative):
                continue
            add(
                KIND_SHARED_TO_DOMAIN,
                info.relative,
                "共享层 import 领域：%s:%d import 了 %s（共享层不得感知任何领域）"
                % (info.relative, line, target.relative),
                line=line,
                target=target.relative,
            )

    violations.sort(key=lambda item: (KIND_ORDER.get(item.kind, 9), item.source, item.line, item.target))
    return Report(
        root=root,
        domains=layout.domains,
        shared_modules=layout.shared_modules,
        violations=violations,
        max_lines=max_lines,
    )


def format_report(report):
    lines = []
    if report.domains:
        lines.append(
            "发现 %d 个领域路由目录：%s"
            % (len(report.domains), "、".join(domain.name for domain in report.domains))
        )
    else:
        lines.append("未发现领域路由模块，跳过领域边界与行数检查。")
    if report.shared_modules:
        lines.append(
            "共享层模块 %d 个：%s"
            % (len(report.shared_modules), "、".join(info.relative for info in report.shared_modules))
        )
    if report.violations:
        lines.append("")
        lines.append("发现 %d 处违规：" % len(report.violations))
        for violation in report.violations:
            lines.append("  - " + violation.message)
        lines.append("")
        lines.append("架构检查未通过（领域路由文件行数上限 %d 行）。" % report.max_lines)
    else:
        lines.append("架构检查通过。")
    return "\n".join(lines)


def build_parser():
    parser = argparse.ArgumentParser(
        description="检查后端领域拆分的三条硬约束：领域间无 import 边、共享层不 import 领域、领域路由文件不超行数上限。"
    )
    parser.add_argument("--root", default=None, help="仓库根目录，默认取本脚本所在仓库")
    parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LINES,
        help="单个领域路由文件的行数上限，默认 %(default)s",
    )
    parser.add_argument(
        "--shared",
        default=None,
        help="逗号分隔的共享层名字，默认 %s" % ",".join(DEFAULT_SHARED_NAMES),
    )
    return parser


def configure_output_encoding():
    """让 stdout 能输出中文。Windows 默认按本地代码页编码，控制台会是乱码。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    shared_names = DEFAULT_SHARED_NAMES
    if args.shared:
        shared_names = tuple(name.strip() for name in args.shared.split(",") if name.strip())
    if args.max_lines <= 0:
        parser.error("--max-lines 必须是正整数")
    root = Path(args.root).resolve() if args.root else REPO_ROOT
    if not root.is_dir():
        parser.error("仓库根目录不存在：%s" % root)

    report = check(root=root, max_lines=args.max_lines, shared_names=shared_names)
    configure_output_encoding()
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
