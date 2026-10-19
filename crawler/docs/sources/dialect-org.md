# 中国方言库

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `dialect-org`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:08 Asia/Shanghai`

## 来源概况

- 名称: 中国方言库
- 域名: `dialect.org.cn`
- 主管机构: 未在页面公开主管机构；页脚写“Powered by 造蓝科技基金 & AI测试俱乐部”
- 内容域: 方言词条、地区、读音、释义
- 优先级: P1
- 访问等级: `public`
- `license_or_usage`: 未见明确开放许可或转载授权；词条数量很小，建议仅保存元数据、短释义和来源链接，音频不复制
- `confidence`: `high`（15 条及详情字段已逐条验证；音频可用性为 `low`）

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `https://dialect.org.cn/` | GET | 200，页面显示“共收录 15 条” |
| 列表页 | `https://dialect.org.cn/` | GET | 首页即全量列表，无独立分页 |
| 搜索结果页 | `https://dialect.org.cn/` | GET | 前端 `#searchInput` 触发 `GET /api/search?q=` |
| 搜索 API | `https://dialect.org.cn/api/search?q={关键词}` | GET | 返回 JSON 数组 |
| 详情页模式 | `https://dialect.org.cn/dialect/{id}` | GET | `id` 为 1..15 的小整数 |

## 请求与分页

- 请求方式: HTML `GET`；搜索为 JSON `GET`
- 查询参数: `q`（搜索关键词，UTF-8 URL 编码；空字符串返回空数组）
- 分页字段: 无。首页一次性返回 15 张 `.card`
- 每页数量: 15（全量）
- 总数字段: 首页文本“共收录 15 条”；无 JSON 总数
- 筛选字段: 仅全文搜索 `q`，未发现地区、方言名、词条字段的独立筛选参数

## 字段定位

### JSON API

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `id` | 详情 ID | `1` |
| `name` | 词条文本 | `你好` |
| `phonetic` | 页面展示的读音/拼音 | `Nǐ hǎo` |
| `region` | 地区标签 | `北京` |

`GET /api/search?q=食饭` 返回 2 条：`{"id":3,"name":"食饭未","phonetic":"Sik6 faan6 mei6","region":"广州"}` 和 `{"id":8,"name":"食饭","phonetic":"Sik6 faan6","region":"广东广州"}`。API 只做搜索，不提供全量列表接口；不能靠空查询枚举全部词条。

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 总数 | `main` 文本中“共收录 15 条” | 当前数量 |
| 列表卡片 | `.card` | 首页 15 个 |
| 地区 | `.card .card-tag` | 如 `上海`、`广东广州` |
| 词条 | `.card h3` | 如 `侬好` |
| 摘要 | `.card p` | 如 `上海话：你好...`，带省略号 |
| 详情链接 | `.card .card-link[href^="/dialect/"]` | 文本“听发音 →”不代表音频一定存在 |
| 搜索输入 | `#searchInput` | 前端输入框 |
| 搜索按钮 | `#searchBtn` | 触发 `performSearch()` |
| 详情地区 | `.detail-header .card-tag` | 如 `北京` |
| 详情词条 | `.detail-word` | 如 `你好` |
| 详情读音 | `.detail-phonetic` | 如 `Nǐ hǎo` |
| 音频 | `.audio-box audio[src]` | 无音频时该元素不存在 |
| 音频缺失 | `.audio-box` 文本“暂无音频录音” | 15 条中 14 条为此状态 |
| 文化解读 | `main .card p` | 详情正文的唯一段落 |

## 真实样本

### 样本 1

- 详情 URL: `https://dialect.org.cn/dialect/1`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 地区 `北京`；词条 `你好`；读音 `Nǐ hǎo`；释义 `普通话标准发音`；页面存在 `<audio src="https://你的OSS bucket.oss-cn-hangzhou.aliyuncs.com/hello.mp3">`
- 音频结论: 存在 `audio` 元素但地址是占位字符串，Playwright 实测 `MediaError code 4`、`networkState=3`，音频不可用
- 目标映射: `std_dialect_pointss`（北京）+ `std_dialect_lexemes` + `std_dialect_lexeme_sources`

### 样本 2

- 详情 URL: `https://dialect.org.cn/dialect/8`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 地区 `广东广州`；词条 `食饭`；读音 `Sik6 faan6`；释义 `粤语`；`audio` 不存在，页面显示“🎵 暂无音频录音”
- 目标映射: 同上；方言名可暂填 `粤语`，但来源没有独立方言名字段，不能据此建立确定谱系

### 样本 3

- 详情 URL: `https://dialect.org.cn/dialect/3`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 地区 `广州`；词条 `食饭未`；读音 `Sik6 faan6 mei6`；释义 `粤语：吃饭了吗`；无音频
- 用途: 验证 `region` 的写法不统一（`广州` 与 `广东广州` 并存），地区归一不能只做字符串相等

### 全部 15 条核验摘要

`/dialect/1` 到 `/dialect/15` 在验证时均返回 200，标题、地区、词条和读音字段可读；仅 `/dialect/1` 有 `audio` 元素，且该元素不可播放。首页顺序不等于 ID 顺序。

## 字段映射

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| 详情路径中的 `id` | `std_dialect_lexeme_sources.source_record_id` | `dialect_lexeme_sources.source_record_id` | 来源内自然键一部分 |
| `region` | `std_dialect_pointss.region_raw` | `dialect_points.region_raw` | 保留原值，再生成规范化省/市 |
| `region` 规范化结果 | `std_dialect_pointss.province`、`std_dialect_pointss.city` | `dialect_points.province`、`dialect_points.city` | 仅在有证据时拆分，不猜县级点 |
| `name` / `.detail-word` | `std_dialect_lexemes.lemma` | `dialect_lexemes.lemma` | 词条/词形原文 |
| `phonetic` / `.detail-phonetic` | `std_dialect_lexemes.phonetic` | `dialect_lexemes.phonetic` | 保留来源拼写；不擅自改国际音标 |
| 文化解读 | `std_dialect_lexemes.definition` | `dialect_lexemes.definition` | 保存短释义，保留原文 |
| 摘要中的“粤语”“上海话”等 | `std_dialect_pointss.dialect_name` | `dialect_points.dialect_name` | 仅作建议值，需人工复核 |
| `<audio src>` | `std_dialect_lexemes.audio_url` | `dialect_lexemes.audio_url` | 只在 URL 可实际访问时写入；当前全部为 null |
| “暂无音频录音” | `std_dialect_lexemes.audio_status` | `dialect_lexemes.audio_status` | 记为 `missing`；占位 URL 记为 `invalid` |
| 详情 URL | `std_dialect_lexeme_sources.source_url` | `dialect_lexeme_sources.source_url` | 直接可打开 |
| 抓取时间 | `std_dialect_lexeme_sources.fetched_at` | `dialect_lexeme_sources.fetched_at` | 每次采集更新时间 |

建议自然键: `(source_id='dialect-org', source_record_id=id)`；跨来源去重时再用 `(dialect_point_id, lemma, source_id)` 判定词条来源，不要用词条文本单独去重，因为不同方言点存在同名词条。

### 粤乡智匠建议表

| 建议表 | 用途 | 关键字段 |
| --- | --- | --- |
| `dialect_points` | 方言点/地区 | `id`、`source_id`、`source_record_id`、`region_raw`、`province`、`city`、`dialect_name`、`fetched_at` |
| `dialect_lexemes` | 词条、读音、释义、音频 | `id`、`dialect_point_id`、`lemma`、`phonetic`、`definition`、`audio_url`、`audio_status`、`fetched_at` |
| `dialect_lexeme_sources` | 词条来源 | `lexeme_id`、`source_id`、`source_record_id`、`source_url`、`fetched_at` |

现有 `dialect_phrases` 是前台展示表（`dialect`、`mandarin`、`pinyin`），只能作为发布目标之一，不能替代上述规范化表。不要修改现有表结构来承载来源字段。

## 数据量与更新

- 当前数量估算: 15 条词条，覆盖 15 个首页卡片、15 个详情 ID
- 更新频率: 不可从页面判断；当前看起来是演示级静态数据
- 变更检测: 首页“共收录 N 条”、15 个 `.card` 的字段哈希、详情页字段哈希、`/api/search` 返回变化
- 建议采集频率: 每周 1 次；首页新增/删除卡片或详情 404 时立即复核
- 历史数据保留: 采集库保留每次详情快照；业务库只发布审核通过的词条

## 风险与限制

- 登录: 不需要登录
- robots: `https://dialect.org.cn/robots.txt` 返回 404，`http://` 会重定向到 HTTPS；未发现可用 robots 规则，按公开页面最小频率访问
- 版权: 未发现开放许可；只保存来源元数据、短释义和列表结构，不批量复制音频或大段正文
- 结构稳定性: Flask 页面结构简单但不稳定；音频字段是占位 URL；`region` 粒度不统一；没有独立方言名字段
- 缺失字段: 音标与拼音混用、无音频来源和许可、无更新时间、无结构化谱系、无全量分页 API
- 音频: 不能因为存在“听发音”链接就认定有音频；必须同时检查 `<audio>` 可加载性和 HTTP 响应

## 验证记录

- 验证方式: `requests` 实际 HTTP + Playwright Chromium
- 验证结果: 首页 200；`/dialect/1` 到 `/dialect/15` 均 200；`/api/search?q=你好` 与 `q=食饭` 返回 200 JSON；`/dialect/1` 音频在浏览器中加载失败
- 未验证项: 站点未来是否新增词条、音频是否会在其他域名恢复、是否有未公开的全量 API、版权方明确授权范围

## 审核要求

- 入口可打开: 是
- 样本可复现: 是（3 条详情样本 + 15 条全量核验）
- 字段映射完整: 是；方言名和音频标记为待复核/缺失
- 详情 URL 可直达: 是
