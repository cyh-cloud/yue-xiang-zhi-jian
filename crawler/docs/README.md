# 粤乡智匠数据采集设计索引

本目录是数据采集系统的设计、运行和验收索引。Scrapy 项目位于 `crawler/collection/projects/`，共享契约位于 `crawler/collection/shared/`。

## 交付边界

- 只修改 `crawler` 子项目。
- 不修改粤乡智匠后端、业务数据库、前端或部署配置。
- 单个下载文件不超过 100MB；超限文件只写说明。

## Crawler 验收

从仓库根运行自包含采集套件:

```powershell
python -m unittest discover -s crawler/tests -p "test_*.py" -t .
```

再运行:

```powershell
python crawler/tools/check_contracts.py
python tools/check_python.py
python tools/check_architecture.py
python -m crawler.tools.build_live_evidence_index --validate-only
uv lock --check
git diff --check
```

逐个项目检查 Spider 发现和契约:

```powershell
Get-ChildItem crawler/collection/projects -Directory |
  Where-Object Name -ne "__pycache__" |
  ForEach-Object {
    Push-Location $_.FullName
    python -m scrapy list
    python -m scrapy check
    Pop-Location
  }
```

Scrapy 项目的依赖由 `crawler/pyproject.toml` 和 `crawler/uv.lock` 统一管理。项目运行入口、fixture 回放和当前 8 项目验收结果见 `operations/scrapy-migration.md`、`specs/scrapy-migration-validation.md` 与 `specs/collection-state-and-evidence-acceptance.md`。

旧在线 CLI 和 `pipeline/run_source.py` 已退役。`pipeline/offline_fixture.py` 只用于离线 fixture 回归，不接受 `live` 模式。实时采集写入只允许通过 8 个 Scrapy 项目。

仓库根的全量单测需要应用基线数据库 `data/baseline.db` 或等效测试库，不属于 crawler 验收。clean clone 没有该被忽略数据库时，全量单测失败不代表 crawler 交付失败。

## 阅读顺序

1. `SPEC.md`：完整规格和已冻结的产品决策。
2. `GLOSSARY.md`：采集域术语。
3. `sources/CONTRACT.md`：来源文档共享接口和发布硬规则。
4. `sources.json`：来源清单、来源状态和访问边界的唯一真相源。
5. `sources/`：逐来源差异、证据、样本和字段映射。
6. `reviews/`：逐来源独立审核记录。
7. `schema/`：采集库、业务库变更和转换器设计。
8. `mapping/`：内容域字段映射。
9. `operations/`：采集规则、验收和上线顺序。
10. `specs/scrapy-migration-validation.md`：8 个 Scrapy 项目的集成验收和阻断记录。
11. `specs/collection-state-and-evidence-acceptance.md`：最终集成、旧入口退役和全量回归记录。
12. `TASKS.md`：当前任务图、依赖和实施批次指针。
13. `ISSUES.md`：问题清单、状态和待决事项的唯一真相源；`BLOCKERS.md` 只是入口指针。

## 状态含义

- `draft`：来源文档仍在编写，尚未形成可复核结论。
- `approved`：入口、字段、样本、映射和发布边界均可复现。
- `approved-with-gaps`：主体可用，缺口已明确记录。
- `blocked`：访问、结构或合规边界未解决，不能进入实现或业务发布。
- `deferred`：主体保留但当前不接入，文档必须写解除条件。
- `excluded`：已决定不采集，文档必须写排除原因和证据。

每个来源的实际状态以 `sources.json` 为准，审核记录必须与它保持一致。

## 实施批次

当前实施批次、依赖关系和完成情况只看 `TASKS.md`。原始六波次定义见 `SPEC.md` 的“Agent 编排”。

## 最新交付位置

最新设计交付位于 `crawler/docs`。来源变更先更新 `sources.json` 和对应来源文档，再更新任务图；未决问题只在 `ISSUES.md` 维护。
