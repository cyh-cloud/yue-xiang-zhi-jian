# -*- coding: utf-8 -*-
"""能力表与能力鉴权：全站唯一的「角色到能力」映射。

为什么按能力判定而不是按角色名：平台有五个角色，第六个（operator）即将由 T13 落地。
按角色名写守卫（`user['role'] != 'super_admin'`）会把同一件事在二十个路由文件里各写
一遍，加角色时漏一处就是一个权限漏洞，而且机械检查无从判起。改成按能力判定后，
角色与能力的对应只收在本文件的一张表里，加角色或调整边界都只改这一处。

能力命名 `<域>.read` / `<域>.manage`，空元组表示公开（不需要登录）。

与 core.session.require_role 的分工：require_role 按角色名放行、未登录回 401，
它是拆分前就有的形状，行为保持不变；require_capability 按能力放行、未登录回 403，
复刻域内联守卫的行为（见它的文档字符串）。新代码一律用 require_capability。
"""

from functools import wraps

from flask import jsonify

# 当前已注册的角色。operator 由 T13 落地为真实角色，届时把它加进这个元组与
# 登录/注册白名单即可，上面的能力表已经为它留好了位置。
ROLES = ('student', 'teacher', 'enterprise', 'government', 'super_admin')

# 学员角色的字面量。除本模块与 core/session.py（require_role 的实现）之外，
# 其它文件不再出现角色名比较，一律走 can() / require_capability()。
STUDENT = 'student'

# 教师角色的字面量。用于「只给教师本人看的数据范围」这类读侧收窄
# （例如 3D 模型列表只列本人上传的），它按身份收窄结果，不是权限判定。
TEACHER = 'teacher'

# ---- 能力表 ----
# 键是能力，值是持有它的角色；空元组表示公开。表是唯一真相源：新增一个能力域只要
# 在这里加一行，不触碰任何路由文件。
#
# 有三处与 spec 5.1 的目标形态不同，原因是本票据承诺零对外行为变化，而现行路由比
# 目标形态更严（都有单测锁着，见 tests/test_permissions.py 的矩阵）：
#   policy.manage 只含 government：政府控制台现在拒绝 super_admin（403），
#     超管看统计走 /api/admin/dashboard 这条独立口径；
#   job.manage 只含 enterprise：企业控制台现在拒绝 super_admin（403）；
#   course.manage 只含 teacher：课程的增删改现在只允许教师本人，super_admin 只读
#     （读走 course.read）。等「超管可代管」真正落地时各改一行即可。
CAPABILITIES = {
    # 农时日历：作物、物候期、农事任务、来源、分类标签
    'farming.read': (),
    'farming.manage': ('operator', 'super_admin'),
    # 病虫害知识：条目、来源、实拍图
    'pest.read': (),
    'pest.manage': ('operator', 'super_admin'),
    # 手工技艺：技艺、步骤、采购指南
    'craft.read': (),
    'craft.manage': ('teacher', 'operator', 'super_admin'),
    # 方言知识：方言、短语、快捷问题
    'dialect.read': (),
    'dialect.manage': ('operator', 'super_admin'),
    # 公开招聘公告
    'recruit.read': (),
    'recruit.manage': ('operator', 'super_admin'),
    # 成功案例
    'case.read': (),
    'case.manage': ('government', 'operator', 'super_admin'),
    # 政策
    'policy.read': (),
    'policy.manage': ('government',),
    # 课程与课程素材
    'course.read': ('teacher', 'super_admin'),
    'course.manage': ('teacher',),
    # 教学支撑：公告、批改、实训提交列表、学情分析
    'teaching.read': ('teacher', 'super_admin'),
    'teaching.manage': ('teacher', 'super_admin'),
    # 企业岗位
    'job.manage': ('enterprise',),
    # 平台用户
    'user.manage': ('super_admin',),
    # 内容审核
    'review.moderate': ('super_admin',),
    # 平台级内容监管。这两个域不在 spec 的十一个内容域里，但管理端确实有「全员公告」
    # 与「评论/帖子删除」两类只有 super_admin 能做的操作。不给它们能力名，就只能把
    # 它们挂到 user.manage 上，名不副实。
    'announcement.manage': ('super_admin',),
    'community.manage': ('super_admin',),
}


def can(role, capability):
    """role 是否持有 capability。能力不在表里一律不放行（fail-closed）。"""
    allowed = CAPABILITIES.get(capability)
    if allowed is None:
        return False
    # 空元组 = 公开：任何身份（含未登录）都可访问
    return not allowed or role in allowed


def is_student(role):
    """该角色是不是学员。名册只能关联学员账号（db_domains.students.set_student_account）。"""
    return role == STUDENT


def roles_with(capability):
    """持有该能力的角色集合，供展示与测试用（不是判权入口，判权一律走 can）。"""
    return frozenset(CAPABILITIES.get(capability, ()))


def require_capability(capability, anonymous=403):
    """能力鉴权装饰器：当前用户不持有 capability 时拒之门外。

    三个分支与 require_role 一致：未登录 / 能力不足 / 账号停用。

    anonymous 是「未登录」时的状态码，默认 403。本仓库的域内联守卫对未登录与角色
    不符一律回 403 且 message 都是「权限不足」（admin / government / enterprise /
    教学支撑的课程与材料几条），装饰器必须逐字复刻，否则「纯内部重构」会变成对外
    响应体变化。传 401 即退回 require_role 的分工（未登录 message 为「请先登录」）。
    """
    if capability not in CAPABILITIES:
        raise KeyError('未知的能力：%r' % (capability,))

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # 函数体内导入：既让测试能 patch core.session.get_session_user，
            # 也让本模块可以被单独 import 而不牵出整个数据层。
            from core.session import get_session_user
            user = get_session_user()
            if not user:
                # 内联守卫原本对未登录也说「权限不足」，逐字保留
                message = "权限不足" if anonymous == 403 else "请先登录"
                return jsonify({"success": False, "message": message}), anonymous
            if not can(user.get('role'), capability):
                return jsonify({"success": False, "message": "权限不足"}), 403
            if user.get('status') == 'suspended':
                return jsonify({"success": False, "message": "账号已被停用"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    'ROLES', 'STUDENT', 'TEACHER', 'CAPABILITIES', 'can', 'is_student',
    'require_capability', 'roles_with',
]
