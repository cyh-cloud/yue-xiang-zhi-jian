# 方言点、词条与来源映射

状态: draft

日期: 2026-10-19

本文覆盖方言点、词条和来源映射。现有 `dialects`、`dialect_phrases`、`dialect_quick_questions` 继续服务前台，新规范化模型作为建议新增表，不改现有三张表。

## 现有展示表

- `dialects`: 方言介绍卡，字段为 `id`、`name`、`region`、`emoji`、`areas`、`speakers`、`greeting`、`greeting_meaning`、`features`、`sort_order`、`extra`。
- `dialect_phrases`: 展示短语，字段为 `dialect_id`、`dialect`、`mandarin`、`pinyin`、`sort_order`、`extra`。
- `dialect_quick_questions`: 快捷问题，字段为 `dialect_id`、`question`、`sort_order`、`extra`。
- 前台 `GET /api/resources/dialects` 读取方言列表，`GET /api/resources/dialect-info` 读取详情、短语和快捷问题。

这些表缺少来源 ID、原始详情 URL、经纬度、国际音标、置信度和词条级来源，不能替代规范化表。

## 规范化建议表

### `dialect_points`

| 字段 | 含义 |
| --- | --- |
| `id` | 内部稳定 id |
| `source_id` | 来源 ID |
| `source_record_id` | 来源内记录 ID |
| `dialect_name` | 方言名，来源有明确值时填写 |
| `dialect_family` | 方言系属，来源有明确值时填写 |
| `province`、`city`、`county` | 规范化行政区划 |
| `region_raw` | 来源地区原文 |
| `latitude`、`longitude` | 经纬度，只有来源明确给出时才填 |
| `coordinate_precision` | `point`、`city`、`county` 或 `unknown` |
| `fetched_at` | 取得时间 |
| `confidence` | 识别置信度 |

### `dialect_lexemes`

| 字段 | 含义 |
| --- | --- |
| `id` | 内部稳定 id |
| `dialect_point_id` | 指向方言点 |
| `lemma` | 词条原文 |
| `mandarin_definition` | 普通话释义 |
| `pinyin` | 来源拼音或注音 |
| `ipa` | 国际音标，来源没有时 null |
| `part_of_speech` | 词性，来源明确时填写 |
| `example_sentence` | 例句 |
| `audio_url` | 可实际访问的音频 URL |
| `audio_status` | `available`、`missing`、`invalid` 或 `unknown` |
| `confidence` | 词条级置信度 |

### `dialect_lexeme_sources`

保存 `lexeme_id`、`source_id`、`source_record_id`、`source_url`、`fetched_at`、`content_hash` 和 `raw_snapshot_path`。

## 字段映射

| 业务字段 | `dialect-org` | `cass-linguistics` | 其他来源 | crawler std 层 | 现有展示表落点 |
| --- | --- | --- | --- | --- | --- |
| 方言名 | 摘要或释义中的“粤语”“上海话”等，需复核 | 研究资源说明，待验证 | 待验证 | `std_dialect_point.dialect_name` | 人工映射后写 `dialects.name` |
| 方言系属 | 未提供 | 研究资源可能提及，待验证 | 待验证 | `std_dialect_point.dialect_family` | 人工映射后写 `dialects.extra.dialect_family` |
| 省份 | `region` 规范化 | 待验证 | 待验证 | `std_dialect_point.province` | `dialects.region` 的一部分 |
| 城市 | `region` 规范化，如 `广东广州` | 待验证 | 待验证 | `std_dialect_point.city` | `dialects.region` |
| 县区 | 样本未提供 | 待验证 | 待验证 | `std_dialect_point.county` | `dialects.extra.county` |
| 经纬度 | 未提供 | 未提供 | 待验证 | `std_dialect_point.latitude`、`longitude` | 不建议写入现有表 |
| 词条 | `name` / `.detail-word` | 不映射为词条 | 待验证 | `std_dialect_lexeme.lemma` | `dialect_phrases.dialect` |
| 普通话释义 | 文化解读短段 | 不映射为词条 | 待验证 | `std_dialect_lexeme.mandarin_definition` | `dialect_phrases.mandarin` |
| 拼音 | `phonetic` / `.detail-phonetic` | 不映射为词条 | 待验证 | `std_dialect_lexeme.pinyin` | `dialect_phrases.pinyin` |
| 国际音标 | 未提供，待验证 | 未提供 | 待验证 | `std_dialect_lexeme.ipa` | `dialect_phrases.extra.ipa` |
| 词性 | 未提供 | 未提供 | 待验证 | `std_dialect_lexeme.part_of_speech` | `dialect_phrases.extra.part_of_speech` |
| 例句 | 未提供 | 登录后语料，不采集 | 待验证 | `std_dialect_lexeme.example_sentence` | `dialect_phrases.extra.example_sentence` |
| 音频 URL | `.audio-box audio[src]` | 不提供 | 待验证 | `std_dialect_lexeme.audio_url` | `dialect_phrases.extra.audio_url` |
| 来源 URL | `/dialect/{id}` | 文章详情 URL | 待验证 | `std_dialect_lexeme_source.source_url` | `dialect_phrases.extra.source_url` |
| confidence | 词条和地区可读，建议 `high` | 研究资料不能生成词条 | 待验证 | `std_dialect_lexeme_source.confidence` | `dialect_phrases.extra.confidence` |

## 方言点与词条的关系

- 一个方言点可以有多个词条。
- 一个词条可以有一个或多个来源。
- 同一词条文本在不同方言点不是同一实体，不能只按词条文本去重。
- 建议词条自然键: `dialect_point_id + lemma + source_id`。
- 建议来源自然键: `(source_id, source_record_id)`；没有来源记录 ID 时用 canonical `source_url`。
- `dialect.org.cn` 的 `/dialect/1` 到 `/dialect/15` 是词条详情，不是 15 个独立方言点。
- `cass-linguistics` 是研究资料和资讯来源，不生成方言词条。
- `zhongguoyuyan.cn` 为 `robots-restricted`，只登记，不自动采集正文。

## 现有表与新表的关系

新规范化表是事实源，现有展示表是发布视图。转换器从 std 层选审核通过、可展示的方言点和词条，生成或更新展示表:

- `dialect_points.dialect_name` 或人工配置映射到 `dialects.name`。来源没有明确方言名时，转换器不自动写 `dialects.name`。
- `dialect_point.province`、`city` 组合为 `dialects.region`。
- `dialect_lexemes.lemma`、`mandarin_definition`、`pinyin` 映射到 `dialect_phrases`。
- 音标、词性、例句、音频和来源放 `dialect_phrases.extra`，避免改现有表结构。
- 现有展示行的手工修改受人工字段保护，不由采集结果覆盖。

## 音频与版权

- 音频 URL 只有在实际请求可播放时才写 `audio_url`。
- `dialect.org.cn` 样本 1 的 `audio` 指向占位 OSS 地址，加载失败，应记为 `invalid`。
- 页面写“暂无音频录音”时记 `missing`。
- 未发现开放许可的音频不批量下载、不复制到业务库。

## 已知缺口

- `dialect.org.cn` 没有结构化方言名、方言系属、经纬度、词性和国际音标。
- `region` 写法不统一，如 `广州` 与 `广东广州`。
- `cass-linguistics` 的方言语料需要登录，不能进入公开词条。
- `zhongguoyuyan.cn` 当前 robots 全站禁止抓取。
- 现有 `dialects` 表没有来源和置信度列。

## 待验证

- 其他方言来源是否提供经纬度和方言系属。
- 普通话释义、拼音和国际音标是否需要分别保留多个版本。
- 现有前端是否需要按方言点、县区或词性筛选。
- 音频授权和长期可用性。
