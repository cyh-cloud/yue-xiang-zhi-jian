# 运维问题登记

状态: active

日期: 2026-10-20

本文是所有已知问题的单一登记处。状态取值: `resolved`、`deferred`、`excluded`。`deferred` 必须写解除条件，`excluded` 必须写排除原因。`阻塞首批` 只回答是否阻止首批业务发布。

## 统计

- P0: 6
- P1: 15
- P2: 9
- 合计: 30
- 阻塞首批: 0

## P0

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P0-01 | `zhongguoyuyan` | 来源版权说明不允许使用数据，已决定不采集。 | `docs/reviews/zhongguoyuyan.md` | 保持 `excluded`，保留 robots、版权排除原因和重新评估条件。 | excluded | 否 |
| P0-02 | `cnipa` | PDF 临时签名 URL 不能作为长期详情或样本字段。 | `crawler/tests/test_raw_evidence.py`；`docs/sources/cnipa.md` | 稳定公告 URL 进入长期字段，PDF 签名地址只保留在 raw 证据中；发布门禁拒绝无 direct 详情的产品行。 | resolved | 否 |
| P0-03 | 全局 | 整合 worktree 仍可能访问清理前历史；公开发布制品是单分支 clean artifact，基线为空。 | `docs/operations/history-hygiene.md`；`docs/operations/history-hygiene-baseline.json`；`crawler/tests/test_history_hygiene.py` | 解除条件: 在独立 public branch 从干净工作树生成发布制品，运行 `check_history_hygiene.py` 并确认 0 命中；本分支不改写历史。 | deferred | 否 |
| P0-04 | `aqsc-moa` | XLSX 行没有单条详情 URL，旧规则会把它误判成不可发布。 | `crawler/tests/test_raw_evidence.py`；`docs/sources/aqsc-moa.md` | 公告页作为承载页 URL，附件行和工作表行号作为 locator；承载页和 locator 完整时进入候选和发布审核，缺失时写 deferred。 | resolved | 否 |
| P0-05 | 全局 | 旧 XLSX、PDF、HTML fixture 含联系人列、隐藏 `__VIEWSTATE` 和原始作者元数据。 | `crawler/tests/test_public_repository_hygiene.py`；`crawler/tools/public_hygiene.py`；`docs/operations/evidence-ledger.md` | 已替换为确定性合成 fixture，扫描器检查联系人列、隐藏表单、作者元数据、嵌入附件和个人数据。 | resolved | 否 |
| P0-06 | 全局 | `crawler-db.md`、`std-entities.md`、`converter.md` 与 `database.py` 的列、自然键和 URL/locator 约束不一致。 | `crawler/tests/test_schema_contract.py`；`crawler/pipeline/database.py`；`docs/schema/crawler-db.md` | 文档嵌入实际 DDL，主 std 和关系表统一 direct/missing locator CHECK，农产品物理自然键统一为来源记录键。 | resolved | 否 |

## P1

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | `ihchina` | 列表发现和总数一致性已验证，离线项目详情与传承人遍历已实现，3610 个详情未完成真实全量写入与可达性核验。 | `crawler/tests/test_ihchina.py`；`docs/reviews/ihchina.md` | 解除条件: 完成真实分层抽样和全量详情运行证据。 | deferred | 否 |
| P1-03 | `aqsc-moa` | 水产关键词有地名、茶名、蔬菜名和药材误报。 | `crawler/tests/test_aqsc_moa.py` | 已冻结 `1/0/NULL` 三态，关键词命中保持 NULL，误报反例测试通过。 | resolved | 否 |
| P1-04 | `aqsc-moa` | 历史 PDF、OCR、注销公告和全量历史批次未验证。 | `docs/sources/aqsc-moa.md` | 解除条件: 完成历史公告抽样、OCR 质量评估和注销事件回放。 | deferred | 否 |
| P1-05 | `cnipa` | `col1400` 是前端 jpage 分页，直接请求页码会重复第 1 页。 | `docs/sources/cnipa.md` | 解除条件: 用真实接口完成跨页唯一 ID 校验和分页回放。 | deferred | 否 |
| P1-06 | `cnipa` | 产品级全量目录未证明，537 条公告只验证了 3 份 PDF 样本。 | `crawler/tests/test_raw_evidence.py`；`docs/sources/cnipa.md` | 解除条件: 完成全量 PDF 表格重建、OCR 抽样和产品级对账。 | deferred | 否 |
| P1-07 | `nzrc` | 联系方式需登录，公开 Ajax 只返回企业地址和网址。 | `crawler/tests/test_nzrc.py` | 登录后个人联系方式保持 null；fixture 不写入敏感联系方式。 | resolved | 否 |
| P1-08 | `nzrc` | 搜索 GET 入口 404，样本实际来自首页推荐。 | `docs/sources/nzrc.md` | 解除条件: 实现并验证 PostBack 分页契约。 | deferred | 否 |
| P1-09 | `nongmuhr` | 分页从 0 开始，两个样本已过期，职位描述选择器混入公司介绍。 | `crawler/tests/test_nongmuhr.py` | 解除条件: 完成零基分页和过期状态的全量回放。 | deferred | 否 |
| P1-10 | `5ajob` | `p251` 回绕，跨页存在重复。 | `crawler/tests/test_5ajob.py` | fixture 已按 job_id 和 canonical URL 去重，无新增 ID 即停止。 | resolved | 否 |
| P1-11 | `5ajob` | 非农业岗位过滤规则过弱，页面明确禁止未经许可转载。 | `crawler/tests/test_5ajob.py`；`docs/reviews/5ajob.md` | 农业主题过滤保留证据；权利状态统一为 `prohibited`，统一运行入口拒绝执行，解析器只作离线测试。 | resolved | 否 |
| P1-12 | `dialect-org` | `/dialect/1` 音频为占位地址，浏览器不可播放。 | `crawler/tests/test_dialect_org.py` | 已区分 invalid/missing，不可播放时置空 audio_url。 | resolved | 否 |
| P1-13 | `dialect-org` | 15 条详情未逐条展开，地区粒度不统一，缺音频和快照证据。 | `crawler/tests/test_dialect_org.py`；`docs/reviews/dialect-org.md` | 解除条件: 完成 15 条真实详情、音频状态和快照证据。 | deferred | 否 |
| P1-15 | `cnopendata` | 完整数据、API 和下载受付费、登录或合同限制，无行级样本和详情 URL。 | `docs/reviews/cnopendata.md` | 解除条件: 订阅文化数据集并取得可复核的授权与 API 契约。 | deferred | 否 |
| P1-16 | `feiyiw` | 二次整理来源免责声明不保证权属，全文转载授权不明。 | `crawler/tests/test_feiyiw.py`；`docs/sources/feiyiw.md` | 已按 `attribution-required` 记录署名要求，保留 `extra.rights_risk`，会员和商城 URL 明确拒绝。 | resolved | 否 |
| P1-17 | `weather` | API 复用授权和配额未确认；Referer、隐藏 input `value` 和 15 分钟运行时缓存已实现。 | `crawler/tests/test_weather_sources.py`；`docs/sources/weather.md` | 解除条件: 完成中国天气网接口授权、配额和真实运行时接入核验。 | deferred | 否 |

## P2

| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P2-01 | 多来源 | 数据量多为估算或单批样本，不能作为全量规模承诺。 | `docs/reviews/ihchina.md`；`docs/reviews/aqsc-moa.md` | 解除条件: 为每个来源记录真实拉取数、去重数和失败数。 | deferred | 否 |
| P2-02 | 全局 | 各来源更新频率不统一，部分站点无法从响应头判断变化。 | `docs/reviews/weather.md` | 解除条件: 冻结按来源的调度周期和正文内容哈希策略并完成真实运行验证。 | deferred | 否 |
| P2-03 | `nzrc`、`5ajob`、`feiyiw` | 版权措辞仍有误引或力度不足。 | `crawler/docs/sources.json`；`crawler/docs/reviews/5ajob.md` | 已统一权利事实；5ajob 为 `prohibited`，其余保留署名和风险说明。 | resolved | 否 |
| P2-04 | `5ajob`、`cnipa`、`ihchina` | 详情 URL 形态不统一，存在两套 URL、查询串和临时 PDF。 | `crawler/tests/test_raw_evidence.py` | 已冻结来源级 canonical URL；5ajob 空 company hash 已规范化，签名 PDF 不入长期字段。 | resolved | 否 |
| P2-05 | `5ajob`、`nzrc`、`feiyiw` | 去重键和分页终止条件描述不一致。 | `crawler/tests/test_5ajob.py`；`crawler/tests/test_feiyiw.py` | 5ajob 与 feiyiw 已按来源 ID 加 canonical URL/article_id 去重。 | resolved | 否 |
| P2-07 | 多来源 | robots 返回 404 或错误页时未统一保存证据链。 | `crawler/tests/test_raw_evidence.py`；`docs/reviews/dialect-org.md` | 解除条件: 为每个来源记录 robots 状态码、大小、SHA-256、取得时间和访问结论。 | deferred | 否 |
| P2-08 | `cnopendata` | API 商店数量口径混用，未记录 `llms.txt` 和 sitemap。 | `docs/reviews/cnopendata.md` | 解除条件: 按产品数、分类键数和可见主题数持续记录公开元数据。 | deferred | 否 |
| P2-09 | `weather` | headers 哈希会随 Date、缓存和 Cookie 变化，不能作为内容版本依据。 | `crawler/tests/test_weather_sources.py` | 已只使用正文 content_hash 作为版本，headers 哈希仅保存单次证据。 | resolved | 否 |
| P2-10 | 全局 | `stage_source_items` 仍是通用表，来源特有字段保存在 `extra`。 | `docs/schema/crawler-db.md`；`crawler/tests/test_schema_contract.py` | 解除条件: 首个来源需要可查询的来源特有列时，冻结 source-shaped stage schema 并完成迁移。 | deferred | 否 |

## 首批放行规则

- 当前没有 `阻塞首批=是` 的未关闭项。
- 未阻塞首批的来源可以继续采集和 dry-run。发布必须满足 direct 详情 URL，或 long_term_url 加 locator 的回溯条件；不得绕过权限和版权边界。
- 问题状态变化只改本文件，不在 `BLOCKERS.md` 维护副本。
