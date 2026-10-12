# -*- coding: utf-8 -*-
"""本土资源域：方言问答、成功案例、政策信息。

一个领域一个蓝图（docs/adr/0001），蓝图对象 resources_bp 定义在 routes.py。
因 spec 的「单个领域路由文件不超过 600 行」，方言知识库与降级话术库拆到
dialect_voice.py，两者都是本域的模块，共用同一个蓝图对象。

方言问答与农业培训域、病虫害诊断域共用农技口径的**判定函数**
（shared.agri_dosage.has_chem_dosage）与免责声明文案（CHEM_DOSE_NOTICE），
本域不复制第二份。方言问答只需要「这段正文要不要提示」，不需要农业培训域的
农技问答提示词组，因此不引入任何跨域 import。
"""

from domains.resources.routes import resources_bp

__all__ = ['resources_bp']
