#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""就业域的演示岗位播种。

演示岗位不是真实招聘信息，而是显式声明为演示的投递链路载体，四重标注：
① 公司名带「（演示）」后缀；② job_listings.is_demo = 1；③ 前端强制打「演示数据」角标；
④ 描述正文里写明「本岗位为平台演示数据，仅用于展示站内投递流程」。

与真实链路的关系：归属账号是真实的企业演示账号 enterprise_demo，新建行进
content_reviews 待审队列，**必须由管理员审核通过后才出现在学员端**。
"""

import hashlib
import json

# ==================== 演示企业岗位（2026-10-06 建；2026-10-07 改接企业端 + 审核链路）====================
# 背景：企业岗位表在移除 30 条编造岗位后归零 → 「我的投递」没有真实载体、链路跑不通。
# 用户 2026-10-06 决定放**少量、明确标注为演示**的岗位；2026-10-07 进一步要求
# 「**必须与真实链路一致**：由企业端发布，管理员审核通过后才在学员端显示」。
#
# ⚠️ 与「不编造」红线的关系：这些行**不是**冒充真实招聘信息，而是**显式声明为演示**：
#    ① 公司名带「（演示）」后缀；② job_listings.is_demo = 1；③ 前端强制打「演示数据」角标；
#    ④ 描述正文里写明「本岗位为平台演示数据，仅用于展示投递流程」。
#    四重标注确保学员不可能把它误认为真实在招岗位。
#
# ⚠️ 与真实链路的关系（2026-10-07 起）：
#    · 归属账号 = `DEMO_JOB_ENTERPRISE_ID`（**真实企业演示账号 `enterprise_demo`**，
#      不再是早期那个 `'__demo__'` sentinel）→ 企业端「岗位管理」里能看到、能编辑、能删除；
#    · 新建行 `review_status = 'pending'` 并**同时写一条 content_reviews**，
#      **必须由管理员审核通过后**才会出现在学员端（与真实企业发布的岗位走同一道门禁）；
#    · 已有行**只更新内容字段，绝不改写 `review_status`** —— 否则管理员驳回后
#      一重启就被种子逻辑重置（与政策侧踩过的「种子逻辑静默覆盖数据」同类）。
DEMO_JOBS = [
    {
        'key': 'demo-ec-operator',
        'title': '农产品电商运营专员',
        'company': '粤乡优品农业发展有限公司（演示）',
        'salary': '5K-8K',
        'location': '广州',
        'category': '电商运营',
        'job_type': '全职',
        'education': '大专',
        'experience': '1-3年',
        'company_size': '50-200人',
        'industry': '农产品电商',
        'requirements': [
            '熟悉主流电商平台的店铺运营与活动提报',
            '具备基础数据复盘能力，能看懂转化率、客单价等指标',
            '有生鲜或农产品类目经验者优先',
        ],
        'description': '负责公司农产品线上店铺的日常运营、活动策划与数据复盘。'
                       '（本岗位为平台演示数据，仅用于展示站内投递流程，非真实招聘信息）',
    },
    {
        'key': 'demo-lychee-tech',
        'title': '荔枝种植技术员',
        'company': '茂名荔乡种植专业合作社（演示）',
        'salary': '4K-6K',
        'location': '茂名',
        'category': '农业技术',
        'job_type': '全职',
        'education': '中专',
        'experience': '不限',
        'company_size': '20-50人',
        'industry': '种植业',
        'requirements': [
            '掌握荔枝栽培管理与主要病虫害防治基本知识',
            '能适应田间地头工作环境',
            '有农技推广或果园管理经验者优先',
        ],
        'description': '负责合作社荔枝园的日常栽培管理、物候期记录与技术归档。'
                       '（本岗位为平台演示数据，仅用于展示站内投递流程，非真实招聘信息）',
    },
]

# 演示岗位的归属账号 = **真实存在的企业演示账号**（由 `_ensure_demo_accounts` 创建：
# `enterprise_demo` / 123456 / 陈经理）。2026-10-07 用户要求「演示岗位要跟企业端挂钩」，
# 故由 sentinel `'__demo__'` 改为真实账号 —— 这样它在企业端「岗位管理」里可见可管，
# 审核也走同一个链路。
# ⚠️ 不要改回 sentinel：企业端列表查询是 `WHERE enterprise_id = <当前登录企业>`。
DEMO_JOB_ENTERPRISE_ID = 'enterprise_demo'

DEMO_JOBS_SEED_KEY = 'demo_jobs_seed'


def demo_jobs_signature():
    """演示岗位内容签名：内容有变才重建，避免每次启动都写库。"""
    payload = json.dumps(
        [[j['key'], j['title'], j['company'], j['salary'], j['location'], j['category'],
          j['job_type'], j['education'], j['experience'], j['company_size'], j['industry'],
          j['requirements'], j['description']] for j in DEMO_JOBS],
        ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode('utf-8')).hexdigest()


def create_review_with_cursor(cursor, content_type, content_id, submitter_id):
    """在既有事务里补一条待审记录。

    与 `create_content_review()` 等价，只是复用调用方已开的连接/事务 ——
    种子函数在 `init_db()` 里跑，不能中途另开连接（会撞 SQLite 写锁）。
    """
    cursor.execute(
        "INSERT INTO content_reviews (content_type, content_id, submitter_id, status) "
        "VALUES (?, ?, ?, 'pending')",
        (content_type, content_id, submitter_id))


def seed_demo_jobs(cursor):
    """灌入/更新演示企业岗位（幂等，按内容签名驱动）。

    ⚠️ 四条红线：
      1. **只动 `is_demo = 1` 的行** —— 真实企业发布的岗位、以及学员对它们的投递/收藏完全不受影响。
      2. **按标题就地更新，不删后重建** —— 删后重建会换 id，学员已有的 job_applications
         会变成指向不存在岗位的孤儿记录（与「_refresh_policies 静默抹数据」同一类坑）。
      3. **绝不覆盖 `review_status`** —— 那是管理员的审核结论，种子逻辑无权改写。
         只有「一次性迁移」与「首次新建」两种情形才会把它置为 `pending`。
      4. 仅当某个演示岗位**确实已从 DEMO_JOBS 中移除**时，才连带清理它的投递/收藏记录。

    2026-10-07 变更（用户要求「演示数据要跟企业端挂钩」）：
      由「平台预置 + 直接 approved」改为「**挂真实企业演示账号 + 走同一条审核链路**」。
    """
    signature = demo_jobs_signature()
    row = cursor.execute("SELECT value FROM seed_meta WHERE key = ?", (DEMO_JOBS_SEED_KEY,)).fetchone()

    # ① 一次性迁移（幂等）：早期版本把演示岗位挂在 sentinel '__demo__' 名下、并直接写成
    #    approved，完全绕过了审核链路。现在改挂真实企业演示账号，并回退成「待审核」。
    #    ⚠️ 只命中 `is_demo = 1` 的行（真实企业岗位的 is_demo 恒为 0），
    #    且改完 enterprise_id 后该条件即不再成立 → 再次启动**不会**把管理员后来的
    #    审核结论又打回 pending。
    cursor.execute(
        "UPDATE job_listings SET enterprise_id = ?, review_status = 'pending' "
        "WHERE is_demo = 1 AND (enterprise_id IS NULL OR enterprise_id = '' "
        "                       OR enterprise_id = '__demo__')",
        (DEMO_JOB_ENTERPRISE_ID,))

    # ② 补齐审核记录：没有 content_reviews 的演示岗位在管理端审核列表里不出现，
    #    「企业发布 → 平台审核」这条链路就是断的（迁移过来的老行本来就没有记录）。
    #    这一步放在签名短路**之前**，否则老库改不动（签名相同会直接 return）。
    missing = cursor.execute(
        "SELECT id FROM job_listings WHERE is_demo = 1 AND id NOT IN ("
        "  SELECT content_id FROM content_reviews WHERE content_type = 'job')").fetchall()
    for r in missing:
        create_review_with_cursor(cursor, 'job', r[0], DEMO_JOB_ENTERPRISE_ID)

    if row and row[0] == signature:
        return

    wanted_titles = {j['title'] for j in DEMO_JOBS}
    existing = {
        r['title']: r['id']
        for r in cursor.execute(
            "SELECT id, title FROM job_listings WHERE is_demo = 1").fetchall()
    }

    for job in DEMO_JOBS:
        reqs = json.dumps(job['requirements'], ensure_ascii=False)
        prev_id = existing.get(job['title'])
        if prev_id:
            # ⚠️ 这里**不写 review_status**：pending / approved / rejected 一律保持原样
            cursor.execute("""
                UPDATE job_listings
                   SET company = ?, salary = ?, requirements = ?, description = ?,
                       location = ?, category = ?, job_type = ?, education = ?,
                       experience = ?, company_size = ?, industry = ?,
                       enterprise_id = ?, is_demo = 1
                 WHERE id = ?
            """, (job['company'], job['salary'], reqs, job['description'],
                  job['location'], job['category'], job['job_type'], job['education'],
                  job['experience'], job['company_size'], job['industry'],
                  DEMO_JOB_ENTERPRISE_ID, prev_id))
        else:
            # 新建 = 企业「刚发布」的状态：待审核，学员端不可见
            cursor.execute("""
                INSERT INTO job_listings
                    (title, company, salary, requirements, description, location, category,
                     job_type, education, experience, company_size, industry,
                     posted_at, enterprise_id, review_status, is_demo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        datetime('now','localtime'), ?, 'pending', 1)
            """, (job['title'], job['company'], job['salary'], reqs, job['description'],
                  job['location'], job['category'], job['job_type'], job['education'],
                  job['experience'], job['company_size'], job['industry'],
                  DEMO_JOB_ENTERPRISE_ID))
            prev_id = cursor.lastrowid
            create_review_with_cursor(cursor, 'job', prev_id, DEMO_JOB_ENTERPRISE_ID)

    # 已被移出 DEMO_JOBS 的演示岗位：连带清掉指向它的投递/收藏/审核记录，避免孤儿
    stale_ids = [jid for title, jid in existing.items() if title not in wanted_titles]
    if stale_ids:
        _qm = ','.join('?' * len(stale_ids))
        cursor.execute("DELETE FROM job_applications WHERE job_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM saved_jobs WHERE job_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM content_reviews WHERE content_type = 'job' AND content_id IN (%s)" % _qm, stale_ids)
        cursor.execute("DELETE FROM job_listings WHERE id IN (%s)" % _qm, stale_ids)

    cursor.execute(
        "INSERT OR REPLACE INTO seed_meta (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
        (DEMO_JOBS_SEED_KEY, signature))
