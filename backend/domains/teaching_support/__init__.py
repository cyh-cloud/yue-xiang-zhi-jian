# -*- coding: utf-8 -*-
"""教学支撑域：公告、实训批改、学情分析、课程与材料、3D 模型。

T16 从 app.py 的「通知公告API」「实训批改 API」「学情分析API」「教师扩展 API」
三个区块整体迁出，URL、请求响应结构、状态码、错误码保持不变。

与教师管理域（domains.teacher）的分界按 spec 的「切分单位」一节：本域管「教学内容
与教学过程」这一侧；名册与账号绑定属教师管理域。两者共用 `/api/teacher/*` 前缀但
分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 teaching_support_bp 定义在 routes.py。
本域 274 行，未触及 spec 的 600 行上限，因此不再拆第二层。

跨域边界：

- 会话与角色只用共享层 core.session；本域两种把关写法（装饰器 401/403 与函数内
  inline 403）都与拆分前逐字一致，不统一；
- 上传落盘目录 BASE_DIR 从 core.app_factory 取（仓库根），与静态资源域放行的
  uploads/ 是同一处，否则「存得下却取不回」；
- 实训状态标签取共享层 shared.training_status：直播实训域也要用它，
  而领域之间不得互相 import。
"""

from domains.teaching_support.routes import teaching_support_bp

__all__ = ['teaching_support_bp']