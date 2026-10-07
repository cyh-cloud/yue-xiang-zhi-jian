#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删除 script.js 中 直播间实训 与 手工AR指导 两个代码段（到 电商模块 标记前）"""
import io

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\script.js"
with io.open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start = end = None
for i, ln in enumerate(lines):
    if "==================== 直播间实训" in ln and start is None:
        start = i
    if "==================== 电商模块 ====================" in ln and start is not None:
        end = i
        break

assert start is not None and end is not None, "未找到标记"

# end 前如果有一个空行，则该空行保留（电商模块标记前需要空行分隔，直接截到 end 即可）
new_lines = lines[:start] + lines[end:]
# 压缩多余连续空行
out = []
for ln in new_lines:
    if ln.strip() == "" and out and out[-1].strip() == "":
        continue
    out.append(ln)

with io.open(path, "w", encoding="utf-8") as f:
    f.writelines(out)

print("removed lines:", start + 1, "-", end)
print("remaining total:", len(out))
