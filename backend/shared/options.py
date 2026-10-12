# -*- coding: utf-8 -*-
"""下拉选项拼装：把 `{分类: 条数}` 变成前端下拉要的 `[{"value","count"}]`。
"""


def category_option_list(counts, known):
    """`{分类: 条数}` → `[{"value","count"}]`。

    `known` 里的分类**即使 0 条也保留**（前端标「（暂无）」）——
    把死分类直接从下拉里删掉，学员会以为平台不支持这类岗位；
    而数据里冒出来的新分类（企业端分类是自由文本）追加在后面，不漏。
    顺序固定为 `known` 原始顺序，避免条数变化时选项来回跳。
    """
    vals = list(known)
    vals += [k for k in counts if k not in vals]
    return [{"value": k, "count": counts.get(k, 0)} for k in vals]


__all__ = ['category_option_list']
