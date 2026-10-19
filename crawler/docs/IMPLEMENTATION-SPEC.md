# 粤乡智匠采集系统实现规格

状态: ready-for-agent

日期: 2026-10-19

本文件是实现规格，供新会话直接驱动编码。设计来源是 `SPEC.md`、`sources/CONTRACT.md`、`schema/std-entities.md`、`schema/conversion-interface.md` 和 `ISSUES.md`。本文件不替代这些设计文档，只冻结实现顺序、模块 interface 和验收 seam。

## Problem Statement

采集设计已经冻结，但仓库里还没有可运行的采集器、采集库、std 投影和转换器。新会话如果从零探索，会重复读取大量来源文档，容易把“来源契约”“采集实现”和“业务发布”混在一起。需要一份独立实现规格，明确先建什么、模块之间用什么 interface、哪些 P0 门槛未关闭、哪些测试必须先写。

## Solution

在 `crawler` 子项目内实现一条可重复运行的采集流水线：

来源适配器 -> raw 采集记录 -> stage 来源投影 -> std 标准实体 -> dry-run 转换结果

第一版只实现 P0 来源的发现、详情抓取、raw/stage 落库和 std 投影。转换器先只支持 `dry_run=true`，不写粤乡智匠业务库。业务库写入、P1/P2 来源和真实发布在 P0 验收通过后另开实现票据。

## User Stories

1. 作为实现者，我想让新会话只读一份实现规格就能开始编码，以便不重复消化全部来源文档。
2. 作为实现者，我想让每个来源适配器有同一个 interface，以便新增来源不复制调度和落库逻辑。
3. 作为实现者，我想让采集库初始化幂等，以便重复运行不会重建或污染数据。
4. 作为实现者，我想让 raw 层保存 URL、状态、内容类型、取得时间、大小和 SHA-256，以便任何 std 记录都能回溯。
5. 作为实现者，我想让 stage 层按来源形状保存，以便来源字段改动不传播到 std。
6. 作为实现者，我想让 std 层只暴露标准实体，以便转换器不依赖页面结构。
7. 作为实现者，我想让 `ihchina` 通过公开 JSON 全量发现 3610 个子项，以便验证分页和去重。
8. 作为实现者，我想让 `ihchina` 详情抓取保留正文、传承人和相关项目，以便后续教学筛选。
9. 作为实现者，我想让 `aqsc-moa` 解析公告和 XLSX，以便得到名特优新、特质农品和行级来源定位。
10. 作为实现者，我想让 `cnipa` 通过检索接口找到公告和 PDF，以便保存公告级来源和产品行。
11. 作为审核者，我想让无详情 URL 的记录停在 std 或人工队列，以便不违反发布门槛。
12. 作为审核者，我想让水产标记有明确三态，以便关键词误报不会进入正确数据。
13. 作为审核者，我想让所有受限来源在调度前被拒绝，以便 robots 和登录边界不被绕过。
14. 作为转换器实现者，我想让 dry-run 只生成差异计划和冲突，以便先验证映射不写业务库。
15. 作为转换器实现者，我想让正式写入接口存在但默认关闭，以便 P0 门槛关闭后再启用。
16. 作为维护者，我想让实现代码集中在 `crawler` 内，以便不影响 Flask 后端。
17. 作为维护者，我想让测试从来源适配器 interface 和转换器 interface 进入，以便不锁内部函数。
18. 作为维护者，我想让一次采集运行有 run ID 和统计，以便失败可定位。
19. 作为维护者，我想让下载文件遵守 100MB 上限和目录规则，以便仓库不失控。
20. 作为维护者，我想让 P1/P2 来源在 P0 验收后接入，以便第一阶段可控。

## Implementation Decisions

### 目录与运行边界

- 运行代码放在 `crawler` 子项目内，使用独立 Python 包和独立采集库。
- 不修改 `backend/`、`db_schema.py`、前端、粤乡智匠业务库和现有 API。
- 新会话从 `crawler` 分支开始，不创建 PR 或 issue。
- 采集库路径通过环境变量覆盖，默认放在 `crawler/data/crawler.db`，不进入 Git。
- 下载根为 `crawler/download/<domain>/`。
- 依赖只增加采集所需的最小集合，优先使用 Python 标准库、`requests`、`openpyxl`、`pypdf` 和 Playwright。

### 单一来源适配器 Interface

每个来源实现一个适配器，外部 interface 固定为：

```text
discover(source, run) -> Iterable[SourceItem]
fetch_detail(item, run) -> DetailResult
to_stage(item, detail, run) -> StageRows
to_std(stage_rows, run) -> StdEntities
```

调用方只依赖这个 interface。分页、重试、限速、raw 保存、run 统计和异常分类由采集运行 module 统一处理。来源适配器只实现来源特有解析。

第一版适配器：`ihchina`、`aqsc-moa`、`cnipa`。其他来源只保留注册表条目，不实现采集。

### raw、stage、std 的写入顺序

每次运行：

1. 创建 `import_batches` 对应采集运行记录或独立采集运行记录。
2. `discover` 返回来源条目，写入 raw 请求记录和 stage 列表行。
3. `fetch_detail` 保存详情响应到 raw，再写 stage 详情行。
4. `to_std` 只从 stage 投影，不重新请求页面。
5. 同一实体按自然键升级写入 std。
6. 运行结束写成功数、失败数、跳过数和冲突数。

raw 写入失败时不得继续写 stage 和 std。stage 解析失败时保留 raw，记录失败，不生成空实体。

### 访问与合规门禁

- `access=public` 才允许自动请求。
- `access=login-required`、`robots-restricted`、`manual-only` 在调度层直接拒绝，不进入适配器。
- `zhongguoyuyan` 第一版不实现采集。
- `cnopendata` 只实现公开元数据登记，不实现行级采集。
- 个人简历、登录后联系方式、Cookie、会话令牌不进入任何表。
- 每个请求前解析 robots；失败或不可读时不视为允许。

### P0 来源实现

#### ihchina

- 列表使用公开 JSON 接口，`category_id=16`，`limit=100`，按 `p` 遍历。
- 必须校验 `total=3610`、唯一 ID 数量和重复数量。
- 详情 URL 使用 `/project_details/{id}.html`。
- 详情选择器使用已修正的 `.inherit_xx2 .x-tables` 容器和 `.article-nav`。
- 第一版至少投影 `std_ich_projects`；传承人和相关项目可写入 stage，std 投影优先项目主体。

#### aqsc-moa

- 公告列表按栏目分页，详情页解析附件链接。
- XLSX 使用 `openpyxl` 解析，保留工作表、行号、原始行和内容哈希。
- 同一公告存在附件和内嵌表时优先附件，不能重复计数。
- 动态查询只进入人工对账，不生成可直接发布的产品实体。
- 水产标记三态：`1`、`0`、`NULL`。关键词只触发复核，不单独判定。

#### cnipa

- 使用公开检索接口获取公告，详情接口返回短期签名 PDF URL。
- 签名 URL 只写 raw，不写长期来源字段。
- 长期详情 URL 使用检索详情页或公告页。
- PDF 解析失败时保留 raw 和失败原因，不生成猜测产品行。

### std 投影

第一版 std 输出：

- `std_ich_projects`
- `std_agri_products`
- `std_agri_product_sources`
- `std_sources`
- `import_conflicts` 或采集失败记录

实现必须遵守 `std-entities.md` 的自然键和不变式。标准实体名使用下划线复数，不使用点分名称。

### 转换器

- 第一版只实现 `run_batch(domain, batch)` 的 `dry_run=true`。
- `domain` 只支持 `ich` 和 `agri`。
- 输出差异计划、插入数、更新数、跳过数、冲突数和失败数。
- 不写粤乡智匠业务库。
- 正式写入分支可以存在，但必须由显式配置关闭，默认不可达。
- 天气不是合法 domain。

### 配置

配置通过环境变量或本地配置文件提供：

- 采集库路径
- 下载根
- 请求超时、重试次数、限速
- 是否启用 Playwright
- 目标数据库路径，仅 dry-run 读取
- 运行日志级别

账号、Cookie 和登录凭据不进入配置样例或仓库。

## Testing Decisions

### 最高测试 seam

最高 seam 是来源适配器 interface。测试从 `discover`、`fetch_detail`、`to_stage`、`to_std` 进入，验证来源契约和输出形状，不直接调用内部解析函数。

第二 seam 是转换器 `run_batch(domain, batch)`。测试只检查返回计划和冲突，不检查 SQL 或内部 helper。

第三 seam 是采集库迁移后的外部可观察行为：raw/stage/std 表和查询能按 URL、来源 ID、自然键回溯。

### 必须覆盖的行为

- 采集库初始化幂等。
- 重复 `discover` 不产生重复 std 实体。
- `ihchina` 分页总数、唯一 ID 和重复 ID 校验。
- 无详情 URL 的 aqsc 动态查询行不会进入业务发布候选。
- cnipa 签名 URL 不写入长期字段。
- robots-restricted 来源在调度层被拒绝。
- 水产关键词误报保持 `NULL` 或待复核。
- dry-run 不写业务库。
- 失败实体写失败统计和 raw 证据，不生成空记录。
- 100MB 下载上限和下载目录规则。

### 好测试的标准

测试验证外部可观察行为和契约输出，不锁解析函数名、SQL 字符串或日志措辞。网络测试使用已保存的 raw/stage fixture，不依赖站点当天可访问。真实网络验证只作为人工验收和来源文档更新。

### 既有参照

粤乡智匠现有单测使用 `unittest`，强调接口输出和业务行为。采集实现沿用 `unittest`，按 `crawler/tests/test_*.py` 组织，不引入新的测试框架。

## Out of Scope

- 不实现 P1/P2 来源采集器。
- 不实现正式业务库写入。
- 不实现发布审核后台和前端页面。
- 不实现代理池、分布式调度、消息队列和云存储。
- 不修改粤乡智匠现有 API、数据库 schema 和前端。
- 不创建正式数据库迁移。
- 不采集登录后内容、个人简历和受限正文。
- 不批量下载超过单文件 100MB 的文件。
- 不创建 PR 或 issue。

## Further Notes

P0-02 和 P0-04 是首批业务发布门槛。实现规格允许先做采集、raw/stage/std 和 dry-run，因为这两项只阻止发布，不阻止证据积累。

新会话应先读本文件，再按需读三个来源文档和对应 schema。不要把全部来源文档重新读一遍。

实现完成后的验收包括：

- `python -m unittest discover -s crawler/tests -p "test_*.py" -t .`
- `python tools/check_python.py`，如果新代码在检查范围内
- 一次 `ihchina` 分页全量发现
- 一次 `aqsc-moa` XLSX 样本采集
- 一次 `cnipa` 公告和 PDF 样本采集
- 一次 dry-run 转换计划
- `ISSUES.md` 中 P0 状态更新

