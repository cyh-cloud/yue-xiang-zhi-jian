# 0002 迁库 PostgreSQL，内容数据全部落库，代码零硬数据

状态：accepted

## Context

原架构有三套彼此冲突的数据位置：SQLite 36 张表（业务数据）、`backend/domain_data/`
六个内容模块（约 6400 行 Python 字面量）、`backend/domains/` 里六份混在路由文件中的
内容常量。内容改了要重启，重启时靠 sha1 内容签名决定是否 DELETE + INSERT 重灌。

这套机制有三个后果，都是本次迁移要消除的：

1. **种子重灌会吃掉人工结论。** `db_seed_farming.py` 按产品 DELETE 后重插，
   `farming_tasks.id` 自增值随之变化（库里实测起点为 431，是历史重灌的痕迹），
   而该 id 直接下发给前端。农技人员在后台标记的复核结论、运营改过的内容，
   只要有人动了对应的 `*_data.py`，下次启动即被冲掉。
2. **启动耗时随内容量线性增长。** 指纹计算要把全部字段 JSON 序列化一遍，
   再加全表 DELETE + INSERT。内容涨十倍，启动从 5 秒变 50 秒。
3. **「代码是真相源、库是缓存」与「数据库是唯一数据源」直接矛盾。**

## Decision

- 数据库换 PostgreSQL，SQLite 彻底移除，`sqlite3` 不再出现在仓库任何位置。
- `domain_data/` 六个内容模块与 `domains/` 里六份内容常量全部落库，
  对应 Python 模块删除，代码里不再有业务内容字面量。
- 删除全部内容签名与种子重灌机制：`farming_seed_meta`、`seed_meta` 两张表，
  `farming_seed_signature()`、`policies_signature()`、`demo_jobs_signature()`
  一并移除。
- `init_db()` 不再承担建表、播种、清会话，启动路径只做「应用装配」。
- 表按领域分 schema（`public` / `agriculture` / `pest` / `employment` / `teaching` /
  `resources` / `community` / `notification` / `operator`），跨域 SQL 写全限定名。
- 每张表带 `extra JSONB NOT NULL DEFAULT '{}'::jsonb` 一列，用于容纳未来字段。
  不建 GIN 索引：当前没有任何查询走 JSONB，等有需求时在同一处迁移里补。
- 对外 API 契约零变化。为达到这一点，数据层保留既有形状：
  时间列仍是 `TEXT` 存 `YYYY-MM-DD HH:MM:SS`，布尔列仍是 `SMALLINT` 存 `0/1`，
  JSON 列在读取侧由兼容层还原成 Python 对象（替代原先 11 处 `json.loads`）。
- 登录凭证表 `auth.sessions` 继续放在 PostgreSQL。它是登录令牌登记簿，
  不是 AI 对话上下文；AI 对话历史原本只活在前端内存，本次不新增该能力。

## Consequences

- 新环境部署改为 `pg_dump` / `psql` 还原基线，仓库里不保留内容副本。
- `test_db_infrastructure.py` 的「只有一个 `sqlite3.connect(`」「`DB_PATH` 恒为
  `data/yuexiang.db`」「33 张表精确清单」三条断言全部重写。
- `test_domain_data_modules.py`（352 行，锁死五个 `domain_data` 文件必须存在且
  内容不变）整体删除，改写为「内容表有行、接口输出不变」的契约测试。
- `test_db_domain_boundaries.py` 的跨域表名扫描改为扫 `schema.table`，比原先更严。
- 新增第六个角色 `operator`（运营），它是 `super_admin` 的子集：
  运营拥有内容管理权限，不拥有用户管理权限。角色判定集中在各域的
  `EDITABLE_BY` 元组，不再散落 `role != 'x'` 硬判。
- 部署去掉 Vercel：serverless 无持久盘，PG 成为唯一数据源后没有 `DATABASE_URL`
  的 Vercel 部署必然坏掉。改为自托管单机部署，Flask 裸跑 + `threaded=True`，
  静态文件继续由 Flask 伺服。

## 拒绝的备选

- **保留内容签名、只把 SQLite 换成 PG**：签名机制的存在前提是「代码是真相源」，
  与本次目标冲突，且重灌吃掉人工结论的问题原样存在。
- **`migrations/0003_content.sql` 灌内容**：仓库里仍留一份数据副本，
  只是从「运行时读」变成「迁移时读」，源头没变。
- **Redis 存会话**：引入第二个数据源，与宪法冲突；本项目访问量下无收益。
- **JWT 无状态会话**：无法撤销，改密码后旧 token 仍有效。
- **引入 ORM（SQLAlchemy）**：手写 SQL 迁 PG 的逐条比对比 ORM 的隐式行为更可控。
- **时间列换 `timestamptz`、布尔列换 `BOOLEAN`**：会把 `2026-10-05 13:20:33`
  变成带时区 ISO 串、把 `0/1` 变成 `false/true`，直接打破对外输出不变。
- **Gunicorn / waitress 多 worker**：2GB 内存、低访问量下只会让连接池变 N 份，
  收益为零。
