# -*- coding: utf-8 -*-
"""企业域：岗位管理、投递处理与统计。

T17 从 app.py 的「企业用户 API」区块整体迁出，URL、请求响应结构、状态码、错误码
保持不变。

本域与超级管理员域、政府域共用「按角色切分管理端」的形状，但三者分属不同领域
（spec 的切分单位一节各自单列），因此是三个蓝图对象。

一个领域一个蓝图（docs/adr/0001），蓝图对象 enterprise_bp 定义在 routes.py。
本域 130 行左右，未触及 spec 的 600 行上限，因此不再拆第二层。

三条必须保持的口径：

1. 发布即 pending：新岗位与改过的岗位都重新开一条审核记录，学员端在审核通过前
   完全看不到（`get_job_listings_base` 只放行 review_status='approved'）。
2. 删除只认归属：只能删自己发布的岗位，别人的岗位按不存在处理。
3. 「在招职位」只算审核通过的，未通过的单列 pending_jobs —— 企业不能以为岗位
   已经对外可见。

跨域边界：会话取用户与角色判定只用共享层 core.session；数据访问一律走就业域
（db_domains.employment）的窄接口与 reviews 域的共享表入口，本域不 import
任何其他领域路由模块。T11 起本域不再自己开数据库连接：六处直连 SQL 收进
就业域窄接口，两处跨表 JOIN 改走视图，审核记录的跨域删除走 reviews 域。
"""


from domains.enterprise.routes import enterprise_bp

__all__ = ['enterprise_bp']
