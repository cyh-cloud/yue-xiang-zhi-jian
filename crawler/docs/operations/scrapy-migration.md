# Scrapy 迁移计划

状态: implemented

日期: 2026-10-21

本计划执行 [ADR 0003](../adr/0003-scrapy-collection-boundary.md) 的采集边界。Scrapy 是默认且最终的实时采集执行层，一个采集网站一个项目，通用契约进入共享包。转换器继续作为独立的跨库阶段。

天气是运行时 API 客户端，不属于 Scrapy 迁移。`weather` 继续负责请求、天气 DTO 解析和 15 分钟缓存；`open-meteo` 与 `qweather` 保持 `draft` 和禁用状态，不建立可执行 Spider。

采集生命周期和跨库术语以 ADR 0003 为权威定义。本计划采用固定流程：

```text
raw
  -> stage
  -> 采集库 std 候选标准实体
  -> 转换器
  -> 业务实体（draft / pending_review）
  -> 审核
  -> 同一条业务实体变为 published
  -> 前端只查询 published
```

`raw`、`stage` 和采集库 std 候选标准实体位于采集库，没有业务主键，前台不可见。业务实体位于业务库，有稳定业务主键和生命周期状态。发布实体是同一条业务实体审核、权利和可见性检查通过后的 `published` 状态，不是独立表或第二条记录。审核记录结论、审核人和时间并更新状态，不复制数据，不建立发布镜像表。`archived` 仍是同一条业务实体，只是不再是发布实体。

## 目标目录

下面的结构已实现。项目目录、共享契约和项目发现入口已经冻结；后续站点变更只修改对应项目目录。

```text
crawler/
  pyproject.toml
  uv.lock
  collection/
    shared/
      crawler_collection/
        candidate.py
        schema.py
        items.py
        evidence.py
        database.py
        registry.py
        admission.py
        dedupe.py
        logging.py
        robots.py
        run_id.py
        spiders.py
    projects/
      <source_id>/
        scrapy.cfg
        <source_package>/
          settings.py
          items.py
          middlewares.py
          pipelines.py
          candidate.py
          replay.py
          spiders/
  pipeline/
    converter.py
  tests/
    fixtures/
      evidence/
        <source_id>/
          ...
    collection/
```

## 运行入口

安装依赖和生成锁文件：

```powershell
cd crawler
uv lock
uv sync --group dev
```

共享依赖只包含 Scrapy。站点依赖按项目声明为可选依赖组，例如：

```powershell
uv sync --extra ihchina
uv sync --extra aqsc-moa
uv sync --extra cnipa
```

`--group dev` 安装全量测试需要的 BeautifulSoup、openpyxl 和 pypdf。单个项目运行只安装自己的 extra；不要把这些站点依赖重新放回全局 `dependencies`。

运行全量 crawler 测试：

```powershell
cd <repo-root>
python -m unittest discover -s crawler/tests -p "test_*.py" -t .
```

单独运行站点项目时，在该项目目录使用其 `scrapy.cfg`。fixture 项目（`aqsc-moa`、`cnipa`）没有 live 入口，只运行站点测试和 fixture 接口验证。

项目设置会自行把 crawler 包根加入 `sys.path`，因此可以直接从任一项目目录运行：

```powershell
cd crawler/collection/projects/ihchina
python -m scrapy list
python -m scrapy check
```

所有项目共用 `CollectionPipeline`、`RawEvidenceMiddleware`、`RobotsEvidenceMiddleware` 和 `RunReportExtension`。Pipeline 只写采集库；raw 中间件把实际响应或请求异常追加为证据；robots 中间件保存 allowed、disallowed、not-found 或 unknown 的真实结论；运行扩展为每次 live crawl 生成结构化 JSON 报告，报告中的 `failure_count` 统计解析异常、HTTP 4xx/5xx 和下载异常，`failure_reason` 保存对应摘要。项目配置同时提供数据库、下载根、报告根、来源注册表和限速参数。

一次 crawl 的 `run_id` 由 `CollectionSpiderMixin.from_crawler` 初始化，该次 crawl 的所有请求、raw、stage 和候选共用同一标识。写入 stage 前必须确认 raw 的 `source_id` 和 `run_id` 与 Item 一致，跨来源或跨运行引用会被阻断。

`crawler/pyproject.toml` 和 `crawler/uv.lock` 是唯一依赖声明和锁文件，所有项目在同一 uv 环境中运行。项目自己的目录、settings、Spider 和测试入口仍然隔离，不复制根锁文件。fixture 统一放在 `crawler/tests/fixtures/evidence/<source_id>/`，现有证据原地保留，每个项目只引用自己的子目录。

`crawler/pipeline/converter.py` 保持在 Scrapy 项目树之外。旧的手写来源实现和 `run_source.py` 在迁移期保留，直到对应来源完成切换。

## 责任边界

| 位置 | 责任 |
| --- | --- |
| 共享包 | Item 公共契约、原始证据、采集库写入、来源注册表、采集侧准入、去重、运行日志、robots 事实和公共测试 helper。 |
| 共享包之外 | 站点选择器、站点分页、站点限速、站点依赖、站点 helper 和站点验收样本。 |
| Scrapy 项目 | Spider、settings、middlewares、pipelines 组合、fixture 回放和站点依赖声明。 |
| 转换器 | 读取候选标准实体，执行跨库转换、冲突、人工保护、批次和回滚。 |

共享包不导入任何站点模块，不感知业务库，不包含转换器。Scrapy 项目不复制共享实现，不打开业务库，不调用转换器。

Pipeline 只写 `raw`、`stage` 和采集库 std 候选标准实体。它可以检查 rights、robots、必需字段和证据完整性，但检查不通过时只能把候选标记为 `blocked`、`deferred`，或者跳过候选写入，不能发布业务实体。业务发布门禁位于转换和审核链路。

运行产物固定落在 crawler 根下：数据库为 `crawler/data/crawler.db`，raw 文件为 `crawler/download/`，运行报告为 `crawler/data/reports/`。这些路径都在 `.gitignore` 覆盖范围内。

## 每个项目的职责

- 定义站点入口、分页、详情 URL 和选择器。
- 设置 User-Agent、并发、延迟、超时、重试、robots 策略和下载边界。
- 组合共享 Item、证据、去重、采集侧准入和采集库写入。
- 在共享 `pyproject.toml` 中声明站点专用依赖和运行说明。
- 用 `crawler/tests/fixtures/evidence/<source_id>/` 做离线回放，并增加该站点的失败和边界样本。
- 在来源审核记录中留下 canary、计数、证据和切换结论。

## 迁移顺序

1. **契约基线。** 固定共享 Item、证据字段、采集库写入、来源判断、采集侧准入、去重和日志契约，建立旧实现与新项目的 fixture 对照。
2. **共享包。** 从 8 个项目中选一个已登记来源验证共享包，不新增 demo 项目。
3. **`ihchina`。** 它是当前已有实时请求的 P0 来源，先完成 JSON 分页、详情、原始证据和候选标准实体的离线及隔离实时对照，再切换实时入口。
4. **`nzrc` 与 `nongmuhr`。** 迁移招聘列表、详情和保存式 fixture，并在站点允许时完成 5 条列表记录和 5 条详情记录的实时样本验证。
5. **`dialect-org`、`cass-linguistics`、`feiyiw`。** 迁移方言、公开研究资料和非遗资讯，并在站点允许时完成 5 条列表记录和 5 条详情记录的实时样本验证。受限或登录后内容继续排除。
6. **`aqsc-moa` 与 `cnipa`。** 只建立项目骨架、fixture 和接口契约测试，不执行实时文件采集。两者继续使用现有 XLSX、PDF 和公告附件契约，业务发布门禁不变。
7. **旧实现退役。** 每个已通过实时验证和审核的来源切换后，单独提交旧路径清理。清理不删除历史证据，不修改既有 ADR。

每个阶段一次只切换一个来源。批量迁移可以作为计划分组，不能作为一次实时切换。

## 样本验收门

| 门 | 通过条件 |
| --- | --- |
| 离线契约 | 现有 fixture 套件通过；Scrapy 回放得到相同的必填字段、URL、locator、版权字段和跳过结果。 |
| 采集库回放 | 使用临时采集库连续运行两次，raw 按请求追加，stage 按 `(source_id, source_item_id)` 幂等并指向最近一次 raw 证据，候选标准实体按来源自然键不重复，运行计数可对账。 |
| 实时 canary | 使用独立采集库和下载目录；robots、访问等级、User-Agent、限速、状态码、哈希和取得时间完整。 |
| 样本覆盖 | `ihchina`、`nzrc`、`nongmuhr`、`dialect-org`、`cass-linguistics`、`feiyiw` 在站点允许时验证 5 条列表记录和 5 条详情记录；保留失败样本和反例。 |
| 文件项目边界 | `aqsc-moa` 和 `cnipa` 只通过项目骨架、fixture 和接口契约测试验收，不执行实时文件采集。 |
| 封锁记录 | 站点阻止实时验证时，记录 URL、时间、状态码或错误、证据位置和重试条件；fixture 通过不等于实时成功。 |
| 业务发布门禁 | 与旧实现逐条比较发布资格；`aqsc-moa`、`cnipa` 和受限来源的边界不得放宽。 |
| 边界检查 | 项目导入图和测试证明 Scrapy 运行不打开业务库，不调用转换器。 |
| 回退演练 | 记录切回旧实现的方式，并证明回退不删除 raw、stage 或候选标准实体证据。 |
| 文档契约 | 新增或修改的路径、命令和链接通过机械检查；文档不出现 em-dash。 |

实时 canary 只在核心字段、计数和门禁结果达到来源审核记录中的约定后，才允许切换正式写入权。

## 共存与回退

- 迁移期一个来源只有一个实时写入者。旧实现保持写入权时，Scrapy 项目只写临时采集库和临时下载目录。
- 禁止旧实现和 Scrapy 项目在同一运行窗口同时写正式采集库。
- 切换以来源为粒度，通过运行路由配置把该 `source_id` 指向 Scrapy 项目。回退时把同一路由指回旧实现。
- 切换后保留旧实现至少一个观察周期。旧代码删除是独立变更，不与首次切换合并。
- fixture 测试在切换前同时覆盖旧、新路径；切换后以新路径为主，旧路径只保留到退役完成。
- 回退保留已采集证据和新候选实体，不通过删除数据伪造干净回退。

## 非目标

- 本轮不修改业务库 schema、后端、前端或 ADR 0001/0002/0003。
- 不让 Scrapy Pipeline 写业务库，不用 Pipeline 替代转换器。
- 不把天气迁移为 Scrapy 项目；`open-meteo` 和 `qweather` 不建立 Spider。
- 不为排除或延后的来源创建项目。本轮恰好 8 个项目：`ihchina`、`nzrc`、`nongmuhr`、`dialect-org`、`cass-linguistics`、`feiyiw`、`aqsc-moa`、`cnipa`。
- 前 6 个项目做小样本联网验证，目标为 5 条列表记录和 5 条详情记录；`aqsc-moa` 与 `cnipa` 只做项目骨架、接口和 fixture 测试，不做真实文件采集。
- `5ajob`、`zhongguoyuyan`、`cnopendata`、`open-meteo`、`qweather` 不是可执行项目。`5ajob` 不建 Scrapy 项目、不启用 live、不重新开启采集，只保留现有离线解析器和 fixture 测试；`zhongguoyuyan` 保持 `excluded`，`cnopendata` 保持 `deferred`。
- [来源扩展候选](source-expansion.md) 中的 9 个未验证站点仍是候选，不属于本轮 8 个项目；正式登记和审核前不建立项目。
- 不新增调度平台、代理池、验证码处理或反爬策略。
- 不执行全量采集，不改写 Git 历史。`aqsc-moa` 与 `cnipa` 不执行真实文件采集。

## 当前验收结果

完整记录见 [Scrapy 迁移集成验收](../specs/scrapy-migration-validation.md)。

| 项目 | 结果 |
| --- | --- |
| `ihchina` | live 5 列表 + 5 详情通过 |
| `nzrc` | live 21 列表 + 5 详情通过，联系方式不采集 |
| `nongmuhr` | 5 列表 + 5 详情 HTTP 200，但字段结构变化，blocked |
| `dialect-org` | live 15 列表 + 5 详情通过 |
| `cass-linguistics` | live 9 列表 + 5 详情通过 |
| `feiyiw` | live 25 列表 + 5 详情通过 |
| `aqsc-moa` | fixture 骨架通过，无 live |
| `cnipa` | fixture 骨架通过，无 live |

## 框架例外

Scrapy 是默认且最终的采集执行层。只有出现可复现的 Scrapy 能力边界时，才允许为单个来源引入其他框架；并且必须新增 ADR 或获得项目负责人明确批准。实现者不能因为不熟悉 Scrapy、需要浏览器脚本、需要解析 XLSX 或 PDF、或者需要自定义限速而自行切换框架。

## 相关文档

- [采集规则](collection-rules.md)
- [采集验收清单](validation.md)
- [证据账本](evidence-ledger.md)
- [批次转换 Interface](../schema/conversion-interface.md)
- [来源注册表](../sources.json)
