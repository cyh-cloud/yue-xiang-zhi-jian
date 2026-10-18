# 认证农产品字段映射

状态: draft

日期: 2026-10-19

本文覆盖全国名特优新、全国特质农品和地理标志产品。三类认证共用一套建议标准实体，`cert_type` 必须分开保存。当前业务库 `farming_products` 是农事作物目录，不是认证农产品目录，本文中的 `agri_certified_products`、`agri_product_sources` 仍为建议新增表，二者不得混写。

## 口径

- 名特优新来源 ID: `aqsc-moa`。已验证附件为 2025 年第三批公示表，不能据此声称覆盖全部批次。
- 特质农品来源 ID: `aqsc-moa`。已验证附件为 2025 年第三批公示表，字段比名特优新少。
- 地理标志来源 ID: `cnipa`。公告列表与 PDF 已验证，产品行需从附件或正文解析。
- 只纳入农业、食品、饮料、酒类、中药材和水产相关产品。纯工艺品和非食品工业品保留排除原因，不进入建议主表。
- 每条记录必须能回到公告、检索详情或附件。只给栏目首页不算详情 URL。
- 无法确认的字段写 `null` 或“待验证”，不根据名称猜证书号、批次、日期、行政区划或授权。

## 字段映射

表中 `std_agri_product` 表示跨来源标准实体，`std_agri_product_source` 表示产品与官方来源的关联。业务库列名是建议契约，不代表当前已有列。

| 业务字段 | 名特优新来源 | 特质农品来源 | 地理标志来源 | crawler 表.字段 | 建议业务表.字段 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| 公告号 | 公告标题，待验证 | 公告标题，待验证 | 公告标题或 PDF 首页，如 `第687号` | `std_agri_product_source.announcement_no` | `agri_product_sources.announcement_no` | 公告发布批次与产品证书号分开 |
| 批次 | 公告标题或附件标题 `2025年第三批` | 公告标题或附件标题 `2025年第三批` | 通常无“批次”，按公告号区分 | `std_agri_product_source.batch_label` | `agri_product_sources.batch_label` | 保存来源原文，不强行编成数字 |
| 发布日期 | 公告页日期，待验证 | 公告页日期，待验证 | 栏目发布日期，如 `2026-08-12` | `std_agri_product_source.published_at` | `agri_product_sources.published_at` | 栏目日期不等于认定日期 |
| 认证类型 | 固定 `名特优新` | 固定 `特质农品` | 固定 `地理标志` | `std_agri_product.cert_type` | `agri_certified_products.cert_type` | 三类不能合并 |
| 产品名称 | XLSX `产品名称` | XLSX `产品全称` | PDF 附件 1 或保护要求 | `std_agri_product.product_name` | `agri_certified_products.product_name` | 去换行和多余空白，不改写商品名 |
| 别名 | 未提供，待验证 | 未提供，待验证 | 正文中的“又名”或历史名称，待验证 | `std_agri_product.alias` | `agri_certified_products.alias` | 没有明确证据时写 null |
| 省份 | XLSX `省份` | XLSX `省份` | PDF `省份` 或保护范围 | `std_agri_product.province` | `agri_certified_products.province` | 保留来源写法 |
| 地市 | XLSX 未提供，待验证 | XLSX 未提供，待验证 | 从产地范围文本提取 | `std_agri_product.city` | `agri_certified_products.city` | 无法确定时 null，原文留 `region_raw` |
| 县域 | XLSX `县域` | XLSX `县域` | 从产地范围文本提取 | `std_agri_product.county` | `agri_certified_products.county` | 名特优新和特质农品直接映射 |
| 申请单位 | XLSX `获证单位` | XLSX `申请单位全称` | PDF 附件 1 的申请主体 | `std_agri_product.applicant` | `agri_certified_products.applicant` | 不把联系人填进申请单位 |
| 联系人 | XLSX `联系人` | XLSX `联系人` | PDF 通常不提供 | `std_agri_product_source.contact_name` | `agri_product_sources.contact_name` | 公开联系人字段，默认不对外展示 |
| 生产规模 | XLSX `生产规模（...）` | XLSX `生产规模（...）` | PDF 保护要求中的产量或规模，待验证 | `std_agri_product.production_scale` | `agri_certified_products.production_scale` | 保留原文和单位，不换算 |
| 主要生产经营单位 | XLSX `主要生产经营单位`，换行分隔 | 未提供，待验证 | PDF 可能列生产者，待验证 | `std_agri_product.main_operators` | `agri_certified_products.main_operators` | 建议存 JSON 数组文本 |
| 品类 | 附件没有，按产品名和正文判定 | 附件没有，按产品名和正文判定 | PDF 质量要求或保护范围判定 | `std_agri_product.category` | `agri_certified_products.category` | 无法判定写 `unknown`，不猜 |
| 水产标记 | 由品类或正文证据推导 | 由品类或正文证据推导 | 由品类或正文证据推导 | `std_agri_product.is_aquatic` | `agri_certified_products.is_aquatic` | 0/1；证据不足时 null |
| 详情 URL | 公告详情页，待验证 | 公告详情页，待验证 | 国家知识产权局文章页或检索详情页 | `std_agri_product_source.detail_url` | `agri_product_sources.detail_url` | 必须直接打开单条公告 |
| 来源 URL | 公告列表页或公告页，待验证 | 公告列表页或公告页，待验证 | 公告栏目 URL、检索页 URL | `std_agri_product_source.source_url` | `agri_product_sources.source_url` | 保存发现记录的页面 |
| 附件 URL | 两份 XLSX 的 `P020...xlsx` 地址 | 两份 XLSX 的 `P020...xlsx` 地址 | PDF 长期下载页，不保存临时签名 URL | `std_agri_product_source.attachment_url` | `agri_product_sources.attachment_url` | 附件地址和详情 URL 分开 |
| retrieved_at | 采集响应时间 | 采集响应时间 | 采集响应时间 | `std_agri_product_source.retrieved_at` | `agri_product_sources.retrieved_at` | ISO 8601，含时区 |
| license_or_usage | 政府公开信息，具体许可待验证 | 同左 | 政府公开信息，未发现开放许可 | `std_agri_product_source.license_or_usage` | `agri_product_sources.license_or_usage` | 保存事实和待核状态 |
| confidence | 附件行直接可读为 `high` | 附件行直接可读为 `high` | PDF 可解析时 `high`，需 OCR 时 `medium` | `std_agri_product_source.confidence` | `agri_product_sources.confidence` | 不用一个来源级值覆盖全部行 |
| target_table | 见下节 | 见下节 | 见下节 | `std_agri_product` | `agri_certified_products` | 目标表名是建议 |
| target_field | 见上表 | 见上表 | 见上表 | 同名 snake_case | 同名 snake_case | 转换器按映射写入 |

## 来源内字段

### 名特优新

已验证附件 `crawler/download/www.aqsc.agri.cn/2025年第三批名特优新公示表.xlsx` 的表头:

`序号`、`省份`、`县域`、`证书编号`、`产品名称`、`获证单位`、`联系人`、`生产规模（公顷、万头、万只、万羽等）`、`主要生产经营单位`。

`证书编号` 只落 `std_agri_product.certificate_no` 和 `agri_certified_products.certificate_no`，不能当公告号。`序号` 只作附件行定位。

### 特质农品

已验证附件 `crawler/download/www.aqsc.agri.cn/2025年第三批特质农品公示表.xlsx` 的表头:

`序号`、`省份`、`县域`、`产品全称`、`申请单位全称`、`联系人`、`生产规模（公顷、万头、万只、万羽等）`。

该附件没有证书编号、主要生产经营单位和地市。未知字段写 null，不从名特优新表借用。

### 地理标志

PDF 新公告的产品表常见列为 `序号`、`产品名称`、`省份`、`申请人`、`产地范围`、`备注`。旧公告按产品段落切分。`公告号`、栏目发布日期和 PDF 落款日期分别保存，`certified_at` 使用落款日期。

## 落层

| 内容 | crawler 层 | 粤乡智匠 |
| --- | --- | --- |
| 原始公告 HTML、XLSX、PDF | raw | 不进入业务库 |
| 单个 XLSX 行或 PDF 产品段 | stage，一来源一表 | 不直接进入业务库 |
| 统一认证类型、产品名、行政区划、申请人 | std | `agri_certified_products` 建议新增 |
| 公告号、批次、日期、详情 URL、附件 URL、许可、置信度 | std | `agri_product_sources` 建议新增 |
| 排除产品的名称和原因 | stage 或 std 排除记录 | 不自建主表，保留审核依据 |

## 自然键与转换

- 建议自然键: `cert_type + product_name + province + county`。
- `county` 缺失时用 `region_raw` 的规范化值，仍不唯一则进入冲突队列。
- 同一产品多次公告时保留来源历史，当前有效版本由审核状态决定。
- 名特优新、特质农品、地理标志永不互相 upsert。
- XLSX 行必须保留附件 URL、工作表名和行号，PDF 产品必须保留页码。
- `retrieved_at` 和附件 SHA-256 只作追溯，不覆盖业务字段。

## 已知缺口

- `crawler/docs/sources/aqsc-moa.md` 当前不存在，公告列表页、公告详情 URL 模式、robots 和转载许可待补。
- 名特优新与特质农品的公告号、发布日期无法从已下载的 XLSX 本身确认。
- 两份附件只覆盖 2025 年第三批，不能据此给出历史总量。
- 附件没有地市、品类和水产标记，需规则判定和人工复核。
- 地理标志 PDF 的表格列可能错位，扫描件可能没有文字层。

## 待验证

- `aqsc-moa` 官方公告列表、公告详情和附件下载的稳定 URL。
- 名特优新证书编号是否在全国范围内永久唯一。
- 地理标志是否所有公告都能给出县级行政区划。
- `license_or_usage` 是否允许业务库展示产品名称以外的图片、证书或正文。
