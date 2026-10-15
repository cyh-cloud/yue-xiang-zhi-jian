# -*- coding: utf-8 -*-
"""公开招聘（招募）公告域：公告与公告来源的读取。

T09 把招募公告从代码常量切到读库（ADR 0002）。内容是平台
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
import，放数据层两个域才能取到同一份。代码常量删掉之后，这里是唯一真相源。
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


# ==================== 运营维护（写侧，T15） ====================
# 列名白名单、校验归路由层、无跨域删除三条口径与其它域一致。
#
# status / status_label / days_left / starts_in 四个字段**不在**可写列里：
# 它们是 _with_status() 按当天日期从 signup_start / deadline 现算出来的派生值
# （见模块 docstring），库里没有这些列。运营要改报名状态，改起止日期。
#
# 公告不带审核门禁（不像课程 / 岗位 / 求购 / 3D 模型 / 案例），所以这里没有
# review_status，也不需要 reviews 域参与。

# 公告主表可写的列。key 是主键，由调用方给出，不在白名单里。
RECRUIT_FIELDS = ('title', 'org', 'region', 'category', 'job_type', 'headcount',
                  'education', 'experience', 'salary', 'description',
                  'publish_date', 'signup_start', 'deadline', 'signup_way',
                  'contact', 'sort_order')

# 来源子表可写的列。recruit_key 是外键，由调用方给出。
SOURCE_FIELDS = ('title', 'media', 'date', 'url', 'sort_order')


def _pick(fields, allowed):
    """按白名单挑出要写的列。None 表示「不碰这一列」，与「置空」是两件事。"""
    return {k: v for k, v in fields.items() if k in allowed and v is not None}


def _require_date(value, label):
    """校验 ISO 日期（YYYY-MM-DD）。空串表示「不设这一天」，是合法值。"""
    text = (value or '').strip()
    if not text:
        return ''
    try:
        return datetime.date.fromisoformat(text).isoformat()
    except ValueError:
        raise ValueError('%s需为 YYYY-MM-DD 格式' % label)


def create_recruitment(key, title, **fields):
    """新增一条招募公告，返回 key（字符串主键由调用方给出）。"""
    key = (key or '').strip()
    title = (title or '').strip()
    if not key:
        raise ValueError(u'公告 key 不能为空')
    if not title:
        raise ValueError(u'公告标题不能为空')
    values = _pick(fields, RECRUIT_FIELDS)
    for column in ('publish_date', 'signup_start', 'deadline'):
        if column in values:
            values[column] = _require_date(values[column], column)
    values.update({'key': key, 'title': title})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO recruitments (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        conn.commit()
    finally:
        conn.close()
    return key


def update_recruitment(key, **fields):
    """按白名单改一条公告。字段全是 None 时不动库，返回是否真的改了。"""
    updates = _pick(fields, RECRUIT_FIELDS)
    if 'title' in updates:
        updates['title'] = (updates['title'] or '').strip()
    if 'title' in updates and not updates['title']:
        raise ValueError(u'公告标题不能为空')
    for column in ('publish_date', 'signup_start', 'deadline'):
        if column in updates:
            updates[column] = _require_date(updates[column], column)
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute("UPDATE recruitments SET %s WHERE key=?" % set_clause,
                           list(updates.values()) + [key])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_recruitment(key):
    """删除一条公告。它的来源行由外键级联删除。"""
    conn = get_connection()
    try:
        cur = conn.execute("DELETE FROM recruitments WHERE key = ?", (key,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def get_recruitment_row(key):
    """按 key 取一行公告（不含派生状态），不存在返回 None。"""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM recruitments WHERE key = ?", (key,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def get_recruitment_rows():
    """全部公告行（不含派生状态），按前台同一顺序（sort_order, key）。

    与 get_recruitments() 分开的理由：那个函数对外，每条都带 status /
    status_label / days_left / starts_in 四个派生字段，是学员端的契约；
    后台列表要的是**可编辑列**，混着四个改不了的派生值只会让表单
    把它们一起提交回来。顺序保持一致，运营看到的行序与前台一致。
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM recruitments ORDER BY sort_order, key").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# ---- 公告来源 ----

def get_recruitment_sources(recruit_key):
    """一条公告的来源行，带 rowid（后台编辑用）。顺序与前台一致。"""
    conn = get_connection()
    try:
        rows = conn.execute(
            'SELECT rowid AS id, title, media, date, url, sort_order '
            'FROM recruitment_sources WHERE recruit_key = ? '
            'ORDER BY sort_order, rowid', (recruit_key,)).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def create_recruitment_source(recruit_key, title, **fields):
    """新增一条公告来源，返回新 id。"""
    title = (title or '').strip()
    if not title:
        raise ValueError(u'来源标题不能为空')
    values = _pick(fields, SOURCE_FIELDS)
    values.update({'recruit_key': recruit_key, 'title': title})
    columns = ', '.join(values)
    conn = get_connection()
    try:
        row = conn.execute("SELECT key FROM recruitments WHERE key = ?",
                           (recruit_key,)).fetchone()
        if row is None:
            raise ValueError(u'公告不存在：%s' % recruit_key)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recruitment_sources (%s) VALUES (%s)"
            % (columns, ', '.join('?' * len(values))), list(values.values()))
        source_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    return source_id


def update_recruitment_source(source_id, **fields):
    """按白名单改一条公告来源。"""
    updates = _pick(fields, SOURCE_FIELDS)
    if 'title' in updates:
        updates['title'] = (updates['title'] or '').strip()
    if 'title' in updates and not updates['title']:
        raise ValueError(u'来源标题不能为空')
    if not updates:
        return False
    # 列名走双引号：desc / where 是 SQL 关键字，裸拼进 SET 子句会语法错误
    set_clause = ', '.join('"%s"=?' % column for column in updates)
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE recruitment_sources SET %s WHERE rowid=?" % set_clause,
            list(updates.values()) + [source_id])
        changed = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return changed > 0


def delete_recruitment_source(source_id):
    """删除一条公告来源。返回是否真的删掉了行。"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM recruitment_sources WHERE rowid = ?", (source_id,))
        deleted = cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return deleted > 0


def get_recruitment_notes():
    """招募页口径说明（来源说明 + 免责声明）。"""
    return {'source_note': RECRUIT_SOURCE_NOTE, 'disclaimer': RECRUIT_DISCLAIMER}
