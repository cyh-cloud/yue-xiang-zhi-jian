# 采集验收清单

状态: active

日期: 2026-10-19

本文用于来源实现、转换器和最终交付验收。验收结论只能是 `approved`、`approved-with-gaps`、`blocked`、`deferred` 或 `excluded`。

## Crawler 验收命令

从仓库根运行，命令自包含，不依赖应用基线数据库:

```powershell
python -m unittest discover -s crawler/tests -p "test_*.py" -t .
```

通过后再运行契约和静态检查:

```powershell
python crawler/tools/check_contracts.py
python tools/check_python.py
python tools/check_architecture.py
```

仓库根的全量单测 `python -m unittest discover -s . -p "test_*.py" -t .` 需要应用基线数据库 `data/baseline.db` 或等效测试数据库，不属于 crawler 验收范围。clean clone 不包含这些被忽略的数据库文件，因此不能把全量单测当作 crawler 的 clean-clone 通过证明。

## 1. URL 可访问

- 首页、栏目页、列表页、详情页和附件实际返回可解释的状态码。
- 记录验证时间、请求方式、User-Agent、HTTP 状态和内容类型。
- 404、403、429、5xx 和连接重置如实记录，不写成可用。
- robots、登录限制和版权限制已按来源访问等级核对。
- URL 使用 HTTPS 或有明确来源依据的 HTTP，不保存临时签名地址作为长期详情。

## 2. 详情 URL 可直达

- 每条样本的详情 URL 能直接打开单条记录，或提供可长期打开的承载页 URL 和非空 locator。
- 只给站点首页、列表首页、公司首页或搜索页不算直接详情 URL，但公告页、数据集页和检索详情页可以作为承载页 URL。
- `detail_url_status=missing` 时，承载页 URL 必须能重新打开，locator 必须能定位到同一记录。
- `cnipa` 的检索详情页可直达；签名 PDF URL 只进 raw，不写长期字段。
- `ihchina` 使用 `/project_details/{id}.html`，`5ajob` 使用 canonical 岗位 URL。
- 详情 URL 规范化后保留原始查询参数，去掉无意义跟踪参数。
- 重新访问详情 URL 或承载页 URL 后仍能定位同一记录。

## 3. DOM 选择器非空

- 每个关键选择器在真实页面上执行一次，结果数量大于 0。
- 列表行、详情标题、核心字段和详情链接分别验证。
- Playwright 等待条件明确，不靠固定睡眠制造偶然成功。
- 选择器为空时记录页面 URL、截图或 HTML 哈希，不写入空记录。
- 多套选择器按优先级排列，回退选择器也需实测。
- 依赖中文标签的选择器先做全角空格和空白归一化。

## 4. JSON 字段

- 记录接口 URL、请求参数、响应状态、内容类型和样本。
- 顶层字段、分页字段、列表字段和详情字段逐项核对。
- JSON 解析失败时保留原始正文并记录错误位置。
- `weather` 的 `var dataSK=...;` 不是严格 JSON，需按包裹格式解析并验证。
- 字段名变化、空数组、缺少 `list` 和越界页码有明确处理。
- 不以接口返回的推测字段补造业务字段。

## 5. 样本可复现

- 每个来源至少 1 至 3 条真实样本。
- 样本记录详情 URL、列表位置、抓取时间、关键字段和目标映射。
- 重新运行同一入口能得到相同记录或明确说明动态变化。
- 招聘、天气等时效数据说明验证时的值和当前值可能不同。
- 反例样本保留，例如 `5ajob` 的非农业岗位。
- 样本中的联系方式和个人信息按规则脱敏或不转录。

## 6. 字段映射

- 每个业务字段都有来源字段、crawler std 字段和建议业务字段。
- 目标表不存在时明确写“建议新增”，不假装已存在。
- 认证农产品、非遗、招聘、方言和天气分别按对应映射文档核对。
- 未知字段写 null 或“待验证”，不根据名称猜证书号、日期、行政区划和授权。
- 目标表、来源表和自然键分别写清。
- 人工字段保护和冲突记录规则已说明。

## 7. source_url

- 每条可入库记录保留发现来源 URL。
- `source_url` 与 `detail_url` 分开，不互相替代。
- 多来源同一实体保留每个来源 URL。
- 来源 URL 不使用临时签名、登录后地址或失效跳转。
- 原始响应、std 记录和业务来源表之间能通过 URL 和哈希回溯。

## 8. 下载校验和

- 每个下载文件记录 URL、大小、SHA-256 和取得时间。
- 重新下载后校验哈希；内容变化保留版本。
- 不计算截断文件或错误页的成功哈希。
- 超过 100MB 的文件只写 `OVERSIZE.md`。
- 下载目录、文件名和扩展名符合采集规则。
- 文档中的哈希与实际文件一致。

## 9. sources.json 合法性

- 文件是合法 JSON。
- 每个来源 ID 全局唯一。
- 必需字段齐全: `id`、`name`、`domains`、`content_domains`、`priority`、`enabled`、`status`、`access`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`run_modes`、`verification`、`document`、`review`。
- `priority` 取值在 P0、P1、P2 范围内。
- `access` 取值在 `public`、`login-required`、`robots-restricted`、`manual-only` 范围内。
- `document` 和 `review` 路径存在；缺失时在审核结论中明确记录为缺口。
- 目标表引用只指向本文档声明的现有表或建议新增表。
- 来源清单不与共享索引、ADR 或来源 ID 文档冲突。

## 10. 转换与业务表

- 转换器只读取 std 层。
- 自然键和幂等 升级写入 可复现。
- 同一自然键重复导入不产生重复业务记录。
- 官方来源优先于聚合来源。
- 冲突记录保留双方值、来源 URL、取得时间和原因。
- 人工修改字段不被自动覆盖。
- 导入批次可以统计成功、跳过、冲突、失败，并可撤销未被人工修改的结果。
- `job_listings` 和 `recruitments` 未被公开岗位采集写入。
- `crafts`、`dialects` 的现有展示契约未被破坏。

## 11. 审核结论

### `approved`

入口、字段、样本、映射、来源 URL、下载校验和来源清单均通过。没有影响使用的未验证项。

### `approved-with-gaps`

主体可复现，但存在明确缺口，例如部分字段未验证、样本缺失、授权待确认或全量页未穷举。缺口必须单列，并说明影响范围。

### `blocked`

访问受限、robots 禁止、结构不可确认、版权风险未解决或样本无法复现。不得进入自动采集和业务发布。

## 12. 审核记录必须包含

- 审核对象、审核时间和审核人。
- 实际验证的 URL 和请求方式。
- 样本复现结果。
- 选择器或 JSON 字段结果。
- 字段映射核对结果。
- 下载和哈希核对结果。
- 来源清单核对结果。
- 结论和未验证项。
- 若为 `blocked`，写明解除条件。

## 机械检查命令

以下命令从仓库根运行，退出码非零即失败。

```powershell
python -c "import json,pathlib; r=pathlib.Path('crawler/docs'); d=json.loads((r/'sources.json').read_text(encoding='utf-8')); ids=[s['id'] for s in d['sources']]; assert len(ids)==len(set(ids)); assert all((r/s[k]).exists() for s in d['sources'] for k in ('document','review')); print('sources.json OK', len(ids))"
```

预期输出: `sources.json OK 14`。

```powershell
python -c "import pathlib; r=pathlib.Path('crawler/docs'); bad=[str(p) for p in r.rglob('*.md') if chr(0x2014) in p.read_text(encoding='utf-8')]; assert not bad, bad; print('no em-dash')"
```

预期输出: `no em-dash`。

```powershell
python -c "import pathlib; r=pathlib.Path('crawler/download'); fs=[p for p in r.rglob('*') if p.is_file()]; over=[str(p) for p in fs if p.stat().st_size>100*1024*1024]; print('files',len(fs),'bytes',sum(p.stat().st_size for p in fs),'over100',len(over)); assert not over"
```

预期输出包含 `over100 0`。

```powershell
python -c "import pathlib,re; r=pathlib.Path('crawler/docs'); bad=[]; pats=[r'\b(?:std|stage)_[a-z0-9_]+ss\b', r'\bstd_ich_project\b', r'\bstd_recruitment_posting\b', r'\bstd_dialect_point\b', r'\bstd_weather_candidate\b', r'\bstd\.[a-z_]', r'\bcrawler\.std\.', r'\bstage\.[a-z_]']; [bad.append((str(p),pat)) for p in r.rglob('*.md') for pat in pats if re.search(pat,p.read_text(encoding='utf-8'))]; assert not bad,bad; print('table names OK')"
```

预期输出: `table names OK`。

## 契约机械检查

从仓库根运行：

```powershell
python crawler/tools/check_contracts.py
```

检查来源状态、std 表名、mapping 字段、URL 与版权列、问题统计、实现契约和空历史基线。任何错误都必须先修复再提交。整合 worktree 的旧历史不在这里扫描；需要同时扫描时加 `--scan-history`。

```powershell
python crawler/tools/check_history_hygiene.py
```

扫描所有可达 Git 历史中的 raw 路径、`.headers`、Cookie、Authorization、签名、私钥、HTML 隐藏表单、XLSX 联系人列、PDF 原始元数据和常见个人数据。公开分支必须使用空基线，任何命中都必须失败。

## 无网络 dry-run

公开 fixture 足以复核 P0 的附件行门禁。以下命令使用临时采集库，不访问网络：

```powershell
python -m crawler.run aqsc-moa --mode xlsx --database crawler/data/crawler-audit.db --xlsx-root crawler/tests/fixtures/evidence/aqsc-moa
python -m crawler.run cnipa --mode pdf --database crawler/data/crawler-audit.db --pdf-root crawler/tests/fixtures/evidence/cnipa
```

两条命令都必须返回 `status='succeeded'`；AQSC 公开合成样本应发现 8 行，CNIPA 公开合成 PDF 应发现 2 行。附件行保留在 raw/stage，并写入公告承载页和非空 locator。没有直接详情 URL 不是阻断条件；承载页或 locator 缺失时才写 `deferred`，不得发布。

## ihchina 3610 实测

2026-10-19 用公开 JSON 接口 `limit=100` 遍历 37 页，累计 `total=3610`，唯一项目 ID 3610，重复 ID 0。实测输出:

```json
{"total": 3610, "pages": 37, "pages_fetched": 37, "rows": 3610, "unique_ids": 3610, "duplicates": 0}
```

详情页可访问性全量检查仍列为缺口。

## 待验证

- 3610 个详情页未全量打开，仅完成分页总数和唯一 ID 校验。
- 各来源真实调度频率和失败重试参数需在实现期确认。
- 审核记录模板中审核人字段沿用 agent 标识，未建立人工账号映射。
