# 批次转换 Module Interface

状态: 设计冻结

日期: 2026-10-19

本文件定义 `converter` 的外部 interface。调用方只依赖 `run_batch(domain, batch)`，不直接调用自然键、去重、来源优先、冲突、发布或回滚内部步骤。本地测试可通过可选关键字 `crawler_database_path` 指定采集库，生产调用使用 `CRAWLER_DB` 或默认路径。

## 外部 Interface

```text
run_batch(domain, batch) -> BatchResult
```

### 输入

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `domain` | enum | 是 | `ich`、`agri`、`jobs`、`dialects` |
| `batch.batch_key` | string | 是 | 幂等键，建议包含时间、内容域和随机短后缀 |
| `batch.source_ids` | string[] | 否 | 限定来源，空数组表示该内容域全部启用来源 |
| `batch.std_entity_ids` | integer[] | 否 | 限定 std 实体，空数组表示按内容域读取全部候选 |
| `batch.converter_version` | string | 是 | 转换器版本 |
| `batch.target_database` | string | 是 | 目标库标识，当前为 `yuexiang` |
| `batch.dry_run` | boolean | 否 | 默认 `true`。`false` 时写入已启用的业务域；批次和冲突仍落采集库供审计 |

### 输出

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `batch_id` | integer | `import_batches.id` |
| `status` | enum | `succeeded`、`partial`、`failed` |
| `input_count` | integer | 读取的 std 行数 |
| `inserted_count` | integer | 新建业务行数 |
| `updated_count` | integer | 更新业务行数 |
| `skipped_count` | integer | 因人工保护、内容未变或发布规则跳过 |
| `conflict_count` | integer | 写入的冲突数 |
| `failed_count` | integer | 单条或事务失败数 |
| `by_entity` | object | 每个实体类型的统计 |
| `failures` | object[] | 不含敏感内容的失败摘要 |

## 内部统一步骤

调用 `run_batch` 后，module 固定按以下顺序执行:

1. 校验 `domain` 和 `batch`，加载 `sources.json` 注册表和 `std_sources` 优先级。
2. 读取该内容域 std 实体，按实体自然键分组。
3. 选择主值来源，计算字段计划。
4. 按注册表的 enabled、status、access、rights 和发布门禁筛选行。
5. 生成字段计划、冲突、统计和批次状态。
6. 写 `import_batches`、`import_conflicts` 和 `import_batch_items`。
7. dry-run 只提交采集库审计；真实写入把采集库审计与业务库写入放在同一事务提交。

调用方不传自然键、字段优先级、SQL、表名或回滚命令。module 内部按 `std-entities.md` 和 `converter.md` 执行。当前真实写入只启用 `jobs`，目标表为现有 `recruitments` 和 `recruitment_sources`；其他内容域仍只支持 dry-run。

## 不变量

- 一次调用只处理一个内容域。
- 同一 `batch.batch_key` 重复调用不重复写入。
- 天气不是合法 `domain`。
- `dry_run=true` 不写业务表，但写 `import_batches`、`import_conflicts` 和计划对象映射，供审计和回滚。
- `dry_run=false` 只接受 `jobs`。业务库路径必须显式给出，或由 `YUEXIANG_DB` 指定。
- 真实写入只消费 `std_jobs.candidate_status=candidate`；`deferred` 和 `blocked` 计入 `skipped_count`。
- 同一自然键跨批次 upsert，同一 `batch_key` 直接返回既有批次结果。
- 人工字段通过业务行 `extra.manual_fields` 声明，导入值冲突时写 `import_conflicts` 并保留人工值。
- `partial` 和 `failed` 不得伪装成 `succeeded`。
- 人工保护字段永不自动覆盖。
- 返回统计之和与 `input_count` 对账一致，无法归类的输入计为 `failed`。

## CLI

从仓库根执行。默认仍是 dry-run，真实写入必须显式传 `--write`：

```powershell
python -m crawler.pipeline.cli `
  --crawler-db E:\path\to\crawler.db `
  --business-db E:\path\to\yuexiang-copy.db `
  --domain jobs `
  --batch-key jobs-nongmuhr-20261022-01
```

```powershell
python -m crawler.pipeline.cli `
  --crawler-db E:\path\to\crawler.db `
  --business-db E:\path\to\yuexiang-copy.db `
  --domain jobs `
  --batch-key jobs-nongmuhr-20261022-02 `
  --write
```

`--business-db` 也可以省略，此时真实写入读取 `YUEXIANG_DB`。CLI 不创建业务库，不执行 `db_init`，也不修改业务库 schema。

## 当前 jobs 写入约定

- 业务 key：`job-<source_id>-<source_item_id>`；缺少 `source_item_id` 时使用来源 URL 的稳定摘要。
- `recruitments` 字段映射：标题到 `title`，企业到 `org`，地点原文到 `region`，行业到 `category`，工作性质到 `job_type`，人数、学历、经验、薪资原样落到同名文本字段，正文落到 `description`，发布日期和截止日期落到 `publish_date` / `deadline`。
- 业务行 `extra.review_status=pending_review`、`extra.publish_status=draft`，并保存批次 ID、批次 key、来源 URL、详情 URL、内容哈希和版权证据。不得据此推断审核已通过。
- `recruitment_sources` 使用来源名称加来源记录 ID 作为唯一标题，保存详情 URL、采集时间和版权证据。
- 重复导入时先比较字段、来源关系和导入内容指纹。内容未变计 `skipped_count`，变化才计 `updated_count`。
- 事务失败时采集库批次、冲突、对象映射和业务表行一起回滚。

当前限制：

- 只启用 jobs；agri、dialects、ich 仍为 dry-run。
- 不新增 `recruitment_postings`，不修改现有后端接口和前端。
- 不自动发布。审核状态与发布状态只写入 `extra`，等待后续人工审核流程。
- 不回填人工审核结果。`extra.manual_fields` 需由运营流程显式维护。
- 不使用跨库快照。真实写入执行中发生故障时依赖同一事务整体回滚；成功批次暂不支持业务回滚。

## 回滚 Interface

```text
rollback_batch(batch_id) -> RollbackResult
```

`rollback_batch` 只接受已结束批次。输出 `rolled_back_count`、`skipped_count`、`conflict_count` 和最终状态。依赖 `import_batches`、`import_batch_items`、人工字段锁和批次前快照。dry-run 批次没有业务写入，回滚只标记批次为 `rolled_back` 并保留计划对象映射；没有快照的更新不得盲删或盲还原。当前真实写入批次没有快照，调用 `rollback_batch` 会明确报错且不修改任何业务行。

## 错误模型

| 错误 | 结果 |
| --- | --- |
| 参数非法 | 不创建批次，直接返回 `invalid_argument` |
| 来源或 std 表不可读 | 创建批次后以 `failed` 结束 |
| 单条实体字段不可解析 | 记 `failed_count`，写冲突，继续其余实体 |
| 业务唯一约束冲突 | 写 `import_conflicts`，不重试覆盖 |
| 事务提交失败 | 整体 `failed`，不返回部分计数为成功 |

## 业务写入启用后的验收

- 调用方只 import `run_batch` 和 `rollback_batch`，不直接访问内部 helper。
- 任一批次都能按 `batch_id` 查到统计、冲突和对象映射。
- 人工字段保护和官方优先在 `dry_run` 中给出相同计划。
- 天气请求无法构造合法 `domain`。
