# 运维问题登记

状态: active

日期: 2026-10-19

本文是所有已知问题的单一登记处，合并自 `BLOCKERS.md` 和各来源 `reviews/*.md`。状态取值: `open`、`in-progress`、`resolved`、`deferred`。`阻塞首批` 只回答是否阻止首批业务发布，不回答是否值得后续修复。

## 统计

- P0: 7
- P1: 17
- P2: 9
- 合计: 33
- 阻塞首批: 9

## P0

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | `zhongguoyuyan` | 全站 robots 禁止自动抓取，首页、正文、字段和样本均不可验证。 | `docs/reviews/zhongguoyuyan.md:25` | 保持 `robots-restricted`，只允许自动读取 robots；获得书面许可后再变更。 | open | 否 |
| P0-02 | `cnipa` | PDF 下载地址约 5 小时过期，完整签名 URL 不能作为长期详情或样本字段。 | `docs/reviews/cnipa.md:36` | 长期 URL 固定为检索详情页或公告页；PDF 只保存本地哈希和重新获取方式。 | open | 是 |
| P0-03 | `ihchina` | 相关项目和编辑选择器已修正并复测。 | `docs/sources/ihchina.md`；`docs/reviews/ihchina.md` | 保持在 12178、23632 两个详情样本上的复测。 | resolved | 否 |
| P0-04 | `aqsc-moa` | 动态查询行没有单条详情 URL，不满足业务发布硬约束。 | `docs/reviews/aqsc-moa.md:29` | 只关联公告详情和附件行；无长期公告入口的行不进入业务发布。 | open | 是 |
| P0-05 | 全局 schema 与映射 | 表名已统一为冻结的 `std_*` 与 `stage_*`，机械检查已加入验收。 | `docs/operations/validation.md` | 持续运行机械检查。 | resolved | 否 |
| P0-06 | `weather` | 天气已定义为运行时 DTO，不建 std 表、不建历史表。 | `docs/sources/weather.md`；`docs/mapping/weather.md` | 保持运行时 DTO + raw 证据；不建 std 表，不建历史表。 | resolved | 否 |
| P0-07 | `cass-linguistics`、`feiyiw` | 研究资源和资讯实体已在 std-entities 标为建议新增、尚未冻结；冻结前不进入转换器输入。 | `docs/schema/std-entities.md` | 保持建议新增状态，冻结时再补迁移和回滚。 | resolved | 否 |

## P1

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | `ihchina` | 361 页全量分页已完成，但 3610 个详情页未全量打开，关联区块覆盖未统计。 | `docs/operations/validation.md` 的 ihchina 实测记录 | 实现前跑详情可访问性全量或分层抽样，并记录缺失详情。 | open | 否 |
| P1-02 | 多来源 | 多个来源缺少 raw 快照、响应大小、SHA-256 和取得时间。 | `docs/reviews/ihchina.md:46`；`docs/reviews/5ajob.md:38`；`docs/reviews/feiyiw.md:46` | 统一补下载记录，或明确只读不落盘的重跑方式。 | open | 否 |
| P1-03 | `aqsc-moa` | 水产关键词有地名、茶名、蔬菜名和药材误报，人工复核集未建立。 | `docs/reviews/aqsc-moa.md:60` | 冻结三态 `aquatic` 规则并建立反例集。 | open | 否 |
| P1-04 | `aqsc-moa` | 历史 PDF、OCR、注销公告和全量历史批次未验证。 | `docs/reviews/aqsc-moa.md:60` | 首批只承诺已验证 XLSX 与内嵌表，历史回填另开任务。 | open | 否 |
| P1-05 | `cnipa` | `col1400` 是前端 jpage 分页，直接请求页码会重复第 1 页。 | `docs/reviews/cnipa.md:31`；`docs/reviews/cnipa.md:40` | 记录 `dataproxy.jsp` 或 Playwright 翻页契约，按公告 ID 去重。 | open | 否 |
| P1-06 | `cnipa` | 产品级全量目录未证明，537 条公告只验证了 3 份 PDF 样本。 | `docs/reviews/cnipa.md:38` | 完成 PDF 表格解析和产品行统计后再承诺覆盖。 | open | 否 |
| P1-07 | `nzrc` | 联系方式需登录，公开 Ajax 只返回企业地址和网址。 | `docs/reviews/nzrc.md:32` | 冻结“不采集登录后联系方式”，敏感字段保持空值。 | open | 否 |
| P1-08 | `nzrc` | 搜索 GET 入口 404，样本实际来自首页推荐。 | `docs/reviews/nzrc.md:31`；`docs/reviews/nzrc.md:34` | 以职位查询页 PostBack 为列表契约，修正样本位置。 | open | 否 |
| P1-09 | `nongmuhr` | 分页从 0 开始，两个样本已过期，职位描述选择器混入公司介绍。 | `docs/reviews/nongmuhr.md:32`；`docs/reviews/nongmuhr.md:34` | 改为 `page=0`，补发布时间和过期状态，限定职位描述节点。 | open | 否 |
| P1-10 | `5ajob` | `p251` 回绕，19/20 条与第 1 页重复，跨页也有重复。 | `docs/reviews/5ajob.md:31`；`docs/reviews/5ajob.md:32` | 按岗位 ID 或 canonical URL 全局去重，遇到无新增 ID 即停止。 | open | 否 |
| P1-11 | `5ajob` | 非农业岗位过滤规则过弱，版权声明被文档低估。 | `docs/reviews/5ajob.md:33`；`docs/reviews/5ajob.md:37` | 给出标题、行业、专业和正文证据规则；版权改为未经许可不得转载。 | open | 否 |
| P1-12 | `dialect-org` | `/dialect/1` 音频为占位地址，浏览器不可播放。 | `docs/reviews/dialect-org.md:31`；`docs/reviews/dialect-org.md:32` | 记录 `audio_status=invalid` 或 `missing`，不伪造哈希。 | open | 否 |
| P1-13 | `dialect-org` | 15 条详情未逐条展开，地区粒度不统一，缺音频和快照证据。 | `docs/reviews/dialect-org.md:33`；`docs/reviews/dialect-org.md:38` | 补逐条检查表，地区无法归一时进入人工复核。 | open | 否 |
| P1-14 | `cass-linguistics` | `dialectgrammar.com` 已在 `sources.json` 登记为 `login-required` 排除子资源。 | `docs/sources.json` | 保持只登记、不采集。 | resolved | 否 |
| P1-15 | `cnopendata` | 完整数据、API 和下载受付费、登录或合同限制，无行级样本和详情 URL。 | `docs/reviews/cnopendata.md:32`；`docs/reviews/cnopendata.md:33`；`docs/reviews/cnopendata.md:38` | 只保留公开元数据；获得合同后再评估缓存、派生和展示权。 | open | 否 |
| P1-16 | `feiyiw` | 二次整理来源免责声明不保证权属，全文转载授权不明。 | `docs/reviews/feiyiw.md:35` | 只作资讯和技艺补充，不发布全文，权威字段回到官方来源核验。 | open | 否 |
| P1-17 | `weather` | API 复用授权和配额未确认，Referer 必需，隐藏 input 需读取 `value`。 | `docs/reviews/weather.md:38`；`docs/reviews/weather.md:40`；`docs/reviews/weather.md:50` | 上线前取得授权；文档改为读取 `value` 并写明 Referer 前置条件。 | open | 否 |

## P2

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P2-01 | 多来源 | 数据量多为估算或单批样本，不能作为全量规模承诺。 | `docs/reviews/ihchina.md:38`；`docs/reviews/aqsc-moa.md:45`；`docs/reviews/cnipa.md:38` | 实现后分别记录拉取数、去重数和失败数。 | open | 否 |
| P2-02 | 全局 | 各来源更新频率不统一，部分站点无法从响应头判断变化。 | `docs/reviews/weather.md:45` | 冻结按来源的调度周期和内容哈希策略。 | open | 否 |
| P2-03 | `nzrc`、`5ajob`、`feiyiw` | 版权措辞仍有误引或力度不足。 | `docs/reviews/nzrc.md:33`；`docs/reviews/5ajob.md:37`；`docs/reviews/feiyiw.md:35` | 统一为“页面声明保留权利，未发现开放许可”。 | open | 否 |
| P2-04 | `5ajob`、`cnipa`、`ihchina` | 详情 URL 形态不统一，存在两套 URL、查询串和临时 PDF。 | `docs/reviews/5ajob.md:31`；`docs/reviews/cnipa.md:34`；`docs/reviews/ihchina.md:36` | 冻结 canonical URL 生成规则；临时签名地址不进入长期字段。 | open | 否 |
| P2-05 | `5ajob`、`nzrc`、`feiyiw` | 去重键和分页终止条件描述不一致。 | `docs/reviews/5ajob.md:32`；`docs/reviews/nzrc.md:36`；`docs/reviews/feiyiw.md:47` | 按来源 ID 加岗位 ID、`article_id` 或 canonical URL 统一去重。 | open | 否 |
| P2-06 | 全局文档 | 表名、字段名和逻辑域名称仍有风格差异。 | `docs/reviews/ihchina.md:34`；`docs/reviews/5ajob.md:24`；`docs/reviews/feiyiw.md:24` | 在 P0-05 统一后做机械替换检查。 | open | 否 |
| P2-07 | 多来源 | robots 返回 404 或错误页时未统一保存证据链。 | `docs/reviews/dialect-org.md:37`；`docs/reviews/feiyiw.md:37` | 记录状态码、大小、SHA-256、取得时间和“404 不等于授权”。 | open | 否 |
| P2-08 | `cnopendata` | API 商店数量口径混用，未记录 `llms.txt` 和 sitemap。 | `docs/reviews/cnopendata.md:31`；`docs/reviews/cnopendata.md:37` | 分列产品数、分类键数和可见主题数，补授权边界证据。 | open | 否 |
| P2-09 | `weather` | headers 哈希会随 Date、缓存和 Cookie 变化，不能作为内容版本依据。 | `docs/reviews/weather.md:45` | 只把正文哈希用于变更检测，headers 哈希标注为单次证据。 | open | 否 |

## 首批放行规则

- 所有 `阻塞首批=是` 的 P0 项关闭前，不进入首批业务发布。
- 未阻塞首批的来源可以继续采集和 dry-run，但不能绕过本来源的详情 URL、权限和版权边界。
- 问题状态变化只改本文件，不在 `BLOCKERS.md` 维护副本。
