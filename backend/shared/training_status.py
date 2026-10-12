# -*- coding: utf-8 -*-
"""实训提交状态的中文标签。

T16 从 app.py 与 domains/live_training/routes.py 上提到共享层。原因是 spec 的
「边界件归属」一节把 `_training_status_label` 判给直播实训域、实训批改域显式引用，
但「领域路由模块之间不得互相 import」是一条机械检查的硬约束（T01），两个领域都要
用它，直接引用必然违规。它零领域状态：只是一张 status 到中文文案的查表，
与「这是直播实训还是教师批改」无关，和同层的 shared/options.py、
shared/copywriting.py 一样是可以放在共享层的纯函数。

提上来之前它已经是两份实现（app.py 一份随 T13 被删、live_training 一份留下），
属于典型的「两份真相」：改一处忘另一处，学员端与教师端就会显示不同状态文案。
现在全站只有这一份。
"""

# 实训提交状态 → 中文标签（学员端与教师端共用，避免两处各写一套字符串）
TRAINING_STATUS_LABELS = {
    'pending': '待提交',
    'submitted': '待批改',
    'graded': '已批改',
    'resubmitted': '已重新提交·待复核',
}

# 未知状态一律按「待批改」显示：宁可让教师看到一条待处理项，
# 也不要把一个已提交的作业显示成「待提交」而漏批。
_DEFAULT_LABEL = '待批改'


def training_status_label(status):
    return TRAINING_STATUS_LABELS.get((status or '').strip(), _DEFAULT_LABEL)


__all__ = ['TRAINING_STATUS_LABELS', 'training_status_label']