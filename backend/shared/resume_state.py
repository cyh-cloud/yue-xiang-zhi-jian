# -*- coding: utf-8 -*-
"""「是否已有简历」的唯一口径。

T15 从 app.py 的 `_user_has_resume` 上提到共享层。原因是 spec 的边界件一节原本把
它判给就业能力档案域、就业对接域显式引用，但「领域路由模块之间不得互相 import」
是一条机械检查的硬约束（T01），两个领域都要用它，直接引用必然违规。

这个判断本身零领域状态：它只问「resumes 表里这个用户有没有填过内容」，
与「这是就业对接还是就业能力档案」无关，和同层的 shared/options.py、
shared/copywriting.py 一样是可以放在共享层的纯函数。数据访问仍走 database 契约层，
共享层不 import 任何领域路由模块。
"""

import database


def user_has_resume(user_id):
    """学员是否填过简历（判断「有内容」而非「有行」：只有意向岗位或任一正文段才算）。

    两个调用方必须同源同口径：投递成功的提示要据此补一句「你还没有填写简历」
    （否则学员以为简历已随申请投出去），「我的求职」要据此给出持久提示。
    分成两份实现必然漂移，因此只有这一处。
    """
    r = database.get_resume(user_id) or {}
    keys = ('title', 'region', 'education', 'work_years', 'self_eval',
            'skills', 'experience', 'phone', 'email')
    return any((r.get(k) or '').strip() for k in keys)


__all__ = ['user_has_resume']
