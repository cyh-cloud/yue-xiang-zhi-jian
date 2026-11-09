# -*- coding: utf-8 -*-
"""企业相关配置：未认证岗位上限、资质证件照的存放与格式约束、状态文案。

为什么放在共享层：这几项同时被企业域与超管域读，且必须完全一致 ——
- 上限写两处，界面说「还能发 1 条」而接口在第二条就拒，用户会认为系统坏了；
- 证件目录写两处，一家提交的文件另一家读不到，审核侧永远打不开附件；
- 状态文案写两处，同一个 rejected 在两边显示成不同措辞。
领域之间不允许互相 import（ADR 0001），所以这些常量不能挂在企业域路由里。
"""

import os

from repo_paths import REPO_ROOT

# 未认证企业最多能挂的「在招岗位」数（审核通过的才算在招，与
# v_enterprise_job_stats.total_jobs 同一口径）。认证通过后不再受限。
UNVERIFIED_ACTIVE_JOB_LIMIT = 1

# 证件照存放目录。刻意落在 data/ 下：静态路由只放行 uploads 与 images，
# data/ 是整目录拒绝的，因此这里的文件不可能被直链拿到，只能走鉴权接口。
QUALIFICATION_LICENSE_DIR = os.path.join(REPO_ROOT, 'data', 'qualifications')

# 只收这三类。PDF 是营业执照电子版的常见格式；不收 doc/docx（可带宏、难预览）。
QUALIFICATION_ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.pdf')

# 单张上限 5MB。营业执照手机拍摄一般 1~3MB，5MB 足够且不会把请求撑大。
QUALIFICATION_MAX_BYTES = 5 * 1024 * 1024

# 认证状态文案，前后端共用一份口径。
QUALIFICATION_STATUS_LABELS = {
    'none': '未提交',
    'pending': '审核中',
    'approved': '已认证',
    'rejected': '已驳回',
    'withdrawn': '已撤回',
    'expired': '认证已过期',
}

__all__ = ['UNVERIFIED_ACTIVE_JOB_LIMIT', 'QUALIFICATION_LICENSE_DIR',
           'QUALIFICATION_ALLOWED_EXTENSIONS', 'QUALIFICATION_MAX_BYTES',
           'QUALIFICATION_STATUS_LABELS']
