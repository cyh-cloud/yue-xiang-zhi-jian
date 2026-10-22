# -*- coding: utf-8 -*-
"""清理 styles.css 就业侧边栏死样式：用唯一行锚点定位块边界"""
import io, re

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\styles.css"
with io.open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def find_line(marker, start=0):
    for i in range(start, len(lines)):
        if marker in lines[i]:
            return i
    return -1

def find_next_rule(start):
    """从 start 行起找下一条以非空白开头且以 { 结尾的规则行（顶层选择器）"""
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s and not s.startswith('/*') and not s.startswith('*') and s.endswith('{') and not lines[i].startswith((' ', '\t')):
            return i
    return len(lines)

def delete_range(a, b, label):
    """删除 [a, b) 行（0基），含中间完整规则"""
    n = b - a
    del lines[a:b]
    print(f"[OK] {label}: removed {n} lines")

# --- 主块：从 '/* Sidebar */' 注释行到 '/* Detail Modal */' 注释行 ---
a = find_line('/* Sidebar */')
b = find_line('/* Detail Modal */')
assert a > 0 and b > a, (a, b)
delete_range(a, b, 'sidebar main block (/* Sidebar */ -> /* Detail Modal */)')
# 同时把 '/* Detail Modal */' 前面的空行规整（保留一个空行已由删除边界处理）

# --- 顶部 dark-mode 散行（倒序删除防错位）---
drops = [
    '[data-theme="dark"] .emp-startup-footer-link:hover',
    '[data-theme="dark"] .emp-startup-item-icon',
    '[data-theme="dark"] .emp-startup-item:hover',
    '[data-theme="dark"] .emp-points-exchange-grid .exchange-item:hover',
    '[data-theme="dark"] .emp-points-exchange-grid .exchange-item',
    '[data-theme="dark"] .emp-points-header',
    '[data-theme="dark"] .emp-stats-card',
    '[data-theme="dark"] .emp-sidebar-card',
    '[data-theme="dark"] .exchange-item',
]
for m in drops:
    i = find_line(m)
    if i >= 0:
        del lines[i]
        print(f"[OK] dark rule dropped: {m}")
    else:
        print(f"[MISS] not found: {m}")

# --- 媒体查询中的侧边栏规则行 ---
for m in [
    '.emp-sidebar { order: -1;',
    '.emp-stats-card { grid-column: 1 / -1; }',
    '.emp-sidebar { grid-template-columns: 1fr; }',
    '.emp-points-exchange-grid { grid-template-columns: repeat(3, 1fr); }',
]:
    i = find_line(m)
    if i >= 0:
        del lines[i]
        print(f"[OK] media rule dropped: {m}")
    else:
        print(f"[MISS] not found: {m}")

text = ''.join(lines)
text = re.sub(r'\n{4,}', '\n\n\n', text)
with io.open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("DONE")
