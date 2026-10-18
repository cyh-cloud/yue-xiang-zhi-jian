# 粤乡智匠数据采集设计索引

本目录是数据采集系统的设计交付，不是运行中的爬虫。目标是为后续爬虫、双 SQLite 数据库和转换器提供可复核的来源契约。

## 交付边界

- 只修改 `crawler` 子项目。
- 不修改粤乡智匠后端、数据库、前端、业务数据或部署配置。
- 不创建 PR 或 issue。
- 单个下载文件不超过 100MB；超限文件只写说明。

## 阅读顺序

1. `SPEC.md`：完整规格和已冻结的产品决策。
2. `GLOSSARY.md`：采集域术语。
3. `adr/`：架构决策。
4. `sources.json`：机器可读来源清单。
5. `sources/`：逐来源采集契约。
6. `reviews/`：逐来源独立审核记录。
7. `schema/`：采集库、业务库变更和转换器设计。
8. `mapping/`：内容域字段映射。
9. `operations/`：采集规则、验收和上线顺序。
10. `BLOCKERS.md`：明早需要人工决策的 P0/P1/P2 清单。
11. `TASKS.md`：本地任务图，代替远程 tracker。

## 来源状态

| ID | 内容域 | 优先级 | 实现文档 | 审核文档 |
| --- | --- | --- | --- | --- |
| `ihchina` | 国家级非遗、手工技艺 | P0 | `sources/ihchina.md` | `reviews/ihchina.md` |
| `aqsc-moa` | 名特优新、特质农品、农业公告 | P0 | `sources/aqsc-moa.md` | `reviews/aqsc-moa.md` |
| `cnipa` | 地理标志产品 | P0 | `sources/cnipa.md` | `reviews/cnipa.md` |
| `weather` | 实时天气 API | P1 | `sources/weather.md` | `reviews/weather.md` |
| `nzrc` | 农业招聘 | P1 | `sources/nzrc.md` | `reviews/nzrc.md` |
| `nongmuhr` | 农牧招聘 | P1 | `sources/nongmuhr.md` | `reviews/nongmuhr.md` |
| `5ajob` | 农业招聘 | P1 | `sources/5ajob.md` | `reviews/5ajob.md` |
| `dialect-org` | 方言词条 | P1 | `sources/dialect-org.md` | `reviews/dialect-org.md` |
| `cass-linguistics` | 语言研究资料 | P2 | `sources/cass-linguistics.md` | `reviews/cass-linguistics.md` |
| `cnopendata` | 方言与非遗聚合数据 | P2 | `sources/cnopendata.md` | `reviews/cnopendata.md` |
| `zhongguoyuyan` | 方言资源 | P2 | `sources/zhongguoyuyan.md` | `reviews/zhongguoyuyan.md` |
| `feiyiw` | 非遗资讯与技艺 | P2 | `sources/feiyiw.md` | `reviews/feiyiw.md` |

## 数据流

```text
页面 / API / 附件
        |
        v
crawler.db
  raw -> stage -> std
        |
        v
转换器
natural key / upsert / conflict / publish / rollback
        |
        v
粤乡智匠业务库
```

## 来源文档最低要求

每份来源文档必须写清：

- 来源 ID、名称、域名、主管机构、内容域和优先级。
- 首页、列表页、详情页的真实 URL 和详情 URL 模式。
- HTML、JSON API、XLSX 或 PDF 的定位方式。
- 请求参数、分页方式、响应字段或 DOM 选择器。
- 至少 1 至 3 条真实样本。
- 样本到 crawler 库和粤乡智匠目标表的字段映射。
- 数量估算、更新频率、变更检测和抓取频率建议。
- `access`、`license_or_usage`、`confidence` 和验证时间。
- 可让用户跳转的详情 URL。

## 审核结论

- `approved`：入口、字段、样本和映射均可复现。
- `approved-with-gaps`：主体可用，但存在明确缺口。
- `blocked`：访问受限、结构不可确认或合规风险未解决。

## 实施批次

1. P0 官方来源：非遗、名特优新、地理标志。
2. P1 招聘、天气和方言。
3. P2 聚合与补充来源。
4. 数据模型、转换器和字段映射。
5. 汇总、独立审核和最终验收。

## 当前交付状态

- 12 个来源均有实现文档和独立审核记录。
- P0 来源 3 个，P1 来源 5 个，P2 来源 4 个。
- 下载文件 45 个，合计约 3.35MB，无单文件超过 100MB。
- 所有来源审核结论为 `approved-with-gaps`，`zhongguoyuyan` 为 `blocked`。
- 未决事项见 `BLOCKERS.md`，共 36 项。
2. P1 招聘、天气和方言。
3. P2 聚合与补充来源。
4. 数据模型、转换器和字段映射。
5. 汇总、独立审核和最终验收。
