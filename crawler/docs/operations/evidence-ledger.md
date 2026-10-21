# 证据账本

状态: active

日期: 2026-10-19

本文是采集证据的单一索引。账本只记录位置、规模、哈希和审核入口，不复制样本正文。本地下载目录的逐文件哈希以 `download/SHA256SUMS.txt` 为机器可读索引；公开 fixture 的哈希以下方专用表为准，人工说明以本表和来源审核记录为准。

## 公开仓库安全边界

`crawler/download/` 是本地证据目录，已整体忽略。原始 HTML、JSON、PDF、XLSX、图片和 `.headers` 默认只保留在本机；需要公开时，只提交标准化全文、元数据和 `crawler/tests/fixtures/evidence/` 下经过脱敏、体积受控的最小测试样本。`.headers` 可能包含 `Set-Cookie`、会话标识或第三方响应信息；下载目录中的 `.headers` 禁止提交，fixture 中的 headers 也必须先确认不含凭据。

公开发布使用从 `main` 重建的干净公开分支 `codex/crawler-public-release`。该分支只在 `main` 之后新增 crawler 提交，可达历史不含 `crawler/download/`、`.headers`、会话头或原始附件；`check_history_hygiene.py` 在单分支 clean clone 中为 0 命中。内部集成分支的旧历史不进入公开分支，也不需要改写。

## 字段

| 字段 | 含义 |
| --- | --- |
| `source_id` | 与 `sources.json` 一致的来源 ID |
| `verified_at` | 来源入口与样本最近一次复核时间 |
| `key_urls` | 入口、列表、详情或附件的关键 URL |
| `fixture_dir` | `crawler/tests/fixtures/evidence/` 下的公开来源目录 |
| `files` | 当前公开 fixture 文件数 |
| `bytes` | 当前公开 fixture 总字节 |
| `sha256_index` | 文件哈希索引位置 |
| `review` | 独立审核文档路径 |

## 总账

| source_id | verified_at | key_urls | fixture_dir | files | bytes | sha256_index | review |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `ihchina` | 2026-10-19 18:05 Asia/Shanghai | `https://www.ihchina.cn/getProject.html`；`https://www.ihchina.cn/project_details/12178.html` | `crawler/tests/fixtures/evidence/ihchina/` | 3 | 3250 | 见下方 fixture 表 | `docs/reviews/ihchina.md` |
| `aqsc-moa` | 2026-10-19 01:29 Asia/Shanghai | `http://www.aqsc.agri.cn/tzgg/`；`http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm` | `crawler/tests/fixtures/evidence/aqsc-moa/` | 3 | 11830 | 下方 fixture 表 | `docs/reviews/aqsc-moa.md` |
| `cnipa` | 2026-10-19 01:53 Asia/Shanghai | `https://ggfw.cnipa.gov.cn/dlbzsq/dbQuery`；`https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541` | `crawler/tests/fixtures/evidence/cnipa/` | 2 | 2030 | 下方 fixture 表 | `docs/reviews/cnipa.md` |
| `weather` | 2026-10-19 01:29 Asia/Shanghai | `https://www.weather.com.cn/`；`https://d1.weather.com.cn/sk_2d/101010100.html` | `crawler/tests/fixtures/evidence/weather/` | 2 | 407 | 下方 fixture 表 | `docs/reviews/weather.md` |
| `open-meteo` | 2026-10-20 Asia/Shanghai | `https://open-meteo.com/`；`https://api.open-meteo.com/v1/forecast` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/open-meteo.md` |
| `qweather` | 2026-10-20 Asia/Shanghai | `https://www.qweather.com/`；`https://devapi.qweather.com/v7/weather/now` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/qweather.md` |
| `nzrc` | 2026-10-19 01:28 Asia/Shanghai | `http://www.nzrc.com.cn/career_seek.html`；`http://www.nzrc.com.cn/company/jobs/8235500.html` | `crawler/tests/fixtures/evidence/nzrc/` | 3 | 1955 | 下方 fixture 表 | `docs/reviews/nzrc.md` |
| `nongmuhr` | 2026-10-19 01:28 Asia/Shanghai | `http://nongmuhr.com/Employ.aspx`；`http://nongmuhr.com/EmployView.aspx?id=13520` | `crawler/tests/fixtures/evidence/nongmuhr/` | 3 | 1686 | 下方 fixture 表 | `docs/reviews/nongmuhr.md` |
| `5ajob` | 2026-10-19 01:29 Asia/Shanghai | `http://www.5ajob.com/job/`；`http://www.5ajob.com/c-d-9975f684d6022631-h/50506.html` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/5ajob.md` |
| `dialect-org` | 2026-10-19 01:29 Asia/Shanghai | `https://dialect.org.cn/`；`https://dialect.org.cn/dialect/1` | `crawler/tests/fixtures/evidence/dialect-org/` | 1 | 495 | 下方 fixture 表 | `docs/reviews/dialect-org.md` |
| `cass-linguistics` | 2026-10-19 01:29 Asia/Shanghai | `http://ling.cass.cn/`；`http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html` | `crawler/tests/fixtures/evidence/cass-linguistics/` | 1 | 631 | 下方 fixture 表 | `docs/reviews/cass-linguistics.md` |
| `cnopendata` | 2026-10-19 01:45 Asia/Shanghai | `https://www.cnopendata.com/data/m/culture/zgfyxx.html`；`https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/cnopendata.md` |
| `zhongguoyuyan` | 2026-10-19 01:45 Asia/Shanghai | `https://zhongguoyuyan.cn/robots.txt`；首页未请求 | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/zhongguoyuyan.md` |
| `feiyiw` | 2026-10-19 01:45 Asia/Shanghai | `https://www.feiyiw.cn/`；`https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70177` | `crawler/tests/fixtures/evidence/feiyiw/` | 1 | 572 | 下方 fixture 表 | `docs/reviews/feiyiw.md` |

## 当前汇总

- 公开合成 fixture 共 19 个文件，总字节 22856，最大单文件 5445 字节，低于 100MB。
- 所有公开 XLSX、PDF、HTML 都带合成标记，不含真实联系人列、隐藏表单 token、原始作者元数据或嵌入附件。
- 本地 `crawler/download/` 仍为未跟踪证据目录，不进入公开索引；没有文件时记为 0，不伪造哈希。
- 公开分支使用空历史基线，最终 clean-clone 扫描由独立 public-branch 步骤执行，见 `operations/history-hygiene.md`。
- `ihchina` 2026-10-19 的分页全量校验只保存统计结果，见 `operations/validation.md`。详情 HTML 已落为公开合成 fixture，原始 live raw 快照未提交。
- `cnipa` 的短期签名 URL 不进入账本。长期入口使用检索详情页或公告页，文件本体用本地 SHA-256 标识。
- live 小样本的运行结果、`failure_count` 和阻断原因以 `reviews/` 与 `scrapy-migration-validation.md` 为准，本账本不复制这些计数。

## 公开 fixture 索引

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `crawler/tests/fixtures/evidence/aqsc-moa/discover.json` | 1073 | `a368b534dc46b5b6c013f6ea32a665bdfc8cd7fafbba4202cc74d63f82d561b3` |
| `crawler/tests/fixtures/evidence/aqsc-moa/synthetic-mtyx-sample.xlsx` | 5445 | `c77f3a82b228f09303188eeef30d3e4beb275405fe790624d3aca49140749924` |
| `crawler/tests/fixtures/evidence/aqsc-moa/synthetic-tepinongpin-sample.xlsx` | 5312 | `af128ce30aea149f6ce54ef9c6b4eaab5bacc5fa1a5ded35b5224ddc0bd5038f` |
| `crawler/tests/fixtures/evidence/cass-linguistics/discover.json` | 631 | `f33fe734ce28386c8dd3820cb4781d750f7d70509654e4ff6a11919e08b15d35` |
| `crawler/tests/fixtures/evidence/cnipa/discover.json` | 546 | `7b09c89d8e27e740f4bd5b322228fd185722e68efbc86422c8921e62ed9125c6` |
| `crawler/tests/fixtures/evidence/cnipa/synthetic-announcement-687.pdf` | 1484 | `a003e49e62921be5b06de41993ed8f55ba6faceb805521f860e2fe21c947caea` |
| `crawler/tests/fixtures/evidence/dialect-org/discover.json` | 495 | `7236c533df2f9100684adbd8b65a5e18c2abb7f48452474273bb3970c1e6fd20` |
| `crawler/tests/fixtures/evidence/feiyiw/discover.json` | 572 | `2e955d41f3d66fd30fd89811645f5f01146323b6c947b284c0ca67be95868ada` |
| `crawler/tests/fixtures/evidence/ihchina/discover.json` | 1019 | `2865d896c53bf4d87b0724eba9ec8efcebed0936af618ab9a2c800513fb2f9aa` |
| `crawler/tests/fixtures/evidence/ihchina/detail-12178.html` | 1674 | `57d973a6b107bf27329ff1aceb9cde9b66ad464c835e286b84cc8e8f5ba9dec4` |
| `crawler/tests/fixtures/evidence/ihchina/detail-12179.html` | 557 | `db66fd777c2e9a0293e8044d3882d8f3c6ef340caa0fc7bd420384daa3cc2462` |
| `crawler/tests/fixtures/evidence/nongmuhr/discover.json` | 1148 | `cb8c251dc501511e23a1fb3eed3b1a8269e010d5d344f5912c9f7991f4d8e4d2` |
| `crawler/tests/fixtures/evidence/nongmuhr/employ-view-13519.html` | 269 | `05461e1599117ab5a294852722e9ac84b246150d36b80e2ecd6dc2ff3be297d5` |
| `crawler/tests/fixtures/evidence/nongmuhr/employ-view-13520.html` | 269 | `a23e87237d11d244e8f625a2f73c74c045a54da97dcb10c43d532f6479245a09` |
| `crawler/tests/fixtures/evidence/nzrc/discover.json` | 1185 | `978466a6b6c1644b152131928e09e361cb6de954ebd3599eb0594e8e035ef3df` |
| `crawler/tests/fixtures/evidence/nzrc/job-detail-8235500.html` | 385 | `bba750d9e49b65942bdad7e1eaf712fce5a11f19cb859adfb64191cf35960308` |
| `crawler/tests/fixtures/evidence/nzrc/job-detail-8240109.html` | 385 | `1b3807fdeac5fd5b4e9c68917ed3a193c6ae746cd443d77f084ce67048fe7100` |
| `crawler/tests/fixtures/evidence/weather/sk-beijing.json` | 375 | `49f02176a74963714b173ef291b36e995783563e86a0fc1fa3acfdec8351046b` |
| `crawler/tests/fixtures/evidence/weather/sk-beijing.response-headers.txt` | 32 | `722ab081249af11d22563126b6a2c04b67e9309cee994b5f98474c5e59f1f408` |

## 维护规则

1. 每次新增、替换或删除下载文件后重新生成 `download/SHA256SUMS.txt`，再更新本表文件数和总字节。
2. `headers` 文件的哈希只证明本次响应头样本，不用于跨请求内容变更判断。
3. 临时签名 URL、Cookie、账号密码和会话令牌不进入关键 URL 或哈希索引。
4. 来源没有稳定附件时，写明“只读不落盘”、响应元数据位置和重跑命令，不补造空文件。
5. 审核结论和缺口以 `reviews/` 为准，本账本不维护第二份问题明细。

## 实现说明

- XLSX、PDF 和 HTML fixture 由 `python -m crawler.tools.generate_public_fixtures` 确定性生成。生成器固定元数据和 ZIP 时间戳，文件可重复重建。
- 生成器不包含真实联系人列、个人联系方式、隐藏表单、源作者元数据、原始嵌入对象或完整源附件。
- 多页 JSON fixture 按页保存确定性序列化后的页对象，并在 `metadata_json` 记录整份 fixture 路径和 SHA-256。这是为聚合 fixture 保留的明确取舍，真实 live 运行保存原始响应字节。
- `stage_fixture_items` 是 `stage_source_items` 的兼容视图；当前适配器共享中性 stage 表，来源专属 stage 表继续按 schema 演进。
