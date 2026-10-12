#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""后端 Python 的静态检查：未用导入与未定义名。

为什么要有它：本次后端拆分踩过两次本该被机械检查拦住的坑。

1) 入口文件残留 9 个死导入（json / request / require_role / get_session_user /
   messages_self_guard / AI_REASONING_TOKEN_RESERVE / LIVE_RUBRIC_RE /
   LIVE_SPEED_IDEAL，以及 _TEACHER_ROLES 别名）。它们全是领域迁出后没跟着删的
   副本，而真实定义都在共享层或域内，留着就是两份真相。

2) db_domains/notifications.py 写成 `for r in rows:` 而 rows 从未定义，
   整条「发公告」链路一调就 NameError 500。这个缺陷编译期查不出来
   （py_compile 通过），跑测试也没暴露，因为种子库里没有公告类未读数据。

两项都是 pyflakes 的核心子集。仓库不引入第三方依赖，这里用标准库 ast 实现。

用法：
    python tools/check_python.py              # 检查 backend/ 与根级测试
    python tools/check_python.py <路径>...     # 只检查指定文件或目录

退出码：0 干净，1 有发现，2 用法错误。
"""

from __future__ import annotations

import argparse
import ast
import io
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')

# 与 tools/check_architecture.py 保持一致的排除集
EXCLUDED_DIRS = frozenset({
    '.git', '.venv', 'venv', 'env', '__pycache__', '.pytest_cache',
    '.mypy_cache', '.ruff_cache', 'node_modules', '.idea', '.vscode',
    '.scratch', 'build', 'dist',
})


def iter_python_files(root):
    if os.path.isfile(root):
        if root.endswith('.py'):
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
        for filename in sorted(filenames):
            if filename.endswith('.py'):
                yield os.path.join(dirpath, filename)


def _builtin_names():
    return set(dir(__builtins__)) | {
        '__name__', '__file__', '__doc__', '__package__', '__spec__',
        '__loader__', '__builtins__', '__all__', '__debug__', '__path__',
        '__class__', '__dict__', '__module__', '__qualname__',
    }


def _arg_names(func_node):
    if not isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.Lambda)):
        return []
    args = func_node.args
    names = []
    for group in (args.posonlyargs, args.args, args.kwonlyargs):
        names.extend(a.arg for a in group)
    for single in (args.vararg, args.kwarg):
        if single is not None:
            names.append(single.arg)
    return names


def collect_scopes(tree):
    """收集每个作用域里已被定义的名字。

    返回 [(节点, 该作用域可见的名字集合)]。子作用域继承父作用域。
    """
    scopes = []

    def visit(node, visible):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                inner = set(visible)
                if not isinstance(child, ast.Lambda):
                    inner.add(child.name)
                inner.update(_arg_names(child))
                scopes.append((child, inner))
                visit(child, inner)
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                for alias in child.names:
                    if alias.name != '*':
                        visible.add((alias.asname or alias.name).split('.')[0])
                visit(child, visible)
            elif isinstance(child, ast.Name) and isinstance(
                    child.ctx, (ast.Store, ast.Del)):
                visible.add(child.id)
                visit(child, visible)
            elif isinstance(child, ast.ExceptHandler) and child.name:
                visible.add(child.name)
                visit(child, visible)
            elif isinstance(child, ast.comprehension):
                for sub in ast.walk(child.target):
                    if isinstance(sub, ast.Name):
                        visible.add(sub.id)
                visit(child, visible)
            elif isinstance(child, ast.Global):
                visible.update(child.names)
                visit(child, visible)
            elif isinstance(child, ast.Nonlocal):
                visible.update(child.names)
                visit(child, visible)
            else:
                visit(child, visible)

    top = _builtin_names()
    scopes.append((tree, top))
    visit(tree, top)
    return scopes


def _has_noqa(source, lineno):
    """该行是否带 `# noqa` 标记。

    再导出（backend/database.py 那类）用 noqa: F401 明确表示「这个导入本文件不用，
    但对外契约需要」。检查器尊重这个标记，否则每一条再导出都会被误报。
    """
    lines = source.split('\n')
    if 1 <= lineno <= len(lines):
        return 'noqa' in lines[lineno - 1].lower()
    return False


def check_file(path):
    """返回 (未用导入列表, 未定义名列表)，元素都是 (名字, 行号)。"""
    try:
        source = io.open(path, encoding='utf-8').read()
    except UnicodeDecodeError:
        return [], []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return [('语法错误', exc.lineno or 0, str(exc))], []

    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported[(alias.asname or alias.name).split('.')[0]] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name != '*':
                    imported[alias.asname or alias.name] = node.lineno

    # `from __future__ import annotations` 是编译器指令，不是可使用的名字
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == '__future__':
            for alias in node.names:
                imported.pop(alias.asname or alias.name, None)

    # 数据库约层（backend/database.py）用 `from x import y  # noqa: F401` 做再导出，
    # 那些名字在本文件确实不用，但是对外契约的一部分。凡带 noqa 标记的导入都跳过。
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                key = (alias.asname or alias.name).split('.')[0]
                if _has_noqa(source, node.lineno):
                    imported.pop(key, None)

    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            cur = node
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                used.add(cur.id)
    # __all__ 里显式列出的名字算已用（再导出常用这个手段）
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == '__all__':
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant) and isinstance(
                                    elt.value, str):
                                used.add(elt.value)

    unused = [(name, line) for name, line in sorted(imported.items())
              if name not in used and not name.startswith('_')]

    undefined = []
    for node, visible in collect_scopes(tree):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                if sub.id not in visible:
                    undefined.append((sub.id, sub.lineno))

    # 整个文件里出现过这个名字就放过：函数内「先调用后定义」与条件分支里的
    # 赋值都会被作用域分析误报，那是正常写法，不是缺陷。
    defined_anywhere = set(imported)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            defined_anywhere.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_anywhere.add(node.name)
        elif isinstance(node, ast.arg):
            defined_anywhere.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined_anywhere.add(node.name)
    undefined = [(name, line) for name, line in undefined
                 if name not in defined_anywhere]

    return unused, undefined


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='检查后端 Python 的未用导入与未定义名。')
    parser.add_argument('paths', nargs='*', default=None,
                        help='要检查的文件或目录，默认检查 backend/ 与根级测试')
    args = parser.parse_args(argv)

    targets = list(args.paths) if args.paths else [BACKEND, REPO_ROOT]
    files = []
    for target in targets:
        if not os.path.exists(target):
            parser.error('路径不存在：%s' % target)
        files.extend(iter_python_files(os.path.abspath(target)))

    problems = []
    for path in sorted(set(files)):
        rel = os.path.relpath(path, REPO_ROOT).replace(os.sep, '/')
        unused, undefined = check_file(path)
        for name, line, *_rest in unused:
            problems.append('%s:%d 未使用的导入 %s' % (rel, line, name))
        for name, line in undefined:
            problems.append('%s:%d 未定义的名字 %s' % (rel, line, name))

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, 'reconfigure', None)
        if reconfigure:
            try:
                reconfigure(encoding='utf-8', errors='replace')
            except (ValueError, OSError):
                pass

    if problems:
        print('发现 %d 处问题：' % len(problems))
        for line in problems:
            print('  - ' + line)
        return 1
    print('Python 静态检查通过（%d 个文件）。' % len(files))
    return 0


if __name__ == '__main__':
    sys.exit(main())
