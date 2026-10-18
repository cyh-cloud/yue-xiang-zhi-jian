# 转换器契约

状态：设计冻结

日期：2026-10-19

## 目标

转换器负责把采集库 `std` 层的标准实体写入粤乡智匠业务库。它不抓页面、不读取 `raw` 或 `stage`、不解析 XLSX/PDF、不修改采集库的来源事实。转换器的输出必须可重复、可审计、可撤销，并且不能覆盖运营手工修改过的字段。

本次只定义契约，不实现转换器。实现时所有写入使用参数化 SQL，不拼接用户输入或来源文本。

## 输入与输出

### 输入

只读以下内容：

- `std_ich_projects`、`std_ich_inheritors`、`std_ich_related_items`、`std_ich_media_links`
- `std_agri_products`、`std_agri_product_sources`、`std_agri_product_aliases`
- `std_jobs`、`std_job_sources`、`std_job_locations`
- `std_dialect_points`、`std_dialect_lexemes`、`std_dialect_lexeme_sources`
- `std_sources` 中与本次内容域有关的来源登记

不得读取 `raw_*`、`stage_*`，不得从页面重新抽取字段，也不得把 `sources.json` 当作运行时数据源；`std_sources` 是转换期来源元数据。

### 输出

- 业务库的 `agri_certified_products`、`agri_product_sources`
- `crafts` 的新增列及相关审计信息
- `recruitment_postings`、`recruitment_posting_sources`
- `dialect_points`、`dialect_lexemes`、`dialect_lexeme_sources`
- 采集库的 `import_batches`、`import_conflicts`

不输出天气表。天气只作为运行时 DTO 或短期缓存，不经过持久化转换。

## 核心契约

### 1. 自然键

转换器按以下自然键识别同一实体。自然键使用规范化后的值计算，原始值仍保留在 `*_raw` 字段。

| 实体 | 自然键 | 说明 |
| --- | --- | --- |
| 非遗项目 | `ich_code + province + city + county + name` | 同一项目名在不同申报地区或批次下保留多条 |
| 传承人 | `source_id + source_item_id + project_id` | 同一人可关联多个项目 |
| 认证农产品 | `cert_type + normalized_name + province + region` | 缺少 `region` 时使用 `origin_scope` 的稳定摘要 |
| 认证产品来源 | `product_id + source_id + source_url` | 同一产品可有多个公告 |
| 招聘岗位 | `source_id + source_item_id` | 缺失时退回 `source_id + source_url` |
| 招聘来源 | `posting_id + source_id + source_url` | |
| 方言点 | `source_id + source_item_id` | 缺失时退回 `region_raw + dialect_name` |
| 方言词条 | `dialect_point_id + lemma` | 不按词条文本跨方言点去重 |
| 词条来源 | `lexeme_id + source_id + source_item_id + source_url` | |

规范化只做可复现的文本处理：去首尾空白、合并连续空白、统一全半角括号和连字符样式、统一大小写不敏感的比较值。不得删除有意义的行政区划、批次、保护单位或来源限定词。

### 2. 官方优先

多个来源候选同一实体时，按以下顺序选择主值：

1. 政府或官方机构原始公告。
2. 官方名录查询系统和原始附件。
3. 学术机构或非遗官方机构。
4. 行业招聘站。
5. 商业聚合站。
6. UGC 或无法核验来源。

同等优先级按以下顺序裁决：

1. `confidence` 更高者。
2. `retrieved_at` 更新且仍有有效来源证据者。
3. 内容哈希不同且无法裁决时写冲突，不静默选一边。

官方优先只决定主值来源，不删除其他来源关系。较低优先级来源仍可补充别名、媒体或地点。

### 3. 升级写入

“升级写入”指按自然键存在则更新、不存在则插入。具体规则：

- 先按自然键查目标行。
- 不存在：插入新行，`import_batch_id` 记录本次批次。
- 存在且本批次来源优先级更高：更新允许自动更新的字段。
- 存在且来源优先级相同：逐字段比较，相同则跳过，不同则按冲突规则处理。
- 存在且本批次来源优先级更低：只补充空字段和来源关系，不覆盖已有主值。

更新必须限定列白名单。不得用 `SELECT *` 的结果直接拼回 `UPDATE`，也不得更新 `id`、人工字段、审核状态和已有发布状态。

### 4. 人工字段保护

运营手工修改过的字段不自动覆盖。保护的判断依据由业务库维护，建议使用字段级修订记录或统一的 `manual_field_locks` 辅助表；若暂不建表，至少要在转换前读取并跳过已标记人工保护的字段。

受保护字段包括但不限于：

- `crafts.name`、`crafts.origin`、`crafts.history`、`crafts.level`
- `crafts.is_teachable`
- 招聘展示摘要和联系方式展示开关
- 方言释义、音标、音频状态的人工修正
- 审核状态、发布状态和下架状态

保护不是“整行只读”。未受保护的空白字段仍可由更高优先级来源补充；受保护字段产生差异时写 `import_conflicts`，并在批次摘要中计入 `skipped_count`。

### 5. 冲突记录

以下情况写 `import_conflicts`：

- 同一自然键出现不同主值，且官方优先或时间规则无法裁决。
- 字段类型或枚举无法解析。
- 行政区划、项目编号、认证类型、截止日期等关键字段互相矛盾。
- 来源已失效，但业务行仍被引用。
- 人工保护字段与导入值不同。

每条冲突必须保存：

- `batch_id`
- `content_domain`
- `target_table`
- `target_key`
- `target_field`
- `existing_value`、`incoming_value`
- 两侧 `source_id`、`source_url`
- 两侧 `retrieved_at`
- `reason`
- 初始 `resolution=unresolved`

转换器不自动解决 `unresolved` 冲突。运营复核后写 `resolution`、`resolved_by`、`resolved_at` 和说明。

### 6. 导入批次

每次转换运行创建一条 `import_batches`：

- `batch_key` 唯一，建议包含时间、内容域和随机短后缀。
- 开始时写 `status=running`。
- 结束时写 `finished_at` 和最终状态。
- 统计 `input_count`、`inserted_count`、`updated_count`、`skipped_count`、`conflict_count`、`failed_count`。
- 保存 `converter_version` 和目标库标识。

一个批次只处理一个内容域或一个明确的任务集合，避免一次运行跨越太多目标表。部分成功时 `status=partial`，不能用 `succeeded` 掩盖冲突或失败。

### 7. 发布状态

转换器默认写入 `draft`，不直接把新抓取内容标记为 `published`。发布需要满足：

- 来源 `access_level` 允许发布对应字段。
- 来源 `license_or_usage` 未禁止该使用方式。
- 业务侧已有人工审核记录。
- 非遗项目有可直接打开的详情 URL；教学步骤为空时 `is_teachable=0`。
- 招聘岗位有详情 URL，且未超过截止日期或已明确标记过期。
- 方言词条有来源 URL；音频不可用时 `audio_status` 不是 `available`。

发布状态变更由业务侧审核流程完成，不由转换器自动升级。转换器只写 `draft` 或保持已有状态。

### 8. 回滚

回滚以批次为单位：

1. 读取 `import_batches` 和本批次的对象映射。
2. 对每个对象检查是否被人工修改或已有后续批次覆盖。
3. 只撤销本批次插入且未被人工修改的行。
4. 本批次更新过的行恢复到批次前快照；没有快照时不得盲删。
5. 恢复失败或涉及人工字段时写冲突，不强行覆盖。
6. 批次标记 `rolled_back`，保留审计记录。

回滚不删除 `import_conflicts`，也不删除 `raw`、`stage`、`std` 证据。业务库删除顺序遵循目标库文档的外键关系。

## 追踪字段在转换链中的位置

| 字段 | 产生位置 | 在转换链中的作用 | 是否写入业务库 |
| --- | --- | --- | --- |
| `retrieved_at` | `raw_fetches` 写入时 | 判断内容版本、时效和冲突新旧；不得用导入时间替代 | 写入 `imported_at` 或来源时间字段，保留在来源关系表 |
| `license_or_usage` | 来源文档和 `std_sources` | 发布前检查是否允许该使用方式；不得由转换器推断授权 | 写入来源关系或产品/岗位发布审计字段 |
| `confidence` | 来源文档和 std 实体 | 官方优先后的次级裁决；低于阈值时进入人工复核 | 写入实体或来源关系 |
| `target_table` | 转换器映射配置 | 指明冲突和批次对象最终落到哪张表 | 写入冲突表和批次摘要，不写入实体内容 |
| `target_field` | 转换器字段映射 | 指明冲突发生在哪个字段，支持字段级保护和回滚 | 写入冲突表，不写入实体内容 |

`retrieved_at`、`license_or_usage`、`confidence` 是决策输入；`target_table`、`target_field` 是审计定位信息。转换器不得把 `confidence` 解释为授权，也不得把 `license_or_usage` 解释为质量评分。

## 各内容域转换伪流程

### 非遗

```text
读取 std_ich_projects 及关联传承人、相关项目、媒体
  -> 检查 source_id 可发布、URL 可打开
  -> 计算业务自然键
  -> 查 crafts
  -> 不存在：插入基础资料，is_teachable=0，publish_status=draft
  -> 存在：按字段白名单补充官方字段，保护人工字段
  -> 继承人或关联项按业务键 upsert
  -> 无教学证据时不创建步骤、视频、采购指南
  -> 冲突写 import_conflicts
  -> 更新批次统计
```

非遗项目的基础资料可以全量入库，但不能为了页面完整性伪造步骤。`is_teachable=1` 由运营在有教学步骤、视频或采购指南后设置。

### 认证农产品

```text
读取 std_agri_products 和 std_agri_product_sources
  -> 按 cert_type 分开处理，不混同名特优新、特质农品、地理标志
  -> 规范化产品名和地区
  -> 按自然键查 agri_certified_products
  -> 官方来源优先，补充 province/city/county/region/category
  -> 插入或更新主表，来源关系写入 agri_product_sources
  -> 水产设置 is_aquatic=1
  -> 排除项记录 exclusion_reason，不进入发布
  -> 冲突写 import_conflicts
```

地理标志的 PDF 签名 URL 只留在 raw 层。业务来源 URL 使用可长期打开的检索详情或公告页。

### 招聘

```text
读取 std_jobs、std_job_sources、std_job_locations
  -> 过滤非农业和乡村相关岗位
  -> 按 source_id + source_item_id 查 recruitment_postings
  -> 插入或更新岗位，保留原文和摘要
  -> 写入 recruitment_posting_sources
  -> 公开联系方式默认空或不展示，不能从登录后页面补
  -> 过期岗位标记 expired，不物理删除
  -> 不写 job_listings，不创建站内投递关系
  -> 冲突写 import_conflicts
```

招聘转换器只处理公开岗位。简历、求职者、账号、登录后联系方式和个人数据一律跳过。

### 方言

```text
读取 std_dialect_points、std_dialect_lexemes、std_dialect_lexeme_sources
  -> 先 upsert dialect_points
  -> 再 upsert dialect_lexemes
  -> 写入 dialect_lexeme_sources
  -> 音频只在确认真实可访问时写 audio_url
  -> 保留来源拼音/音标原文，不擅自转换成统一音标
  -> 冲突写 import_conflicts
```

现有 `dialects`、`dialect_phrases`、`dialect_quick_questions` 不改写。需要向前台展示时，由后续明确的发布映射把审核后的词条转为展示短语。

### 天气

```text
读取 std_weather_candidate 或运行时响应
  -> 校验 city_code、observed_at、fetched_at
  -> 生成短生命周期 DTO
  -> 不写业务库
  -> 不建立历史天气表
```

天气不进入批次回滚，因为不持久化。运行时 DTO 必须显示取得时间和来源 URL。

## 事务与幂等

- 单条实体及其来源关系尽量在同一事务中处理。
- 批次统计可以在批次结束后单独提交，但失败时必须保留 `partial` 或 `failed`。
- 重复运行同一批 std 行必须得到相同自然键和相同业务结果。
- 同一内容哈希重复导入应跳过写入，只更新 `last_seen_at`。
- 任何写入异常都不得把该实体标记为成功。

## 最小验收用例

1. 同一 std 非遗项目运行两次，`crafts` 不产生重复行。
2. 官方来源与聚合站字段冲突时，官方值成为主值，聚合来源仍保留在来源表。
3. 人工修改 `crafts.name` 后重跑导入，名称不变且冲突表出现记录。
4. 产品缺少 `region` 时，去重键使用 `origin_scope` 摘要，不把两个地区产品合并。
5. 过期招聘岗位重跑后标记 `expired`，`job_listings` 不新增记录。
6. 方言词条在不同方言点存在同名词形时不合并。
7. 回滚一个批次只撤销该批次未人工修改的结果。
8. 所有冲突都能通过 `source_url` 和 `retrieved_at` 回溯到来源。

## 本次不改代码

本文件只定义转换器契约。实现所需的数据库迁移、领域模块、后台审核接口、测试和发布开关均留给后续票据。
