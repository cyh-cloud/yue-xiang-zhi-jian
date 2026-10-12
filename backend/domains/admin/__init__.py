# -*- coding: utf-8 -*-
"""超级管理员域：用户管理、内容审核、系统公告、评论与帖子删除。

T17 从 app.py 的「超级管理员 API」区块整体迁出，URL、请求响应结构、状态码、错误码
保持不变。

本域与政府域、企业域共用「按角色切分管理端」的形状，但三者分属不同领域（spec 的
切分单位一节各自单列），因此是三个蓝图对象，不合并成一个 admin 大蓝图。

一个领域一个蓝图（docs/adr/0001），蓝图对象 admin_bp 定义在 routes.py。

跨域边界：

- 会话取用户与角色判定只用共享层 core.session；本域的三种把关写法（函数内 inline
  403）与拆分前逐字一致，不统一成装饰器 —— 改写判定形式就是改行为；
- 数据访问一律走 database 契约层，路由层不直接写任何领域表；
- 审核状态变更只走 database.approve_review / reject_review / revoke_review，
  它们最终收敛到 db_domains.reviews.set_review_status 的单一分派入口，
  按内容类型分派到课程 / 岗位 / 3D 模型各域的窄接口。本域不 import 任何其他
  领域路由模块。
"""


from domains.admin.routes import admin_bp

__all__ = ['admin_bp']
