# -*- coding: utf-8 -*-
"""企业资质认证的数据访问层：提交、查询、审核、有效期。

为什么归在 job 能力域：资质不是独立的业务对象，它唯一的用途就是决定「这家企业
能不能发岗位、能发几条」。把 CAPABILITY 标成 'job' 之后，job.read 是公开读，
企业域与超管域都能引用本模块而不必新增能力名，机械检查（tools/check_architecture.py）
也不会判越界。

三条口径：

1. **一次提交一行，历史不覆盖**。驳回后重交是新行，旧行留着，审核侧才能看到
   「这家企业改过几次、上次为什么被驳回」。
2. **同一时刻只允许一份在审**。已有 pending 时再提交直接拒绝，避免审核队列里
   同一家企业堆出多条相互矛盾的材料。
3. **有效期只对 approved 有意义**。通过时写 expires_at = 一年后；过期即视为未认证，
   但记录不删，界面上仍能看到「曾于某年通过」。

证件照只存相对路径，读出来的原始路径仅在鉴权路由内部使用，不进任何对外响应。
"""

from datetime import date
import sqlite3

from db_connection import get_connection

# 本模块的数据归属这个能力域（见模块 docstring）。
CAPABILITY = 'job'

# 允许写入的字段。id / 状态 / 审核留痕由本模块自己维护，调用方碰不到。
_WRITABLE = ('company_name', 'credit_code', 'legal_person', 'contact_phone',
             'address', 'industry', 'company_size', 'license_file', 'license_name')

# 认证有效期（年）。续期口径与内容复核（REVIEW_STALE_DAYS=183 天）不同：
# 资质是行政登记信息，一年一审比内容更合理。
VALID_YEARS = 1


def _row(row):
    return dict(row) if row else None


def _connect():
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    return conn


def get_by_id(qualification_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM enterprise_qualifications WHERE id = ?",
                           (qualification_id,)).fetchone()
    finally:
        conn.close()
    return _row(row)


def get_latest(user_id):
    """该企业最近一次提交（不论状态）。没有则 None。"""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM enterprise_qualifications WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
    finally:
        conn.close()
    return _row(row)


def _is_expired(record):
    """approved 且 expires_at 早于今天算过期；空字符串按不过期处理（历史数据）。"""
    if not record or record.get('status') != 'approved':
        return False
    expires = (record.get('expires_at') or '').strip()
    if not expires:
        return False
    return expires < date.today().isoformat()


def status_of(user_id):
    """对外统一的认证状态。

    status 取值 none / pending / approved / rejected / expired；
    verified 只在 approved 且未过期时为 True。
    """
    record = get_latest(user_id)
    if not record:
        return {'status': 'none', 'verified': False, 'record': None}
    if _is_expired(record):
        return {'status': 'expired', 'verified': False, 'record': record}
    return {
        'status': record['status'],
        'verified': record['status'] == 'approved',
        'record': record,
    }


def is_verified(user_id):
    return status_of(user_id)['verified']


def list_by_status(status=None, limit=200):
    """审核队列与历史列表。pending 按提交时间正序（先来先审），其余按倒序。"""
    sql = "SELECT * FROM enterprise_qualifications"
    params = []
    if status:
        sql += " WHERE status = ?"
        params.append(status)
    if status == 'pending':
        sql += " ORDER BY submitted_at ASC, id ASC"
    else:
        sql += " ORDER BY id DESC"
    sql += " LIMIT ?"
    params.append(int(limit))

    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [_row(row) for row in rows]


def count_pending():
    conn = _connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM enterprise_qualifications WHERE status='pending'"
        ).fetchone()[0]
    finally:
        conn.close()


def find_credit_code_owner(credit_code, exclude_user_id=''):
    """返回占用该统一社会信用代码的另一个账号（只算在审与已通过）。

    同一张营业执照给两个账号各认证一次，等于平台替两个身份背书同一家企业。
    提交与审核通过两处都要查，前者挡重复投递，后者挡「并发提交后各自通过」。
    已驳回与已撤回不算占用：那是这家企业自己没走完的流程。
    """
    code = (credit_code or '').strip().upper()
    if not code:
        return ''
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT user_id FROM enterprise_qualifications "
            "WHERE UPPER(credit_code) = ? AND user_id != ? "
            "AND status IN ('pending', 'approved') "
            "ORDER BY id DESC LIMIT 1", (code, exclude_user_id or '')).fetchone()
    finally:
        conn.close()
    return row['user_id'] if row else ''


def withdraw(qualification_id, user_id):
    """撤回自己在审的申请。只有 pending 能撤，已裁定的不行。

    撤回后状态记 'withdrawn' 而不是删行：审核侧要能看到「这家企业提交过又撤了」。
    """
    conn = _connect()
    try:
        cur = conn.execute(
            "UPDATE enterprise_qualifications SET status = 'withdrawn' "
            "WHERE id = ? AND user_id = ? AND status = 'pending'",
            (qualification_id, user_id))
        conn.commit()
    finally:
        conn.close()
    return cur.rowcount > 0


def submit(user_id, fields):
    """提交一份资质。返回 (id, 错误消息)；成功时错误消息为空串。"""
    user_id = (user_id or '').strip()
    if not user_id:
        raise ValueError('缺少提交人')

    latest = get_latest(user_id)
    if latest and latest['status'] == 'pending':
        return None, '已有一份资质正在审核中，请等待审核结果后再提交'
    if latest and latest['status'] == 'approved' and not _is_expired(latest):
        return None, '当前认证仍在有效期内，无需重复提交'

    values = {key: (fields.get(key) or '') for key in _WRITABLE}
    if not values['company_name']:
        return None, '企业名称不能为空'
    if not values['credit_code']:
        return None, '统一社会信用代码不能为空'

    owner = find_credit_code_owner(values['credit_code'], user_id)
    if owner:
        return None, '该统一社会信用代码已被其他企业账号使用，请联系平台核实'

    columns = ', '.join(('user_id',) + _WRITABLE)
    placeholders = ', '.join('?' * (len(_WRITABLE) + 1))
    conn = _connect()
    try:
        cursor = conn.execute(
            "INSERT INTO enterprise_qualifications (%s) VALUES (%s)"
            % (columns, placeholders),
            [user_id] + [values[key] for key in _WRITABLE])
        conn.commit()
        return cursor.lastrowid, ''
    finally:
        conn.close()


def review(qualification_id, status, reviewer='', comment=''):
    """裁定一份资质。status 只接受 approved / rejected。

    approved 时写 expires_at（一年后）；rejected 时清空 expires_at，
    避免出现「已驳回但还带着有效期」的自相矛盾记录。
    """
    if status not in ('approved', 'rejected'):
        raise ValueError('未知的审核状态：%r' % (status,))
    record = get_by_id(qualification_id)
    if record is None:
        return False

    conn = _connect()
    try:
        if status == 'approved':
            conn.execute(
                "UPDATE enterprise_qualifications SET status='approved', "
                "review_comment=?, reviewed_by=?, "
                "reviewed_at=datetime('now','localtime'), "
                "expires_at=date('now','localtime','+%d year') WHERE id=?"
                % VALID_YEARS, (comment or '', reviewer or '', qualification_id))
        else:
            conn.execute(
                "UPDATE enterprise_qualifications SET status='rejected', "
                "review_comment=?, reviewed_by=?, "
                "reviewed_at=datetime('now','localtime'), expires_at='' "
                "WHERE id=?", (comment or '', reviewer or '', qualification_id))
        conn.commit()
    finally:
        conn.close()
    return True


def verified_enterprise_ids():
    """当前处于有效期内的已认证企业 id 集合，供岗位列表打标。"""
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT DISTINCT user_id FROM enterprise_qualifications "
            "WHERE status='approved' AND (expires_at='' OR "
            "expires_at >= date('now','localtime'))").fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


__all__ = ['CAPABILITY', 'VALID_YEARS', 'get_by_id', 'get_latest', 'status_of',
           'is_verified', 'list_by_status', 'count_pending', 'submit', 'review',
           'verified_enterprise_ids']
