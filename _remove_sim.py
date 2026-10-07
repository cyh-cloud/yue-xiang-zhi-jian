#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 index.html 中删除虚拟实训沙盒整个 tab-content 块"""
import io

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\index.html"
with io.open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start = end = None
for i, ln in enumerate(lines):
    if "<!-- 虚拟实训沙盒 -->" in ln:
        start = i
    if "<!-- 本土化资源库 -->" in ln and start is not None:
        end = i
        break

assert start is not None and end is not None, "未找到标记"
# start 前如果有一个空行，也一并删除
new_lines = lines[:start] + lines[end:]
# 若删除后上一行是空行且上上行也是空行，去掉一个多余空行
out = []
for ln in new_lines:
    if ln.strip() == "" and out and out[-1].strip() == "":
        continue
    out.append(ln)

with io.open(path, "w", encoding="utf-8") as f:
    f.writelines(out)

print("removed lines:", start + 1, "-", end)
print("remaining total:", len(out))
