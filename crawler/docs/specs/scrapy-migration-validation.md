# Scrapy 迁移集成验收

日期: 2026-10-21

结果: accepted-with-blocker

## 项目清单

- `ihchina`
- `nzrc`
- `nongmuhr`
- `dialect-org`
- `cass-linguistics`
- `feiyiw`
- `aqsc-moa`
- `cnipa`

## 验证结果

| 项目 | fixture/骨架 | 联网小样本 | 结论 |
| --- | --- | --- | --- |
| ihchina | 通过 | 5 列表 + 5 详情 | succeeded |
| nzrc | 通过 | 21 列表 + 5 详情 | succeeded |
| nongmuhr | 通过 | 5 列表 + 5 详情 HTTP 200，但字段结构变化 | blocked |
| dialect-org | 通过 | 15 列表 + 5 详情 | succeeded |
| cass-linguistics | 通过 | 9 列表 + 5 详情 | succeeded |
| feiyiw | 通过 | 25 列表 + 5 详情 | succeeded |
| aqsc-moa | 通过 | 不执行 | skeleton-only |
| cnipa | 通过 | 不执行 | skeleton-only |

## 边界核对

- Scrapy 仅写采集库，共享包没有导入业务库或转换器。
- 天气不在 Scrapy 项目中；`open-meteo` 和 `qweather` 没有 Spider。
- `5ajob`、`zhongguoyuyan`、`cnopendata` 没有新项目。
- `aqsc-moa` 和 `cnipa` 没有 live 请求或真实文件采集。
- 全量 crawler 测试通过，共 154 项。

## 未关闭问题

`nongmuhr` 详情页当前 HTML 不再匹配已登记字段结构。已记录 URL、时间、状态码、字节数和结构结论；解除条件是重新定位详情字段并重跑 5 条详情。
