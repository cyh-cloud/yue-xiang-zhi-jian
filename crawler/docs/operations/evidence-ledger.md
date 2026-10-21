# 证据账本

状态: active

日期: 2026-10-21

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
| `aqsc-moa` | 2026-10-21 23:05 Asia/Shanghai | `https://jgs.moa.gov.cn/rzde/202509/t20250908_6477077.htm`；`http://www.aqsc.agri.cn/tzgg/202508/t20250806_463294.htm`；`http://www.aqsc.agri.cn/tzgg/202508/P020250821548932446299.xlsx` | `crawler/tests/fixtures/evidence/aqsc-moa/` | 3 | 12116 | 下方 fixture 表 | `docs/reviews/aqsc-moa.md` |
| `cnipa` | 2026-10-21 23:05 Asia/Shanghai | `https://www.cnipa.gov.cn/art/2026/8/12/art_1400_207705.html`；`https://www.cnipa.gov.cn/module/download/downfile.jsp` | `crawler/tests/fixtures/evidence/cnipa/` | 2 | 2338 | 下方 fixture 表 | `docs/reviews/cnipa.md` |
| `weather` | 2026-10-19 01:29 Asia/Shanghai | `https://www.weather.com.cn/`；`https://d1.weather.com.cn/sk_2d/101010100.html` | `crawler/tests/fixtures/evidence/weather/` | 2 | 405 | 下方 fixture 表 | `docs/reviews/weather.md` |
| `open-meteo` | 2026-10-20 Asia/Shanghai | `https://open-meteo.com/`；`https://api.open-meteo.com/v1/forecast` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/open-meteo.md` |
| `qweather` | 2026-10-20 Asia/Shanghai | `https://www.qweather.com/`；`https://devapi.qweather.com/v7/weather/now` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/qweather.md` |
| `nzrc` | 2026-10-19 01:28 Asia/Shanghai | `http://www.nzrc.com.cn/career_seek.html`；`http://www.nzrc.com.cn/company/jobs/8235500.html` | `crawler/tests/fixtures/evidence/nzrc/` | 3 | 1916 | 下方 fixture 表 | `docs/reviews/nzrc.md` |
| `nongmuhr` | 2026-10-21 21:48 Asia/Shanghai | `http://nongmuhr.com/Employ.aspx`；`http://nongmuhr.com/EmployView.aspx?Id=13553` | `crawler/tests/fixtures/evidence/nongmuhr/` | 3 | 4709 | 下方 fixture 表 | `docs/reviews/nongmuhr-scrapy-sample.md` |
| `5ajob` | 2026-10-19 01:29 Asia/Shanghai | `http://www.5ajob.com/job/`；`http://www.5ajob.com/c-d-9975f684d6022631-h/50506.html` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/5ajob.md` |
| `dialect-org` | 2026-10-19 01:29 Asia/Shanghai | `https://dialect.org.cn/`；`https://dialect.org.cn/dialect/1` | `crawler/tests/fixtures/evidence/dialect-org/` | 1 | 486 | 下方 fixture 表 | `docs/reviews/dialect-org.md` |
| `cass-linguistics` | 2026-10-19 01:29 Asia/Shanghai | `http://ling.cass.cn/`；`http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html` | `crawler/tests/fixtures/evidence/cass-linguistics/` | 1 | 613 | 下方 fixture 表 | `docs/reviews/cass-linguistics.md` |
| `cnopendata` | 2026-10-19 01:45 Asia/Shanghai | `https://www.cnopendata.com/data/m/culture/zgfyxx.html`；`https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html` | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/cnopendata.md` |
| `zhongguoyuyan` | 2026-10-19 01:45 Asia/Shanghai | `https://zhongguoyuyan.cn/robots.txt`；首页未请求 | `crawler/tests/fixtures/evidence/`（无公开文件） | 0 | 0 | 不适用 | `docs/reviews/zhongguoyuyan.md` |
| `feiyiw` | 2026-10-19 01:45 Asia/Shanghai | `https://www.feiyiw.cn/`；`https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70177` | `crawler/tests/fixtures/evidence/feiyiw/` | 1 | 556 | 下方 fixture 表 | `docs/reviews/feiyiw.md` |

## 当前汇总

- 公开合成 fixture 共 19 个文件，总字节 26355，最大单文件 5445 字节，低于 100MB。
- 所有公开 XLSX、PDF、HTML 都带合成标记，不含真实联系人列、隐藏表单 token、原始作者元数据或嵌入附件。
- 本地 `crawler/download/` 仍为未跟踪证据目录，不进入公开索引；没有文件时记为 0，不伪造哈希。
- 公开分支使用空历史基线，最终 clean-clone 扫描由独立 public-branch 步骤执行，见 `operations/history-hygiene.md`。
- `ihchina` 2026-10-19 的分页全量校验只保存统计结果，见 `operations/validation.md`。详情 HTML 已落为公开合成 fixture，原始 live raw 快照未提交。
- `cnipa` 的短期签名 URL 不进入账本。长期入口使用检索详情页或公告页，文件本体用本地 SHA-256 标识。
- `aqsc-moa` live 被 403 阻断；`cnipa` live 使用 www 公告页和 428298 bytes PDF，产生 58 条 deferred 候选。原始证据进入稳定归档目录，摘要见 `reviews/*-scrapy-sample.md`。
- live 小样本的运行结果、`failure_count` 和阻断原因以 `reviews/` 与 `scrapy-migration-validation.md` 为准，本账本不复制这些计数。

## Live 证据归档

- 归档根: `../crawler-live-evidence/issue-133-20261021/`，相对于仓库根，不在 `%TEMP%`。
- 公开索引: `crawler/docs/operations/live-evidence-index.json`。
- 索引覆盖 8 个来源、8 次实际运行，包含 URL、取得时间、HTTP 状态、Content-Type、响应哈希、七类计数、失败摘要、阻断原因和验收记录指针。
- 原始响应正文、个人信息、凭据、Cookie 和签名 URL 只保留在归档目录，不进入公开仓库。
- 重建索引: `python -m crawler.tools.build_live_evidence_index --archive-root ../crawler-live-evidence/issue-133-20261021`。
- 只校验已提交索引: `python -m crawler.tools.build_live_evidence_index --validate-only`。

## 公开 fixture 索引

| 文件 | bytes | SHA-256 |
| --- | ---: | --- |
| `crawler/tests/fixtures/evidence/aqsc-moa/discover.json` | 1359 | `734becbadb8820129b1e1e2bc23b82eac4fb5c9a091533f2342153e88cedc1b5` |
| `crawler/tests/fixtures/evidence/aqsc-moa/synthetic-mtyx-sample.xlsx` | 5445 | `c77f3a82b228f09303188eeef30d3e4beb275405fe790624d3aca49140749924` |
| `crawler/tests/fixtures/evidence/aqsc-moa/synthetic-tepinongpin-sample.xlsx` | 5312 | `af128ce30aea149f6ce54ef9c6b4eaab5bacc5fa1a5ded35b5224ddc0bd5038f` |
| `crawler/tests/fixtures/evidence/cass-linguistics/discover.json` | 613 | `9683fcd3a167e43c434b7c2be358d3634e9776adbe2162c0113040c77508bc8b` |
| `crawler/tests/fixtures/evidence/cnipa/discover.json` | 671 | `777d99d37ff8a27ffabd06aad91851d89c3aecb7c24bd716d9c273258a5fe5e5` |
| `crawler/tests/fixtures/evidence/cnipa/synthetic-announcement-687.pdf` | 1667 | `76a1a3c162b12f95fa48f59380dc210b4a648aab4081299f4459c3c4a6c0e47e` |
| `crawler/tests/fixtures/evidence/dialect-org/discover.json` | 486 | `9321f30bca54c491e095d663d99c6438ab5c639d4303cdd74ce6fad81dd5017b` |
| `crawler/tests/fixtures/evidence/feiyiw/discover.json` | 556 | `443233489783b53f804ad26da39405b2d7b71a6e3e709bdb8082aff4235f8397` |
| `crawler/tests/fixtures/evidence/ihchina/discover.json` | 985 | `3c9c4a974ae46ce4b09f49dd22646c91fa0ff94ef45d8f4366901b04ac219df5` |
| `crawler/tests/fixtures/evidence/ihchina/detail-12178.html` | 1674 | `57d973a6b107bf27329ff1aceb9cde9b66ad464c835e286b84cc8e8f5ba9dec4` |
| `crawler/tests/fixtures/evidence/ihchina/detail-12179.html` | 557 | `db66fd777c2e9a0293e8044d3882d8f3c6ef340caa0fc7bd420384daa3cc2462` |
| `crawler/tests/fixtures/evidence/nongmuhr/discover.json` | 2211 | `6f5855d393d3f781a4fd216d94eddc3d2460267797e8f35b8259416353eb7883` |
| `crawler/tests/fixtures/evidence/nongmuhr/employ-view-13519.html` | 1249 | `e1f0b13264815a0d83df444bcc4917328e85d8505cd9df5bf36aa5748dd9723a` |
| `crawler/tests/fixtures/evidence/nongmuhr/employ-view-13520.html` | 1249 | `5637450c7fcc49d62f29bfcbc2401de3b216a3e03a2ecc5837186eea1cdaafb7` |
| `crawler/tests/fixtures/evidence/nzrc/discover.json` | 1150 | `685a2c0c75fb3e3a8c9db1c12de6971d9074cb03e4c8169919e28c5afbb544d1` |
| `crawler/tests/fixtures/evidence/nzrc/job-detail-8235500.html` | 383 | `fbd7deeaf65e539b4cd61d2ca6f44018c44b300c3977f69bb21d21646d1d9415` |
| `crawler/tests/fixtures/evidence/nzrc/job-detail-8240109.html` | 383 | `20fbb2859ea901fe75f8bd5e23186d8f6d4ea5e7591f7dfebc9c2582587dba18` |
| `crawler/tests/fixtures/evidence/weather/sk-beijing.json` | 374 | `cbcc00c4578724dd7dbb1e49d9eb32dfa5f6dcfc1eb583963d85123ad0d1adba` |
| `crawler/tests/fixtures/evidence/weather/sk-beijing.response-headers.txt` | 31 | `bb48375c103489ea3ab239933d2b8eacde7e19c7bdad55a761868189b13be59f` |

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
