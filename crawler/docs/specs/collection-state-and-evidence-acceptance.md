# 采集状态与证据链最终验收

状态: accepted-with-live-gaps

日期: 2026-10-22

基线提交: `d6e57ae`

本记录完成 issue #135 的最终集成、旧实时入口退役和全量回归。实现验收已完成，GitHub issue 与子票据保持 OPEN，符合本规格“不关闭任何 issue”的约束。

## 指针

- 父 issue: [#126](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/126)
- 验收 issue: [#135](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/135)
- 父规格: [collection-state-and-evidence.md](collection-state-and-evidence.md)
- 票据图: [collection-state-and-evidence-tickets.md](collection-state-and-evidence-tickets.md)
- 迁移边界: [ADR 0003](../adr/0003-scrapy-collection-boundary.md)
- live 验收: [scrapy-migration-validation.md](scrapy-migration-validation.md)
- 公开证据索引: [live-evidence-index.json](../operations/live-evidence-index.json)
- 稳定归档: `../crawler-live-evidence/issue-133-20261021/`

## 子票据状态

2026-10-22 使用 GitHub API 核对，7 个阻塞票据均为 OPEN，状态一致。实现工作已落在基线提交之前的集成历史中，关闭动作不在本分支执行。

| 票据 | 标题 | 状态 |
| --- | --- | --- |
| #127 | 统一采集状态、准入原因与权利优先级 | OPEN |
| #128 | 来源注册表派生唯一项目清单 | OPEN |
| #129 | 招聘候选写入岗位来源与地点关系 | OPEN |
| #130 | nongmuhr 真实站点校验与解析修复 | OPEN |
| #131 | ihchina 缺详情边界与真实 Scrapy 回放 | OPEN |
| #132 | aqsc-moa 与 cnipa 真实文件小样本 | OPEN |
| #133 | live 证据归档与验收记录收口 | OPEN |

## 切换前门禁

8 个正式来源均完成项目级 fixture replay、live canary 尝试、来源审核和隔离数据库检查。live canary 的失败或缺口按实际结果保留，没有把 fixture 写成 live 成功。

| 来源 | fixture replay | live canary | 来源审核 | 隔离数据库 |
| --- | --- | --- | --- | --- |
| `ihchina` | 通过 | 失败，列表 HTTP 504 | `approved-with-gaps` | 通过 |
| `nzrc` | 通过 | partial，robots not-found 写 deferred | `approved-with-gaps` | 通过 |
| `nongmuhr` | 通过 | succeeded | `approved` | 通过 |
| `dialect-org` | 通过 | partial，robots not-found 写 deferred | `approved-with-gaps` | 通过 |
| `cass-linguistics` | 通过 | partial，5 条成功、4 条详情 404 | `approved-with-gaps` | 通过 |
| `feiyiw` | 通过 | partial，robots not-found 写 deferred | `approved-with-gaps` | 通过 |
| `aqsc-moa` | 通过 | partial，附件 HTTP 403，blocked | `blocked` | 通过 |
| `cnipa` | 通过 | partial，58 条 deferred | `approved-with-gaps` | 通过 |

## Fixture 双回放

每个项目使用独立临时数据库和下载目录，从项目 replay 入口连续运行两次。下表的 stage、candidate、deferred、blocked、failed 来自第一次运行报告；raw_fetches 是两次运行后的数据库计数。

| 来源 | 运行次数 | 首次状态 | discovered | stage | candidate | deferred | blocked | failed | raw_fetches 两次 |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `ihchina` | 2 | succeeded | 2 | 2 | 2 | 0 | 0 | 0 | 6 |
| `nzrc` | 2 | succeeded | 2 | 2 | 2 | 0 | 0 | 0 | 2 |
| `nongmuhr` | 2 | succeeded | 2 | 2 | 2 | 0 | 0 | 0 | 2 |
| `dialect-org` | 2 | succeeded | 1 | 1 | 1 | 0 | 0 | 0 | 2 |
| `cass-linguistics` | 2 | succeeded | 1 | 1 | 1 | 0 | 0 | 0 | 2 |
| `feiyiw` | 2 | succeeded | 1 | 1 | 1 | 0 | 0 | 0 | 2 |
| `aqsc-moa` | 2 | partial | 8 | 8 | 0 | 8 | 0 | 0 | 10 |
| `cnipa` | 2 | partial | 2 | 2 | 0 | 2 | 0 | 0 | 6 |

候选状态在两次回放后保持幂等:

- `ihchina`、`nzrc`、`nongmuhr`、`dialect-org`、`cass-linguistics`、`feiyiw` 分别为 2、2、2、1、1、1 条 `candidate`。
- `aqsc-moa` 为 8 条 `deferred`，`cnipa` 为 2 条 `deferred`。
- 文件项目的 XLSX 和 PDF 哈希、字节数、承载页和 locator 在项目测试中断言。
- 所有回放只写临时采集库，不创建 `yuexiang.db`，不导入转换器或后端。

## Live 实际结果

live 证据沿用稳定归档，没有改写索引口径。2026-10-21 的 8 次实际运行结果如下。

| 来源 | 状态 | raw | stage | candidate | deferred | blocked | failed | 阻断或缺口 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `ihchina` | failed | 1 | 0 | 0 | 0 | 0 | 1 | 列表 HTTP 504 |
| `nzrc` | partial | 21 | 20 | 0 | 20 | 0 | 0 | robots not-found |
| `nongmuhr` | succeeded | 11 | 10 | 10 | 0 | 0 | 0 | 无 |
| `dialect-org` | partial | 16 | 15 | 0 | 15 | 0 | 0 | robots not-found |
| `cass-linguistics` | partial | 10 | 5 | 0 | 5 | 0 | 4 | 4 条详情 HTTP 404 |
| `feiyiw` | partial | 23 | 20 | 0 | 20 | 0 | 0 | robots not-found |
| `aqsc-moa` | partial | 3 | 1 | 0 | 0 | 1 | 1 | robots unknown，附件 HTTP 403 |
| `cnipa` | partial | 2 | 58 | 0 | 58 | 0 | 0 | robots not-found，仅验证 www 公告页和第一份 PDF |

## 旧入口退役

- 删除 `crawler/run.py`，不再提供跨来源在线 CLI。
- 删除 `crawler/pipeline/run_source.py`，不再提供旧实时 runner。
- 将旧 fixture 回归器改为 `crawler/pipeline/offline_fixture.py`，移除 `urllib.request`、`HTTPError`、`urlopen` 和 `Request`。
- `offline_fixture.py` 只接受 `fixture`、`xlsx`、`pdf`、`saved` 和 `announcement-fixture`，传入 `live` 会在打开数据库前失败。
- `crawler.pipeline` 不再导出 `run_source`、`RunConfig`、`SourceRunResult` 或 `RUN_MODES`。
- 回归测试 `test_legacy_online_entrypoints_are_retired` 和 `test_live_mode_is_rejected_before_any_writer_is_opened` 防止旧入口被重新引入。
- 8 个正式来源的实时写入只允许通过 `crawler/collection/projects/` 下各自的 Scrapy 项目。

## 全量验证

| 检查 | 结果 |
| --- | --- |
| crawler 全量单测 | 231 tests，OK |
| schema 与 contract | `test_schema_contract`、`test_candidate_state_schema`、`check_contracts.py` 通过 |
| Python 静态 | `tools/check_python.py` 通过，448 个文件 |
| 架构检查 | `tools/check_architecture.py` 通过，21 个领域路由目录、16 个共享层模块 |
| 8 项目 `scrapy list` | 8/8 退出 0，均返回对应 Spider 名 |
| 8 项目 `scrapy check` | 8/8 退出 0，每个项目当前运行 0 contracts |
| whitespace | `git diff --check` 退出 0 |
| lock | `crawler/uv.lock` 通过 `uv lock --check` |
| live evidence index | `build_live_evidence_index --validate-only` 通过 |

## 残余风险与发布条件

- `ihchina` live 仍 blocked。解除条件是 `https://www.ihchina.cn/getProject.html` 恢复稳定响应，并重新运行列表和至少 5 条详情。
- `aqsc-moa` live 仍 blocked。解除条件是 robots 和附件入口恢复可采集响应，并取得真实 XLSX 的文件名、MIME、大小和 SHA-256。
- `cass-linguistics` 有 4 条详情 404。解除条件是列表链接指向的详情恢复，或来源审核确认这些记录已下线并从样本口径排除。
- `cnipa` 只验证 www 公告页和第一份 PDF。`ggfw` 签名 PDF 路径继续保持 unknown robots 约束，扩大范围前需单独复核。
- `nzrc`、`dialect-org`、`cass-linguistics`、`feiyiw`、`cnipa` 的 robots not-found 只表示没有可读规则，不构成发布授权。
- 8 个项目当前 `scrapy check` 为 0 contracts。该命令证明项目可加载，不证明 Spider 行为；行为回归由 231 项单测和项目 fixture replay 覆盖。
- live 证据归档时间为 2026-10-21，本次未刷新索引。任何后续 live 成功或失败都必须重新运行并生成新归档，不能复用本记录覆盖旧结论。
- 子票据和验收 issue 保持 OPEN。关闭动作由有权限的负责人按 tracker 流程执行，不属于本分支。
- 回滚依赖上一个应用版本和数据库快照。不得恢复旧双 writer，也不得删除已采集 raw、stage 和候选证据。

## 结论

旧实时入口已退役，Scrapy 是唯一实时采集写入路径。8 个正式项目完成 fixture 双回放、来源审核、live canary 尝试和隔离数据库检查。`ihchina` 与 `aqsc-moa` 保持有实际证据的 live blocked 结论，其余来源的缺口按实际 partial 或 deferred 结果记录。
