# -*- coding: utf-8 -*-
"""统一社会信用代码的规范化与校验位计算（GB 32100-2015）。

为什么要校验位：企业注册时手填 18 位代码，肉眼复核成本极高，而代码本身自带
一位校验码。离线算一遍就能挡掉绝大多数手误与随手编的号码，不需要联网、不需要
第三方服务。**它证明不了企业真实存在**，只能说明「这串字符自洽」——真实性仍以
营业执照照片与人工审核为准，两者不能互相替代。

算法（标准第 5.2 条）：
  · 字符集 31 个，去掉易混的 I、O、S、V、Z；
  · 第 1~17 位按固定权重加权求和；
  · 校验码 = 31 − (和 mod 31)，得 31 时记 0；
  · 第 18 位必须等于该值。
"""

CHARSET = '0123456789ABCDEFGHJKLMNPQRTUWXY'
WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
LENGTH = 18


def normalize(value):
    """去空白、转大写。只做格式规范化，不做合法性判断。"""
    return ''.join((value or '').split()).upper()


def is_valid(value):
    """长度、字符集、校验位三项全过才算合法。"""
    code = normalize(value)
    if len(code) != LENGTH:
        return False
    if any(ch not in CHARSET for ch in code):
        return False
    total = 0
    for index, ch in enumerate(code[:17]):
        total += CHARSET.index(ch) * WEIGHTS[index]
    check = 31 - (total % 31)
    if check == 31:
        check = 0
    return code[17] == CHARSET[check]


def mask(value):
    """展示用脱敏：保留前 4 后 4，中间打码。太短的原样返回。"""
    code = normalize(value)
    if len(code) <= 8:
        return code
    return code[:4] + '*' * (len(code) - 8) + code[-4:]


__all__ = ['CHARSET', 'WEIGHTS', 'LENGTH', 'normalize', 'is_valid', 'mask']
