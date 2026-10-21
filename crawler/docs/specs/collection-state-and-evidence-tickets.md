# 采集状态与证据链票据图

状态: ready-for-agent

日期: 2026-10-21

本文件是 [采集状态与证据链规格](collection-state-and-evidence.md) 与 GitHub 子 issue 的导航摘要，不复制票据正文。父 issue: [#126](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/126)。

## 任务图

```text
127 -> 129 -> 133
  |-> 130 ---^
  |-> 131 ---^
  |-> 132 ---^
128 --------------> 135
127,129,130,131,132,133 -> 135
```

## 票据

| 编号 | GitHub | 标题 | 阻塞于 |
| --- | --- | --- | --- |
| 127 | [#127](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/127) | P1 统一采集状态、准入原因与权利优先级 | 无 |
| 128 | [#128](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/128) | P1 来源注册表派生唯一项目清单 | 无 |
| 129 | [#129](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/129) | P1 招聘候选写入岗位来源与地点关系 | 127 |
| 130 | [#130](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/130) | P1 nongmuhr 真实站点校验与解析修复 | 127 |
| 131 | [#131](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/131) | P1 ihchina 缺详情边界与真实 Scrapy 回放 | 127 |
| 132 | [#132](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/132) | P1 aqsc-moa 与 cnipa 真实文件小样本 | 127 |
| 133 | [#133](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/133) | P2 live 证据归档与验收记录收口 | 127, 129, 130, 131, 132 |
| 135 | [#135](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/135) | P1 最终集成、旧入口退役与全量回归 | 127, 128, 129, 130, 131, 132, 133 |

## 并行规则

- 127 先冻结候选状态、准入原因、权利优先级和运行报告契约。
- 128 与 127 可并行，只处理来源注册表派生项目集合和目录一致性。
- 127 完成后，129、130、131、132 可以并行，各自只修改自己的项目、测试和来源记录。
- 133 汇总真实运行结果并归档证据，不把 fixture 结果写成 live 成功。
- 135 最后执行全量回归和旧入口退役，不在前面票据中提前删除实时入口。

## 边界

- 候选状态只使用 `candidate`、`deferred`、`blocked`。
- robots 404 记录为 `not-found`，允许采集和写入 deferred 候选，但不构成发布授权。
- 无直接详情 URL 时使用承载页加 locator，保留 `detail_url_status=missing`。
- 来源注册表是项目集合的唯一真相源。
- 不放宽真实阻断和发布门禁，不用 fixture 冒充 live。
- 不修改业务库 schema、后端或前端。
