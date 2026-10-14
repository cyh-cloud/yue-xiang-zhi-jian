# 迁移方案：SQLite 单库 → PostgreSQL 分 schema + 内容落库

> 宪法：对内优化，对外输出不变。只迁数据层与内容归属，不动 AI 模块，不动 URL 与响应结构。

## 0. 现状实测（全部来自本仓库，非估计）

| 项 | 实测值 |
| --- | --- |
| SQLite 表 | 36 张（含 `sqlite_sequence`） |
| 建表 DDL | `backend/db_schema.py` 503 行，44 条 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX` |
| `execute()` 调用点 | 数据层 257 处 + 领域路由直连 18 处 = 275 处 |
| 直接 SQL 绕过 `db_domains` 的路由 | `enterprise` 8 处、`public` 3 处、`admin` 1、`teaching_support` 1、`notifications` 1 |
| `cursor.lastrowid` | 15 处 |
| `INSERT OR IGNORE` | 5 处（`farming` 2、`notifications` 2、`db_seed_*` 1） |
| `datetime('now','localtime')` | 30 余处默认值与显式写入 |
| `PRAGMA table_info` | 4 处（补列逻辑） |
| 内容字面量 | `domain_data/` 六份约 6400 行 + `domains/` 六份约 1300 行 |
| 单测 | 20 个文件，481 个用例，当前 51.8 秒，2 个既有失败（`test_get_students` / `test_get_teacher_dashboard`，迁移前就红） |
| 现库行数 | `content_reviews` 551、`user_sessions` 6471（全部已过期）、`courses` 277、`job_listings` 47、`models_3d` 28、`discussions` 22、`comments` 22、`messages` 19 |

现库数据质量问题（迁移前必须处理，否则 PG 的 `NOT NULL` 会拒收）：

- `points` 有 2 行 `user_id IS NULL`，`user_id` 是主键。这 2 行是历史脏数据。
- `messages` 有 2 行 `sender_id` / `receiver_id` 指向不存在的 username（uuid 与 `STU001`，
  正是历史上「把 students.id 当收件人」那个 bug 的残留）。
- `job_listings` 最大 id 533 但只有 47 行，中间有 486 个空洞（历史删除）。
- 所有 `*_at` / `date` 列实测均为 `YYYY-MM-DD HH:MM:SS` 或 `YYYY-MM-DD` 字符串，
  无其它格式，可安全保持 TEXT。
- 所有 JSON 列（`points.history` / `assignment_submissions.content` /
  `job_listings.requirements` / `resumes.experience` / `policies.source` /
  `government_policies.source`）实测全部是合法 JSON，可直接转 JSONB。

## 1. Schema 划分（按领域，你已选 b）

跨域引用实测清单决定归属，`public` 承载不归任何领域的共享表：

| schema | 表 | 依据 |
| --- | --- | --- |
| `public` | `users`、`points`、`sessions` | 被 8 个域引用，任何单属都会逼出跨 schema 依赖 |
| `agriculture` | `farming_products`、`farming_phenophases`、`farming_tasks`、`farming_subscriptions`、`farming_reminder_log`、`farming_sources`、`farming_categories` | 农时日历域 |
| `pest` | `pest_crops`、`pest_entries`、`pest_sources`、`pest_images`、`pest_entry_sources` | 病虫害域，`pest_data.py` 的 45 条 × 17 字段拆成正表 |
| `employment` | `job_listings`、`job_applications`、`saved_jobs`、`resumes`、`job_intents`、`recruitments` | 就业域 + 招募公告落库 |
| `teaching` | `announcements`、`assignments`、`assignment_submissions`、`courses`、`course_materials`、`models_3d`、`students` | 教学支撑域 |
| `resources` | `government_policies`、`success_cases`、`dialects`、`dialect_phrases` | 本土资源域 + 案例与方言落库 |
| `community` | `discussions`、`comments` | 社区域 |
| `notification` | `notifications`、`notification_reads` | 通知域 |
| `operator` | `content_reviews`、`system_announcements`、`carousels` | 审核与平台运营内容 |
| `crafts` | `crafts`、`craft_steps`、`craft_purchase_categories`、`craft_purchase_items` | 手工技艺落库（4 门 × 6 步 × 3 类 × 3-6 项） |

重命名两处，其余表名保持：

- `user_sessions` → `auth.sessions`（`auth` 是 PG 保留字，不能作 schema 名；表进 `public`）
- `farming_seed_meta` / `seed_meta` 删除（签名机制废除）

新增内容表 11 张：`pest_*` 5、`recruitments` 1、`success_cases` 1（案例的
`stats` / `milestones` / `sources` / `lessons` 四个子数组各拆一张子表，共 4 张）、
`dialects` + `dialect_phrases` 2、`crafts` 4。合计 36 → 46 张表。

## 2. 每张表的 extra 与两个新字段

- 全部 46 张表加 `extra JSONB NOT NULL DEFAULT '{}'::jsonb`，列名 `extra`（不用
  `metadata`，部分驱动对该名有意见），不建 GIN 索引。
- `agriculture.farming_tasks` 与 `pest.pest_entries` 各补 `verified_by TEXT NOT NULL DEFAULT ''`
  与 `verified_at TEXT NOT NULL DEFAULT ''`。这两个不是预留字段，是既有 `is_verified`
  的必然延伸：现在只记「核过了」，不记谁核的、什么时候核的，后台无法显示复核人、
  无法按时间找出该重新核的条目、出问题无法追溯。

## 3. 兼容层：只做一次，不做 275 次

`backend/db_connection.py` 重写为 PG 连接工厂，返回带行适配器的连接：

| PG 类型 | 适配成 | 替代的原逻辑 |
| --- | --- | --- |
| `jsonb` | Python 对象 | 11 处 `json.loads` |
| `numeric` | `int` / `float` | 否则 `json.dumps` 遇 `Decimal` 直接抛异常 |
| `timestamptz`（若出现） | `YYYY-MM-DD HH:MM:SS` 字符串 | 保持对外形状 |
| `boolean`（若出现） | `0` / `1` | 保持对外形状 |

占位符 `?` → `%s` 机械替换；`cursor.lastrowid` 15 处改为 `INSERT ... RETURNING id`；
`INSERT OR IGNORE` 5 处改为 `ON CONFLICT DO NOTHING`（两者在唯一键上等价，
但 `INSERT OR IGNORE` 会吞掉任何约束冲突，这条差异写进 ADR 0002）；
`PRAGMA table_info` 4 处改为查 `information_schema.columns`；
`executescript` 删除（PG 无对应物，迁移脚本改用 psql 或分条执行）。

必须单独处理的三处：

1. `db_domains/policies.py:68` 的 `substr(created_at, 1, 10)` 与 TEXT 的 `date` 列
   在 `COALESCE` 里混用，PG 报类型不匹配，显式转换。
2. `domains/enterprise/routes.py:155-157` 三表 JOIN 改全限定名
   `employment.job_listings JOIN public.users JOIN employment.resumes`。
3. `domains/notifications/routes.py:87` 用 `cur.rowcount` 判断是否更新成功，
   psycopg3 同为 `rowcount`，但要在适配层确认语义一致。

## 4. 数据迁移（一次性脚本，跑完归档）

`migrations/0001_from_sqlite.py`，只跑一次：

1. 建 schema、建表（DDL 来自 `migrations/0001_schema.sql`，结构定义属于代码，留仓库）。
2. 清 `points` 2 行 NULL 主键脏数据、`messages` 2 行孤儿引用（记录到迁移日志，不静默丢）。
3. 36 张表全量搬运，**整数 id 原样保留**，每张表迁完 `setval` 到 `max(id)+1`。
4. `user_sessions` 6471 行**不搬**（全部已过期，无业务意义），新表从零开始，
   登录自然重建；失效即删，不保留历史。
5. `domain_data/` 六份 + `domains/` 六份内容灌入新增的 11 张内容表。
6. 删除 `farming_seed_meta` 与 `seed_meta` 的对应行（表本身已不在新 schema）。

脚本跑通、验证通过后移入 `.scratch/migration-archive/`，不进版本库长期存放。
仓库里**不留内容副本**：既不留 `*_data.py`，也不留 `content.sql`。

新环境部署：`pg_dump -Fc` 出一份含全部内容的基线，新服务器 `pg_restore` 还原。
这是数据库备份，不是代码里的数据。

## 5. 内容归属与角色（你已定）

| 内容 | 可写角色 | 后台入口 |
| --- | --- | --- |
| 农时日历 | `operator` | 新建 `operator.html` |
| 病虫害知识 | `operator` | 新建 `operator.html` |
| 手工技艺 | `teacher` + `operator` | `teacher.html` 现有页 + `operator.html` |
| 方言知识 | `operator` | 新建 `operator.html` |
| 招募公告 | `operator` | 新建 `operator.html` |
| 成功案例 | `government` + `operator` | `government.html` 现有页 + `operator.html` |
| 政策 | `government` | `government.html` 已有 |
| 课程 / 3D / 公告 / 作业 | `teacher` | `teacher.html` 已有 |
| 岗位 | `enterprise` | `enterprise.html` 已有 |
| 用户 / 审核 / 系统公告 | `super_admin` | `admin.html` 已有 |

新增第 6 个角色 `operator`。它是 `super_admin` 的**子集**：拿到内容管理权，
拿不到用户管理权。`admin.html` 的 `users` 页对 `operator` 隐藏，
`/api/admin/users*` 与 `/api/admin/reviews/*` 对 `operator` 返回 403。

角色判定收敛为各域一个元组，替代散落的 `role != 'x'`：

```python
# backend/domains/agriculture/permissions.py（示例）
EDITABLE_BY = ('operator',)            # 农时与病虫内容
READABLE_BY = ()                       # 空 = 公开
```

`core.session.require_role()` 增加一个接受元组的重载，路由装饰器改为
`@require_role(*EDITABLE_BY)`。`operator` 登录后进 `operator.html`，
`portal.js` 的 `PORTAL.init(expectedRole)` 需要支持多角色，
否则 `operator` 打开 `operator.html` 会被踢回首页。

## 6. 测试改写清单

| 文件 | 动作 |
| --- | --- |
| `test_db_infrastructure.py` | 重写。「一个 `sqlite3.connect(`」改为「一个 PG 建连点」；`DB_PATH` 断言改为 `DATABASE_URL` 断言；表清单换成新 46 张；探针 `db_infrastructure_probe.py` 改为 PG 版 |
| `test_domain_data_modules.py` | **删除**。它锁死五个 `domain_data` 文件必须存在且内容不变，与本次目标直接冲突。改写为「内容表有行 + 11 条接口输出形状不变」 |
| `test_db_domain_boundaries.py` | 表名扫描改扫 `schema.table`；`OWNED_TABLES` 按新 schema 重列 |
| `test_paths.py` | `DB_DIR` / `DB_PATH` / Vercel `/tmp` 三条断言删除；`repo_paths` 断言保留 |
| `test_app.py` | 保留。它是纯 HTTP 契约测试，正好是「对外输出不变」的守门人 |
| `tests/test_*_domains.py` 14 个 | 保留 HTTP 断言。需要改的是 `_cleanup_sessions` 这类直连 SQL 的 helper，以及依赖 `domain_data` 的少数用例 |
| `tests/test_static_crafts_domains.py` | `CRAFTS_KNOWLEDGE` 的导入断言改为打 `/api/crafts/embroidery` |
| `tests/test_resources_domain.py` | `DIALECTS_DATA` 相关断言改打接口 |
| `e2e/serve.py` | 改为「建测试 database + 从基线 dump 还原」，不再 `init_db()` 从零造 |
| `e2e/playwright.config.js` | `YUEXIANG_DB` 环境变量改为 `DATABASE_URL` 指向测试库 |

两个既有失败（`test_get_students` / `test_get_teacher_dashboard`）迁移前就是红的，
原因是没有带 `X-Session-Id` 头，迁移时顺手修掉，不算本次范围外改动。

## 7. 执行顺序

1. PG 环境就绪：`DATABASE_URL` 进 `.env` / `.env.example`，`psycopg` 进 `requirements.txt`
2. `migrations/0001_schema.sql`（46 张表 + 索引 + CHECK）
3. `migrations/0002_from_sqlite.py`（搬 36 张表 + 灌 11 张内容表）
4. `db_connection.py` 重写为 PG 工厂 + 兼容层
5. `db_schema.py` / `database.py` / `db_domains/*` 的 SQL 迁移（275 处）
6. 5 个路由文件的直连 SQL 收进 `db_domains`
7. 删 `domain_data/`、删签名机制、删 `domains/` 里六份内容常量
8. 新增 `operator` 角色 + `operator.html` + 内容管理接口
9. 测试改写与补写
10. 删 `vercel.json` / `api/index.py`，`AGENTS.md` 与 `GLOSSARY.md` 同步

第 3 步完成后即可用 PG 跑通现有代码（SQL 还是 SQLite 方言之前），
第 5 步是唯一的高风险段，按 `db_domains` 模块一个一个换，每个换完跑一次单测。

## 8. 验收口径

- `rg sqlite3` 在仓库里零命中（`.scratch` 与 `.venv` 除外）。
- `rg -l "domain_data" backend/` 零命中。
- 481 个单测全绿（含顺手修的 2 个）。
- 13 个 e2e spec 全绿。
- `python tools/check_architecture.py` 与 `python tools/check_python.py` 通过。
- 11 条农业接口 + 2 条病虫害接口的响应 JSON 与迁移前逐字节一致
  （用迁移前的响应做快照比对）。
- PG 里 `SELECT COUNT(*)` 与现 SQLite 一致（除 `user_sessions` 归零）。
