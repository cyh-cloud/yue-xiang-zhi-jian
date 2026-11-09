# -*- coding: utf-8 -*-
"""社区内容的敏感词初筛。

定位：**只做初筛，不直接拒绝**。命中后内容不进公开列表，转人工审核；词表必然
有误伤（「无抵押贷款」是黑产话术，「农业贷款」是正常讨论），机器判定不能替代
人的判断。真正拦人的是管理端的审核队列，这里只负责让可疑内容先停下来。

词表口径：平台治理类风险（涉赌、涉黄、诈骗与黑产、导流拉人、辱骂），
不涉及政治议题 —— 那不是社区运营能裁定的事，也不该由一份硬编码词表决定。

匹配做了归一化（NFKC 折半角、转小写、去掉空白与常见分隔符），
所以「赌 博」「赌*博」「ＱＱ」都能命中。代价是误伤率略升，
这正是「转人工」而不是「直接拒」的原因。
"""

import re
import unicodedata

# 词表按风险类型分组，便于运营后续替换成库表。新增词只加这里。
BLOCK_WORDS = (
    # 涉赌
    '赌博', '博彩', '赌场', '六合彩', '时时彩', '私彩', '下注', '庄家开盘',
    # 涉黄
    '裸聊', '约炮', '色情', '成人片', '一夜情', '楼凤',
    # 诈骗与黑产
    '刷单', '返利', '代开发票', '办假证', '假证', '洗钱', '套现',
    '无抵押贷款', '贷款包过', '高利贷', '暴力催收', '征信修复',
    '枪支', '毒品', '迷药', '炸药',
    # 导流拉人
    '加微信', '加qq', '私聊我', '扫码进群', '加群', '招代理', '代理加盟',
    '公众号关注', '日赚', '躺赚', '稳赚不赔',
    # 辱骂
    '傻逼', '操你妈', '草泥马', '贱人', '滚出去', '去死吧',
)

# 归一化时要去掉的字符：空白（含全角空格）、常见「插字」符号。
_SEPARATOR_RE = re.compile(r'[\s\u3000*_\-\.·,，、。!！?？~～|/\\@#$%^&()+=\[\]{}<>"\']+')

# 单次扫描的文本上限。帖子正文 5000 字、评论 1000 字，正常不会触发；
# 设上限是防止有人用超长文本把扫描拖慢（正则与逐词比对都是线性，但仍要兜底）。
MAX_SCAN_CHARS = 8000


def normalize(text):
    """NFKC 折半角 + 转小写 + 去掉分隔符。空值返回空串。"""
    if not text:
        return ''
    folded = unicodedata.normalize('NFKC', str(text)).lower()
    return _SEPARATOR_RE.sub('', folded)


def scan(*texts):
    """扫描若干段文本，返回命中的词（去重、保持词表顺序）。

    返回空列表表示可以正常发布。调用方拿这份列表写进 matched_words，
    审核人员据此判断是真违规还是误伤。
    """
    joined = normalize(' '.join(str(t or '') for t in texts))[:MAX_SCAN_CHARS]
    if not joined:
        return []
    hits = []
    for word in BLOCK_WORDS:
        if normalize(word) and normalize(word) in joined:
            hits.append(word)
    return hits


def describe(hits):
    """把命中词拼成给用户看的短句。不暴露完整词表，只回命中的那几个。"""
    if not hits:
        return ''
    return '、'.join(hits)


__all__ = ['BLOCK_WORDS', 'MAX_SCAN_CHARS', 'normalize', 'scan', 'describe']
