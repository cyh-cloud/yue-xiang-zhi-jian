# 0002 内容数据全部落库，代码零硬数据，删掉转发层

状态：accepted

## Context

原架构有三套彼此冲突的数据位置：SQLite 36 张表（业务数据）、`backend/domain_data/`
六个内容模块（约 6400 行 Python 字面量）、`backend/domains/` 里六份混在路由文件中的
内容常量。内容改了要重启，重启时靠 sha1 内容签名决定是否 DELETE + INSERT 重灌。

这套机制有三个后果：

1. **种子重灌会吃掉人工结论。** `db_seed_farming.py` 按产品 DELETE 后重插，
   `farming_tasks.id` 自增值随之变化（库里实测起点为 431，是历史重灌的痕迹），
   而该 id 直接下发给前端。农技人员标记的复核结论、运营改过的内容，
   只要有人动了对应的 `*_data.py`，下次启动即被冲掉。
2. **启动耗时随内容量线性增长。** 指纹计算要把全部字段 JSON 序列化一遍，
   再加全表 DELETE + INSERT。内容涨十倍，启动从 5 秒变 50 秒。
3. **「代码是真相源、库是缓存」与「数据库是唯一数据源」直接矛盾。**

另有两个独立问题在同一次重构里解决：

- `backend/database.py` 是 163 个符号的纯转发层，零逻辑。它被
  `test_db_infrastructure.py` 的「不得出现 `from database import`」锁死，
  导致任何代码简化都要先绕过这条检查。
- 5 个领域路由文件绕过 `db_domains` 直连 SQL，其中 5 处一个查询 JOIN 跨了多张表，
  是「领域之间不得互相 import」这条硬约束与真实跨域读取需求冲突的结果。

## Decision

- `domain_data/` 六个内容模块与 `domains/` 里六份内容常量全部落库，
  对应 Python 模块删除，代码里不再有业务内容字面量。
- 删除全部内容签名与种子重灌机制：`farming_seed_meta`、`seed_meta` 两张表，
  `farming_seed_signature()`、`policies_signature()`、`demo_jobs_signature()`
  一并移除。`init_db()` 不再播种内容，启动路径只做建表与补列。
- 删 `backend/database.py` 转发层。数据层接口就是 `db_domains/<域>.py` 本身，
  调用方 `from db_domains import farming`。
- 5 处跨域多表查询改用 SQLite 视图（`v_enterprise_applications` /
  `v_enterprise_job_stats` / `v_home_stats` / `v_submission_context` /
  `v_reviewable_models`），定义与建表语句同住 `db_schema.py`。
  域路由只 `SELECT * FROM v_xxx`，域间 import 边为零。
- 剩下 13 处直连 SQL 收进 `db_domains`；`content_reviews` 的跨域删除收敛为
  `reviews.delete_reviews_for(content_type, content_id)` 一个入口。
- 新增第 6 个角色 `operator`，它是 `super_admin` 的子集：拿内容管理权，
  不拿用户管理与审核权。权限判定收敛到 `core/permissions.py` 一张
  `CAPABILITIES` 表，不再散落 `role != 'x'` 硬判。
- `farming_tasks` 与 `pest_entries` 补 `verified_by` / `verified_at`，
  作为既有 `is_verified` 的必然延伸。
- 全部 56 张表带 `extra TEXT NOT NULL DEFAULT '{}'` 一列容纳未来字段，不建索引。
- 对外 API 契约基本不变：URL、状态码、错误码一律不动。**唯一例外**是
  `GET /api/agriculture/pest-knowledge` 改为服务端筛选 + 分页
  （新增 `limit` / `offset` / `total`，`crops[].count` 语义改为筛选后条数）。
  理由：45 条时一次拉完可行，数据涨到成百上千条时不可行，
  而该接口是唯一一个「一次拉全量再前端筛」的接口。
- 去掉 Vercel 部署。serverless 无持久盘，本项目也不适合 512MB / 10 秒限制。
  改为自托管单机部署，Flask 裸跑 + `threaded=True`，静态文件继续由 Flask 伺服。

## ADR 0001 的修订

ADR 0001 的「领域路由模块之间不得互相 import」修为
「**不得访问不具有该角色权限的数据**」。运营角色出现后跨域是常态，
禁止 import 已不适用。

`tools/check_architecture.py` 的 `KIND_CROSS_DOMAIN` 改为按
`core/permissions.py` 的 `CAPABILITIES` 判权，判据是「调用方声明的能力集
是否覆盖被调模块所属能力域」。每个 `db_domains` 模块标注 `CAPABILITY`，
检查器才有判据。

机械检查覆盖**结构性越界**（某个域的代码 import 了它无权访问的 `db_domains`
模块）。它抓不住**动态绕过**（函数内先查权限再写），后者靠单测覆盖：
`operator` 打 `/api/admin/users` 必须 403。

## Consequences

- 新环境部署改为「拷一份基线 `.db` 文件」，仓库里不保留内容副本。
- `test_domain_data_modules.py`（352 行，锁死五个 `domain_data` 文件必须存在且
  内容不变）整体删除，改写为「内容表有行 + 接口输出形状不变」。
- `test_db_infrastructure.py` 的「`database.xxx` 符号面不变」与
  「不得 `from database import`」两条断言删除，改为断言 `db_domains` 各模块符号面。
- 改内容从「改 `*_data.py` + 重启」变成「运营后台改 + 立即生效」，无需重启。
- 一次性迁移脚本 `migrations/0001_content_to_db.py` 跑完归档进 `.scratch/`，
  不作为运行时代码，也不作为内容副本长期留在仓库。

## 拒绝的备选

- **换 PostgreSQL**：动机（爬数据多导致 SQLite 瓶颈）实测不成立。现库最大表
  6471 行且全是过期会话，第二大 551 行；本项目瓶颈在 AI 调用与 Flask 并发，
  不在数据库。PG 在小数据下更慢且多占约 150MB 内存，服务器只有 2GB。
- **保留内容签名、只把内容搬进库**：签名机制的存在前提是「代码是真相源」，
  与本次目标冲突，且重灌吃掉人工结论的问题原样存在。
- **`migrations/0002_content.sql` 常驻仓库**：仓库里仍留一份数据副本，
  只是从「运行时读」变成「迁移时读」，源头没变。
- **每个域一个 `EDITABLE_BY` 元组**：只把散落从 20 个文件减到 10 个，
  且表达不了「`operator` 是 `super_admin` 子集」，加角色时要改多处，漏一个就是漏洞。
- **跨域用窄接口而非视图**：为 5 个单调用方各造一个接口，接口数量暴涨，
  每个仍然只有 1 个调用方，是一批浅模块。视图让 JOIN 只有一份且域间零 import。
- **保留 `database.py` 契约层**：163 个符号的纯转发，删除测试下复杂度会消失
  而非扩散；且它在重构期会藏住「某个调用打到哪份数据」。
- **Redis 或 JWT 存会话**：引入第二个数据源，与宪法冲突；本项目访问量下无收益。
- **时间列换 `timestamptz`、布尔列换 `BOOLEAN`**：会打破对外输出不变。
- **Gunicorn / waitress 多 worker**：2GB 内存、低访问量下只会让连接池变 N 份。
- **权限判定留在各域的 `EDITABLE_BY` 元组**：只把散落从 20 个文件减到 10 个，
  且表达不了「`operator` 是 `super_admin` 子集」，加角色时要改多处，漏一个就是漏洞。
- **速查接口保持一次拉全量**：数据量上来后首屏要传成百上千条，移动端直接卡死。
  且后端 `list_pest_entries` 早已支持 `crop` / `kind` / `q` 三个参数，前端只是没用。
