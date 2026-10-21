# Scrapy 迁移集成验收

日期: 2026-10-21

结果: cutover complete，live 缺口保留（ihchina 本次重跑 504，aqsc-moa 附件仍 403）

## 项目清单

- `ihchina`
- `nzrc`
- `nongmuhr`
- `dialect-org`
- `cass-linguistics`
- `feiyiw`
- `aqsc-moa`
- `cnipa`

## 实际重跑结果

| 项目 | run_id | 实际计数 | 运行结果 | 验收结论 |
| --- | --- | --- | --- | --- |
| ihchina | `ihchina-703ba5dd90304355b31576e508452d21` | raw 1、stage 0、candidate 0、deferred 0、blocked 0、failed 1、skipped 0 | failed（列表 HTTP 504） | blocked |
| nzrc | `nzrc-f13c8dae7ed74d278ca7807c9cc733ee` | raw 21、stage 20、candidate 0、deferred 20、blocked 0、failed 0、skipped 0 | partial | approved-with-gaps |
| nongmuhr | `nongmuhr-3b01c369718c47d2a690284f939a5791` | raw 11、stage 10、candidate 10、deferred 0、blocked 0、failed 0、skipped 0 | succeeded | approved |
| dialect-org | `dialect-org-e7265be7d9d14059a9c086f13150c883` | raw 16、stage 15、candidate 0、deferred 15、blocked 0、failed 0、skipped 0 | partial | approved-with-gaps |
| cass-linguistics | `cass-linguistics-d97213dd2aca4465b630ef1b4abcecc9` | raw 10、stage 5、candidate 0、deferred 5、blocked 0、failed 4、skipped 0 | partial | approved-with-gaps |
| feiyiw | `feiyiw-9f11f4195c654773ae362fbdda8de7b6` | raw 23、stage 20、candidate 0、deferred 20、blocked 0、failed 0、skipped 0 | partial | approved-with-gaps |
| aqsc-moa | `crawler-132-aqsc-live-20261021` | raw 3、stage 1、candidate 0、deferred 0、blocked 1、failed 1、skipped 0 | partial | blocked |
| cnipa | `crawler-132-cnipa-live-20261021` | raw 2、stage 58、candidate 0、deferred 58、blocked 0、failed 0、skipped 0 | partial | approved-with-gaps |

合计: 8 个来源，8 次实际运行，raw 87、stage 129、candidate 10、deferred 118、blocked 1、failed 6、skipped 0。

## 证据归档

- 归档根: `../crawler-live-evidence/issue-133-20261021/`，相对于仓库根，不在 `%TEMP%`。
- 公开索引: `crawler/docs/operations/live-evidence-index.json`。
- 索引记录来源 ID、来源与列表、详情、承载页、附件 URL、取得时间、HTTP 状态、Content-Type、响应哈希、七类计数、失败摘要、阻断原因和验收记录指针。
- 原始响应正文、个人信息、凭据、Cookie 和签名 URL 留在归档目录，不进入公开仓库。

## 边界核对

- Scrapy 仅写采集库，共享包没有导入业务库或转换器。
- 天气不在 Scrapy 项目中；`open-meteo` 和 `qweather` 没有 Spider。
- `5ajob`、`zhongguoyuyan`、`cnopendata` 没有新项目。
- 5 个 robots 404 来源已按当前代码重跑。`nzrc`、`dialect-org`、`cass-linguistics`、`feiyiw` 写出 deferred 候选；`ihchina` 因列表 HTTP 504 没有产生候选，保留 failed 事实。
- `nongmuhr` 按真实列表和 10 条详情重跑，旧 `#project_L` 选择器已移除，运行得到 10 条 candidate。
- `aqsc-moa` 的公告页可访问，附件和 robots 被 403 阻断，真实运行保持 blocked 证据。
- `cnipa` 的公告页和 PDF 可访问，58 条产品行写为 deferred，签名 URL 不进入长期字段。
- 每个项目都有独立 fixture 回放入口；连续两次回放时 raw 追加，stage 和候选按来源自然键幂等。
- 8 个项目的 fixture 回放均经过各自项目入口，并断言候选数量、状态和连续两次幂等。
- `aqsc-moa` 和 `cnipa` 的 fixture 回放经过真实 Scrapy process，把合成 XLSX 或 PDF 写入 `raw_files`。
- 运行报告分开统计 candidate、deferred、blocked、skipped 和 failed，并保留真实 failure_reason。
- robots 结论覆盖 allowed、disallowed、not-found 和 unknown。not-found 请求保留 raw 证据并按业务状态写 deferred；明确拒绝请求保留 raw 证据并写 blocked。

## 未关闭问题

- `ihchina` 本次列表入口返回 HTTP 504，解除条件是入口恢复稳定响应后重新运行列表和至少 5 条详情。
- `cass-linguistics` 有 4 条详情返回 404，未写成成功样本。
- `aqsc-moa` 的附件仍被 WAF 403 阻断，解除条件是 robots 和附件入口恢复可采集响应。
- `cnipa` 当前只验证 www 公告页和第一份 PDF，`ggfw` 签名 PDF 路径仍保持 unknown robots 约束。

## 2026-10-22 最终集成

- 旧在线 CLI 和 `pipeline/run_source.py` 已退役，Scrapy 是唯一实时采集写入路径。
- 8 个项目均完成隔离数据库 fixture 双回放、`scrapy list`、`scrapy check`、来源审核和 live canary 尝试。
- 全量回归、schema/contract、Python 静态、whitespace、lock 和 live evidence index 校验结果见 `collection-state-and-evidence-acceptance.md`。
- 本文件保留 2026-10-21 的实际 live 计数，不把 fixture 成功改写为 live 成功。
