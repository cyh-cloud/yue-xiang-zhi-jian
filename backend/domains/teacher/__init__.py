# -*- coding: utf-8 -*-
"""教师管理域：名册与学员的增删改查、账号绑定。

T16 从 app.py 的「教师管理API」区块整体迁出，URL、请求响应结构、状态码、错误码
保持不变。

与教学支撑域（domains.teaching_support）的分界按 spec 的「切分单位」一节：
本域管「教师手下的学员是谁」这一侧；课程、材料、公告、批改、学情分析属教学支撑域。
两者共用 `/api/teacher/*` 前缀但分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 teacher_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，本域拆成两个模块，共用同一个蓝图对象：

- routes.py  名册增删改查、账号绑定、AI 教学报告的入口；
- reports.py 名册归一、数据上下文组装、上游调用、兜底报告与概览。

跨域边界：会话与角色只用共享层 core.session；AI 调用走共享层 ai.client；
数据访问一律走 database 契约层。本域不 import 任何其他领域路由模块。
"""

from domains.teacher.routes import teacher_bp

__all__ = ['teacher_bp']