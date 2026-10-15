# -*- coding: utf-8 -*-
"""公开招聘（招募）公告域：公告与公告来源的读取。

T09 把招募公告从 domain_data.employment.jobs_data 切到读库（ADR 0002）。内容是平台
策展的基层岗位招募公告，由 migrations/0001_content_to_db.py 灌进 recruitments 与
recruitment_sources 两张表，本模块只读不写：公告由运营在后台维护，路由层不再持有
一份代码副本。

对外契约不变，这是 /api/employment/jobs 能零改动切换的前提：

  - 公告 dict 的键集与切换前 RECRUIT_DATA 的元素一致（16 个公告字段 + sources）；
  - sources 是带全部来源字段的 dict 列表，顺序按 recruitment_sources.sort_order
    （迁移脚本按原 sources 列表顺序写入，故与旧版逐项一致）；
  - 报名状态（status / status_label / days_left / starts_in）由本模块按当天日期算出，
    口径与切换前 _with_status() 逐字相同；
  - 列表排序同为「报名中 -> 即将开始 -> 已过期，组内按截止日期」，且组内相对顺序稳定
    （SQL 按 sort_order 取，与旧版 RECRUIT_DATA 的列表序一致）。

口径文案（来源说明 / 免责声明 / 分类白名单 / 状态标签）为什么也住在本模块：它们是
读侧口径，不是内容行，运营改的是公告本身、不是这句免责声明。而它们有两个消费方
（就业对接域的岗位列表、就业能力档案域的求职意向登记），领域路由之间不得互相
import，放数据层两个域才能取到同一份。T10 删掉 domain_data 之后，这里是唯一真相源。
"""

import datetime

from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES 与
# tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import 本模块，
# 谁就必须持 recruit.manage（读操作受 recruit.read 管，它是空元组，公开）。
CAPABILITY = 'recruit'

# 公告主表的字段。顺序与切换前 RECRUIT_DATA 元素的键一致。
_RECRUIT_FIELDS = ('key', 'title', 'org', 'region', 'category', 'job_type', 'headcount',
                   'education', 'experience', 'salary', 'description', 'publish_date',
                   'signup_start', 'deadline', 'signup_way', 'contact')

# 来源子表下发给前端的字段。刻意不是 recruitment_sources 的全部列：sort_order 只用于
# 排序，带上它会让接口响应多出一个切换前没有的键。
_SOURCE_FIELDS = ('title', 'media', 'date', 'url')

# 报名状态文案（前端直接用 status_label）。与切换前 jobs_data.STATUS_LABEL 一致。
RECRUIT_STATUS_LABELS = {
    'upcoming': u'即将开始报名',
    'open': u'报名中',
    'closed': u'已过报名期',
    'unknown': u'详见公告',
}

# 岗位类别白名单（前端筛选用）。只保留实际用到的分类：留着没有条目使用的分类会出现
# 「筛了永远是 0 条」的死筛选项。
RECRUIT_CATEGORIES = (u'农业技术', u'基层服务', u'乡村治理')

# 页面口径说明（前端展示）。
RECRUIT_SOURCE_NOTE = (
    u'以下为广东省各级党委政府、乡镇（街道）与涉农部门公开发布的基层岗位招募（招聘）公告汇编，'
    u'以乡村公益性岗位、编外人员、网格员、特聘农技（动物防疫）等本地岗位为主，'
    u'由本站整理呈现，供了解基层岗位与报名渠道参考。'
)
RECRUIT_DISCLAIMER = (
    u'岗位条件、报名时间、考试安排等一律以发布单位公告原文为准，请点击「查看公告」核对后再报名。'
    u'本平台不代办报名，也不对招募结果作任何承诺。'
)

# 列表排序的分组序：报名中 -> 即将开始 -> 详见公告 -> 已过报名期。
_STATUS_ORDER = {'open': 0, 'upcoming': 1, 'unknown': 2, 'closed': 3}

# 无截止日期时的排序兜底值：排在所有有截止日期的条目之后。
_NO_DEADLINE = '9999-99-99'


def _parse_date(value):
    """把日期字符串解析成 date，空值或非法格式返回 None（宁缺勿编）。"""
    try:
        return datetime.date.fromisoformat((value or '').strip())
    except ValueError:
        return None


def _with_status(entry, today=None):
    """为一条公告补上报名状态与剩余天数。口径与切换前 jobs_data._with_status() 一致。"""
    today = today or datetime.date.today()
    start = _parse_date(entry.get('signup_start'))
    end = _parse_date(entry.get('deadline'))
    if not end:
        status = 'unknown'
    elif today > end:
        status = 'closed'
    elif start and today < start:
        status = 'upcoming'
    else:
        status = 'open'
    entry['status'] = status
    entry['status_label'] = RECRUIT_STATUS_LABELS.get(status, u'详见公告')
    entry['days_left'] = (end - today).days if (end and status in ('open', 'upcoming')) else None
    entry['starts_in'] = (start - today).days if (start and status == 'upcoming') else None
    return entry


def _source_dict(row):
    return {field: (row[field] or '') for field in _SOURCE_FIELDS}


def _sources_by_key(conn):
    """{recruit_key: [来源 dict, ...]}，顺序按 sort_order。"""
    try:
        rows = conn.execute(
            "SELECT * FROM recruitment_sources ORDER BY recruit_key, sort_order").fetchall()
    except Exception:
        return {}
    out = {}
    for row in rows:
        out.setdefault(row['recruit_key'], []).append(_source_dict(row))
    return out


def get_recruitments(today=None):
    """返回全部公开招聘公告（含报名状态），默认按「报名中 -> 即将开始 -> 已过期」排序。

    不带参数时与切换前的 jobs_data.get_recruitment_list() 逐字段等价（键、值、顺序）。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM recruitments ORDER BY sort_order, key").fetchall()
        sources = _sources_by_key(conn)
    except Exception:
        return []
    finally:
        conn.close()

    items = []
    for row in rows:
        entry = {field: (row[field] or '') for field in _RECRUIT_FIELDS}
        entry['sources'] = sources.get(entry['key'], [])
        items.append(_with_status(entry, today))
    items.sort(key=lambda item: (_STATUS_ORDER.get(item['status'], 9),
                                 item.get('deadline') or _NO_DEADLINE))
    return items


def get_recruitment(recruit_key, today=None):
    """按 key 取单条公告（含报名状态），不存在返回 None。"""
    for item in get_recruitments(today):
        if item['key'] == recruit_key:
            return item
    return None


def get_recruitment_notes():
    """招募页口径说明（来源说明 + 免责声明）。"""
    return {'source_note': RECRUIT_SOURCE_NOTE, 'disclaimer': RECRUIT_DISCLAIMER}
