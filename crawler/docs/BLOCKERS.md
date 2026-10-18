# 阻塞收尾决策清单

日期: 2026-10-19

用途: 汇总需在明天早上人工决策或后续修复的事项。只保留结论和动作，原文见证据路径。

计数: P0 7 项，P1 19 项，P2 10 项，共 36 项。

## P0 阻塞

| 编号 | 来源或文档 | 问题 | 证据路径 | 建议动作 | 阻塞第一批实现 |
| --- | --- | --- | --- | --- | --- |
| P0-01 | `zhongguoyuyan` | robots 全站禁止抓取，列表、详情、字段和样本均不可验证。 | `sources/zhongguoyuyan.md:120`、`reviews/zhongguoyuyan.md:25` | 维持 `robots-restricted`，首批不实现；仅允许自动读取 robots，站内内容须书面许可。 | 否 |
| P0-02 | `cnipa` | PDF 下载地址约 5 小时过期，`samples.json` 还保存完整签名 URL。 | `sources/cnipa.md:263`、`reviews/cnipa.md:36` | 冻结“检索详情页或公告页为长期 URL，PDF 只在 raw 层短期保存”的规则；从样本中移除签名参数。 | 是 |
| P0-03 | `ihchina` | 相关项目选择器实测为空，资讯/学术编辑选择器层级错误。 | `reviews/ihchina.md:31`、`reviews/ihchina.md:32` | 按实际 `.x-tables` 容器和 `.article-nav` 修正，并在 2 个详情样本重新断言。 | 是 |
| P0-04 | `aqsc-moa` | 动态查询行没有单条详情 URL，无法满足“入库记录必须可直达详情”的硬约束。 | `sources/aqsc-moa.md:422`、`reviews/aqsc-moa.md:29` | 决定以公告页加附件行号作为来源 URL，或只把动态查询用于对账、不单独入库。 | 是 |
| P0-05 | 全局 schema 与多份来源映射 | 文档混用 `std.xxx`、`crawler.std.xxx`、`ich_projects` 和冻结的 `std_xxx`，转换器无法按统一契约实现。 | `schema/crawler-db.md:612`、`reviews/dialect-org.md:35`、`reviews/cnopendata.md:34` | 冻结唯一命名；所有来源与映射改为 `std_*`、`stage_*`，或明确点分名只是逻辑域。 | 是 |
| P0-06 | `weather` | `std_weather_candidate` 不在冻结 schema 中，raw、stage、std 落点未定。 | `reviews/weather.md:39`、`mapping/weather.md:3` | 明确它是运行时 DTO，不建 std 表；如需持久化，先补冻结 schema、TTL 和清理策略。 | 是 |
| P0-07 | `cass-linguistics`、`feiyiw` | 研究文章/资源和 `std_ich_articles` 被引用但未定义，部分来源也没有对应 stage 表。 | `reviews/cass-linguistics.md:34`、`reviews/feiyiw.md:36`、`schema/crawler-db.md:1126` | 决定新增冻结表及字段、自然键、关系、回滚，或明确本期不建表并停止映射。 | 是 |

## P1 缺口

| 编号 | 来源或文档 | 问题 | 证据路径 | 建议动作 | 阻塞第一批实现 |
| --- | --- | --- | --- | --- | --- |
| P1-01 | `ihchina` | 未逐页验证 361 页累计去重严格等于 3610，也未全量打开 3610 个详情。 | `reviews/ihchina.md:38`、`reviews/ihchina.md:51` | 实现前跑一次全量分页计数、ID 去重和详情可访问性抽样，再决定是否宣称全量可复现。 | 否 |
| P1-02 | `ihchina`、`5ajob`、`dialect-org`、`cass-linguistics`、`feiyiw` | 多个来源缺少 raw 快照、响应大小、SHA-256 和取得时间记录。 | `reviews/ihchina.md:25`、`reviews/5ajob.md:25`、`reviews/dialect-org.md:27`、`reviews/feiyiw.md:27` | 统一补下载记录；无附件时记录“只读不落盘”的例外和重跑方式。 | 否 |
| P1-03 | `aqsc-moa` | 水产关键词存在地名、茶名、蔬菜名和药材误报，人工复核集未建立。 | `sources/aqsc-moa.md:423`、`reviews/aqsc-moa.md:60` | 冻结三态 `aquatic` 规则，建立已知反例测试集，低置信记录只进人工队列。 | 否 |
| P1-04 | `aqsc-moa` | 历史 PDF、OCR、注销公告和全量历史批次未验证。 | `sources/aqsc-moa.md:428`、`reviews/aqsc-moa.md:60` | 首批只承诺已验证的 XLSX 与 HTML 内嵌表；历史 PDF 另开回填任务。 | 否 |
| P1-05 | `cnipa` | `col1400` 是前端 jpage 分页，直接请求 `pageNum` 会重复第 1 页。 | `reviews/cnipa.md:31`、`reviews/cnipa.md:44` | 记录 `dataproxy.jsp` 或 Playwright 翻页契约，并以公告 ID 去重和终止。 | 否 |
| P1-06 | `cnipa` | 产品级全量目录未证明，537 条公告的 PDF 表格只验证了 3 份样本。 | `sources/cnipa.md:268`、`reviews/cnipa.md:38` | 先完成 PDF 表格解析与产品行统计，再承诺水产和地理标志全量覆盖。 | 否 |
| P1-07 | `nzrc` | 联系方式需登录，公开 Ajax 仅返回企业地址和网址；敏感字段为空。 | `sources/nzrc.md:260`、`reviews/nzrc.md:32` | 冻结“不采集登录后联系方式”，公开地址和网址按字段授权决定是否展示。 | 否 |
| P1-08 | `nzrc` | 搜索 GET 入口返回 404，样本实际来自首页推荐而非职位列表。 | `reviews/nzrc.md:31`、`reviews/nzrc.md:34` | 以 `career_seek.html` 加 PostBack 为列表契约，或改用可复现的搜索请求；修正样本位置。 | 否 |
| P1-09 | `nongmuhr` | 分页实际从 0 开始，两个样本均已过期，职位描述选择器会混入公司介绍。 | `reviews/nongmuhr.md:32`、`reviews/nongmuhr.md:34`、`reviews/nongmuhr.md:36` | 改为 `page=0` 起始；补发布时间和过期状态；限定职位描述节点。 | 否 |
| P1-10 | `5ajob` | `p251` 回绕，19/20 条与第 1 页重复，且跨页也有重复。 | `reviews/5ajob.md:31`、`reviews/5ajob.md:32` | 以岗位 ID 或 canonical URL 全局去重；遇到已见 ID、无新增 ID 或尾页标记即停止。 | 否 |
| P1-11 | `5ajob` | 非农业岗位过滤规则过弱，版权声明被文档低估。 | `reviews/5ajob.md:33`、`reviews/5ajob.md:37` | 给出标题、行业、专业和正文的证据规则；版权改为“未经许可不得转载”。 | 否 |
| P1-12 | `dialect-org` | `/dialect/1` 音频为占位地址，浏览器不可播放，不能计为可下载资源。 | `reviews/dialect-org.md:31`、`reviews/dialect-org.md:32` | 记录 `audio_status=invalid` 或 `missing`，只保存 URL 元数据，不伪造哈希。 | 否 |
| P1-13 | `dialect-org` | 15 条详情未逐条展开，地区粒度不统一，缺少音频和快照证据。 | `reviews/dialect-org.md:33`、`reviews/dialect-org.md:38` | 补 15 条检查表；地区无法归一时进入人工复核，不按字符串强行合并。 | 否 |
| P1-14 | `cass-linguistics` | `dialectgrammar.com` 需登录，但 `sources.json` 只登记公开的 `ling.cass.cn`。 | `reviews/cass-linguistics.md:32`、`reviews/cass-linguistics.md:44` | 新增独立来源 ID 和 `login-required` 等级，或明确不采集且写清子资源边界。 | 否 |
| P1-15 | `cnopendata` | 完整数据、API 和下载受付费、登录或合同限制，页面无行级样本和详情 URL。 | `sources/cnopendata.md:162`、`sources/cnopendata.md:166`、`reviews/cnopendata.md:43` | 只保留公开元数据人工研究；获得合同并确认缓存、派生、公开展示权后再评估接入。 | 否 |
| P1-16 | `feiyiw` | 站点为二次整理来源，免责声明不保证权属，全文转载授权不明。 | `sources/feiyiw.md:211`、`sources/feiyiw.md:214`、`reviews/feiyiw.md:35` | 仅作资讯和技艺补充证据；不发布全文，级别、批次和编号回到官方来源核验。 | 否 |
| P1-17 | `weather` | API 复用授权、配额和长期稳定性未确认；隐藏 input 需读 `value`，实时接口必须带 Referer。 | `sources/weather.md:185`、`reviews/weather.md:38`、`reviews/weather.md:40` | 上线前取得授权或书面确认；文档改为读取 `value`、Referer 必需，并冻结 `observed_at` 规则。 | 否 |
| P1-18 | `crafts` 与 `std_ich_projects` | 多来源合并规则仍待定，`ihchina`、`feiyiw`、`cnopendata` 的主值和证据关系未冻结。 | `schema/yuexiang-target-db.md:421`、`mapping/ich-crafts.md:79` | 明确官方主值、补充来源、冲突记录和人工保护规则，并用导入样本验证。 | 是（转换器前） |
| P1-19 | 目标库与映射 | 招聘联系方式是否展示、方言词条如何发布到现有 `dialect_phrases`、`normalized_name` 规则均未冻结。 | `schema/yuexiang-target-db.md:422`、`schema/yuexiang-target-db.md:423`、`schema/yuexiang-target-db.md:424` | 按内容域分别决策，默认不展示个人联系方式；方言展示映射单独立项。 | 否 |

## P2 改进

| 编号 | 来源或文档 | 问题 | 证据路径 | 建议动作 | 阻塞第一批实现 |
| --- | --- | --- | --- | --- | --- |
| P2-01 | `ihchina`、`aqsc-moa`、`cnipa`、`feiyiw` | 数据量多为估算或单批样本，不能作为全量规模承诺。 | `sources/ihchina.md:365`、`sources/aqsc-moa.md:403`、`sources/cnipa.md:247`、`sources/feiyiw.md:198` | 实现后按来源记录真实拉取数、去重数和失败数，并与估算分开标注。 | 否 |
| P2-02 | 全局 | 各来源更新频率不统一，部分站点无法从响应头判断变化。 | `operations/rollout.md:168`、`mapping/weather.md:85` | 冻结按来源的调度周期、内容哈希策略和人工复核节奏。 | 否 |
| P2-03 | `nzrc`、`5ajob`、`feiyiw` | 版权措辞仍有误引或力度不足。 | `reviews/nzrc.md:33`、`reviews/5ajob.md:37`、`reviews/feiyiw.md:35` | 统一为“页面声明保留权利，未发现开放许可”，禁止把 404 或公开可访问解释为授权。 | 否 |
| P2-04 | `5ajob`、`cnipa`、`ihchina` | URL 形态不统一，存在两套详情 URL、查询串与 `links` 路径、临时 PDF 路径。 | `reviews/5ajob.md:31`、`reviews/cnipa.md:34`、`reviews/ihchina.md:36` | 冻结 canonical URL 生成规则；临时签名地址不进入长期字段。 | 否 |
| P2-05 | `5ajob`、`nzrc`、`feiyiw` | 去重键和分页终止条件描述不一致。 | `reviews/5ajob.md:32`、`reviews/nzrc.md:36`、`reviews/feiyiw.md:47` | 按来源 ID 加岗位 ID、`article_id` 或 canonical URL 统一去重，并写明停止条件。 | 否 |
| P2-06 | 全局文档 | 表名、字段名和逻辑域名称仍有风格差异。 | `reviews/ihchina.md:34`、`reviews/5ajob.md:24`、`reviews/feiyiw.md:24` | 在 P0-05 统一后做一次机械替换检查，避免人工再解释别名。 | 否 |
| P2-07 | `ihchina`、`dialect-org`、`feiyiw` | robots 返回 404 时未统一保存证据链。 | `reviews/dialect-org.md:37`、`sources/feiyiw.md:210`、`sources/ihchina.md:403` | 记录状态码、响应体大小、SHA-256、取得时间和“404 不等于授权”的结论。 | 否 |
| P2-08 | `weather` | headers 哈希会随 Date、缓存和 Cookie 变化，不能作为内容版本依据。 | `reviews/weather.md:45` | 只把正文哈希用于变更检测，headers 哈希标注为单次样本证据。 | 否 |
| P2-09 | schema 与运维 | 迁移编号、raw 响应存放方式和清理策略未定。 | `schema/yuexiang-target-db.md:425`、`schema/crawler-db.md:1125`、`operations/collection-rules.md:133` | 在实现票据中分配编号，并按部署容量决定文件系统或 SQLite BLOB。 | 否 |
| P2-10 | 验收流程 | `sources.json`、链接、哈希和审核字段的自动检查尚未实现。 | `operations/validation.md:130`、`operations/validation.md:131` | 将来源覆盖、JSON 合法性、ID 唯一性、链接和哈希巡检做成脚本或 CI 检查。 | 否 |

## 最需要决策的 5 项

1. 冻结 schema 命名及缺失表，解决 `std.*` 与 `std_*`、研究表和天气实体的冲突。
2. 冻结来源授权边界，明确 `zhongguoyuyan` 不实施，以及 `weather`、`cnopendata`、`feiyiw` 能否进入首批。
3. 决定 `cnipa` 的长期详情 URL 和 PDF 短期签名处理方式。
4. 决定 `aqsc-moa` 动态查询记录的详情 URL 口径，并冻结水产人工复核规则。
5. 修正并验收 `ihchina` 详情选择器，同时冻结 `crafts` 多来源合并与人工保护规则。
