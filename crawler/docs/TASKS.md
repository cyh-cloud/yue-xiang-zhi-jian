# 本地任务图

本文件代替远程 tracker，不创建 issue 或 PR。任务只记录依赖、产出和当前状态，问题明细指向 `ISSUES.md`。

## 已完成

| 任务 | 产出 | 状态依据 |
| --- | --- | --- |
| `spec` | `SPEC.md` | 规格已冻结 |
| `source-baseline` | 14 份来源文档 | 首轮实现已落盘 |
| `review-baseline` | 14 份独立审核记录 | 首轮审核已落盘 |
| `architecture-baseline` | `schema/`、`mapping/`、`operations/` | 设计文档已落盘 |
| `registry-contract` | `sources.json`、`sources/CONTRACT.md`、`README.md` | 来源注册表和共享契约已建立 |
| `publication-gate` | `pipeline/publication.py`、`pipeline/converter.py`、`pipeline/run_source.py` | 四域共用发布门禁，missing/null/blocked 只计一次跳过 |
| `raw-evidence` | `pipeline/evidence.py`、`pipeline/database.py` | 实际响应字节、哈希、URL、headers、locator 和 raw_files 落库 |
| `raw-evidence-append-only` | `pipeline/evidence.py`、`pipeline/database.py`、`crawler/tests/test_raw_evidence.py` | 重复运行追加 raw_files，保存最终 URL 和实际字节数，missing 记录强制 locator |
| `registry-enforcement` | `pipeline/source_registry.py`、`pipeline/run_source.py`、`pipeline/converter.py` | 运行和转换统一读取来源注册表，blocked/login/prohibited/excluded 不执行 |
| `offline-detail-parsers` | `pipeline/sources/ihchina.py`、`pipeline/sources/fiveajob.py`、`pipeline/run_source.py` | IHChina 项目/传承人 fixture 遍历、CNIPA 多 PDF、5ajob 详情 HTML 解析 |
| `weather-runtime-cache` | `pipeline/sources/weather_sources.py` | 15 分钟线程安全 DTO 缓存和 TTL 测试 |
| `history-scan-hardening` | `tools/check_history_hygiene.py`、`tools/public_hygiene.py` | 私有/session 路径、凭证、HTML 隐藏表单、XLSX 联系人列、PDF 元数据和二进制证据扫描；公开基线为空 |
| `public-fixture-hygiene` | `tools/generate_public_fixtures.py`、`tests/fixtures/evidence/` | 9 个确定性合成 fixture，无个人数据、隐藏 token、原始作者元数据或完整源附件 |
| `schema-contract-parity` | `pipeline/database.py`、`docs/schema/crawler-db.md` | 文档嵌入实际 DDL，主 std 和关系表带 direct/missing locator CHECK，农产品自然键统一 |
| `crawler-acceptance-command` | `docs/README.md`、`docs/operations/validation.md` | 自包含 crawler 单测命令和全仓基线数据库边界 |
| `history-clean-public-branch` | `main`、`crawler/docs/operations/history-hygiene.md` | 从 `main` 重建单提交公开分支，空基线，clean clone 历史扫描 0 命中 |
| `converter-service` | `pipeline/converter.py` | 真实 batch_id、std_sources 优先级、冲突落库和 rollback |
| `registry-alignment` | `sources.json`、`sources/`、`reviews/`、`ISSUES.md` | 状态、权利、计数和证据对齐 |
| `contract-hardening` | `tools/check_contracts.py`、`tools/check_history_hygiene.py` | 文档、实现、问题统计和历史卫生机械检查 |

## 延后

| 任务 | 状态 | 解除条件 |
| --- | --- | --- |
| `real-source-runs` | deferred | 完成 IHChina 全量详情、CNIPA 全量 PDF 和 HTML 公告附件、Dialect 15 条的真实运行证据；5ajob 需先取得可复核许可，再验证 250 页列表和详情回填 |
| `research-resource-schema` | deferred | 冻结 `std_research_sources`、`std_research_resources` 的字段、自然键和回滚方式 |

## 待复核

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `acceptance-remediation-review` | `contract-hardening` | 复核发布门禁、raw 证据、转换器批次和来源状态 |

## 首批阻塞

无。所有未完成项都在 `ISSUES.md` 标为 `deferred` 或 `excluded`，且 `阻塞首批=否`。公开分支已从 `main` 重建并验证 0 命中；实时源全量证据仍按 deferred 条件处理。
