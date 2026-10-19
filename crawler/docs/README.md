# 粤乡智匠数据采集设计索引

本目录是数据采集系统的设计交付，不是运行中的爬虫。这里只保留导航和共享语义，不复制来源明细或问题明细。

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
```

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
10. `TASKS.md`：当前任务图、依赖和实施批次指针。
11. `ISSUES.md`：问题清单、状态和待决事项的唯一真相源；`BLOCKERS.md` 只是入口指针。

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
