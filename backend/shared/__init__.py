# -*- coding: utf-8 -*-
"""纯函数工具：节气计算、农技口径判定、直播朗读评分、文案评分、下拉选项拼装。

这些函数零领域依赖、可复现、无随机数，任何领域都可能用到。它们不读写数据层，
因此领域数据层拆成什么样与这里无关。
"""

from shared.solar_terms import SOLAR_TERM_NAMES, solar_terms, solar_terms_of_month
from shared.agri_dosage import (
    CHEM_DOSE_NOTICE,
    CHEM_DOSE_NOTICE_BLOCK,
    has_chem_dosage,
)
from shared.live_reading import live_cjk, live_speed_score
from shared.copywriting import copy_score
from shared.options import category_option_list
from shared.resume_state import user_has_resume
from shared.review_freshness import REVIEW_STALE_DAYS, is_review_current
from shared.training_status import training_status_label

__all__ = [
    'SOLAR_TERM_NAMES', 'solar_terms', 'solar_terms_of_month',
    'has_chem_dosage',
    'CHEM_DOSE_NOTICE', 'CHEM_DOSE_NOTICE_BLOCK',
    'live_cjk', 'live_speed_score',
    'copy_score',
    'category_option_list',
    'user_has_resume',
    'REVIEW_STALE_DAYS', 'is_review_current',
    'training_status_label',
]
