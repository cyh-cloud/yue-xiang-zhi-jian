# Scrapy 迁移计划

状态: draft

日期: 2026-10-21

本计划执行 [ADR 0003](../adr/0003-scrapy-collection-boundary.md) 的采集边界。Scrapy 是默认实时采集执行层，一个采集网站一个项目，通用契约进入共享包。转换器继续作为独立的跨库阶段。

## 目标目录

下面的结构是迁移目标。目录和模块在第一个实现票据中冻结，本轮不创建运行代码。

```text
crawler/
  collection/
    shared/
      crawler_collection/
        items.py
        evidence.py
        database.py
        registry.py
        publication.py
        dedupe.py
        logging.py
        robots.py
    projects/
      <source_id>/
        scrapy.cfg
        <source_package>/
          settings.py
          items.py
          middlewares.py
          pipelines.py
          spiders/
        requirements.txt
  pipeline/
    converter.py
  tests/
    fixtures/
    collection/
```

`crawler/pipeline/converter.py` 保持在 Scrapy 项目树之外。旧的手写来源实现和 `run_source.py` 在迁移期保留，直到对应来源完成切换。

## 责任边界

| 位置 | 责任 |
| --- | --- |
| 共享包 | Item 公共契约、原始证据、采集库写入、来源注册表、发布门禁、去重、运行日志、robots 事实和公共测试 helper。 |
| 共享包之外 | 站点选择器、站点分页、站点限速、站点依赖、站点 helper 和站点验收样本。 |
| Scrapy 项目 | Spider、settings、middlewares、pipelines 组合、fixture 回放和站点依赖锁定。 |
| 转换器 | 读取候选标准实体，执行跨库转换、冲突、人工保护、批次和回滚。 |

共享包不导入任何站点模块，不感知业务库，不包含转换器。Scrapy 项目不复制共享实现，不打开业务库，不调用转换器。

## 每个项目的职责

- 定义站点入口、分页、详情 URL 和选择器。
- 设置 User-Agent、并发、延迟、超时、重试、robots 策略和下载边界。
- 组合共享 Item、证据、去重、发布门禁和采集库写入。
- 保存站点专用依赖和运行说明。
- 用现有 fixture 做离线回放，并增加该站点的失败和边界样本。
- 在来源审核记录中留下 canary、计数、证据和切换结论。

## 迁移顺序

1. **契约基线。** 固定共享 Item、证据字段、采集库写入、来源判断、发布门禁、去重和日志契约，建立旧实现与新项目的 fixture 对照。
2. **共享包。** 用一个 fixture-only 项目验证共享包，不接实时来源。
3. **`ihchina`。** 它是当前已有实时请求的 P0 来源，先完成 JSON 分页、详情、原始证据和候选标准实体的离线及隔离实时对照，再切换实时入口。
4. **`aqsc-moa` 与 `cnipa`。** 分别迁移 XLSX 和 PDF、公告附件路径。每个来源单独切换，并保持现有详情 URL 与发布门禁不变。
5. **`nzrc` 与 `nongmuhr`。** 迁移招聘列表、详情和保存式 fixture。实时访问只在来源文档和授权边界允许时启用。
6. **`dialect-org`、`feiyiw`、`cass-linguistics`。** 迁移方言、非遗资讯和公开研究资料。受限或登录后内容继续排除。
7. **旧实现退役。** 每个来源切换并通过观察期后，单独提交旧路径清理。清理不删除历史证据，不修改既有 ADR。

每个阶段一次只切换一个来源。批量迁移可以作为计划分组，不能作为一次实时切换。

## 样本验收门

| 门 | 通过条件 |
| --- | --- |
| 离线契约 | 现有 fixture 套件通过；Scrapy 回放得到相同的必填字段、URL、locator、版权字段和跳过结果。 |
| 采集库回放 | 使用临时采集库连续运行两次，raw 按请求追加，stage 与本次 raw 证据一一对应，候选标准实体按来源自然键不重复，运行计数可对账。 |
| 实时 canary | 使用独立采集库和下载目录；robots、访问等级、User-Agent、限速、状态码、哈希和取得时间完整。 |
| 样本覆盖 | 至少验证一个列表页和三条详情记录，少于三条时验证全部；保留失败样本和反例。 |
| 发布门禁 | 与旧实现逐条比较发布资格；`aqsc-moa`、`cnipa` 和受限来源的边界不得放宽。 |
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

- 不安装 Scrapy，不创建 Spider、settings、middlewares 或 pipelines。
- 不修改采集库 schema、业务库 schema、来源注册表或现有 ADR。
- 不让 Scrapy Pipeline 写业务库，不用 Pipeline 替代转换器。
- 不为排除或延后的来源创建项目，列表以 [ADR 0003](../adr/0003-scrapy-collection-boundary.md) 为准。
- 不新增调度平台、代理池、验证码处理或反爬策略。
- 不执行网络采集，不改写 Git 历史，不创建 PR 或 issue。

## 相关文档

- [采集规则](collection-rules.md)
- [采集验收清单](validation.md)
- [证据账本](evidence-ledger.md)
- [批次转换 Interface](../schema/conversion-interface.md)
- [来源注册表](../sources.json)
