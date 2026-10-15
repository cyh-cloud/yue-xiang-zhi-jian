# -*- coding: utf-8 -*-
"""政府域：政策管理与数据大屏。

T17 从 app.py 的「政府人员 API」区块整体迁出，URL、请求响应结构、状态码、错误码
保持不变。

本域与超级管理员域、企业域共用「按角色切分管理端」的形状，但三者分属不同领域
（spec 的切分单位一节各自单列），因此是三个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 government_bp 定义在 routes.py。
本域 90 行左右，未触及 spec 的 600 行上限，因此不再拆第二层。

跨域边界：

- 会话取用户与角色判定只用共享层 core.session；角色把关沿用拆分前的函数内 inline
  403 写法，不改成装饰器 —— 改写判定形式就是改行为；
- 数据访问一律走 db_domains 各域模块。政策发布/更新的三条口径
  （policy_sources_to_json、default_policy_summary、normalize_policy_category）
  都在 db_domains/resources.py，本域不复制第二份；
- 政策正文的事实源是 government_policies 表（政府端自行发布与下架），
  学员端只读其中 is_published=1 的行，不回退旧 policies 表。
"""


from domains.government.routes import government_bp

__all__ = ['government_bp']
