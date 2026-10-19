# 证据账本

状态: active

日期: 2026-10-19

本文是采集证据的单一索引。账本只记录位置、规模、哈希和审核入口，不复制样本正文。逐文件哈希以 `download/SHA256SUMS.txt` 为机器可读索引，人工说明以本表和来源审核记录为准。

## 字段

| 字段 | 含义 |
| --- | --- |
| `source_id` | 与 `sources.json` 一致的来源 ID |
| `verified_at` | 来源入口与样本最近一次复核时间 |
| `key_urls` | 入口、列表、详情或附件的关键 URL |
| `download_dir` | `crawler/download/` 下的来源目录 |
| `files` | 当前目录文件数，包含 headers 和说明文件 |
| `bytes` | 当前目录全部文件总字节 |
| `sha256_index` | 文件哈希索引位置 |
| `review` | 独立审核文档路径 |

## 总账

| source_id | verified_at | key_urls | download_dir | files | bytes | sha256_index | review |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
| `ihchina` | 2026-10-19 18:05 Asia/Shanghai | `https://www.ihchina.cn/getProject.html`；`https://www.ihchina.cn/project_details/12178.html` | `download/www.ihchina.cn/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/ihchina.md` |
| `aqsc-moa` | 2026-10-19 01:29 Asia/Shanghai | `http://www.aqsc.agri.cn/tzgg/`；`http://www.aqsc.agri.cn/tzgg/202511/t20251128_468194.htm` | `download/www.aqsc.agri.cn/` | 2 | 137959 | `download/SHA256SUMS.txt` | `docs/reviews/aqsc-moa.md` |
| `cnipa` | 2026-10-19 01:53 Asia/Shanghai | `https://ggfw.cnipa.gov.cn/dlbzsq/dbQuery`；`https://ggfw.cnipa.gov.cn/dlbzsq/detail?id=541&name=...` | `download/ggfw.cnipa.gov.cn/` | 5 | 1911740 | `download/SHA256SUMS.txt` | `docs/reviews/cnipa.md` |
| `weather` | 2026-10-19 01:29 Asia/Shanghai | `https://www.weather.com.cn/`；`https://d1.weather.com.cn/sk_2d/101010100.html` | `download/www.weather.com.cn/` | 14 | 602783 | `download/SHA256SUMS.txt` | `docs/reviews/weather.md` |
| `nzrc` | 2026-10-19 01:28 Asia/Shanghai | `http://www.nzrc.com.cn/career_seek.html`；`http://www.nzrc.com.cn/company/jobs/8235500.html` | `download/www.nzrc.com.cn/` | 12 | 376129 | `download/SHA256SUMS.txt` | `docs/reviews/nzrc.md` |
| `nongmuhr` | 2026-10-19 01:28 Asia/Shanghai | `http://nongmuhr.com/Employ.aspx`；`http://nongmuhr.com/EmployView.aspx?id=13520` | `download/nongmuhr.com/` | 12 | 482734 | `download/SHA256SUMS.txt` | `docs/reviews/nongmuhr.md` |
| `5ajob` | 2026-10-19 01:29 Asia/Shanghai | `http://www.5ajob.com/job/`；`http://www.5ajob.com/c-d-9975f684d6022631-h/50506.html` | `download/www.5ajob.com/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/5ajob.md` |
| `dialect-org` | 2026-10-19 01:29 Asia/Shanghai | `https://dialect.org.cn/`；`https://dialect.org.cn/dialect/1` | `download/dialect.org.cn/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/dialect-org.md` |
| `cass-linguistics` | 2026-10-19 01:29 Asia/Shanghai | `http://ling.cass.cn/`；`http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html` | `download/ling.cass.cn/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/cass-linguistics.md` |
| `cnopendata` | 2026-10-19 01:45 Asia/Shanghai | `https://www.cnopendata.com/data/m/culture/zgfyxx.html`；`https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html` | `download/www.cnopendata.com/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/cnopendata.md` |
| `zhongguoyuyan` | 2026-10-19 01:45 Asia/Shanghai | `https://zhongguoyuyan.cn/robots.txt`；首页未请求 | `download/zhongguoyuyan.cn/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/zhongguoyuyan.md` |
| `feiyiw` | 2026-10-19 01:45 Asia/Shanghai | `https://www.feiyiw.cn/`；`https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70177` | `download/www.feiyiw.cn/`（待建） | 0 | 0 | 待首次运行时生成 | `docs/reviews/feiyiw.md` |

## 当前汇总

- 有下载文件的来源目录 5 个，文件 45 个，总字节 3511345。
- 最大单文件 1174529 字节，低于 100MB。
- 有 7 个来源只在文档中保存页面和样本证据，尚未建立下载目录。没有文件时目录记为 0，不伪造哈希。
- `ihchina` 2026-10-19 的分页全量校验只保存统计结果，见 `operations/validation.md`。详情 HTML 与 raw 快照尚未落盘。
- `cnipa` 的短期签名 URL 不进入账本。长期入口使用检索详情页或公告页，文件本体用本地 SHA-256 标识。

## 维护规则

1. 每次新增、替换或删除下载文件后重新生成 `download/SHA256SUMS.txt`，再更新本表文件数和总字节。
2. `headers` 文件的哈希只证明本次响应头样本，不用于跨请求内容变更判断。
3. 临时签名 URL、Cookie、账号密码和会话令牌不进入关键 URL 或哈希索引。
4. 来源没有稳定附件时，写明“只读不落盘”、响应元数据位置和重跑命令，不补造空文件。
5. 审核结论和缺口以 `reviews/` 为准，本账本不维护第二份问题明细。
