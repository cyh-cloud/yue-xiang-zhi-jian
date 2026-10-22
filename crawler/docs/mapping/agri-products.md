# 认证农产品字段映射

状态: draft

日期: 2026-10-19

本文只说明来源字段到 std 实体和业务 `target_field` 的映射。std 字段、自然键和不变式见 `../schema/std-entities.md`，转换规则见 `../schema/conversion-interface.md`。`farming_products` 是农事作物目录，认证农产品仍写建议新增的 `agri_certified_products`、`agri_product_sources`。

## 口径

- 名特优新来源 ID: `aqsc-moa`。已验证附件为 2025 年第三批公示表，不能据此声称覆盖全部批次。
- 特质农品来源 ID: `aqsc-moa`。已验证附件为 2025 年第三批公示表，字段比名特优新少。
- 地理标志来源 ID: `cnipa`。公告列表与 PDF 已验证，产品行需从附件或正文解析。
- 只纳入农业、食品、饮料、酒类、中药材和水产相关产品。纯工艺品和非食品工业品保留排除原因，不进入业务发布。
- 每条业务记录必须能回到公告或检索详情。没有单条详情 URL 时，使用公告页或检索详情页作为承载页 URL，并保留工作表行号、PDF 页码或表格行号 locator。承载页和 locator 都满足时可以进入候选、业务库和发布审核；任一缺失时写 `deferred`。
- 无法确认的字段写 `null`，不根据名称猜证书号、批次、日期、行政区划或授权。

## 字段映射

| 业务字段 `target_field` | 名特优新来源 | 特质农品来源 | 地理标志来源 | std 字段 |
| --- | --- | --- | --- | --- |
| `cert_type` | 固定 `名特优新` | 固定 `特质农品` | 固定 `地理标志` | `std_agri_products.cert_type` |
| `product_name` | XLSX `产品名称` | XLSX `产品全称` | PDF 附件 1 或保护要求 | `std_agri_products.product_name` |
| `product_name_raw` | XLSX `产品名称` 原文 | XLSX `产品全称` 原文 | PDF 原文 | `std_agri_products.product_name_raw` |
| `normalized_name` | 按统一规则归一 | 按统一规则归一 | 按统一规则归一 | `std_agri_products.normalized_name` |
| `province` | XLSX `省份` | XLSX `省份` | PDF `省份` 或保护范围 | `std_agri_products.province` |
| `city` | XLSX 未提供，待验证 | XLSX 未提供，待验证 | 从产地范围文本提取 | `std_agri_products.city` |
| `county` | XLSX `县域` | XLSX `县域` | 从产地范围文本提取 | `std_agri_products.county` |
| `region` | 县级或来源地区展示值 | 县级或来源地区展示值 | 产地范围稳定摘要或检索地区 | `std_agri_products.region` |
| `origin_scope` | 附件无，待验证 | 附件无，待验证 | PDF `产地范围` | `std_agri_products.origin_scope` |
| `applicant` | XLSX `获证单位` | XLSX `申请单位全称` | PDF 附件 1 的申请主体 | `std_agri_products.applicant` |
| `protection_unit` | 未提供，待验证 | 未提供，待验证 | PDF 保护单位 | `std_agri_products.protection_unit` |
| `certificate_no` | XLSX `证书编号` | 未提供 | 公告明确给出的编号 | `std_agri_products.certificate_no` |
| `certified_at` | 待验证 | 待验证 | PDF 落款日期 | `std_agri_products.certified_at` |
| `category` | 按产品名和正文判定 | 按产品名和正文判定 | PDF 质量要求或保护范围判定 | `std_agri_products.category` |
| `is_aquatic` | 三态判定 | 三态判定 | 三态判定 | `std_agri_products.is_aquatic` |
| `source_url` | 公告详情页 | 公告详情页 | 公告页或检索详情页 | `std_agri_products.source_url` |
| `announcement_no` | 公告标题或文号 | 公告标题或文号 | 公告标题或 PDF 首页 | `std_agri_product_sources.announcement_no` |
| `published_at` | 公告页日期 | 公告页日期 | 栏目发布日期 | `std_agri_product_sources.published_at` |
| `certified_at` | 待验证 | 待验证 | PDF 落款日期 | `std_agri_product_sources.certified_at` |
| `source_product_name` | XLSX `产品名称` | XLSX `产品全称` | PDF 产品名称 | `std_agri_product_sources.source_product_name` |
| `source_region` | XLSX `省份`、`县域` | XLSX `省份`、`县域` | PDF 产地范围 | `std_agri_product_sources.source_region` |
| `source_title` | 公告标题 | 公告标题 | 公告标题 | `std_agri_product_sources.source_title` |
| `retrieved_at` | 采集响应时间 | 采集响应时间 | 采集响应时间 | `std_agri_product_sources.retrieved_at` |
| `content_hash` | 行内容哈希 | 行内容哈希 | PDF 产品段哈希 | `std_agri_product_sources.content_hash` |

附件 URL、工作表名、行号、页码、附件 SHA-256 和联系人只作为来源证据写入 `std_agri_product_sources.extra` 或 stage，不扩成业务主表字段。业务侧字段以 `yuexiang-target-db.md` 的 `agri_certified_products`、`agri_product_sources` 为准。

## 来源内字段

### 名特优新

已验证附件 `crawler/download/www.aqsc.agri.cn/2025年第三批名特优新公示表.xlsx` 的表头:

`序号`、`省份`、`县域`、`证书编号`、`产品名称`、`获证单位`、`联系人`、`生产规模（公顷、万头、万只、万羽等）`、`主要生产经营单位`。

`证书编号` 只落 `std_agri_products.certificate_no` 和 `agri_certified_products.certificate_no`，不能当公告号。`序号` 只作附件行定位。

### 特质农品

已验证附件 `crawler/download/www.aqsc.agri.cn/2025年第三批特质农品公示表.xlsx` 的表头:

`序号`、`省份`、`县域`、`产品全称`、`申请单位全称`、`联系人`、`生产规模（公顷、万头、万只、万羽等）`。

该附件没有证书编号、主要生产经营单位和地市。未知字段写 `null`，不从名特优新表借用。

### 地理标志

PDF 新公告的产品表常见列为 `序号`、`产品名称`、`省份`、`申请人`、`产地范围`、`备注`。旧公告按产品段落切分。公告号、栏目发布日期和 PDF 落款日期分别保存。

`aqsc-moa` 来源和审核文件均已存在。动态查询可返回产品行，但没有单条详情 URL，因此使用公告详情、XLSX 附件所属公告或可长期打开的检索详情作为承载页 URL，并把工作表名和行号写入 locator。满足权利和审核条件时可以发布。承载页或 locator 不满足条件时写 `deferred`。

## 自然键与发布

- `std_agri_products` 物理自然键固定为 `source_id + source_item_id`。转换器合并键为 `cert_type + normalized_name + province + region`，跨来源差异由 `std_agri_product_sources` 保留。
- `normalized_name` 去首尾空白、合并连续空白、统一全半角括号和连字符、使用大小写不敏感比较值。
- `region` 为空时用 `origin_scope` 的稳定摘要；两者都为空时进入冲突或人工复核。
- 名特优新、特质农品、地理标志只按各自 `cert_type` 升级写入，不跨类型合并。
- 纯工艺品、非食品工业品和明确排除的产品不进入 std 或业务发布。无 direct 详情 URL 的产品使用承载页 URL 和 locator 回溯；缺失时写 `deferred`。
- 同一产品多次公告保留多条来源关系。

## 水产三态与误报复核

- `is_aquatic=1`: 有官方品类、产品名或申请主体证据，并经规则或人工确认。
- `is_aquatic=0`: 有证据表明不是水产。
- `is_aquatic=NULL`: 证据不足或存在误报风险。

关键词只能触发复核，不能单独决定 `is_aquatic=1`。以下词形已确认存在误报风险: `鲅鱼圈鸡蛋`、`安溪毛蟹`、`仪征紫菜薹`、`贝贝南瓜`、`贝母`、`丹参`、`鱼腥草`、`螺丝椒`。判定证据和复核结论写入 `std_agri_products.extra`，至少保留 `aquatic_evidence`、复核人和复核时间。

## 落层

| 内容 | crawler 层 | 粤乡智匠 |
| --- | --- | --- |
| 原始公告 HTML、XLSX、PDF | raw | 不进入业务库 |
| 单个 XLSX 行或 PDF 产品段 | stage，一来源一表 | 不直接进入业务库 |
| 标准产品或来源关系 | std | 转换器按 `run_batch('agri', batch)` 写入 |
| 无详情 URL 但承载页和 locator 完整的动态查询行 | std，`detail_url_status=missing` | 满足权利和审核条件时发布 |

## 已知缺口

- 名特优新与特质农品的公告号、发布日期无法从已下载的 XLSX 本身确认。
- 两份附件只覆盖 2025 年第三批，不能据此给出历史总量。
- 附件没有地市、品类和水产标记，需规则判定和人工复核。
- 地理标志 PDF 的表格列可能错位，扫描件可能没有文字层。

## 待验证

- 名特优新证书编号是否在全国范围内永久唯一。
- 地理标志是否所有公告都能给出县级行政区划。
- `license_or_usage` 是否允许业务库展示产品名称以外的图片、证书或正文。
