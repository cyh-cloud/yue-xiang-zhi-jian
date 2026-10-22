# Scrapy 迁移票据图

状态: ready-for-agent

日期: 2026-10-21

本文件是 [Scrapy 迁移规格](scrapy-migration.md) 与 GitHub 子 issue 的导航摘要，不复制票据正文。父 issue: [#106](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/106)。

## 任务图

```text
01 -> 02 -> 03 -> 04
                    |-> 05 ihchina
                    |-> 06 nzrc
                    |-> 07 nongmuhr
                    |-> 08 dialect-org
                    |-> 09 cass-linguistics
                    |-> 10 feiyiw
                    |-> 11 aqsc-moa
                    |-> 12 cnipa
                    |          |
                    +----------+-> 13 -> 14
```

## 票据

| 编号 | GitHub | 标题 | 阻塞于 |
| --- | --- | --- | --- |
| 01 | [#107](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/107) | 建立 Scrapy 共享骨架并冻结公共采集契约 | 无 |
| 02 | [#108](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/108) | 扩展采集库候选状态并保持旧实现兼容 | 01 |
| 03 | [#109](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/109) | 实现共享采集运行时与采集库写入边界 | 01, 02 |
| 04 | [#110](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/110) | 实现项目 fixture 回放与连续两次幂等验收框架 | 03 |
| 05 | [#111](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/111) | 实现 ihchina 独立 Scrapy 项目与小样本验证 | 04 |
| 06 | [#112](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/112) | 实现 nzrc 独立 Scrapy 项目与小样本验证 | 04 |
| 07 | [#113](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/113) | 实现 nongmuhr 独立 Scrapy 项目与小样本验证 | 04 |
| 08 | [#114](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/114) | 实现 dialect-org 独立 Scrapy 项目与小样本验证 | 04 |
| 09 | [#115](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/115) | 实现 cass-linguistics 独立 Scrapy 项目与小样本验证 | 04 |
| 10 | [#116](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/116) | 实现 feiyiw 独立 Scrapy 项目与小样本验证 | 04 |
| 11 | [#117](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/117) | 实现 aqsc-moa Scrapy 项目骨架与 fixture 契约验证 | 04 |
| 12 | [#118](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/118) | 实现 cnipa Scrapy 项目骨架与 fixture 契约验证 | 04 |
| 13 | [#119](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/119) | 完成 8 个 Scrapy 项目集成验收与边界核对 | 05 至 12 |
| 14 | [#120](https://github.com/cyh-cloud/yue-xiang-zhi-jian/issues/120) | 同步 Scrapy 迁移运行文档与验收记录 | 13 |

## 并行规则

- 01 冻结公共契约，02 和 03 按依赖顺序完成。
- 04 完成后，05 至 12 可以并行，各自只修改自己的项目目录和来源 fixture/测试。
- 05、06、07、08、09、10 完成 5 条列表和 5 条详情的小样本联网验证，成功或阻断都保留证据。
- 11、12 只做骨架、fixture 和接口契约验证，不执行真实文件采集。
- 13 汇总全部站点和边界验收，14 最后同步运行文档与验收记录。

## 边界

- 一个采集网站一个独立 Scrapy 项目，不使用参数化 Spider 承载多站。
- Pipeline 只写 raw、stage 和采集库 std 候选标准实体，不写业务库。
- 转换器和业务审核位于 Scrapy 运行之外。
- 不创建 `5ajob`、`zhongguoyuyan`、`cnopendata`、`open-meteo`、`qweather` 项目。
- 天气是后端运行时 API 客户端，不进入 Scrapy、采集库或转换器。
- 不修改后端、前端或业务库 schema。
