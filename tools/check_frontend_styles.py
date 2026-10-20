#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Frontend CSS ownership and legacy-style guardrails.

The checker is intentionally static: it reads active frontend sources and the
read-only reference tree, then reports boundary violations without changing
files. It is the mechanical companion to docs/css-style-ownership.md.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]

ACTIVE_SOURCE_ROOT = "frontend/src"
ACTIVE_INDEX = "frontend/index.html"
LEGACY_REFERENCE_ROOT = "legacy/reference"

TRANSITIONAL_LEGACY_SHEET = "frontend/src/styles/legacy-public.css"
TRANSITIONAL_LEGACY_IMPORTER = "frontend/src/main.ts"
REFERENCE_LEGACY_SHEET = "legacy/reference/frontend/legacy-public.css"

STYLE_EXTENSIONS = frozenset({".css", ".scss", ".sass", ".less", ".pcss"})
SOURCE_EXTENSIONS = frozenset(
    {
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".pcss",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".vue",
        ".html",
    }
)

BASE_LAYER_FILES = frozenset(
    {
        "frontend/src/styles/global.css",
        "frontend/src/styles/base.css",
        "frontend/src/styles/reset.css",
    }
)
BASE_LAYER_PREFIXES = ("frontend/src/styles/base/",)
TOKEN_LAYER_FILES = frozenset({"frontend/src/styles/tokens.css"})
SHELL_LAYER_FILES = frozenset(
    {
        "frontend/src/styles/public-shell.css",
        "frontend/src/styles/backoffice.css",
        "frontend/src/styles/community-shell.css",
    }
)
SHELL_LAYER_PREFIXES = ("frontend/src/layouts/",)

EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "coverage",
        "test-results",
        "playwright-report",
        "__pycache__",
    }
)

KIND_LEGACY_IMPORT = "legacy-style-import"
KIND_REFERENCE_HEADER = "legacy-reference-header"
KIND_CROSS_PAGE_STYLE = "cross-page-style-import"
KIND_GLOBAL_OVERRIDE = "universal-global-override"
KIND_RAW_ROLE_SELECTOR = "raw-role-selector"

KIND_ORDER = {
    KIND_LEGACY_IMPORT: 0,
    KIND_REFERENCE_HEADER: 1,
    KIND_CROSS_PAGE_STYLE: 2,
    KIND_GLOBAL_OVERRIDE: 3,
    KIND_RAW_ROLE_SELECTOR: 4,
}

TS_IMPORT_RE = re.compile(
    r"""(?<![\w@.])(?:import|export)\s+(?:[^"'`;]*?\s+from\s+)?["']([^"']+)["']"""
)
DYNAMIC_IMPORT_RE = re.compile(
    r"""(?<![\w@.])import\s*\(\s*["']([^"']+)["']\s*\)"""
)
CSS_IMPORT_RE = re.compile(
    r"""@import\s+(?:url\(\s*)?["']([^"']+)["']""",
    re.IGNORECASE,
)
STYLE_TAG_RE = re.compile(
    r"^[ \t]*<style\b(?P<attrs>[^>]*)>(?P<body>.*?)</style\s*>",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
ATTR_RE = re.compile(
    r"""([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"""
)
SELECTOR_RE = re.compile(r"([^{}]+)\{")
ROLE_SELECTOR_RE = re.compile(r"\[\s*data-role\b[^\]]*\]", re.IGNORECASE)


@dataclass(frozen=True)
class Violation:
    kind: str
    source: str
    line: int
    message: str
    target: str = ""


@dataclass
class Report:
    root: Path
    active_files: int = 0
    reference_files: int = 0
    violations: list[Violation] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


@dataclass(frozen=True)
class ImportRef:
    line: int
    specifier: str


@dataclass(frozen=True)
class StyleBlock:
    line: int
    text: str


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def iter_active_files(root: Path):
    source_root = root / ACTIVE_SOURCE_ROOT
    if source_root.is_dir():
        for dirpath, dirnames, filenames in os.walk(source_root):
            dirnames[:] = sorted(
                name for name in dirnames if name not in EXCLUDED_DIRS
            )
            for filename in sorted(filenames):
                path = Path(dirpath) / filename
                if path.suffix.lower() in SOURCE_EXTENSIONS:
                    yield relative_posix(path, root)
    index = root / ACTIVE_INDEX
    if index.is_file():
        yield ACTIVE_INDEX


def iter_reference_files(root: Path):
    reference_root = root / LEGACY_REFERENCE_ROOT
    if not reference_root.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(reference_root):
        dirnames[:] = sorted(
            name for name in dirnames if name not in EXCLUDED_DIRS
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.suffix.lower() in STYLE_EXTENSIONS:
                yield relative_posix(path, root)


def strip_css_comments(text: str) -> str:
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/", blank, text, flags=re.DOTALL)


def attrs_from_tag(attrs: str) -> dict[str, str]:
    result = {}
    for match in ATTR_RE.finditer(attrs):
        value = next(
            (group for group in match.groups()[1:] if group is not None),
            "",
        )
        result[match.group(1).lower()] = value
    return result


def extract_imports(relative: str, text: str) -> list[ImportRef]:
    imports = []
    for regex in (TS_IMPORT_RE, DYNAMIC_IMPORT_RE, CSS_IMPORT_RE):
        for match in regex.finditer(text):
            imports.append(
                ImportRef(text.count("\n", 0, match.start()) + 1, match.group(1))
            )

    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in {".vue", ".html"}:
        for match in STYLE_TAG_RE.finditer(text):
            attrs = attrs_from_tag(match.group("attrs"))
            source = attrs.get("src", "").strip()
            if source:
                imports.append(
                    ImportRef(
                        text.count("\n", 0, match.start()) + 1,
                        source,
                    )
                )
    if suffix == ".html":
        for match in LINK_TAG_RE.finditer(text):
            attrs = attrs_from_tag(match.group(0))
            rel = attrs.get("rel", "").lower().split()
            href = attrs.get("href", "").strip()
            if "stylesheet" in rel and href:
                imports.append(
                    ImportRef(
                        text.count("\n", 0, match.start()) + 1,
                        href,
                    )
                )
    return imports


def style_blocks(relative: str, text: str) -> list[StyleBlock]:
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in STYLE_EXTENSIONS:
        return [StyleBlock(1, text)]
    if suffix not in {".vue", ".html"}:
        return []

    blocks = []
    for match in STYLE_TAG_RE.finditer(text):
        attrs = attrs_from_tag(match.group("attrs"))
        if attrs.get("src"):
            continue
        body = match.group("body")
        body_start = match.start("body")
        blocks.append(
            StyleBlock(text.count("\n", 0, body_start) + 1, body)
        )
    return blocks


def resolve_specifier(source: str, specifier: str) -> str | None:
    value = specifier.strip().strip("\"'")
    url_match = re.fullmatch(r"url\(\s*[\"']?([^\"')]+)[\"']?\s*\)", value, re.I)
    if url_match:
        value = url_match.group(1)
    value = value.split("?", 1)[0].split("#", 1)[0].strip()
    if not value:
        return None
    if re.match(r"^(?:https?:)?//", value, re.I):
        return None
    if re.match(r"^(?:data:|mailto:|tel:|#)", value, re.I):
        return None
    if value.startswith("~"):
        return None
    if value.startswith("@/"):
        candidate = "frontend/src/" + value[2:]
    elif value.startswith("/"):
        candidate = "frontend/" + value.lstrip("/")
    else:
        candidate = posixpath.join(posixpath.dirname(source), value)
    return posixpath.normpath(candidate)


def is_style_target(specifier: str, target: str) -> bool:
    suffix = PurePosixPath(target).suffix.lower()
    return (
        suffix in STYLE_EXTENSIONS
        or PurePosixPath(target).name == "legacy-public.css"
        or "legacy/reference/" in specifier
    )


def is_legacy_target(target: str) -> bool:
    return (
        target == REFERENCE_LEGACY_SHEET
        or target.startswith(LEGACY_REFERENCE_ROOT + "/")
        or PurePosixPath(target).name == "legacy-public.css"
    )


def camel_words(value: str) -> list[str]:
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|\d|\b)|[A-Z]?[a-z]+|\d+", value)


def flat_view_domain(filename: str) -> str:
    stem = PurePosixPath(filename).stem
    if stem.endswith("View"):
        stem = stem[:-4]
    words = camel_words(stem)
    return words[0].lower() if words else ""


def page_domain(relative: str) -> str:
    parts = list(PurePosixPath(relative).parts)
    for marker in ("views", "pages", "components"):
        if marker not in parts:
            continue
        index = parts.index(marker)
        if index + 1 >= len(parts):
            continue
        candidate = parts[index + 1]
        if index + 1 == len(parts) - 1:
            return flat_view_domain(candidate)
        if candidate.lower() in {"shared", "common", "base"}:
            return ""
        return candidate.lower()
    return ""


def private_style_domain(target: str) -> str:
    if PurePosixPath(target).suffix.lower() not in STYLE_EXTENSIONS:
        return ""
    return page_domain(target)


def is_base_layer(relative: str) -> bool:
    return relative in BASE_LAYER_FILES or relative.startswith(BASE_LAYER_PREFIXES)


def is_token_layer(relative: str) -> bool:
    return relative in TOKEN_LAYER_FILES


def is_shell_layer(relative: str) -> bool:
    return relative in SHELL_LAYER_FILES or relative.startswith(SHELL_LAYER_PREFIXES)


def split_selector_list(selector: str) -> list[str]:
    parts = []
    start = 0
    depth = 0
    quote = ""
    for index, character in enumerate(selector):
        if quote:
            if character == quote and (index == 0 or selector[index - 1] != "\\"):
                quote = ""
            continue
        if character in {"'", '"'}:
            quote = character
        elif character in "([":
            depth += 1
        elif character in ")]":
            depth = max(depth - 1, 0)
        elif character == "," and depth == 0:
            parts.append(selector[start:index].strip())
            start = index + 1
    parts.append(selector[start:].strip())
    return [part for part in parts if part]


def selector_first_compound(selector: str) -> str:
    return re.split(r"[\s>+~]", selector.strip(), maxsplit=1)[0]


def is_global_override(selector: str) -> bool:
    first = selector_first_compound(selector)
    if not first:
        return False
    if "*" in first:
        return True
    if re.match(r"^(?:html|body|#app|:root)(?:\b|$|[\[.:#])", first):
        return True
    return bool(re.search(r"(^|[\s>+~,(])\*(?=$|[\s>+~.#:[,])", selector))


def is_shell_scoped_selector(selector: str) -> bool:
    return bool(
        re.search(
            r"\.(?:bo-shell|public-shell|community-shell)(?:\b|$|[\[.:#])",
            selector,
        )
    )


def check_reference_header(root: Path, report: Report) -> None:
    path = root / REFERENCE_LEGACY_SHEET
    if not path.is_file():
        return
    header = read_text(path)[:1600]
    missing = []
    if "历史参照" not in header:
        missing.append("历史参照")
    if "禁止活动代码引用" not in header:
        missing.append("禁止活动代码引用")
    if missing:
        report.violations.append(
            Violation(
                KIND_REFERENCE_HEADER,
                REFERENCE_LEGACY_SHEET,
                1,
                "只读旧样式文件头缺少标记：" + "、".join(missing),
            )
        )


def check_imports(
    relative: str,
    text: str,
    report: Report,
) -> None:
    for ref in extract_imports(relative, text):
        target = resolve_specifier(relative, ref.specifier)
        if target is None or not is_style_target(ref.specifier, target):
            continue
        if is_legacy_target(target):
            allowed = (
                relative == TRANSITIONAL_LEGACY_IMPORTER
                and target == TRANSITIONAL_LEGACY_SHEET
            )
            if not allowed:
                report.violations.append(
                    Violation(
                        KIND_LEGACY_IMPORT,
                        relative,
                        ref.line,
                        "活动代码不得引用只读旧样式；当前仅允许 main.ts 过渡期导入"
                        " frontend/src/styles/legacy-public.css",
                        target,
                    )
                )
            continue

        target_domain = private_style_domain(target)
        if not target_domain:
            continue
        source_domain = page_domain(relative)
        if source_domain != target_domain:
            report.violations.append(
                Violation(
                    KIND_CROSS_PAGE_STYLE,
                    relative,
                    ref.line,
                    "页面私有样式只能由同一页面域导入；"
                    f"来源域={source_domain or '(shared)'}，目标域={target_domain}",
                    target,
                )
            )


def check_style_blocks(
    relative: str,
    blocks: list[StyleBlock],
    report: Report,
) -> None:
    if relative == TRANSITIONAL_LEGACY_SHEET:
        return
    base_layer = is_base_layer(relative)
    token_layer = is_token_layer(relative)
    shell_layer = is_shell_layer(relative)
    for block in blocks:
        text = strip_css_comments(block.text)
        for match in SELECTOR_RE.finditer(text):
            raw_selector = match.group(1).strip()
            if not raw_selector or raw_selector.startswith("@"):
                continue
            line = block.line + text.count("\n", 0, match.start(1))
            for selector in split_selector_list(raw_selector):
                if ROLE_SELECTOR_RE.search(selector) and not (
                    shell_layer or token_layer
                ):
                    report.violations.append(
                        Violation(
                            KIND_RAW_ROLE_SELECTOR,
                            relative,
                            line,
                            "裸角色选择器 [data-role] 只允许出现在外壳或 token 层；"
                            "组件和页面通过根节点 token 消费角色主题",
                        )
                    )
                if not is_global_override(selector):
                    continue
                if base_layer or token_layer:
                    continue
                if shell_layer and is_shell_scoped_selector(selector):
                    continue
                report.violations.append(
                    Violation(
                        KIND_GLOBAL_OVERRIDE,
                        relative,
                        line,
                        "万能全局选择器只允许出现在基础层；外壳内必须由外壳根节点限定",
                    )
                )


def check(root: Path = REPO_ROOT) -> Report:
    root = Path(root).resolve()
    report = Report(root)

    for relative in iter_active_files(root):
        path = root / relative
        text = read_text(path)
        report.active_files += 1
        check_imports(relative, text, report)
        check_style_blocks(relative, style_blocks(relative, text), report)

    reference_files = list(iter_reference_files(root))
    report.reference_files = len(reference_files)
    check_reference_header(root, report)

    report.violations.sort(
        key=lambda item: (
            KIND_ORDER.get(item.kind, 99),
            item.source,
            item.line,
            item.message,
        )
    )
    return report


def format_report(report: Report) -> str:
    if report.ok:
        return (
            "CSS 样式检查通过：扫描 %d 个活动文件、%d 个只读参照样式文件。"
            % (report.active_files, report.reference_files)
        )
    lines = [
        "CSS 样式检查发现 %d 个问题：" % len(report.violations),
    ]
    for violation in report.violations:
        location = violation.source
        if violation.line:
            location += ":%d" % violation.line
        lines.append("- [%s] %s" % (violation.kind, location))
        lines.append("  %s" % violation.message)
        if violation.target:
            lines.append("  -> %s" % violation.target)
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="检查前端 CSS 归属、只读旧样式和全局覆盖边界。"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="仓库根目录，默认从本脚本位置推导",
    )
    args = parser.parse_args(argv)
    try:
        report = check(args.root)
    except OSError as error:
        print("CSS 样式检查无法读取文件：%s" % error, file=sys.stderr)
        return 2
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
