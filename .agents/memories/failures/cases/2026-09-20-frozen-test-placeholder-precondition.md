# 冻结模块测试用占位常量构造前提，生产者替换注册槽后失效

- Case ID: project-20260920-frozen-test-placeholder-precondition

- Date: 2026-09-20
- Status: RESOLVED
- Scope: project
- Keywords: SDD, 011, 05, frozen module, placeholder provider, test precondition, provider slot, PLACEHOLDER_REWARDS
- Owner: SDD controller

## Scene

- Project or path: `E:\Project\skipped_work\粤乡智匠项目\.worktrees\011-admin-console`
- Branch or commit: `v2/lixKRT/011-admin-console`，Task 10 之前 HEAD `68fe604`
- OS and shell: Windows，PowerShell
- Relevant versions: Python 3.12，Flask，SQLite（`PRAGMA foreign_keys = ON`）
- Relevant configuration: `uv run --directory backend python -m unittest ...`

## Expectation and Evidence

- Expected: 011 通过 `handcraft_reward_catalog_provider` 提供权威奖品目录后，05 既有测试保持绿色。
- Observed: `tests/test_handcraft_rewards.py::test_concurrent_redeem_of_last_stock_conflict_is_atomic` 失败于 `AssertionError: 2 != 1`（第 396 行）。
- Reproduction: 该测试用 `patch("app.handcraft_inheritance.presets.PLACEHOLDER_REWARDS", one_stock_rewards)` 构造“只剩一件库存”的前提。该机制只在 05 的 `PlaceholderRewardCatalogProvider` 于调用时从模块常量推导基础库存时有效；011 接管槽位后库存权威来源是 `admin_rewards`（`init_db()` 时 seed），补丁不再影响库存，两个并发兑换都成功。
- Evidence: 用未改动的占位 provider 把基础库存强制为 10，复现完全相同的 2 成功结果，说明库存值是唯一变量、不是事务处理问题；把 `stock = 1` 写入 `admin_rewards` 后重放同一场景，该冻结测试六个断言全部通过（1 成功 / 1 失败，消息恰为 `库存或积分已变化，请刷新后重试`，兑换 1、预约 1、扣分 1、履约 1）。要求的 53 个冻结测试中 52 个通过。

## Attempts

- Attempt 1: 实现者按 brief 的停机规则停止并报告 BLOCKED，未提交、未改消费者或其测试。
- Attempt 2: 控制器核实测试断言本身有效，仅前提构造方式依赖占位常量；同文件第 411-413 行已有正确先例（通过 `set_reward_catalog_provider` 安装自有 provider 构造前提）。

## Diagnosis

- Facts: 05 的若干测试用 `patch()` 05 模块内部常量来构造前提；011 作为生产者替换注册槽后，这些常量不再是权威来源。
- Hypotheses: 是否应让 `list_rewards()` 在调用时读 `PLACEHOLDER_REWARDS`。已排除——那等于继续提供占位内容，并违反 FR-091（管理端库存编辑必须在下一次读取生效）。
- Root cause: 冻结模块的测试把“前提构造”绑定在占位实现内部状态上，而不是绑定在 provider 契约上。这是结构性问题，不是单次失误；Task 16 的积分规则会以相同形态复现（`test_handcraft_presets.py::test_points_policy_matches_demo_values` 断言 `isinstance(provider, PlaceholderPointsPolicyProvider)` 与演示数值）。

## Resolution

- Fix or workaround: 控制器裁决——断言必须逐字保留，只允许把前提构造改写为通过权威来源建立状态。本例中将 `patch(PLACEHOLDER_REWARDS, ...)` 改为在 `self.app.app_context()` 内向 `admin_rewards` 写入 `stock = 1` 并提交，第 396-406 行六个断言逐字不变。该测试适配单独提交，可独立审查与回退。
- Verification: 适配后 `tests.test_handcraft_rewards` 及要求的冻结集合全绿；实现者自有 34 个测试全绿。
- Confidence: High。被测属性（最后一件库存的并发冲突原子性）被完整保留，且有独立证据表明实现在 `stock = 1` 下满足全部断言。

## Prevention

- Guardrail: 派单 brief 必须预先声明“05 测试中用 `patch()` 05 内部常量构造前提的用例，在 011 接管对应槽位后需要适配前提；断言不得改动；适配必须单独提交”。Task 16 派单时必须带上这条，并预先处理 `test_points_policy_matches_demo_values` 的 `isinstance` 与演示数值断言。
- Forbidden: 不得为让测试通过而让 011 的 provider 继续读占位常量；不得删除、放松或改写冻结测试的断言；不得修改 `backend/app/handcraft_inheritance/`、`backend/app/agri_skills/`、`backend/app/local_resources/` 下任何文件。
- Next probe: Task 16 派单前先跑 `uv run --directory backend python -m unittest tests.test_handcraft_presets -v` 确认哪些断言依赖占位实现，并把需要适配的前提写进 brief。
- Stop condition: 若某个冻结测试的断言本身（而非前提）与 011 契约冲突，停止并报告，由规格所有者决策，不得自行改写断言。

## Review

- Last reviewed: 2026-09-20
- Review interval: 2026-09-27
- Reopen count: 0
- Supersedes or duplicates: none
- Expiry or obsolescence condition: 011 合并入 `v2/lixKRT/dev` 且 05 测试前提已全部适配后失效
