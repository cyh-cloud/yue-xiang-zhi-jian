# -*- coding: utf-8 -*-
"""清理 styles.css 中就业侧边栏死样式"""
import io, re

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\styles.css"
with io.open(path, 'r', encoding='utf-8') as f:
    text = f.read()

def cut(text, start_marker, end_marker, label, exclusive_end=True):
    s = text.find(start_marker)
    if s < 0:
        print(f"[FAIL] {label}: start not found"); return text, False
    e = text.find(end_marker, s)
    if e < 0:
        print(f"[FAIL] {label}: end not found"); return text, False
    if not exclusive_end:
        e += len(end_marker)
    lines = text[s:e].count('\n') + 1
    text = text[:s] + text[e:]
    print(f"[OK] {label}: removed ~{lines} lines")
    return text, True

ok = True

# 1. 侧边栏卡片样式块：.emp-stats-card 到 .emp-job-list 之前（先确认下一个锚点）
# 查找 .emp-stats-card 之后的下一个主要选择器
idx = text.find('.emp-stats-card')
print("next 400 chars after .emp-stats-card:")
print(text[idx:idx+100].replace('\n', '\\n'))
