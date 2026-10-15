# -*- coding: utf-8 -*-
"""运营域：运营后台（operator.html）的全部内容维护接口。

T14 先落农时与病虫害两块，T15 补齐技艺、方言、招募、案例，六块内容齐了。
一个领域一个蓝图
（docs/adr/0001），蓝图对象 operator_bp 定义在 routes.py。

为什么运营后台是**一个**领域而不是按内容块拆成六个：它的职责只有一件事，
「让运营改内容」。这些接口共享同一套形状（能力表判权、同一套表单校验、
同一套「改完立即生效」的承诺），也共享同一批读者：前台只读接口。把它们按
内容域拆开，会得到六个几乎相同的路由文件，而 ADR 0001 的切分单位是**领域**，
不是「哪个模块碰哪张表」。

本域因 spec 的「单个领域路由文件不超过 600 行」拆成六个模块，共用同一个蓝图对象：

- routes.py       路由装配与鉴权：只挂 require_capability，业务在另外五个模块；
- farming.py      农时日历的作物、物候期、任务、来源、分类的增删改与复核；
- pest.py         病虫害的条目、来源、实拍图关联的增删改与复核；
- crafts.py       手工技艺的技艺、步骤、采购分类、采购条目与预算；
- dialects.py     方言的方言层、短语、快捷问题；
- recruitments.py 招募公告的公告与来源；
- cases.py        成功案例的案例与四个子表。

跨域边界：本域读 farming / pest / craft / dialect / recruit / case 六个能力域，
各模块分别声明 CAPABILITIES_USED，供
tools/check_architecture.py 判权。它不 import 任何其它领域路由模块。
"""

from domains.operator.cases import OPERATOR_CASES_ROUTES
from domains.operator.crafts import OPERATOR_CRAFTS_ROUTES
from domains.operator.dialects import OPERATOR_DIALECTS_ROUTES
from domains.operator.farming import OPERATOR_FARMING_ROUTES
from domains.operator.pest import OPERATOR_PEST_ROUTES
from domains.operator.recruitments import OPERATOR_RECRUITMENTS_ROUTES
from domains.operator.routes import operator_bp, register_routes

# 六个模块都导入完成后再挂路由：routes.py 不能在自己的导入期 import 它们，
# 否则 routes -> <模块> -> routes 成环。注册序即这里的调用序。
register_routes()

__all__ = ['operator_bp', 'OPERATOR_FARMING_ROUTES', 'OPERATOR_PEST_ROUTES',
           'OPERATOR_CRAFTS_ROUTES', 'OPERATOR_DIALECTS_ROUTES',
           'OPERATOR_RECRUITMENTS_ROUTES', 'OPERATOR_CASES_ROUTES']
