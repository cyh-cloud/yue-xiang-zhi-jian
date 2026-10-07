#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""styles.css 清理：删除直播间实训与手工AR指导的无效样式，清理 dark mode 残留"""
import io

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\styles.css"
with io.open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start = end = None
for i, ln in enumerate(lines):
    if "/* 直播间实训 */" in ln and start is None:
        start = i
    if "/* Upload area (for photo upload) */" in ln and start is not None:
        end = i
        break
assert start is not None and end is not None
lines[start:end] = []

text = "".join(lines)

# 清理 dark mode 中已无对应元素的规则
text = text.replace('[data-theme="dark"] .scenario-card { background: var(--bg-tertiary); border-color: var(--border); }\n', '')
text = text.replace('[data-theme="dark"] .practice-input-area textarea { background: var(--bg-tertiary); border-color: var(--border); color: var(--text-primary); }\n', '')
text = text.replace('[data-theme="dark"] .practice-score { background: var(--bg-secondary); border-color: var(--border); }\n', '')
text = text.replace('[data-theme="dark"] .score-metric-item { background: var(--bg-tertiary); }\n', '')
text = text.replace('[data-theme="dark"] .guide-section li::before, [data-theme="dark"] .diagnosis-section li::before',
                    '[data-theme="dark"] .diagnosis-section li::before')

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("done, total lines:", len(text.splitlines()))
