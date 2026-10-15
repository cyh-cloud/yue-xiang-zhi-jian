# -*- coding: utf-8 -*-
"""就业对接域：岗位浏览与筛选、投递、收藏、证书与积分。

T15 从 app.py 的「就业对接API」区块整体迁出，URL、请求响应结构、状态码、
错误码保持不变。

与就业能力档案域（domains.employment_profile）的分界按 spec 的「切分单位」一节：
本域管「找工作」这一侧（浏览、筛选、投递、收藏、证书与积分兑换），
能力档案 / 在线简历 / AI 简历辅助 / 求职意向属就业能力档案域。
两者共用 `/api/employment/*` 前缀但分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 employment_bp 定义在 routes.py。

跨域边界：

- 公开招聘（招募）公告是平台策展内容，T09 起唯一事实源是 recruitments 表
  （db_domains.recruitments，ADR 0002）；企业自行发布的岗位走 job_listings 表
  + 内容审核，两者在 /api/employment/jobs 里合并下发（前端按 source_type 区分）；
- 「是否已有简历」取共享层 shared.resume_state.user_has_resume：它有两个调用方
  （本域的投递提示与就业能力档案域的我的求职），而领域之间不得互相 import，
  放共享层才能既单一真相源又不违反边界；
- 数据访问一律走 database 契约层（db_domains/employment.py 那批函数）。
"""

from domains.employment.routes import employment_bp

__all__ = ['employment_bp']
