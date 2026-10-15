# -*- coding: utf-8 -*-
"""本土资源域的**内容**读取：成功案例与政策口径。

T09 把成功案例与政策的内容从代码常量切到读库（ADR 0002），并把
db_domains/resources.py 里「读内容」的那半边搬到这里，两个模块的职责从此分开：

  - content.py（本模块）持有**内容**：案例正文（五张表组装）与案例 / 政策的口径文案。
    它只读自己的表，不知道审核状态，也不知道发布态；
  - resources.py 继续持有**审核与发布态的可见性**：get_success_cases() 按
    content_reviews 过滤、get_case_review_stats() 统计审核进度。

这样切分的理由：案例正文与「这条案例有没有过审」是两件事。正文由运营维护，过审状态
由管理员维护；把两者混在一个模块里，改任何一边都要连带读懂另一边的口径。resources.py
里的 get_success_cases() 从 cases_data 读改为从本模块读，其它函数一字不动。

案例的五张表是拆平的，读回时按原形状组装：

    success_cases     -> case 的 8 个标量字段
    case_stats        -> case['stats']        （按 sort_order）
    case_milestones   -> case['milestones']   （按 sort_order）
    case_sources      -> case['sources']      （按 sort_order）
    case_lessons      -> case['lessons']      （按 sort_order）

政策的口径说明（来源说明 + 免责声明）也住这里：它是读侧口径、有两个消费方（本土资源域的
政策列表与政府端工作概览），而领域路由之间不得互相 import。政策正文本身**不在这里**，
它住在 government_policies 表里，由 policies 域读写（政府端可自行发布与下架）。
"""

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES 与
# tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import 本模块，
# 谁就必须持 case.manage（读操作受 case.read 管，它是空元组，公开）。
CAPABILITY = 'case'

# 案例主表读出的字段。顺序与切换前 SUCCESS_CASES 元素的键序一致（id 在最前）。
CASE_FIELDS = ('id', 'title', 'region', 'location', 'background', 'description',
               'quote', 'quote_author')

# 案例页口径说明（前端展示）。与切换前 cases_data 的两个模块级常量逐字一致。
CASE_SOURCE_NOTE = u'本页内容依据公开报道整理，数据与事实均来自下列公开来源，仅供参考。'
LESSONS_NOTE = u'以下为基于公开报道整理的借鉴点，非官方结论。'

# 政策页口径说明（前端展示）。与切换前 policies_data 的两个模块级常量逐字一致。
POLICY_SOURCE_NOTE = (
    u'本页依据公开政策文件整理，文号与数据均可溯源；'
    u'具体标准与办理时限以当年度当地主管部门正式文件为准。'
)
POLICY_DISCLAIMER = u'本平台仅作政策索引与解读，不替代官方文件，不代办任何申报。'

# 平台预置政策的标题白名单。政府端工作概览据此把「本级发布」与「平台预置」分开统计：
# 预置行与 gov_demo 自己发布的行 author_id 相同（都是 gov_demo），只按作者分不开。
# 白名单取代了原先 db_seed_policies.POLICIES_DATA 里那份由代码播种推导出来的清单，
# 内容播种删除后（ADR 0002），这里是唯一真相源。
PRESET_POLICY_TITLES = frozenset((
    u'农业补贴申请指南',
    u'农村电商扶持政策',
    u'非遗传承人认定办法',
    u'农业技术培训补贴',
    u'农产品质量安全认证',
))


def _case_from_row(row, conn):
    """把 success_cases 一行组装成与切换前 case dict 同形的视图。"""
    case = {field: (row[field] or '') for field in CASE_FIELDS}
    case['stats'] = [{'label': r['label'] or '', 'value': r['value'] or '',
                      'icon': r['icon'] or ''}
                     for r in conn.execute(
                         'SELECT label, value, icon FROM case_stats '
                         'WHERE case_id = ? ORDER BY sort_order', (case['id'],))]
    case['milestones'] = [{'period': r['period'] or '', 'title': r['title'] or '',
                           'desc': r['desc'] or ''}
                          for r in conn.execute(
                              'SELECT period, title, "desc" FROM case_milestones '
                              'WHERE case_id = ? ORDER BY sort_order', (case['id'],))]
    case['sources'] = [{'title': r['title'] or '', 'media': r['media'] or '',
                        'date': r['date'] or '', 'url': r['url'] or ''}
                       for r in conn.execute(
                           'SELECT title, media, date, url FROM case_sources '
                           'WHERE case_id = ? ORDER BY sort_order', (case['id'],))]
    case['lessons'] = [r['text'] for r in conn.execute(
        'SELECT text FROM case_lessons WHERE case_id = ? ORDER BY sort_order',
        (case['id'],))]
    return case


def get_cases():
    """返回全部成功案例（含四个子数组），按 success_cases.sort_order 排序。

    与切换前 cases_data.get_cases() 逐字段等价：键集、键序、四个子数组的顺序
    （迁移脚本按原列表顺序写 sort_order，故与旧版逐项一致）。

    这里**不过滤审核状态**：可见性是 content_reviews 的事，由 resources 域组装。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM success_cases ORDER BY sort_order, id").fetchall()
        # 每条案例的四个子表各查一次，所以组装必须发生在同一个连接上：
        # 先关连接再组装会让第二条起全部落空。
        cases = [_case_from_row(row, conn) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
    return cases


def get_case(case_id):
    """按 id 取单个案例，不存在返回 None。同样不过滤审核状态。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM success_cases WHERE id = ?",
                           (case_id,)).fetchone()
        if row is None:
            return None
        case = _case_from_row(row, conn)
    except Exception:
        return None
    finally:
        conn.close()
    return case


def get_case_notes():
    """案例页口径说明文案（与内容同源，避免前端硬编码漂移）。"""
    return {'source_note': CASE_SOURCE_NOTE, 'lessons_note': LESSONS_NOTE}


def get_policy_notes():
    """政策页口径说明文案（来源说明 + 免责声明）。"""
    return {'source_note': POLICY_SOURCE_NOTE, 'disclaimer': POLICY_DISCLAIMER}
