# -*- coding: utf-8 -*-
"""就业能力档案域的纯函数资产：AI 素材整理与「是否写过简历」口径。

从 app.py 迁出（T15）。两个函数都不 import 任何领域，只吃 `database` 契约层
返回的结构，因此可以安全地被就业对接域显式引用（见下面 user_has_resume 的说明）。
"""

def profile_for_ai(profile):
    """把能力档案整理成交给 AI 的纯文本素材。

    ⚠️ 只列**真实存在**的字段，缺项一律标注「（未填写）」而不是编一个合理值。
    证书必须带状态前缀，否则模型很容易把「学习中」写成「已获得」。
    """
    basic = profile.get('basic') or {}
    rows = [
        '姓名：%s' % (basic.get('name') or '（未填写）'),
        '所在地区：%s' % (basic.get('region') or '（未填写）'),
    ]

    learning = profile.get('learning')
    if learning:
        rows.append('平台学习方向：%s（课程完成度 %s%%）' % (
            learning.get('direction') or '（未填写）', learning.get('progress', 0)))
    else:
        rows.append('平台学习方向：（未填写）')

    certs = profile.get('certificates') or []
    if certs:
        parts = []
        for c in certs:
            status = (c.get('status') or '').lower()
            if c.get('earned'):
                tail = ('，取得时间 ' + c['date']) if c.get('date') else ''
                parts.append('%s（已获得%s）' % (c['name'], tail))
            elif status == 'in_progress':
                parts.append('%s（学习中，进度 %s%%，尚未获得）' % (c['name'], c.get('progress', 0)))
            else:
                parts.append('%s（未开始学习）' % c['name'])
        rows.append('平台学习证书：' + '；'.join(parts))
    else:
        rows.append('平台学习证书：（无）')

    scored = [t for t in (profile.get('training') or []) if t.get('scored')]
    if scored:
        rows.append('平台实训成绩：' + '；'.join('%s %s 分' % (t['title'], t['score']) for t in scored))
    else:
        rows.append('平台实训成绩：（无已评分记录）')

    if profile.get('points'):
        rows.append('平台学习积分：%s' % profile['points'])

    return '\n'.join(rows)


# 「是否已有简历」不在本域定义，而是转出共享层 shared.resume_state 的唯一实现。
# 原因：它有两个调用方，一个在本域（我的求职聚合），一个在就业对接域（投递成功的
# 提示）。spec 的边界件一节原本把它判给本域、由就业对接域显式引用，但
# 「领域路由模块之间不得互相 import」是 T01 的机械硬约束，直接引用必然违规。
# 这个判断本身零领域状态（只问 resumes 表里有没有填过内容），与 shared.options 同类，
# 放共享层既守住单一真相源，又不违反边界。两个域都从这里取，不会出现两份口径。
from shared.resume_state import user_has_resume  # noqa: F401

__all__ = ['profile_for_ai', 'user_has_resume']
