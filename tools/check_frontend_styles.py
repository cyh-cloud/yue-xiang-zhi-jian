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
COMPONENT_LAYER_FILES = frozenset({"frontend/src/styles/components.css"})
ACTIVE_ENTRY = "frontend/src/main.ts"
TOKENS_SHEET = "frontend/src/styles/tokens.css"
BASE_SHEET = "frontend/src/styles/base.css"
COMPONENTS_SHEET = "frontend/src/styles/components.css"
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
KIND_TOKEN_CONTRACT = "token-contract"
KIND_BASE_OWNERSHIP = "base-ownership"
KIND_SHARED_LAYER_ORDER = "shared-layer-order"
KIND_SHARED_ROOT_OVERRIDE = "shared-root-override"
KIND_PAGE_UNIVERSAL_OVERRIDE = "page-universal-override"
KIND_SHARED_PAGE_SELECTOR = "shared-page-selector"
KIND_SHARED_BACKOFFICE_SELECTOR = "shared-backoffice-selector"

KIND_ORDER = {
    KIND_LEGACY_IMPORT: 0,
    KIND_REFERENCE_HEADER: 1,
    KIND_CROSS_PAGE_STYLE: 2,
    KIND_GLOBAL_OVERRIDE: 3,
    KIND_RAW_ROLE_SELECTOR: 4,
    KIND_TOKEN_CONTRACT: 5,
    KIND_BASE_OWNERSHIP: 6,
    KIND_SHARED_ROOT_OVERRIDE: 7,
    KIND_PAGE_UNIVERSAL_OVERRIDE: 8,
    KIND_SHARED_PAGE_SELECTOR: 9,
    KIND_SHARED_BACKOFFICE_SELECTOR: 10,
    KIND_SHARED_LAYER_ORDER: 11,
}

SHARED_COMPONENT_MARKERS = (
    ".tag",
    ".modal-overlay",
    ".message-center-wrap",
    ".message-dropdown",
    ".conversation-send",
)

PAGE_OWNED_SELECTORS = {
    "agriculture": (
        (
            ".agriculture-qa-",
            "frontend/src/views/agriculture/agriculture.css",
        ),
        (
            ".example-btn",
            "frontend/src/views/agriculture/agriculture.css",
        ),
        (
            ".product-icon",
            "frontend/src/views/agriculture/agriculture.css",
        ),
        (
            ".diagnosis-",
            "frontend/src/views/agriculture/agriculture.css",
        ),
        (
            ".pest-",
            "frontend/src/views/agriculture/agriculture.css",
        ),
    ),
    "home": (
        (".hero", "frontend/src/views/home/home.css"),
        (".stat-number", "frontend/src/views/home/home.css"),
        (".stat-label", "frontend/src/views/home/home.css"),
        (".scroll-nav-", "frontend/src/views/home/home.css"),
        (
            ".startup-",
            "frontend/src/views/home/home.css",
        ),
    ),
    "ecommerce": (
        (
            ".copywriting-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (
            ".training-submit-info",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (".live-", "frontend/src/views/ecommerce/ecommerce.css"),
        (".ec-", "frontend/src/views/ecommerce/ecommerce.css"),
        (".cam-", "frontend/src/views/ecommerce/ecommerce.css"),
        (".script-", "frontend/src/views/ecommerce/ecommerce.css"),
        (".style-btn", "frontend/src/views/ecommerce/ecommerce.css"),
        (".score-pulse", "frontend/src/views/ecommerce/ecommerce.css"),
        (
            ".overall-score",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (
            ".feedback-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (".metric", "frontend/src/views/ecommerce/ecommerce.css"),
        (
            ".suggestion-tag",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (".comment-user", "frontend/src/views/ecommerce/ecommerce.css"),
        (
            ".record-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (
            ".simulation-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (".rubric-", "frontend/src/views/ecommerce/ecommerce.css"),
        (
            ".format-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (
            ".customer-service-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (".typing-", "frontend/src/views/ecommerce/ecommerce.css"),
        (
            ".training-history",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
        (
            ".progress-",
            "frontend/src/views/ecommerce/ecommerce.css",
        ),
    ),
    "login": (
        (
            ".auth-tabs",
            "frontend/src/views/login/login.css",
        ),
        (
            ".auth-tab",
            "frontend/src/views/login/login.css",
        ),
    ),
}

TOKEN_REQUIRED_GROUPS = {
    "brand": (
        "--color-brand",
        "--color-brand-strong",
        "--color-brand-soft",
        "--color-brand-tint",
    ),
    "accent": (
        "--color-accent-gold",
        "--color-accent-clay",
        "--color-accent-indigo",
        "--gradient-brand",
    ),
    "surface": (
        "--surface-canvas",
        "--surface-raised",
        "--surface-muted",
        "--surface-inverse",
        "--surface-inverse-strong",
    ),
    "text": (
        "--color-text-primary",
        "--color-text-secondary",
        "--color-text-muted",
        "--color-text-inverse",
    ),
    "border": (
        "--border-default",
        "--border-subtle",
        "--focus-ring-color",
    ),
    "spacing": tuple("--space-%d" % index for index in range(1, 8)),
    "radius": (
        "--radius-xs",
        "--radius-sm",
        "--radius",
        "--radius-full",
    ),
    "shadow": tuple("--shadow-%s" % size for size in ("xs", "sm", "md", "lg", "xl")),
    "layering": (
        "--z-base",
        "--z-navigation",
        "--z-dropdown",
        "--z-overlay",
        "--z-modal",
        "--z-toast",
    ),
    "typography": (
        "--font-family-display",
        "--font-family-ui",
        "--font-family-serif",
        "--font-size-root",
        "--font-size-body",
        "--line-height-body",
        "--text-base",
    ),
    "motion": (
        "--duration-fast",
        "--duration-normal",
        "--duration-slow",
        "--ease-out",
        "--ease-in-out",
        "--transition",
    ),
    "breakpoint": (
        "--breakpoint-xs",
        "--breakpoint-sm",
        "--breakpoint-md",
        "--breakpoint-lg",
        "--breakpoint-xl",
        "--breakpoint-2xl",
        "--breakpoint-content",
    ),
    "compatibility": (
        "--brand",
        "--bg-primary",
        "--text-primary",
        "--border",
        "--font",
        "--app-font",
        "--transition",
    ),
}

DARK_THEME_REQUIRED_TOKENS = (
    "--color-brand",
    "--surface-canvas",
    "--surface-raised",
    "--color-text-primary",
    "--border-default",
    "--shadow-md",
)

LARGE_TEXT_REQUIRED_TOKENS = (
    "--font-size-root",
    "--font-size-body",
    "--line-height-body",
)

BASE_REQUIRED_MARKERS = {
    "reset": (r"\*,\s*\*::before,\s*\*::after", "reset 选择器"),
    "app root": (r"#app", "#app 基础规则"),
    "focus": (r":focus-visible", "全站焦点规则"),
    "reduced motion": (r"prefers-reduced-motion", "减少动效规则"),
    "root font": (r"var\(--font-size-root\)", "根字号 token 消费"),
    "body font": (r"var\(--font-size-body\)", "正文字号 token 消费"),
    "body line height": (r"var\(--line-height-body\)", "正文行高 token 消费"),
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
TOKEN_DEFINITION_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:")
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


def selector_block_body(text: str, selector: str) -> str | None:
    pattern = re.compile(
        r"(?m)^[ \t]*" + re.escape(selector) + r"\s*\{(?P<body>.*?)^[ \t]*\}",
        re.DOTALL,
    )
    match = pattern.search(text)
    return match.group("body") if match else None


def token_definitions(text: str) -> set[str]:
    return set(TOKEN_DEFINITION_RE.findall(strip_css_comments(text)))


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


def is_component_layer(relative: str) -> bool:
    return relative in COMPONENT_LAYER_FILES


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
    stripped = selector.strip()
    if re.match(r"^html(?:\[[^\]]+\])+\s+#", stripped):
        return False
    first = selector_first_compound(selector)
    if not first:
        return False
    if "*" in first:
        return True
    if re.match(r"^(?:html|body|#app|:root)(?:\b|$|[\[.:#])", first):
        return True
    return bool(re.search(r"(^|[\s>+~,(])\*(?=$|[\s>+~.#:[,])", selector))


def is_page_universal_override(selector: str) -> bool:
    if re.match(r"^html(?:\[[^\]]+\])+\s+#", selector.strip()):
        return False
    return bool(
        re.match(r"^(?:body|html)(?=$|[\s\[.:#>+~,])", selector.strip())
    )


def is_shell_scoped_selector(selector: str) -> bool:
    return bool(
        re.search(
            r"\.(?:backoffice-shell|public-shell|community-shell)(?:\b|$|[\[.:#])",
            selector,
        )
    )


def shared_page_selector_owner(selector: str) -> tuple[str, str] | None:
    for domain, selectors in PAGE_OWNED_SELECTORS.items():
        for prefix, target in selectors:
            if prefix == ".hero":
                matched = re.search(
                    r"\.hero(?:[A-Za-z0-9_-]*)(?=$|[^A-Za-z0-9_-])",
                    selector,
                )
            elif prefix.endswith("-"):
                matched = re.search(
                    re.escape(prefix)
                    + r"(?:[A-Za-z0-9_-]*)(?=$|[^A-Za-z0-9_-])",
                    selector,
                )
            else:
                matched = re.search(
                    re.escape(prefix) + r"(?![A-Za-z0-9_-])",
                    selector,
                )
            if matched:
                return domain, target
    return None


def is_backoffice_selector(selector: str) -> bool:
    return bool(
        re.search(
            r"\.backoffice-(?:button|icon-button|field|status|card|table|feedback|state|modal)",
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


def check_style_contract(root: Path, report: Report) -> None:
    entry_path = root / ACTIVE_ENTRY
    if not entry_path.is_file():
        return

    tokens_path = root / TOKENS_SHEET
    if not tokens_path.is_file():
        report.violations.append(
            Violation(
                KIND_TOKEN_CONTRACT,
                TOKENS_SHEET,
                1,
                "活动 SPA 缺少全局语义 token 源",
            )
        )
    else:
        tokens_text = read_text(tokens_path)
        definitions = token_definitions(tokens_text)
        for group, required in TOKEN_REQUIRED_GROUPS.items():
            missing = [name for name in required if name not in definitions]
            if missing:
                report.violations.append(
                    Violation(
                        KIND_TOKEN_CONTRACT,
                        TOKENS_SHEET,
                        1,
                        "语义 token 分组缺少 %s：%s"
                        % (group, "、".join(missing)),
                    )
                )

        dark_body = selector_block_body(tokens_text, '[data-theme="dark"]')
        if dark_body is None:
            report.violations.append(
                Violation(
                    KIND_TOKEN_CONTRACT,
                    TOKENS_SHEET,
                    1,
                    "缺少暗色主题 token 覆盖",
                )
            )
        else:
            dark_tokens = token_definitions(dark_body)
            missing = [
                name
                for name in DARK_THEME_REQUIRED_TOKENS
                if name not in dark_tokens
            ]
            if missing:
                report.violations.append(
                    Violation(
                        KIND_TOKEN_CONTRACT,
                        TOKENS_SHEET,
                        1,
                        "暗色主题缺少 token：%s" % "、".join(missing),
                    )
                )

        large_text_body = selector_block_body(
            tokens_text,
            "html[data-large-text]",
        )
        if large_text_body is None:
            report.violations.append(
                Violation(
                    KIND_TOKEN_CONTRACT,
                    TOKENS_SHEET,
                    1,
                    "缺少大字模式 token 覆盖",
                )
            )
        else:
            large_text_tokens = token_definitions(large_text_body)
            missing = [
                name
                for name in LARGE_TEXT_REQUIRED_TOKENS
                if name not in large_text_tokens
            ]
            if missing:
                report.violations.append(
                    Violation(
                        KIND_TOKEN_CONTRACT,
                        TOKENS_SHEET,
                        1,
                        "大字模式缺少 token：%s" % "、".join(missing),
                    )
                )

    base_path = root / BASE_SHEET
    if not base_path.is_file():
        report.violations.append(
            Violation(
                KIND_BASE_OWNERSHIP,
                BASE_SHEET,
                1,
                "活动 SPA 缺少全局基础层",
            )
        )
    else:
        base_text = read_text(base_path)
        for label, (pattern, description) in BASE_REQUIRED_MARKERS.items():
            if not re.search(pattern, strip_css_comments(base_text)):
                report.violations.append(
                    Violation(
                        KIND_BASE_OWNERSHIP,
                        BASE_SHEET,
                        1,
                        "基础层缺少%s（%s）" % (description, label),
                    )
                )

    components_path = root / COMPONENTS_SHEET
    if not components_path.is_file():
        report.violations.append(
            Violation(
                KIND_SHARED_LAYER_ORDER,
                COMPONENTS_SHEET,
                1,
                "活动 SPA 缺少共享组件样式层",
            )
        )
    else:
        components_text = strip_css_comments(read_text(components_path))
        for marker in SHARED_COMPONENT_MARKERS:
            if marker not in components_text:
                report.violations.append(
                    Violation(
                        KIND_SHARED_LAYER_ORDER,
                        COMPONENTS_SHEET,
                        1,
                        "共享组件层缺少 %s 原语" % marker,
                    )
                )
        if ROLE_SELECTOR_RE.search(components_text):
            report.violations.append(
                Violation(
                    KIND_SHARED_LAYER_ORDER,
                    COMPONENTS_SHEET,
                    1,
                    "共享组件层不得包含裸角色选择器",
                )
            )
        if token_definitions(components_text):
            report.violations.append(
                Violation(
                    KIND_SHARED_LAYER_ORDER,
                    COMPONENTS_SHEET,
                    1,
                    "共享组件层不得重新定义 token；组件只消费 token",
                )
            )
        if "!important" in components_text:
            report.violations.append(
                Violation(
                    KIND_SHARED_LAYER_ORDER,
                    COMPONENTS_SHEET,
                    1,
                    "共享组件层不得依赖 !important",
                )
            )

    entry_text = read_text(entry_path)
    positions = {}
    for index, ref in enumerate(extract_imports(ACTIVE_ENTRY, entry_text)):
        target = resolve_specifier(ACTIVE_ENTRY, ref.specifier)
        if target in {
            TOKENS_SHEET,
            BASE_SHEET,
            COMPONENTS_SHEET,
        }:
            positions.setdefault(target, index)

    for target, label in (
        (TOKENS_SHEET, "tokens.css"),
        (BASE_SHEET, "base.css"),
    ):
        if target not in positions:
            report.violations.append(
                Violation(
                    KIND_BASE_OWNERSHIP,
                    ACTIVE_ENTRY,
                    1,
                    "main.ts 必须显式导入 %s" % label,
                    target,
                )
            )

    token_position = positions.get(TOKENS_SHEET)
    base_position = positions.get(BASE_SHEET)
    components_position = positions.get(COMPONENTS_SHEET)
    for target, label in (
        (TOKENS_SHEET, "tokens.css"),
        (BASE_SHEET, "base.css"),
        (COMPONENTS_SHEET, "components.css"),
    ):
        if target not in positions:
            report.violations.append(
                Violation(
                    KIND_SHARED_LAYER_ORDER,
                    ACTIVE_ENTRY,
                    1,
                    "main.ts 必须显式导入 %s" % label,
                    target,
                )
            )
    if (
        components_position is not None
        and base_position is not None
        and components_position < base_position
    ):
        report.violations.append(
            Violation(
                KIND_SHARED_LAYER_ORDER,
                ACTIVE_ENTRY,
                1,
                "components.css 必须晚于 base.css 导入",
            )
        )
    if (
        token_position is not None
        and base_position is not None
        and token_position > base_position
    ):
        report.violations.append(
            Violation(
                KIND_BASE_OWNERSHIP,
                ACTIVE_ENTRY,
                1,
                "tokens.css 必须早于 base.css 导入",
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
            report.violations.append(
                Violation(
                    KIND_LEGACY_IMPORT,
                    relative,
                    ref.line,
                    "活动代码不得引用只读旧样式",
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
    base_layer = is_base_layer(relative)
    token_layer = is_token_layer(relative)
    component_layer = is_component_layer(relative)
    shell_layer = is_shell_layer(relative)
    for block in blocks:
        text = strip_css_comments(block.text)
        for match in SELECTOR_RE.finditer(text):
            selector_text = match.group(1)
            raw_selector = selector_text.strip()
            if not raw_selector or raw_selector.startswith("@"):
                continue
            leading = len(selector_text) - len(selector_text.lstrip())
            selector_start = match.start(1) + leading
            line = block.line + text.count("\n", 0, selector_start)
            for selector in split_selector_list(raw_selector):
                owner = (
                    shared_page_selector_owner(selector)
                    if component_layer
                    else None
                )
                if component_layer and is_backoffice_selector(selector):
                    report.violations.append(
                        Violation(
                            KIND_SHARED_BACKOFFICE_SELECTOR,
                            relative,
                            line,
                            "共享组件层不得定义后台专属选择器；"
                            f"命中选择器：{selector}；"
                            "建议归属层：frontend/src/styles/backoffice.css",
                            "frontend/src/styles/backoffice.css",
                        )
                    )
                if owner is not None:
                    domain, target = owner
                    report.violations.append(
                        Violation(
                            KIND_SHARED_PAGE_SELECTOR,
                            relative,
                            line,
                            f"共享组件层不得定义 {domain} 页面私有选择器；"
                            f"命中选择器：{selector}；"
                            f"建议归属层：{target}",
                            target,
                        )
                    )
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
                if component_layer and is_global_override(selector):
                    report.violations.append(
                        Violation(
                            KIND_SHARED_ROOT_OVERRIDE,
                            relative,
                            line,
                            "共享组件层不得定义 html / body / #app / :root "
                            "根布局或全站覆盖；"
                            f"命中选择器：{selector}；"
                            "建议归属层：base.css 或对应外壳样式",
                        )
                    )
                    continue
                if (
                    not (base_layer or token_layer or shell_layer)
                    and is_page_universal_override(selector)
                ):
                    report.violations.append(
                        Violation(
                            KIND_PAGE_UNIVERSAL_OVERRIDE,
                            relative,
                            line,
                            "页面级万能覆盖不得直接以 html 或 body 开头的"
                            "全局组合选择器表达；"
                            f"命中选择器：{selector}；"
                            "建议归属层：页面根选择器或对应外壳根节点",
                        )
                    )
                    continue
                if component_layer:
                    continue
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
                        "万能全局选择器只允许出现在基础层；"
                        f"命中选择器：{selector}；"
                        "外壳内必须由外壳根节点限定",
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

    check_style_contract(root, report)

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
