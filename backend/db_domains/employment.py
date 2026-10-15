#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""就业对接域：岗位、投递、收藏、求职意向与能力档案。

T05 从 database.py 按领域切分抽出，SQL 语义与返回结构与拆分前逐字节一致。
"""

import re

import json
import sqlite3
from db_connection import get_connection

# 本模块的数据归属这个能力域。backend/core/permissions.py 的 CAPABILITIES
# 与 tools/check_architecture.py（T02 起按能力表判权）都以此为准：谁 import
# 本模块，谁就必须持 job.manage（读操作受 job.read 管）。
CAPABILITY = 'job'

# 企业端岗位分类的固定枚举。路由层用它拼「分类」下拉，故与业务函数同住就业域。
ENTERPRISE_JOB_CATEGORIES = ['农业技术', '电商运营', '手工工艺', '乡村旅游', '物流仓储']

_SALARY_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*([kK千万元]?)')
_SALARY_MIN_ABS = 100.0


def set_job_review_status(job_id, review_status):
    """就业域的审核窄接口：只改 job_listings 自己的 review_status。

    由审核域的 set_review_status() 按内容类型分派调用。
    ⚠️ 必须与 approve / reject 对称回写：此前只改 content_reviews，导致岗位被驳回后
    企业端一直显示「待审核」，企业会以为还在排队等审（2026-10-07 修）。
    """
    conn = get_connection()
    conn.execute("UPDATE job_listings SET review_status=? WHERE id=?",
                 (review_status, job_id))
    conn.commit()
    conn.close()


def count_job_listings(review_status=None):
    """就业域窄接口：岗位条数，可按审核状态过滤。"""
    conn = get_connection()
    if review_status is None:
        n = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
    else:
        n = conn.execute(
            "SELECT COUNT(*) FROM job_listings WHERE review_status = ?",
            (review_status,)).fetchone()[0]
    conn.close()
    return n


def count_unread_job_applications(user_id):
    """就业域的未读窄接口：未被「全部已读」标记过的投递记录数。

    由通知域的未读总数显式调用。已读标记存在 notification_reads 表里，
    本域只按 source='job_application' 读自己那一类引用。

    T05：已读标记的归属是通知域，这里改为向它取「我这一类已读了哪些」，
    本域不再直接读 notification_reads 表。
    """
    from db_domains.notifications import get_read_refs
    read = set(get_read_refs(user_id, 'job_application'))
    conn = get_connection()
    ids = [str(r['id']) for r in conn.execute(
        "SELECT id FROM job_applications WHERE user_id = ?", (user_id,)).fetchall()]
    conn.close()
    return sum(1 for i in ids if i not in read)
    return n


def get_job_listings():
    """获取岗位列表"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM job_listings").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result

def apply_for_job(user_id, job_id):
    """申请职位。

    返回值（三态，勿再当布尔用）：
      'ok'          —— 申请成功
      'dup'         —— 已申请过
      'unavailable' —— 职位不存在，或**未通过审核**（企业发布后处于 pending）

    ⚠️ 必须校验 review_status：申请会写进 job_applications 并给学员加积分，
    若允许对未审核/不存在的岗位申请，等于绕过了审核门禁（2026-10-06 修复）。
    """
    conn = get_connection()
    row = conn.execute("SELECT review_status FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    if not row or (row['review_status'] or '') != 'approved':
        conn.close()
        return 'unavailable'
    existing = conn.execute("SELECT 1 FROM job_applications WHERE user_id = ? AND job_id = ?",
                            (user_id, job_id)).fetchone()
    if existing:
        conn.close()
        return 'dup'
    conn.execute("INSERT INTO job_applications (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
    conn.commit()
    conn.close()
    return 'ok'

def get_job_by_id(job_id):
    """获取单条职位详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['requirements'] = json.loads(d['requirements'])
    return d


#### 企业岗位分类（学员端下拉 + 条数统计的口径来源）####
# ⚠️ 必须与 index.html 里 `#emp-category-filter` 的静态 <optgroup label="企业招聘岗位"> 保持一致
#    （静态项只是老后端/无脚本时的回退）。这里刻意把「当前 0 条」的分类也列出来，
#    前端会标成「（暂无）」—— 直接把死分类从下拉里藏掉，反而让人以为平台不支持这类岗位。
ENTERPRISE_JOB_CATEGORIES = ['农业技术', '电商运营', '手工工艺', '乡村旅游', '物流仓储']


#### 薪资区间解析（学员端薪资筛选用） ####
# 把「5K-8K」「5000-8000」「1万-1.5万」「2040元/月」里的数字抠出来。
# ⚠️ 只认 **≥100** 的数：否则「试用期2个月」里的 2 会被当成薪资，
#    把一条本来解析不出薪资的文本变成 (2, 2) 的假区间。
_SALARY_NUM_RE = re.compile(r'(\d+(?:\.\d+)?)\s*([kK千万元]?)')
_SALARY_MIN_ABS = 100.0

def parse_salary_bounds(text):
    """把一段薪资文本解析成 `(下界, 上界)`，解析不出来返回 None。

    · `5K-8K`      -> (5000, 8000)
    · `4K-6K`      -> (4000, 6000)
    · `5000-8000`  -> (5000, 8000)
    · `1万-1.5万`   -> (10000, 15000)
    · `12000+`     -> (12000, None)   ← 上界未知
    · `2040元/月`   -> (2040, 2040)
    · `面议` / 空 / 含数字但都不像薪资 -> None
    """
    if text is None:
        return None
    nums = []
    for m in _SALARY_NUM_RE.finditer(str(text)):
        v = float(m.group(1))
        unit = m.group(2)
        if unit in ('k', 'K', '千'):
            v *= 1000
        elif unit == '万':
            v *= 10000
        if v >= _SALARY_MIN_ABS:
            nums.append(v)
    if not nums:
        return None
    if len(nums) == 1:
        # `12000+` / `5K以上` 这类开放上界；其余单值按「恰好这个数」处理
        if '+' in str(text) or '以上' in str(text):
            return (nums[0], None)
        return (nums[0], nums[0])
    return (min(nums), max(nums))

def _salary_matches(job_salary, want_bounds):
    """岗位薪资与筛选区间必须有**长度大于 0 的交集**才算命中。

    ⚠️ 旧实现是 `salary LIKE '%5000%'`，而 `job_listings.salary` 存的是 `5K-8K`
    → **永远匹配不上**，学员选任意薪资都会得到 0 条（2026-10-07 实测）。

    为什么不用「端点相触也算」：三个可选区间是 3K-5K / 5K-8K / 8K-12K，彼此共用端点。
    若把 5K 既算进「3K-5K」又算进「5K-8K」，学员选「3K-5K」会看到一张写着「5K-8K」的
    卡片 —— 薪资数字明晃晃地对不上（卡片本身会显示薪资），比漏掉更让人困惑。
    所以：区间有真实重叠才命中。
    解析不出薪资（如「面议」）的岗位**不参与薪资筛选**，不静默算成 0。
    """
    if not want_bounds:
        return True
    jb = parse_salary_bounds(job_salary)
    if not jb:
        return False
    jmin, jmax = jb
    wmin, wmax = want_bounds

    if jmin == jmax:            # 岗位只给了一个确切数字（如「2040元/月」）
        return jmin >= wmin if wmax is None else (wmin <= jmin <= wmax)
    if jmax is None:            # 岗位「X 以上」
        return True if wmax is None else (jmin < wmax)
    if wmax is None:            # 筛选「X 以上」
        return jmax > wmin
    return max(jmin, wmin) < min(jmax, wmax)

def get_job_listings_base(keyword=None, location=None, salary_range=None):
    """企业岗位基础集合：应用 关键词 / 地点 / 薪资，**不应用分类**。

    分类单独一步做，是为了让前端的下拉能显示「每个分类各有多少条」
    —— 若在这里就把 category 过滤掉，统计永远只剩当前选中项（条数全是 1）。
    """
    conn = get_connection()
    query = "SELECT * FROM job_listings WHERE review_status = 'approved'"
    params = []
    if keyword:
        query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    if location:
        query += " AND location = ?"
        params.append(location)
    query += " ORDER BY posted_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()

    want = parse_salary_bounds(salary_range) if salary_range else None
    result = []
    for r in rows:
        d = dict(r)
        if not _salary_matches(d.get('salary'), want):
            continue
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result

def get_job_category_counts(keyword=None, location=None, salary_range=None):
    """`{分类: 条数}`，口径与 `get_job_listings_base()` 完全一致（不含分类过滤）。"""
    counts = {}
    for j in get_job_listings_base(keyword, location, salary_range):
        cat = (j.get('category') or '').strip() or '未分类'
        counts[cat] = counts.get(cat, 0) + 1
    return counts

def get_job_listings_filtered(keyword=None, location=None, salary_range=None, category=None):
    """按条件筛选职位（**学员端公开接口专用**）。

    ⚠️ 这里必须过滤 `review_status='approved'`：企业发布的岗位初始为 `pending`，
    只有管理员审核通过后才应出现在学员端。此前 SQL 是 `WHERE 1=1`，
    导致**未审核岗位发布即可见**、内容审核形同虚设（2026-10-06 修复）。
    历史遗留行的 review_status 默认即 `'approved'`，不受影响；
    取值用 `= 'approved'`（fail-closed：万一为 NULL 也不会漏出）。
    """
    result = get_job_listings_base(keyword, location, salary_range)
    if category:
        result = [j for j in result if (j.get('category') or '') == category]
    return result

def count_pending_job_listings():
    """尚未通过审核（待审 / 已驳回）的企业岗位条数。

    学员端拿不到这些岗位，所以当它们在库里占满全部企业岗位时，
    列表会出现「一条企业岗都没有」的现象。前端需要据此说明
    「不是平台没有岗位，而是岗位正在审核中」——
    否则学员只会看到一句「未找到匹配的职位」，以为平台是空的。
    """
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM job_listings WHERE COALESCE(review_status, '') != 'approved'"
    ).fetchone()[0]
    conn.close()
    return n

def get_similar_jobs(job_id, category, limit=3):
    """获取同分类相似职位（同样只返回已通过审核的，避免从"相似职位"绕出未审核岗位）"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM job_listings WHERE category = ? AND id != ? AND review_status = 'approved' LIMIT ?",
        (category, job_id, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result

def save_job(user_id, job_id):
    """收藏职位"""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def unsave_job(user_id, job_id):
    """取消收藏"""
    conn = get_connection()
    conn.execute("DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    conn.commit()
    conn.close()
    return True

def get_saved_jobs(user_id):
    """获取用户收藏的职位ID列表"""
    conn = get_connection()
    rows = conn.execute("SELECT job_id FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [r['job_id'] for r in rows]

def get_user_applications(user_id, status_filter=None):
    """获取用户投递记录（含职位详情）"""
    conn = get_connection()
    if status_filter and status_filter != 'all':
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category, jl.enterprise_id
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ? AND ja.status = ?
            ORDER BY ja.applied_at DESC
        """, (user_id, status_filter)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category, jl.enterprise_id
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ?
            ORDER BY ja.applied_at DESC
        """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_application_counts(user_id):
    """获取各状态投递计数"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'pending'", (user_id,)).fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'approved'", (user_id,)).fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'rejected'", (user_id,)).fetchone()[0]
    conn.close()
    return {'total': total, 'pending': pending, 'approved': approved, 'rejected': rejected}

def get_employment_stats(user_id):
    """获取就业模块快捷统计"""
    conn = get_connection()
    applied = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    saved = conn.execute("SELECT COUNT(*) FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchone()[0]
    intents = conn.execute("SELECT COUNT(*) FROM job_intents WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return {'applied': applied, 'saved': saved, 'intents': intents, 'messages': 0}


# ==================== 就业对接：能力档案 / 在线简历 / 求职意向 ====================

# 简历可写字段白名单。`ai_used` 刻意不在其中 —— 它只能由 AI 生成接口置位，
# 否则学员可以传 ai_used=0 伪装成「完全自己写的」。
RESUME_FIELDS = ('title', 'region', 'education', 'work_years', 'phone', 'email',
                 'self_eval', 'skills', 'experience')

def get_learner_profile(user_id):
    """聚合学员的**真实**学习数据，作为「能力档案」与 AI 简历的唯一素材来源。

    ⚠️ 每一项都必须来自库里真实存在的数据，**代码不得补默认值凑数**：
    这些数据会原样交给 AI 当写作素材，凭空补的默认值等于让 AI 编造。
    某项没有数据就返回空列表 / 0，由前端决定「暂无」怎么呈现（宁缺勿编）。

    T05 收敛：basic / certificates / points / learning / training 五段分别向
    用户域、证书域、积分域、学员域、教学支撑域取数，本域只负责拼装，
    不再直接 SQL 读别人领域的表。
    """
    profile = {
        'basic': {}, 'certificates': [], 'points': 0,
        'learning': None, 'training': [],
    }

    # 延迟导入：被组合的四个域都不依赖本域，函数内导入避免顶层绑成导入链。
    from db_domains.profile_sources import (
        get_points_balance,
        get_profile_basic,
        get_profile_certificates,
        get_recent_training_results,
        get_student_progress_for_profile,
    )

    profile['basic'] = get_profile_basic(user_id)
    profile['certificates'] = get_profile_certificates(user_id)
    profile['points'] = get_points_balance(user_id)
    # 学习进度：历史数据里 students.user_id 常为空串，故用姓名兜底匹配
    profile['learning'] = get_student_progress_for_profile(
        user_id, profile['basic'].get('name') or '')
    profile['training'] = get_recent_training_results(user_id)
    return profile

def get_resume(user_id):
    """读取学员的在线简历（没有则返回 None）。experience 解析为列表。"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM resumes WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['experience'] = json.loads(d.get('experience') or '[]')
    except Exception:
        d['experience'] = []
    return d

def save_resume(user_id, data):
    """新增或更新在线简历（一人一份），返回保存后的记录。

    ⚠️ 只接受 RESUME_FIELDS 白名单字段（防越权改写 user_id / ai_used）。
    ⚠️ 更新时用 UPDATE 而非「先删后插」，否则 id 会变、创建时间会丢。
    """
    existing = get_resume(user_id)
    payload = {}
    for k in RESUME_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k == 'experience':
            clean = []
            for item in (v if isinstance(v, list) else [])[:20]:
                if not isinstance(item, dict):
                    continue
                clean.append({
                    'company': str(item.get('company') or '')[:100],
                    'position': str(item.get('position') or '')[:100],
                    'period': str(item.get('period') or '')[:50],
                    'desc': str(item.get('desc') or '')[:2000],
                })
            payload[k] = json.dumps(clean, ensure_ascii=False)
        else:
            payload[k] = str(v or '')[:5000]

    conn = get_connection()
    if not existing:
        cols = ['user_id'] + list(payload.keys())
        vals = [user_id] + list(payload.values())
        conn.execute(
            "INSERT INTO resumes (%s) VALUES (%s)" % (', '.join(cols), ', '.join('?' * len(cols))),
            vals)
    elif payload:
        sets = ', '.join('%s = ?' % c for c in payload)
        conn.execute(
            "UPDATE resumes SET %s, updated_at = datetime('now','localtime') WHERE user_id = ?" % sets,
            list(payload.values()) + [user_id])
    conn.commit()
    conn.close()
    return get_resume(user_id)

def mark_resume_ai_used(user_id):
    """把简历标记为「使用过 AI 辅助」。前端据此如实提示，不隐瞒 AI 参与。"""
    conn = get_connection()
    row = conn.execute("SELECT id FROM resumes WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        conn.execute("UPDATE resumes SET ai_used = 1, updated_at = datetime('now','localtime') "
                     "WHERE user_id = ?", (user_id,))
    else:
        conn.execute("INSERT INTO resumes (user_id, ai_used) VALUES (?, 1)", (user_id,))
    conn.commit()
    conn.close()

def add_job_intent(user_id, recruit_key, note=''):
    """登记对某条公开招聘公告的求职意向（幂等，重复登记只更新备注）。

    返回 True 表示新建、False 表示更新已有。
    ⚠️ 这里**只记录意向**，不代表报名成功 —— 报名由学员按公告原文自行完成。
    """
    conn = get_connection()
    row = conn.execute("SELECT id FROM job_intents WHERE user_id = ? AND recruit_key = ?",
                       (user_id, recruit_key)).fetchone()
    if row:
        conn.execute("UPDATE job_intents SET note = ? WHERE id = ?",
                     (str(note or '')[:500], row['id']))
        created = False
    else:
        conn.execute("INSERT INTO job_intents (user_id, recruit_key, note) VALUES (?, ?, ?)",
                     (user_id, recruit_key, str(note or '')[:500]))
        created = True
    conn.commit()
    conn.close()
    return created

def remove_job_intent(user_id, recruit_key):
    """取消求职意向登记。返回 True 表示确有记录被删除。"""
    conn = get_connection()
    cur = conn.execute("DELETE FROM job_intents WHERE user_id = ? AND recruit_key = ?",
                       (user_id, recruit_key))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_job_intents(user_id):
    """获取学员登记的全部求职意向（按登记时间倒序）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT recruit_key, note, created_at FROM job_intents "
        "WHERE user_id = ? ORDER BY created_at DESC, id DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_application_ids(user_id):
    """该用户全部投递记录 id（「全部已读」要把它们逐个标已读）。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id FROM job_applications WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [str(r[0]) for r in rows]
