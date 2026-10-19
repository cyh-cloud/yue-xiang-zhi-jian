# 批次转换 Module Interface

状态: 设计冻结

日期: 2026-10-19

本文件定义 `converter` 的外部 interface。调用方只依赖 `run_batch(domain, batch)`，不直接调用自然键、去重、来源优先、冲突、发布或回滚内部步骤。

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
| `batch.dry_run` | boolean | 否 | 只计算计划和冲突，不写业务表 |

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

1. 校验 `domain` 和 `batch`，加载 `std_sources` 启用来源。
2. 读取该内容域 std 实体，按实体自然键分组。
3. 选择主值来源，计算字段计划。
4. 读取人工字段锁和批次前快照。
5. 执行升级写入和来源关系写入。
6. 写冲突、统计和批次状态。
7. 提交或回滚本次事务。

调用方不传自然键、字段优先级、SQL、表名或回滚命令。module 内部按 `std-entities.md` 和 `converter.md` 执行。

## 不变量

- 一次调用只处理一个内容域。
- 同一 `batch.batch_key` 重复调用不重复写入。
- 天气不是合法 `domain`。
- `dry_run=true` 不写业务表、批次统计和冲突表，只返回计划结果。
- `partial` 和 `failed` 不得伪装成 `succeeded`。
- 人工保护字段永不自动覆盖。
- 返回统计之和与 `input_count` 对账一致，无法归类的输入计为 `failed`。

## 回滚 Interface

```text
rollback_batch(batch_id) -> RollbackResult
```

`rollback_batch` 只接受已结束批次。输出 `rolled_back_count`、`skipped_count`、`conflict_count` 和最终状态。依赖 `import_batches` 的对象映射、人工字段锁和批次前快照。没有快照的更新不得盲删或盲还原。

## 错误模型

| 错误 | 结果 |
| --- | --- |
| 参数非法 | 不创建批次，直接返回 `invalid_argument` |
| 来源或 std 表不可读 | 创建批次后以 `failed` 结束 |
| 单条实体字段不可解析 | 记 `failed_count`，写冲突，继续其余实体 |
| 业务唯一约束冲突 | 写 `import_conflicts`，不重试覆盖 |
| 事务提交失败 | 整体 `failed`，不返回部分计数为成功 |

## 验收

- 调用方只 import `run_batch` 和 `rollback_batch`，不直接访问内部 helper。
- 任一批次都能按 `batch_id` 查到统计、冲突和对象映射。
- 人工字段保护和官方优先在 `dry_run` 中给出相同计划。
- 天气请求无法构造合法 `domain`。
