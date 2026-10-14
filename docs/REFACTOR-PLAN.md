# 重构方案：内容落库 + 数据层职责重划（继续用 SQLite）

> 宪法：对内优化，对外输出不变。只重构数据层与内容归属，不动 AI 模块，不动 URL 与响应结构。

## 1. 为什么不换 PostgreSQL

最初想换 PG，动机是「后续爬取数据太多，SQLite 会造成性能瓶颈」。实测后否定了这个动机：

- 现库最大表 `user_sessions` 6471 行（且全是过期垃圾），第二大 `content_reviews` 551 行。
  即使爬到现在的 1000 倍（几百万行），仍在 SQLite 的建议范围内。
- 本项目的瓶颈不在数据库：AI 调用是秒级延迟，Flask 单线程处理并发，数据库查询是微秒级。
- PG 在小数据下通常更慢（每次查询多一次进程间往返），且 PG 本身要占约 150MB 内存，
  而服务器只有 2GB。SQLite 库内嵌，内存开销接近零。
- PG 的真实优势（高并发写、复杂查询优化、多应用共享、扩展生态）本项目一个都用不上。

**但架构理由完全成立，且与数据库选型无关**：数据位置混乱（代码一套、库一套）、
种子重灌吃掉人工结论、内容不可运营。这些用 SQLite 一样能解决。

因此本次只做四件事：内容落库、删 `domain_data/`、删签名机制、数据层职责重划。
数据库引擎、275 处 SQL、20 个测试文件的绝大部分，一行不动。

## 2. 现状实测（全部来自本仓库，非估计）

| 项 | 实测值 |
| --- | --- |
| SQLite 表 | 36 张（含 `sqlite_sequence`） |
| 建表 DDL | `backend/db_schema.py` 503 行，44 条 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX` |
| `execute()` 调用点 | 数据层 257 处 + 领域路由直连 18 处 = 275 处 |
| `get_connection()` | 数据层 153 处 + 路由 5 处 |
| `cursor.lastrowid` | 15 处 |
| `INSERT OR IGNORE` | 5 处（`farming` 2、`notifications` 2、`db_seed_*` 1） |
| `datetime('now','localtime')` | 30 余处默认值与显式写入 |
| `PRAGMA table_info` | 4 处（补列逻辑） |
| `database.py` 再导出符号 | 163 个，本身零逻辑 |
| 生产代码 `import database` | 20 个文件，185 处 `database.xxx()` 调用 |
| 内容字面量 | `domain_data/` 六份约 6400 行 + `domains/` 六份约 1300 行 |
| 单测 | 20 个文件，481 个用例，当前 51.8 秒，2 个既有失败 |
| 现库行数 | `content_reviews` 551、`user_sessions` 6471（全部已过期）、`courses` 277、`job_listings` 47、`models_3d` 28、`discussions` 22、`comments` 22、`messages` 19 |

现库数据质量问题（内容落库前必须处理）：

- `points` 有 2 行 `user_id IS NULL`，而 `user_id` 是主键。历史脏数据。
- `messages` 有 2 行 `sender_id` / `receiver_id` 指向不存在的 username
  （一个 uuid、一个 `STU001`），是历史上「把 students.id 当收件人」那个 bug 的残留。
- `job_listings` 最大 id 533 但只有 47 行，中间 486 个空洞（历史删除）。
- 所有 `*_at` / `date` 列实测均为 `YYYY-MM-DD HH:MM:SS` 或 `YYYY-MM-DD`，无其它格式。
- 所有 JSON 列实测全部是合法 JSON。

## 3. 数据层职责重划

### 3.0 先落地权限模型（ADR 0001 修订的前置条件）

用户裁定：ADR 0001 的「领域路由模块之间不得互相 import」修为
「不得访问不具有该角色权限的数据」。运营角色出现后跨域是常态，禁止 import
已不适用。

这条规则要能机械检查，前提是**权限信息先在代码里显式存在**。当前它散落在
20 个路由文件的 `role != 'x'` 里，检查器无从判起。所以第一步是收敛：

```python
# backend/core/permissions.py
CAPABILITIES = {
    'farming.read':   (),                                  # 空 = 公开
    'farming.manage': ('operator', 'super_admin'),
    'pest.read':      (),
    'pest.manage':    ('operator', 'super_admin'),
    'craft.read':     (),
    'craft.manage':   ('teacher', 'operator', 'super_admin'),
    'dialect.manage': ('operator', 'super_admin'),
    'recruit.manage': ('operator', 'super_admin'),
    'case.read':      (),
    'case.manage':    ('government', 'operator', 'super_admin'),
    'policy.manage':  ('government', 'super_admin'),
    'course.manage':  ('teacher', 'super_admin'),
    'job.manage':     ('enterprise', 'super_admin'),
    'user.manage':    ('super_admin',),
    'review.moderate':('super_admin',),
}

def can(role, capability): ...
def require_capability(capability): ...   # 装饰器，替代 require_role
```

同时给每个 `db_domains` 模块标注它服务的能力域，让检查器有判据：

```python
# backend/db_domains/farming.py
CAPABILITY = 'farming'      # 本模块的数据归属这个能力域
```

**`tools/check_architecture.py` 的新规则**（替换 `KIND_CROSS_DOMAIN`）：

```text
对每条「域路由模块 -> db_domains 模块」的 import 边：
  调用方声明的能力集 ∩ 被调模块的 CAPABILITY 所需的 manage 能力
  若调用方是读操作且该域 read 能力为空 -> 放行
  若调用方是写操作且不持该能力 -> 报 violation
```

机械检查能抓住的是「`operator` 的代码 import 了 `users` 模块」这类结构性越界，
抓不住「同一个函数内先查权限再写」的动态绕过。后者靠单测覆盖
（见第 7 节：`operator` 打 `/api/admin/users` 必须 403）。

### 3.1 删掉 `database.py` 转发层

`database.py` 是 163 个符号的纯转发，本身零逻辑。它的「外部调用方」只有 5 个启动入口
或测试文件（`app.py` / `api/index.py` / `run.py` / `e2e/serve.py` / `test_app.py`），
没有一个业务调用方；而 `db_domains/` 的 18 个模块之间本来就直接互相 import，
从不经过它。

**删除测试**：删掉它，复杂度消失而非扩散。153 处 `get_connection()` 与 163 个函数
全部还在原处，只是调用方从 `database.get_x()` 改成 `db_domains.<域>.get_x()`。
这是典型的浅模块：接口（163 个名字）与实现（163 行 import）一样宽。

它在本次重构中的实际危害：`test_db_infrastructure.py` 的「仓库里不得出现
`from database import`」这条机械检查，逼所有新代码走这层转发，迁移期无法用
`grep db_domains.<域>` 判断某个调用打到哪份数据。

动作：删 `backend/database.py`，5 个入口改为 `from db_domains import farming, ...`。

### 3.2 跨域调用的真实规模（实测，不是估计）

把 185 处 `database.xxx()` 调用按「调用域」与「被调函数所属的 `db_domains` 模块」
逐一配对，结果：

- **跨域调用 61 个函数**，其中大半是 ADR 0001 明确定义的「窄接口」模式，
  保持不动：`admin` 调 `users` 8 个、`notifications` 调 `messages` 2 个、
  `teacher` 调 `students` 6 个、`public` 调 `courses` 4 个。
- **需要视图的只有 5 处**，判据是「一个查询里 JOIN 或 COUNT 跨了多张表」：

  | 位置 | 现状 | 视图 |
  | --- | --- | --- |
  | `domains/enterprise/routes.py:139-160` | JOIN `job_applications` + `job_listings` + `users` + `resumes` 四张表 | `v_enterprise_applications` |
  | `domains/enterprise/routes.py:199-208` | JOIN `job_applications` + `job_listings` | `v_enterprise_job_stats` |
  | `domains/public/routes.py:28-33` | 3 次 COUNT 跨 `students` / `courses` / `job_listings` | `v_home_stats` |
  | `domains/teaching_support/routes.py:110-112` | 单表读 `assignment_submissions` 但 JOIN 意图在 `assignments` | `v_submission_context` |
  | `domains/admin/routes.py:216-218` | `SELECT * FROM models_3d` | `v_reviewable_models` |

  视图定义写在 `db_schema.py`（与建表定义同住），域路由只 `SELECT * FROM v_xxx WHERE ...`。
  这样域间 import 边为零（读的是数据库对象，不是 Python 模块），JOIN 只有一份，
  将来拆服务时视图直接变成 API。

- **剩下 13 处直连 SQL 是「写别人的表」**，该收进 `db_domains`：
  `enterprise/routes.py` 的 6 处 INSERT/UPDATE/DELETE 打在 `employment` 的表上
  （含 `DELETE FROM content_reviews`），`notifications/routes.py:87` 的 UPDATE 打在
  `notification` 自己的表上但绕过了 `db_domains`。

### 3.3 `content_reviews` 的跨域删除收敛为一处

实测 5 处 `DELETE FROM content_reviews`，删除者是四个不同内容域
（`courses` 2 处、`procurements` 1 处、`enterprise` 1 处）。属主是 `reviews` 域。

动作：在 `db_domains/reviews.py` 加 `delete_reviews_for(content_type, content_id)`，
五个调用点都改成调它。与既有 `REVIEW_TARGET_WRITERS` 分派表同一形状。

### 3.4 24 处「多语句单连接」里只有 6 处需要真事务

逐个核实后，需要原子性的是：`update_points`（读余额后写）、`add_student`（读 max id 后写）、
`set_review_status`（改自己 + 分派写别人）、`delete_user_by_admin`（删三张表）、
`register_user`（写 users + points）、`save_resume`（upsert 两段）。
其余 18 处是「两条独立 write 恰好放在一个函数里」，不构成事务需求。

本次不动事务语义（SQLite 默认行为不变），但把这 6 处的名单写进代码注释，
避免后续有人在中间插一条不相关语句。

### 3.5 `add_student` 的 id 生成竞态

`students.py:43-48` 是「SELECT max → +1 → INSERT」，两个并发请求会撞主键。
SQLite 下报 `IntegrityError`，冒到前端是 500。改为序列前先查重，撞了重试一次；
或直接改用 `INTEGER PRIMARY KEY AUTOINCREMENT` 的隐式 rowid 再格式化成 `STU%03d`。

## 4. 内容落库

### 4.1 归属划分（按「谁能改」，不按「是不是运营」）

用户设计了 5 个角色，内容管理权按角色划分：

| 内容 | 现在位置 | 可写角色 |
| --- | --- | --- |
| 农时日历（8 作物 / 38 物候 / 123 任务 / 14 来源） | `domain_data/agriculture/farming_data.py` | `operator` |
| 病虫害知识（45 条 × 17 字段 + 24 来源 + 18 图） | `domain_data/pest_diagnosis/pest_data.py` | `operator` |
| 实拍图清单（18 条） | `domain_data/pest_diagnosis/pest_image_manifest.py` | `operator` |
| 招募公告（14 条） | `domain_data/employment/jobs_data.py` | `operator` |
| 成功案例（5 条，4 个子数组） | `domain_data/resources/cases_data.py` | `government` + `operator` |
| 政策（5 篇） | `domain_data/resources/policies_data.py` | `government`（已在库，停止从代码播种） |
| 手工技艺（4 门，三层嵌套采购指南） | `domains/crafts/routes.py` | `teacher` + `operator` |
| 方言知识（3 方言 + 短语 + 快问） | `domains/resources/dialect_voice.py` | `operator` |
| 农时分类标签（5 个） | `domain_data/agriculture/farming_data.py` | `operator` |

### 4.2 删除的内容（不再是数据，是缺陷）

| 位置 | 内容 | 为什么删 |
| --- | --- | --- |
| `domains/agriculture/calendar_data.py` | `_DEFAULT_AGRICULTURE_PRODUCTS` 6 作物 | 表读空时应明确失败，不该退回半份数据 |
| `domains/agriculture/calendar_data.py` | `_STATIC_AGRI_SUGGESTIONS` 6 作物 | AI 不可用时建议栏应明说不可用 |
| `domains/agriculture/prompts.py` | `_AGRI_PRODUCT_NAME_FALLBACK` + `AGRICULTURE_KNOWLEDGE` | 改读 `farming_products` 表 |

`_month_in_phase` / `_farming_task_brief` 两个纯函数保留，移入 `db_domains/farming.py`。

### 4.3 留在代码里的（规则与算法，不是数据）

| 位置 | 内容 | 理由 |
| --- | --- | --- |
| `shared/agri_dosage.py` | 8 条用药数值正则 + 免责声明原文 | 判定规则，三个领域共用 |
| `shared/solar_terms.py` | Meeus 节气算法 | 纯计算 |
| `shared/live_reading.py` `copywriting.py` `training_status.py` `ec_products.py` `resume_state.py` | 评分 rubric、状态标签、作物白名单 | 纯规则与纯配置 |
| `domains/ecommerce/prompts.py` `copy_fallback.py` `service_rules.py` | AI 提示词模板与降级文案 | 用户已声明 AI 模块后续大改，现在搬过去等于白搬 |
| `domains/teacher/reports.py` | AI 不可用时的兜底报告 | 同上 |

### 4.4 新增表

沿用现有命名风格（snake_case 复数、`is_` 前缀布尔、`_at` 后缀时间），每张表带
`extra TEXT NOT NULL DEFAULT '{}'`（SQLite 无 JSONB 类型，用 TEXT 存 JSON，
读取侧由兼容层解析）。

| 新表 | 来源 | 关键列 |
| --- | --- | --- |
| `farming_categories` | `FARMING_CATEGORY_LABELS` | `key` PK、`label`、`color`、`sort_order` |
| `pest_crops` | `PEST_KNOWLEDGE` 的作物层 | `id` PK、`name`、`icon`、`summary`、`sort_order` |
| `pest_entries` | `PEST_KNOWLEDGE[].common_diseases` | `id` PK、`crop_id` FK、`disease`、`alias`、`kind`、`pathogen`、`part`、`severity`、`symptoms`(JSON)、`occurrence`、`treatment`(JSON)、`prevention`(JSON)、`registered`(JSON)、`chem_table`(JSON)、`safety_note`、`is_verified`、`verified_by`、`verified_at` |
| `pest_sources` | `PEST_SOURCES` | `key` PK、`name`、`org`、`doc_type`、`doc_no`、`date`、`url`、`sort_order` |
| `pest_entry_sources` | `entry.sources` 多对多 | `entry_id` + `source_key` 联合 PK |
| `pest_images` | `pest_image_manifest.PEST_IMAGES` | `entry_id` PK/FK、`file`、`credit`、`license`、`caption`、`source_url`、`shot_date`、`note` |
| `recruitments` | `RECRUIT_DATA` | `key` PK、`title`、`org`、`region`、`category`、`job_type`、`headcount`、`education`、`experience`、`salary`、`description`、`publish_date`、`signup_start`、`deadline`、`signup_way`、`contact` |
| `recruitment_sources` | `RECRUIT_DATA[].sources` | `recruit_key` + `title` + `media` + `date` + `url` |
| `success_cases` | `SUCCESS_CASES` | `id` PK、`title`、`region`、`location`、`background`、`description`、`quote`、`quote_author` |
| `case_stats` | `case.stats` | `case_id` FK、`label`、`value`、`icon`、`sort_order` |
| `case_milestones` | `case.milestones` | `case_id` FK、`period`、`title`、`desc`、`sort_order` |
| `case_sources` | `case.sources` | `case_id` FK、`title`、`media`、`date`、`url`、`sort_order` |
| `case_lessons` | `case.lessons` | `case_id` FK、`text`、`sort_order` |
| `dialects` | `DIALECTS_DATA` | `id` PK、`name`、`region`、`emoji`、`areas`、`speakers`、`greeting`、`greeting_meaning`、`features`(JSON)、`sort_order` |
| `dialect_phrases` | `dialect.phrases` | `dialect_id` FK、`dialect`、`mandarin`、`pinyin`、`sort_order` |
| `dialect_quick_questions` | `dialect.quick_questions` | `dialect_id` FK、`question`、`sort_order` |
| `crafts` | `CRAFTS_KNOWLEDGE` 技艺层 | `id` PK、`name`、`origin`、`history`、`level`、`sort_order` |
| `craft_steps` | `craft.steps` | `craft_id` FK、`title`、`desc`、`tips`、`sort_order` |
| `craft_purchase_categories` | `purchase_guide.categories` | `craft_id` FK、`key`、`label`、`desc`、`sort_order` |
| `craft_purchase_items` | `category.items` | `craft_id` + `category_key`、`name`、`price`、`spec`、`tip`、`where`、`sort_order` |
| `craft_budgets` | `purchase_guide.budget` | `craft_id` PK/FK、`starter`、`advanced`、`buying_tips` |

新增 20 张表，总数 36 → 56 张。`pest_entry_sources` / `recruitment_sources` /
`case_*` 四个子表是原有内嵌数组的正规化；`craft_*` 四张是三层嵌套的拆平。

### 4.5 `farming_tasks` 与 `pest_entries` 补两个字段

`verified_by TEXT NOT NULL DEFAULT ''`、`verified_at TEXT NOT NULL DEFAULT ''`。

这两个不是预留字段，是既有 `is_verified` 的必然延伸：现在只记「核过了」，
不记谁核的、什么时候核的。后台无法显示复核人，无法按时间找出该重新核的条目，
出问题无法追溯。

### 4.6 `extra` 列

全部 56 张表加 `extra TEXT NOT NULL DEFAULT '{}'`，SQLite 无 JSONB，存 JSON 文本。
不建索引：当前没有任何查询走这个列。等真有需求时在同一处迁移里补，并写清为什么。

## 5. 新增第 6 个角色 `operator`

`operator` 是 `super_admin` 的**子集**：拿内容管理权，不拿用户管理权。

- `admin.html` 的 `users` 页对 `operator` 隐藏；
- `/api/admin/users*` 与 `/api/admin/reviews/*` 对 `operator` 返回 403；
- 登录后进新建的 `operator.html`；
- `portal.js` 的 `PORTAL.init(expectedRole)` 改为支持多角色白名单，
  否则 `operator` 打开 `operator.html` 会被踢回首页。

### 5.1 权限判定收敛到一个模块

不用「每个域一个 `EDITABLE_BY` 元组」：那只是把散落从 20 个文件减到 10 个，
且表达不了「`operator` 是 `super_admin` 子集」这个语义
（`EDITABLE_BY = ('operator','super_admin')` 写十遍，加第七个角色时要改十处，
漏一个就是权限漏洞）。

改为 `backend/core/permissions.py` 一张表：

```python
CAPABILITIES = {
    'farming.manage':  ('operator', 'super_admin'),
    'pest.manage':     ('operator', 'super_admin'),
    'dialect.manage':  ('operator', 'super_admin'),
    'recruit.manage':  ('operator', 'super_admin'),
    'craft.manage':    ('teacher', 'operator', 'super_admin'),
    'case.manage':     ('government', 'operator', 'super_admin'),
    'policy.manage':   ('government', 'super_admin'),
    'course.manage':   ('teacher', 'super_admin'),
    'job.manage':      ('enterprise', 'super_admin'),
    'user.manage':     ('super_admin',),      # operator 明确不在
    'review.moderate': ('super_admin',),      # operator 明确不在
}

def can(role, capability): ...
```

加角色时改一个字典，「operator 不能碰用户管理」是显式的一条，不是「十处都没写它」。

## 6. 速查接口改服务端筛选（本次唯一一处对外变化）

宪法修订：原「对外输出不变」在这一点上让位于「后期数据量大时不能一次拉全量」。
这是本次**唯一**一处接口形状变化，需在 ADR 0002 与 `GLOSSARY.md` 记录。

现状实测：

- 后端 `domains/pest/knowledge.py:60` 的 `list_pest_entries` **已支持**
  `crop` / `kind` / `q` 三个筛选参数，只是前端一个都没用。
- 前端 `script.js:3527` 调 `/api/agriculture/pest-knowledge` 不带参数，
  一次取回 45 条，`pestGuideMatches()` 本地 filter。
- 响应里的 `crops[].count` 已经存在（`knowledge.py:101`），但那是**全量**条数，
  不是筛选后条数。作物按钮的计数目前由前端 `renderPestCropFilter()` 本地数出来。

改动：

| 侧 | 动作 |
| --- | --- |
| 后端 | 接口不变，仍接 `crop` / `kind` / `q`；`crops[].count` 语义改为「当前筛选条件下该作物的条数」（与按钮计数天然一致） |
| 后端 | 新增 `limit` / `offset`，默认 `limit=50`。45 条时一次拿完，超过时分页 |
| 后端 | 响应新增 `total`（筛选后总条数，供前端显示「共 N 条」与判断是否还有下一页） |
| 前端 | `loadPestKnowledge` 带参数请求；`pestGuideMatches()` 删除，改服务端筛选 |
| 前端 | 作物切换 / 关键词输入改为重新请求（带 300ms 防抖，避免每敲一字打一次） |
| 前端 | 计数直接读 `crops[].count`，`renderPestCropFilter()` 里的本地统计删除 |
| 前端 | 分页控件：`total > limit` 时才出现 |

**不动的**：卡片字段、详情弹窗、`disclaimer`、`stats`、空态与错误态措辞。
「来源没给就显示未提供」「无授权图不冒充」两条硬约定原样保留。

e2e `read-contracts.spec.js` 与 `tests/test_pest_domains.py` 里打到该接口的断言
按新形状更新，并补一条「带 `crop` 参数只返回该作物」的用例。

## 7. 运营后台 `operator.html`

内容落库后必须有个界面改内容，否则只能连库写 SQL，内容落库的运营价值没落地。

新增页面与接口（与既有门户页同构，复用 `portal.js` / `portal.css`）：

| 区块 | 接口 | 操作 |
| --- | --- | --- |
| 农时日历 | `GET/POST/PUT/DELETE /api/operator/farming/*` | 作物、物候期、任务、来源、分类的增删改 |
| 病虫害知识 | `GET/POST/PUT/DELETE /api/operator/pest/*` | 条目、来源、图片关联的增删改 |
| 手工技艺 | `GET/POST/PUT/DELETE /api/operator/crafts/*` | 技艺、步骤、采购指南的增删改 |
| 方言知识 | `GET/POST/PUT/DELETE /api/operator/dialects/*` | 方言、短语、快问的增删改 |
| 招募公告 | `GET/POST/PUT/DELETE /api/operator/recruitments/*` | 公告的增删改 |
| 成功案例 | `GET/POST/PUT/DELETE /api/operator/cases/*` | 案例与四个子表的增删改 |

「标记已复核」按钮写 `verified_by` / `verified_at`（取当前登录用户），
这是本次补这两个字段的直接用途。

## 8. 测试改写清单

| 文件 | 动作 |
| --- | --- |
| `test_domain_data_modules.py` | **删除**。它锁死五个 `domain_data` 文件必须存在且内容不变，与本次目标直接冲突。改写为「内容表有行 + 接口输出形状不变」 |
| `test_db_infrastructure.py` | 重写。「只有一个 `sqlite3.connect(`」「`DB_PATH` 恒为 `data/yuexiang.db`」保留；删 `database.py` 后「符号面不变」改为「`db_domains` 各模块符号面不变」；表清单换成新 56 张；删 `from database import` 禁令 |
| `test_db_domain_boundaries.py` | `OWNED_TABLES` 按新表重列；新增视图的读取不算跨域 |
| `test_paths.py` | 保留（`repo_paths` 断言不依赖 `database.py`） |
| `test_app.py` | 保留。纯 HTTP 契约测试，是「对外输出不变」的守门人 |
| `tests/test_static_crafts_domains.py` | `CRAFTS_KNOWLEDGE` 导入断言改为打 `/api/crafts/embroidery` |
| `tests/test_resources_domain.py` | `DIALECTS_DATA` 相关断言改打接口 |
| `tests/test_agriculture_domain.py` | 删「表读空回退 6 作物硬编码」用例（该行为本次删除） |
| 其余 11 个 `tests/test_*_domains.py` | 保留 HTTP 断言，改直连 SQL 的 helper |
| `e2e/serve.py` | 改为「拷一份基线库 + 灌必要种子」，不再走签名重灌 |
| `e2e/playwright.config.js` | `YUEXIANG_DB` 语义不变，仍指向临时库 |

两个既有失败（`test_get_students` / `test_get_teacher_dashboard`）迁移前就是红的
（没带 `X-Session-Id` 头），顺手修掉，验收口径是「481 全绿」。

## 9. 执行顺序

1. **先立权限模型**：`core/permissions.py` + 各 `db_domains` 模块标注 `CAPABILITY`
   + 20 个路由文件的 `role != 'x'` 改为 `require_capability(...)`。
   这一步零数据变化，20 个测试文件应保持全绿，是后续所有步骤的地基。
2. `tools/check_architecture.py` 的 `KIND_CROSS_DOMAIN` 换成权限判据
3. 清现库脏数据（`points` 2 行 NULL 主键、`messages` 2 行孤儿引用），记录到迁移日志
4. `db_schema.py` 加 20 张新表 + 5 个视图 + `farming_tasks` / `pest_entries` 两列
5. `migrations/0001_content_to_db.py`：把 `domain_data/` 六份 + `domains/` 六份灌进新表，
   跑完验证通过后归档进 `.scratch/`，不进版本库长期存放
6. 数据访问层改读新表（`db_domains/farming.py` / 新增 `db_domains/pest.py` /
   `db_domains/crafts.py` / `db_domains/dialects.py` / `db_domains/recruitments.py` /
   `db_domains/content.py`）
7. 删 `domain_data/`、删签名机制（`farming_seed_meta` / `seed_meta` 两张表 +
   三个 `*_signature()`）、删 `domains/` 里六份内容常量
8. 删 `database.py`，185 处调用改为 `db_domains.<域>.<函数>`
9. 5 处改视图、13 处直连 SQL 收进 `db_domains`、`content_reviews` 删除收敛为一处
10. 速查接口改服务端筛选 + 前端相应改动
11. 新增 `operator` 角色 + `operator.html` + 内容管理接口
12. 修 `add_student` id 竞态
13. 测试改写与补写
14. 删 `vercel.json` / `api/index.py`，`AGENTS.md` / `GLOSSARY.md` / ADR 同步

第 5 步完成后内容就在库里了，但代码还在读 `domain_data/`，两者暂时并存；
第 7 步是切换点。第 8 步（删转发层）可与第 6 步并行，互不影响。
第 1、2 步必须最先做：没有显式权限模型，`check_architecture.py` 无从判起。

## 9. 验收口径

- `rg -l "domain_data" backend/` 零命中。
- `rg "sqlite3" ` 仍在 `db_connection.py` 一处（引擎没换，这是对的）。
- `core/permissions.py` 是全站唯一的角色判定处，`rg "role !=|role ==|role'\] !=" backend/` 零命中。
- 481 个单测全绿（含顺手修的 2 个）。
- 13 个 e2e spec 全绿。
- `python tools/check_architecture.py` 与 `python tools/check_python.py` 通过。
- 11 条农业接口 + 2 条病虫害接口 + 2 条技艺接口 + 2 条方言接口的响应 JSON
  与重构前逐字节一致（用重构前的响应做快照比对）。`pest-knowledge` 例外：
  它按第 6 节改为服务端筛选，需单独比对「不带参数时返回的条目集合与字段」一致。
- 新库里 56 张表全部有行（除订阅、提醒日志等用户行为表）。
- `operator` 登录后能改农时/病虫/技艺/方言/招募/案例，改完前台立即生效（重启也不需要）。
- `operator` 访问 `/api/admin/users` 返回 403。
- `check_architecture.py` 能抓住新造的结构性越界：临时给某个 `operator` 域路由加一句
  `from db_domains.users import delete_user_by_admin`，检查必须报 violation。
