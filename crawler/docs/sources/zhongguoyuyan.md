# 中国语言资源保护工程

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `zhongguoyuyan`

状态: `excluded`

权利状态: `prohibited`

访问等级: `robots-restricted`

验证时间: `2026-10-19 01:10 Asia/Shanghai`

## 来源概况

- 名称: 中国语言资源保护工程
- 域名: `zhongguoyuyan.cn`
- 主管机构: 未在本轮允许的验证范围内确认
- 内容域: 方言资源
- 优先级: P2
- 访问等级: `robots-restricted`
- `license_or_usage`: 版权说明不允许使用站点数据。用户已决定将该来源排除，不采集正文、音频或接口。
- `confidence`: 高，`robots.txt` 已实际读取且明确全站禁止抓取；低，首页正文、资源类型、字段、数量和接口均未验证。

本来源已标记为 `excluded`。`robots.txt` 当前为 `User-agent: *`、`Disallow: /`，且版权说明不允许使用数据，因此不请求首页、正文、音频、图片、接口或其他站内资源。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| robots | `https://zhongguoyuyan.cn/robots.txt` | GET | 已读取，返回 `Disallow: /` |
| 首页 | `https://zhongguoyuyan.cn/index` | GET | 只登记 URL，本轮未自动访问 |
| 列表页 | 未知 | 不请求 | robots 全站禁止，不探索列表路径 |
| 详情页模式 | 未知 | 不请求 | 不探索资源或录音详情路径 |

## 请求与分页

- 请求方式: 未验证。受限来源不使用 HTTP 或 Playwright 自动请求站内内容。
- 查询参数: 未验证。
- 分页字段: 未验证。
- 每页数量: 未验证。
- 总数字段: 未验证。
- 筛选字段: 未验证。
- 当前结论: 由于 robots 禁止全站抓取，请求参数和分页契约只能留空，不得用猜测补全。

## 字段定位

### JSON API

未验证。没有请求任何接口，也没有把浏览器开发者工具里的潜在请求当作证据。

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| 未知 | 未获授权验证 | 无 |

### HTML DOM

未验证。没有加载首页或正文 DOM。

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 未知 | 未知 | 需要人工核验或站方授权后确认 |

### 文件附件

未知。没有请求或下载音频、PDF、表格或其他附件。

| 文件名 | URL | 类型 | 大小 | 结构 |
| --- | --- | --- | --- | --- |
| 未知 | 未知 | 预期可能包含音频和文本资源，未验证 | 未知 | 未知 |

## 真实样本

本轮样本数: 0。

原因: `robots.txt` 明确禁止自动访问全站，不能为了凑样本而请求首页、正文或资源。没有从搜索结果、缓存或第三方转载中拼接伪造样本。

### 受限记录

- 详情 URL: 无，未访问站内详情
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 证据: `https://zhongguoyuyan.cn/robots.txt` 返回 `User-agent: *` 与 `Disallow: /`
- 目标映射: 不形成 stage 或 std 记录

## 字段映射

以下映射是候选模型，不是已验证契约。没有站点授权和人工样本前，不创建 `stage` 或 `std` 记录。

### crawler 层

| 预期来源字段 | crawler 表.字段 | 粤乡智匠建议表.字段 | 转换说明 |
| --- | --- | --- | --- |
| 方言点名称、地区 | `std_dialect_points.name`、`province`、`city`、`county` | `dialects.name`、`dialects.region`、`dialects.areas` | 需要人工确认自然键 |
| 经纬度 | `std_dialect_points.longitude`、`latitude` | 建议新增 `dialects.longitude`、`latitude` | 只在授权且可验证时使用 |
| 方言系属 | `std_dialect_points.dialect_group`、`subgroup` | `dialects.features` 或建议新增专列 | 保留站方术语 |
| 词形 | `std_dialect_lexemes.lemma` | `dialect_phrases.dialect` | 需要人工确认词条含义 |
| 普通话释义 | `std_dialect_lexemes.definition` | `dialect_phrases.mandarin` | 不得自动生成 |
| 注音或拼音 | `std_dialect_lexemes.phonetic` | `dialect_phrases.pinyin` | 需要保留原始标音方案 |
| 音频 | `std_dialect_lexemes.audio_url` | 现有表无对应列 | 音频版权和说话人权利未确认前不落地 |
| 页面地址 | `std_dialect_lexeme_sources.source_url` | `dialect_phrases.extra` 或建议新增 `source_url` | 必须是可打开详情 URL |
| 站方资源编号 | `std_dialect_lexeme_sources.source_item_id` | 建议新增外部 ID 字段 | 优先作为自然键的一部分 |

### 粤乡智匠表

- `dialects`: 可承接方言点概述。现有列不足以稳定表达经纬度、系属和声音资源，需要目标库变更设计。
- `dialect_phrases`: 只有在获得词形、释义、注音和来源 URL 后才能映射。音频不能放入文本字段。
- `dialect_quick_questions`: 该站资源不能推断快捷问题，不映射。
- 现有三张方言展示表继续服务前台，不因该受限来源修改结构。

## 数据量与更新

- 当前数量估算: 未知。没有读取资源目录或统计接口。
- 更新频率: 未知。
- 变更检测: 当前不做自动检测。获得明确授权后，先人工复核 robots 和书面许可，再设计基于资源 ID、更新时间和内容哈希的检测。
- 建议采集频率: 不自动采集。每季度人工复核一次 robots、站点说明和授权状态，只有获得站方许可后才评估低频采集。
- 历史数据保留: 当前不保存站点内容。

## 风险与限制

- 登录: 未知，未验证。
- robots: `User-agent: *` 与 `Disallow: /` 明确禁止全站自动抓取。
- 版权: 未验证。方言录音、发音人声音、文本和地图资源可能分别受不同权利约束。
- 结构稳定性: 未知，没有任何 DOM 或 API 证据。
- 缺失字段: 页面结构、资源类型、API、分页、样本、数量、更新频率和详情 URL 模式全部缺失。
- 个人信息: 音频可能包含可识别的发音人声音，不能把公开可听等同于允许批量采集和再发布。
- 采集边界: 不使用代理、缓存页、搜索引擎快照或第三方转载绕过 robots。

## 验证记录

- 验证方式: 只使用 Python `requests` 请求 `https://zhongguoyuyan.cn/robots.txt`。没有打开首页、正文、音频、图片或接口。
- 验证结果: robots HTTP 200，内容为 `User-agent: *` 和 `Disallow: /`。
- 首页状态: 未请求。首页 URL 只来自任务给定入口。
- 未验证项: 首页公开说明、资源类型、页面结构、接口、分页、资源数量、更新频率、登录要求、使用条款和授权方式。
- 下载: 无。

## 人工核验方式

只有项目明确需要且获得合规判断后，才由人工在普通浏览器中核验。核验前先重新读取 robots 并确认是否有站点书面许可。

1. 人工打开 `https://zhongguoyuyan.cn/index` 和 robots，记录访问日期、页面说明和可见资源类型。
2. 只浏览页面公开提供的导航和说明，不批量打开音频、不导出接口、不运行自动翻页。
3. 若发现资源详情，人工记录资源名称、地区、方言系属、词形、释义、标音、音频是否存在和详情 URL。
4. 向站点或主管机构确认文本、音频、地图和下载的使用许可，以及是否允许缓存、转换和公开展示。
5. 将人工样本交给独立审核者复核后，才决定是否把来源从 `robots-restricted` 改为可实施状态。

## 审核要求

- 入口可打开: robots 可打开；首页本轮未访问
- 样本可复现: 否，样本数为 0
- 字段映射完整: 否，只有候选模型
- 详情 URL 可直达: 未知
- 合规结论: `robots-restricted`，禁止自动采集，等待人工核验或站方许可
