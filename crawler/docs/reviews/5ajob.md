# 5A 农业人才网 审核记录

来源 ID: `5ajob`

审核时间: `2026-10-19 01:29 Asia/Shanghai`

审核结论: `approved-with-gaps`

权利状态: `prohibited`

## 审核范围

- 待审文档: `crawler/docs/sources/5ajob.md`
- 审核者: 来源审核 agent
- 复核方式: 独立 `requests` HTTP 与 Playwright Chromium；重开首页、`/job/`、`p2`、`p250`、`p251`、关键词搜索和详情，核对 robots 及 3 条样本

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | 2026-10-19 复核首页、`/job/` 均返回 200；页面说明与实际入口一致 |
| 列表页与分页 | 通过（有边界缺口） | 列表每页 20 行；尾页为 `index-p250.html`。`index-p251.html` 返回 200，但 20 条中 19 条与第 1 页重复，不能以页码递增判断结束。第 1 页与第 2 页另有 1 条重复，任何全量采集都必须按岗位 ID 或 canonical URL 去重 |
| 详情页 URL | 通过 | 两套 canonical 详情 URL 的 3 条样本均返回 200，可直达同一岗位；`#rjobid` 与 URL 中的职位 ID 一致 |
| JSON 字段或 DOM 选择器 | 通过 | 未发现列表/详情 JSON API；`tr[id^="compareColor"]`、`td.joblink a`、`#zhtitle`、`#jobdetail h1`、`#rjobid`、`#jobdetail tr` 均有非空结果。`#jobexpire` 纯 HTTP 为空，Playwright 执行页面脚本后返回有效期 |
| 样本记录 | 通过 | 样本 1 `50506`、样本 2 `50688` 的岗位、公司、地点、行业、薪资、学历、专业及正文均可复现；样本 3 `50687` 为前台接待反例，详情仍可打开但应被农业主题过滤 |
| 字段映射 | 通过 | 来源文档已统一使用 `std_jobs`、`std_job_sources`、`location_raw` 和 `salary_raw`；未冻结字段进入 `extra` |
| 访问限制 | 通过 | 列表和详情匿名可访问；投递、收藏、联系企业等登录后操作未纳入采集。文档明确排除简历和个人联系方式 |
| 版权与用途 | 通过（限制明确） | 首页实测明确写有“未经5ajob.com许可，不得转载本站之所有农业人才求职招聘信息及作品”；来源与记录统一标记 `prohibited`，只保留 raw/stage 证据，不进入业务发布 |
| 下载记录 | 通过（fixture 范围） | 列表 fixture 已按页保存 raw JSON、大小、SHA-256、取得时间和 locator；真实 250 页全量仍为 deferred |

## 发现的问题

- 历史发现（已处理）：`p251` 回绕已复现；实现现按岗位 ID 和 canonical URL 去重，无新增 ID 即停止。
- 历史发现（已处理）：跨页重复已由全局 ID 和 URL 去重覆盖。
- 非农业岗位过滤已实现为标题、行业、描述的最小关键词规则，并保存命中字段、命中文案和排除记录；`前台接待` 反例已有测试。
- 三份样本只有 1 条反例、2 条正面样本；对薪资、经验、学历的原文格式已覆盖，但没有覆盖“公司 hash 为空”的列表链接和已过期岗位详情。
- 文档将纯 HTTP 的 `#jobexpire` 空值描述为“普通 HTTP 为空”，该事实成立，但实现若只使用 HTTP 会漏掉有效期，必须明确 Playwright 或脚本执行是必需步骤。
- 字段映射已对齐冻结 schema，扩展字段进入 `extra`。
- 文档已把页面声明统一为 `prohibited`；采集仅用于低频率内部核验，不进入业务发布。
- 文档没有下载记录章节，也没有说明为什么没有下载文件、robots 响应是否只读即弃。审核只能确认“没有需要下载的附件”，不能确认“下载与哈希可复现”。
- 只抽查了 `p2`、`p250`、`p251` 和关键词第 1、2 页，没有验证全部 250 页及每个行业/地区路径的 robots 可用性。

## 必须补齐

- 已完成：std 映射统一为 `std_jobs`、`std_job_sources`，业务表指向 `recruitment_postings`、`recruitment_posting_sources`。
- 已完成：按岗位 ID 和 canonical URL 全局去重，遇到无新增 ID 即停止，覆盖 `p251` 回绕。
- 已完成：农业相关性规则保留标题、行业和描述证据，并有正反例 fixture。
- 已完成：公司 hash 为空的 canonical URL fixture。
- 已完成离线详情解析：fixture 可带 `detail_html`，解析公司、地点、薪资、学历、描述、要求和有效期。
- robots 真实响应哈希仍为 `deferred`，解除条件是使用最终调度 UA 完成 robots 快照并保存大小、SHA-256 和取得时间。
- 已明确页面声明“未经许可不得转载”，来源注册表为 `prohibited`；调度器和 Scrapy 项目在发现前拒绝执行，只保留解析器离线测试。

## 2026-10-20 修复复核

- 来源注册表为 `prohibited`，因此离线 harness 在发现前返回 `blocked`，不创建采集库、不产生 raw/stage/std。
- 列表过滤和详情 HTML 解析仍可在离线单元测试中验证，不作为真实运行授权。
- 真实 250 页全量、浏览器脚本有效期和许可恢复均保持 `deferred`；解除条件是取得可复核许可并完成真实全量回放。

## 可后续处理

- 全量 250 页的翻页完整性、停招比例和农业主题误收率，建议在实现阶段以抽样统计验证。
- 不同 User-Agent 下的 robots 精确匹配可在调度器接入时用实际 UA 复测。
- 移动详情页 `m.5ajob.com` 暂不作为主入口，后续如需移动展示再单独验证。
