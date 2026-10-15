#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后端领域拆分的机械检查。只读代码，不修改任何文件。

一条命令判定四件事：

1. 领域路由模块之间没有 import 边（一律禁止，与能力无关）；
2. 领域路由模块 import 数据层模块（db_domains/）按能力表判权：该能力域的 read
   公开，或调用方所在域声明了它的 manage 能力，否则报 violation；
2. 共享层模块不 import 领域路由模块；
3. 单个领域路由文件不超过 600 行。

第 2 条的判据是 backend/core/permissions.py 的 CAPABILITIES 表，本文件不复制第二份：
能力表改了，判定结果跟着改，检查器不用动。调用方「声明了某个能力」的判据是它的代码里
出现了 @require_capability('<域>.manage')；被调方「属于哪个能力域」的判据是它模块级的
CAPABILITY = '<域>'。ADR 0002 把 ADR 0001 的「领域之间不得互相 import」修为「不得访问
不具有该角色权限的数据」，这里就是那条修订的机械形式。

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
import re
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

# 数据层模块所在的目录。判权只对「领域路由模块 -> 这里的模块」这条边生效。
DATA_MODULE_PREFIX = "db_domains/"

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


def declared_capabilities(info):
    """本模块声明的能力集：require_capability('x.manage') 装饰器，加上登录护栏。

    只认 `@require_capability('...')` 这一种写法（含 core.permissions.require_capability
    前缀），与 permissions.require_capability 的签名逐字对应。

    另外认 SESSION_GUARDS 里的会话取用户与身份护栏：它们不指向具体能力名，
    但意味着「本模块要求已登录」。判权时遇到这类模块，见 capability_verdict
    的登录兜底分支。
    """
    if info.tree is None:
        return frozenset()
    names = set()
    for node in info.tree.body:
        # 模块级显式声明：CAPABILITIES_USED = ('auth.read', 'user.read')
        # 给「读别人的域但不走 require_capability 装饰器」的域一个声明位置，
        # 免得为了满足机械检查去改鉴权代码路径。
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "CAPABILITIES_USED"
                for t in node.targets):
            names.update(_string_literals(node.value))
    for node in ast.walk(info.tree):
        if not isinstance(node, ast.Call):
            continue
        if callee_name(node.func).rsplit(".", 1)[-1] != "require_capability":
            continue
        if len(node.args) != 1 or not isinstance(node.args[0], ast.Constant):
            continue
        if isinstance(node.args[0].value, str):
            names.add(node.args[0].value)
    return frozenset(names)


def _string_literals(node):
    """收集表达式里全部字符串字面量（元组 / 列表 / 集合 / 单个常量都认）。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out = []
        for item in node.elts:
            out.extend(_string_literals(item))
        return out
    return []


def load_capabilities():
    """能力表：backend/core/permissions.py 的 CAPABILITIES。

    判定所依据的表只有这一份，本模块不复制。导入失败（例如只给了 --root 指向的
    临时目录）时返回空表，此时一切受管数据模块都判为越界，宁可误报也不放过。
    """
    import importlib.util

    path = REPO_ROOT / "core" / "permissions.py"
    spec = importlib.util.spec_from_file_location("_arch_permissions", path)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except (ImportError, OSError, SyntaxError):
        return {}
    table = getattr(module, "CAPABILITIES", None)
    return dict(table) if isinstance(table, dict) else {}


def capability_of_module(target):
    """数据层模块声明的 CAPABILITY，空串表示它不拥有任何能力域。"""
    if target.tree is None:
        return ""
    for node in target.tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target_name = node.targets[0]
        if not (isinstance(target_name, ast.Name) and target_name.id == "CAPABILITY"):
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return ""


def capability_verdict(domain, target, capabilities):
    """领域路由模块 import 数据层模块是否越界。返回 (是否越界, 说明文字)。

    判据（ADR 0002 / spec 5.1）：
    1. 数据层模块不声明 CAPABILITY：无法判定它属于哪个能力域，一律报违规；
    2. CAPABILITY 为空串：取数窄接口（profile_sources），不拥有能力域，放行；
    3. 该能力域的 read 能力是空元组（公开）：放行；
    4. 调用方所在域声明了它的 read 或 manage 能力：放行；
    5. 其余报违规。
    """
    capability = capability_of_module(target)
    if capability == "":
        if _declares_capability_constant(target):
            # 取数窄接口：它刻意不拥有任何能力域，数据来自多个域，由拼装方负责权限。
            return False, ""
        return (
            True,
            "%s 没有声明 CAPABILITY，无法判定它属于哪个能力域" % target.relative,
        )
    read_holders = capabilities.get(capability + ".read")
    if read_holders is not None and not read_holders:
        # 空元组 = 公开：任何身份（含未登录）都能读，谁 import 都不算越界。
        return False, ""
    # read 是受限元组或不在表里：调用方必须显式持有该域的 read 或 manage。
    # 两条都认，因为「读别人的域」与「管别人的域」是两件事：teacher 域读学员
    # 名册只需 student.read，不该为了读一份名册就把 student.manage 也给它。
    # read 与 manage 双双缺席（例如拼错能力名）时没人声明得了，必然判越界，
    # 不会因为默认放行而开出一个暗门。
    declared = domain_capabilities(domain)
    if capability + ".read" in declared or capability + ".manage" in declared:
        return False, ""
    # 没有「已登录就放行」这条兜底路。它会把结构性越界整个漏掉：任何登录域
    # 都能读任何全角色域，等于没有边界（实测：给 auth 域加一句
    # import db_domains.users 也会被放行）。域要读别人的数据，就显式声明
    # @require_capability('<域>.read')，让边界写在代码里、让检查器有据可判。
    return True, "读 %s 的数据需要 %s.read 或 %s.manage，%s 两个都没有持有" % (
        capability, capability, capability, domain.name)


def _declares_capability_constant(target):
    """模块顶层是否写了 CAPABILITY = <字面量>（值可以不是字符串）。"""
    return any(
        isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "CAPABILITY" for t in node.targets
        )
        for node in (target.tree.body if target.tree else [])
    )


def domain_capabilities(domain):
    """调用方所在域声明的能力集：域内任一模块声明的都算。

    按域聚合而不是按模块，因为同一个域里常常是 routes.py 挂装饰器、别的文件取数，
    「能力声明在哪个文件」是实现细节，边界按域画才抓得住越界。
    """
    names = set()
    for module in domain.modules:
        names.update(declared_capabilities(module))
    return frozenset(names)


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

    def is_data_module(self, relative):
        """是不是数据层模块（db_domains/ 下的 .py）。"""
        return relative.startswith(DATA_MODULE_PREFIX)

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


def check(root=None, max_lines=DEFAULT_MAX_LINES, shared_names=DEFAULT_SHARED_NAMES,
          capabilities=None):
    root = Path(root).resolve() if root else REPO_ROOT
    layout = Layout(root, shared_names)
    if capabilities is None:
        capabilities = load_capabilities()
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
                    if target is None or not layout.is_data_module(target.relative):
                        continue
                    # 领域路由模块 -> 数据层模块：按能力表判权，不再一律禁止。
                    crossed, reason = capability_verdict(domain, target, capabilities)
                    if crossed:
                        add(
                            KIND_CROSS_DOMAIN,
                            info.relative,
                            "领域间越界 import：%s:%d import 了 %s（%s）"
                            % (info.relative, line, target.relative, reason),
                            line=line,
                            target=target.relative,
                        )
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


def check_blueprint_wiring(root=None):
    """第四条检查：蓝图接线一致性。

    domains/__init__.py 导出、core/app_factory 注册、静态蓝图排最后，三者必须对齐。
    T11/T12 并行提交后合并时漏掉过 pest_bp 的导出与注册，症状是应用启动即
    NameError、196 项单测 error。这类漏项在单个 worktree 里看不出来，只有合并后
    才炸，所以值得单独查。
    """
    root = Path(root).resolve() if root else REPO_ROOT
    domains_init = root / "domains" / "__init__.py"
    factory = root / "core" / "app_factory.py"
    if not domains_init.is_file() or not factory.is_file():
        return []

    init_text = domains_init.read_text(encoding="utf-8")
    exported = set(re.findall(r"^from domains\.\w+ import (\w+)",
                              init_text, re.MULTILINE))
    match = re.search(r"__all__ = \[(.*?)\]", init_text, re.S)
    listed = set(re.findall(r"'(\w+)'", match.group(1))) if match else set()

    factory_text = factory.read_text(encoding="utf-8")
    order = re.findall(r"app\.register_blueprint\((\w+)\)", factory_text)

    problems = []
    for name in sorted(exported - listed):
        problems.append("domains/__init__.py 导出了 %s 但没列入 __all__" % name)
    for name in sorted(listed - exported):
        problems.append("domains/__init__.py 的 __all__ 列了 %s 但没有对应导入" % name)
    for name in sorted(listed - set(order)):
        problems.append("%s 已导出但 core/app_factory 没有注册它" % name)
    for name in sorted(set(order) - listed):
        problems.append("core/app_factory 注册了 %s 但它没被 domains/__init__ 导出" % name)
    if order and order[-1] != "static_bp":
        problems.append("静态蓝图必须最后注册（当前最后是 %s），否则 /<path:filename> "
                        "可能吞掉具体路由" % order[-1])
    return problems


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
    wiring = check_blueprint_wiring(root=root)
    if wiring:
        print()
        print("蓝图接线有 %d 处问题：" % len(wiring))
        for line in wiring:
            print("  - " + line)
    return 0 if (report.ok and not wiring) else 1


if __name__ == "__main__":
    sys.exit(main())
