# 转换器契约

状态: 设计冻结

日期: 2026-10-19

`converter` 是批次转换 module，外部只有一个入口 `run_batch(domain, batch)`，内部统一处理自然键、来源优先、人工字段保护、冲突、发布、回滚和统计。完整 interface 见 `conversion-interface.md`。std 实体 interface 见 `std-entities.md`。

## 职责边界

- 输入是 `std-entities.md` 定义的 std 实体和 `std_sources` 来源登记，不读 `raw_*`、`stage_*`、页面或附件。
- 输出按内容域写入业务表，并写采集库的 `import_batches`、`import_conflicts`。
- 天气不进入持久化转换，运行时 DTO 直接在请求或提示组装阶段使用。
- 发布状态由人工审核流程推进。转换器只写 `draft` 或保持已有状态。

## 批次契约

`run_batch(domain, batch)` 的 `domain` 取 `ich`、`agri`、`jobs`、`dialects`。`batch` 提供本次输入范围、转换器版本、目标库标识和幂等键。一次调用只处理一个内容域，不跨域提交事务。

每次调用必须:

1. 创建 `import_batches`，状态先为 `running`。
2. 逐实体计算自然键并选择主值。
3. 按字段白名单升级写入业务表，保留来源关系和本批次对象映射。
4. 记录 `input_count`、`inserted_count`、`updated_count`、`skipped_count`、`conflict_count`、`failed_count`。
5. 以 `succeeded`、`partial` 或 `failed` 结束。存在冲突或单条失败时不得写 `succeeded`。

同一批次重复运行必须得到相同结果。可用 `batch.batch_key + content_hash` 跳过已处理实体。

## 决策实现

### 自然键

自然键只在 `std-entities.md` 定义。转换器按内容域取实体自然键，缺失键组成字段时按实体 interface 的回退规则处理。规范化只做可复现的文本归一，不删除有意义的行政区划、批次、保护单位或来源限定词。

### 来源优先

按 `std_sources` 的来源优先级排序，同优先级比较 `confidence`，仍相同则比较 `retrieved_at`。无法裁决时写 `import_conflicts`，不静默选一边。低优先级来源仍保留为来源关系。

### 人工字段保护

业务库维护字段级人工修订记录或统一锁表。转换器读取锁定字段并跳过自动写入。人工字段与导入值不同时写冲突，计入 `skipped_count`。保护针对字段，不把整行设为只读。

### 冲突

字段类型或枚举无法解析、关键字段矛盾、人工字段与导入值不同、来源失效但业务行仍被引用时写 `import_conflicts`。每条冲突保存两侧值、来源 URL、取得时间、批次和原因，初始 `resolution=unresolved`。

### 发布

转换器写入 `draft`。发布前检查来源访问等级、许可、详情 URL、审核记录和内容域不变式。转换器不推断授权，不自动把 `draft` 升级为 `published`。

### 回滚

回滚以批次为单位。只撤销该批次插入且未被人工修改的行；更新过的行有批次前快照时恢复，没有快照时不得盲删。回滚保留 `import_conflicts`、raw、stage、std 证据。

## 内容域策略

### `ich`

`std_ich_projectss` 转 `crafts` 基础资料，先写 `draft` 和 `is_teachable=0`。传承人、相关项目和媒体只写来源关系或扩展字段，不伪造教学步骤。`is_teachable=1` 由运营补齐教学证据后设置。

### `agri`

`std_agri_products` 转 `agri_certified_products`，来源转 `agri_product_sources`。三种 `cert_type` 分开升级写入，不互相合并。水产三态的 `unknown` 不降为 `false`。无详情 URL 的记录只留在 std 或排除记录中，不进入业务发布。

### `jobs`

`std_jobs` 转 `recruitment_postings`，来源转 `recruitment_posting_sources`。过期岗位标 `expired`，不物理删除。只写公开岗位，不写 `job_listings` 和 `recruitments`。

### `dialects`

`std_dialect_pointss`、`std_dialect_lexemes`、`std_dialect_lexeme_sources` 按自然键升级写入同名业务表。现有 `dialects`、`dialect_phrases`、`dialect_quick_questions` 不变；发布到展示表由独立映射决定。

### `weather`

天气 DTO 不经过 `run_batch`。实时请求生成 DTO，返回前校验 `city_code`、`observed_at`、`fetched_at` 和 `source_url`。不写业务库，不建立 std 表，不进批次回滚。

## 验收

1. 同一 std 实体重复运行不产生重复业务行。
2. 官方来源与聚合站冲突时官方值成为主值，聚合来源关系保留。
3. 人工修改字段后重跑导入，字段不变且写冲突。
4. 产品 `origin_scope` 摘要参与自然键，不误合并两个地区产品。
5. 过期招聘重跑只改状态，不写 `job_listings`。
6. 方言同名词形在不同方言点不合并。
7. 批次回滚只撤销未人工修改的结果。
8. 天气请求不产生批次和业务行。

本文件只定义契约和实现策略，SQL、迁移、接口和测试留给后续票据。
