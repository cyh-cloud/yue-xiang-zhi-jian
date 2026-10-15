# -*- coding: utf-8 -*-
"""就业能力档案域：能力档案、在线简历、AI 简历辅助与求职意向（公开公告侧）。

T15 从 app.py 的「就业对接：能力档案 / 在线简历 / 求职意向」区块整体迁出。
URL、请求响应结构、状态码、错误码保持不变。

与就业对接域（domains.employment）的分界按 spec 的「切分单位」一节：就业对接域管
岗位浏览与筛选、投递、收藏；本域管学员侧的求职资料（能力档案 / 简历 / 意向）与
AI 简历辅助。两者共用 `/api/employment/*` 前缀但分属不同领域，因此是两个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 employment_profile_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，本域拆成三个模块，共用同一个蓝图对象：

- routes.py   三条链路的装配：能力档案、简历读写、AI 简历辅助、求职意向增删查；
- prompts.py  AI 简历辅助的系统提示词、可起草段落表、输入上限与限流额度；
- service.py  交给 AI 的素材整理 `_profile_for_ai`（原 app.py 的 `_profile_for_ai`）。

跨域边界：

- 能力档案的五段数据一律走 `employment.get_learner_profile()`（T05 已把它的取数拆成
  各领域窄接口，本域只拼装、不读别人的表），每个字段都来自真实数据，不补默认值；
- AI 调用走共享层 ai.client，且「上游是否已配置」按模块属性调用
  ai.client.ai_configured()：测试改写的是这个模块属性（开关的真正持有者），
  import 时绑定本地名字会让 patch 失效，用例会从「验证明确失败」退化成真的打上游；
- 限流与限流键走共享层 core.session；
- 求职资料属个人数据：`_self_only` 是「当前登录用户就是 user_id 本人」的校验，
  未登录 401、他人 403。它与 messages_self_guard 同为身份护栏，按 spec 的边界件
  归属进共享层 core.session，消息域与求职资料两个领域共用一份实现。

「是否已有简历」（user_has_resume）不在本域定义：它有两个调用方，本域的
「我的求职」聚合与就业对接域的投递提示各一处，而领域之间不得互相 import。
它零领域状态，因此放共享层 shared.resume_state，本域从那里转出，
与就业对接域共用同一份口径。
"""

from domains.employment_profile.routes import employment_profile_bp

__all__ = ['employment_profile_bp']
