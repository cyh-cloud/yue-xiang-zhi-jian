# Feature Specification: 政务工作台

**Feature Branch**: `v2/lixKRT/010-government-console`

**Created**: 2026-09-18

**Status**: Draft

**Input**: User description: "从零定义 010-government-console：政务工作台子系统。政府发布政策与新闻并查看只读看板；政策发布即上架并触发 02 订阅推送，新闻发布即对学员可见；看板不得展示用户类与培训类数据；就业指标依赖 09 的统计 provider。"

## Clarifications

### Session 2026-09-18

- Q: 政策下架后，订阅关系和已推通知如何处理？ → A: 订阅关系独立保留，下架或删除不撤回已推通知；重新上架不重复推送，历史通知继续可读。
- Q: 订阅推送按上架即时发送还是批量合并？ → A: 每一条政策首次发布时即时触发一条通知；同类多条不合并，重试同一发布事件不重复发送。
- Q: 新闻分类由谁确定？ → A: 政府发布者在发布时手工选择一个规定分类，系统不得自动改类。
- Q: 浏览计数由谁写入，重复浏览如何计算？ → A: 06 在学员成功打开详情后经 10 的 producer 写入；每个不同浏览事件计一次，同一学员重复浏览也重复计数，但同一浏览事件的传输重试不重复计数。
- Q: 政策删除能否恢复？ → A: 政策删除为硬删除，内容和对应浏览计数彻底移除，不提供恢复；历史通知保留其发布时的标题与类别。
- Q: 看板累计投递量是否按学员去重？ → A: 不去重；每个成功申请记录计一次，同一学员投递多个岗位累计多次，失败或重试产生的重复记录不计。
- Q: 是否接受“政策发布与 02 推送强一致、重新上架不重复推送、本期不提供已发布内容编辑、同一学员重复浏览重复计数”四项实现默认？ → A: 全部接受，四项口径作为本期冻结约束。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 政策发布、订阅推送与生命周期管理 (Priority: P1)

政府用户创建政策并选择七类之一。发布后政策立即在学员端对应类别中可见，02 立即向发布时订阅该类别且启用中的学员发送一条包含政策标题和类别的通知。政府可将政策下架、重新上架或彻底删除，并按类别和状态筛选管理列表。

**Why this priority**: 政策生产与准确触达是政务工作台的核心价值，也是 06 政策浏览和 02 订阅推送的上游。

**Independent Test**: 以政府身份完成“发布创业支持政策 → 学员立即可见且订阅者收到一次通知 → 下架不可见 → 重新上架恢复且不重复推送 → 删除彻底不可见”的完整流程。

**Acceptance Scenarios**:

1. **Given** 政府已登录且政策字段完整，**When** 发布政策，**Then** 政策立即进入在架状态，学员端对应类别立即可见，02 向该类别当前订阅学员发送一条含标题和类别的通知。
2. **Given** 政策处于在架状态，**When** 政府下架，**Then** 学员端立即不可见，政策内容、浏览量、订阅关系和已推通知均保留。
3. **Given** 政策处于下架状态，**When** 政府重新上架，**Then** 学员端恢复可见且不产生新的订阅推送。
4. **Given** 政策处于任一未删除状态，**When** 政府删除，**Then** 政策内容与对应浏览量彻底移除，学员端不可见，历史通知仍可读取其标题与类别。
5. **Given** 同类存在多条政策，**When** 连续发布，**Then** 每条政策各触发一次独立通知，不合并为一条。

---

### User Story 2 - 新闻发布与删除 (Priority: P1)

政府用户创建新闻并手工选择“新闻、灾害预警、政策更新”三类之一。发布后新闻立即对学员可见，删除后立即不可见；新闻没有下架或重新上架状态。

**Why this priority**: 新闻和灾害预警是政务内容生产的第二主链路，并且必须与政策状态机严格分离。

**Independent Test**: 分别发布三类新闻，验证学员端分类与可见性；删除后验证列表和详情均不可访问，且系统没有下架操作。

**Acceptance Scenarios**:

1. **Given** 政府已登录且新闻字段完整，**When** 发布新闻，**Then** 新闻立即对学员可见，类别为发布者选择的三类之一。
2. **Given** 新闻已发布，**When** 政府删除，**Then** 新闻立即不可见且不再提供恢复操作。
3. **Given** 新闻为灾害预警，**When** 发布，**Then** 学员可在灾害预警类别中看到该内容。
4. **Given** 新闻已发布，**When** 查看管理操作，**Then** 不提供下架或重新上架动作。

---

### User Story 3 - 政务只读看板 (Priority: P2)

政府用户查看在招岗位数、累计投递量、政策在架/下架数量及累计浏览量、新闻总数及累计浏览量。看板不提供任何用户类或培训类指标，也不提供导出。

**Why this priority**: 看板帮助政府判断内容运营和就业供需情况，但不得越过政府角色的数据边界。

**Independent Test**: 使用固定岗位、申请、政策和新闻数据打开看板，逐项核对指标；同时断言响应和页面中不存在用户类、培训类字段或指标入口。

**Acceptance Scenarios**:

1. **Given** 09 统计 provider 可用，**When** 政府打开看板，**Then** 在招岗位数与累计投递量按 09 的定义正确展示。
2. **Given** 政策包含在架、下架和已删除记录，**When** 查看看板，**Then** 政策总数只统计在架与下架并分列，已删除政策不计入；浏览量保留到删除前并随删除移除。
3. **Given** 新闻包含已发布和已删除记录，**When** 查看看板，**Then** 新闻总数只统计未删除新闻，累计浏览量与其一致。
4. **Given** 09 统计 provider 尚未实现，**When** 政府打开看板，**Then** 两项就业指标显示“就业数据暂不可用”，其余政策与新闻指标正常展示。
5. **Given** 看板响应包含任意用户类或培训类指标，**When** 运行契约测试，**Then** 测试必须失败并报告禁止字段。

---

### Edge Cases

- 政策标题、正文或类别缺失，或类别不属于七类时，不得发布。
- 新闻标题、正文或类别缺失，或类别不属于三类时，不得发布。
- 同一政策因网络重试重复提交发布时，不得创建两条政策或向同一订阅者发送两条通知。
- 政策发布与 02 推送无法同时成功时，不得出现“已显示发布成功但系统未记录该推送事件”的部分成功；调用方应收到失败并可使用同一发布事件安全重试。
- 下架、重新上架、删除使用过期版本或对已删除政策操作时，必须拒绝，不得覆盖较新状态。
- 已发布政策或新闻被删除后，06 的详情读取返回不存在；历史通知仍可显示标题和类别，但来源内容标记为不可用。
- 没有订阅者、没有政策、没有新闻、没有浏览量或没有申请时，指标返回确定的零值；就业 provider 未实现时返回不可用，而不是伪造为零。
- 同一学员重复打开同一政策或新闻时，每个不同浏览事件分别计数；同一浏览事件的重复传输不重复计数。
- 看板数据源不可用不得影响政策或新闻的发布、上下架和删除。
- 政府用户尝试访问用户明细、用户统计、课程或学习统计时必须被拒绝；这些能力不因隐藏前端入口而获得后端许可。
- 政府用户不得通过请求参数改变自身身份、角色或内容归属。

## Requirements *(mandatory)*

### Functional Requirements

#### 角色、边界与状态所有权

- **FR-001**: 010 MUST 仅允许 `government` 角色进入政务工作台并执行政策、新闻和看板操作；身份和角色 MUST 由 01 当前会话覆盖。
- **FR-002**: 010 MUST reuse 01 的登录会话、禁用账户和角色门户；不得建立第二套账户、会话或政府身份系统。
- **FR-003**: 010 MUST NOT consume、import 或模拟 11 的 `ContentReviewProvider`；政策与新闻均不经过发布前审核。
- **FR-004**: 010 MUST NOT call AI services and MUST NOT depend on AI availability for any manual publishing or dashboard path.
- **FR-005**: 010 MUST own policy/news records, lifecycle state, content view counters and source publication events; 02 owns notification delivery and audience resolution.
- **FR-006**: 010 MUST NOT provide policy pre-publication approval, subsidy application/processing, data export, user information, training data, certificate data, account management, or review operations.

#### 政策状态机与订阅推送

- **FR-007**: A policy MUST use exactly three lifecycle states: `在架`、`下架`、`删除`; there is no draft, pending-review, approved or rejected state.
- **FR-008**: Creating and publishing a valid policy MUST be one user action that stores the policy directly in `在架` state, records a non-empty `published_at`, and accepts a non-empty `request_id` used to make repeated submissions of the same publication event idempotent.
- **FR-009**: The policy category MUST be exactly one of: `补贴`、`电商`、`非遗`、`培训`、`认证`、`综合`、`创业支持`.
- **FR-010**: Only `在架` policies MUST be visible to 06 or any student-facing consumer.
- **FR-011**: A `下架` policy MUST remain stored with its content, version, timestamps, view counter, subscription relationships and historical notifications retained.
- **FR-012**: Re-listing a `下架` policy MUST restore student visibility without changing its policy ID and without creating a new subscription-push event.
- **FR-013**: Deleting a policy MUST hard-delete its content and associated content view counter; deleted policies MUST NOT appear in management, student, provider or dashboard content totals.
- **FR-014**: Policy deletion MUST NOT delete policy-category subscriptions or historical 02 notifications; those notifications MUST retain the published title and category snapshot and MUST be marked with an unavailable source reference.
- **FR-015**: Every first publication of a policy MUST invoke 02's existing `emit_policy_published(event_id, policy_id, title, category)` channel exactly once with the policy title and category.
- **FR-016**: The 02 push audience MUST be the enabled students subscribed to the policy category at publication time; later subscribers MUST NOT receive that policy's earlier push, and unsubscribing MUST NOT remove an already delivered notification.
- **FR-017**: Each policy publication MUST be an independent immediate notification; multiple policies in the same category MUST NOT be batched or merged.
- **FR-018**: Policy publication state and its 02 event acceptance MUST use one business operation boundary. If push-event acceptance fails, the publication MUST NOT report success, and retrying the same publication event MUST be idempotent.
- **FR-019**: A policy's stable `event_id` MUST be unique to its first publication event and MUST remain stable across transport retries. Re-listing MUST reuse no new event ID because it MUST NOT push again.
- **FR-020**: Policy list management MUST support filtering by category and by `在架`/`下架` status; deleted records MUST NOT be recoverable.
- **FR-021**: Concurrent publish, unpublish, re-list or delete operations MUST use version checks and MUST reject stale writes.

#### 新闻状态机与可见性

- **FR-022**: News MUST use exactly two lifecycle states: `已发布` and `已删除`; it MUST NOT have `下架` or `重新上架` operations.
- **FR-023**: Creating and publishing valid news MUST be one user action that makes the news immediately visible to students and accepts a non-empty `request_id` used to make repeated submissions of the same publication event idempotent.
- **FR-024**: The news category MUST be manually selected by the government publisher and MUST be exactly one of: `新闻`、`灾害预警`、`政策更新`.
- **FR-025**: Published news MUST be visible to 06 in its selected category, including `灾害预警`.
- **FR-026**: Deleting news MUST hard-delete its content and associated content view counter and immediately remove it from all student-facing reads.
- **FR-027**: News publication MUST NOT trigger a policy-category subscription push and MUST NOT call `emit_policy_published`.
- **FR-028**: News deletion MUST be irreversible and MUST NOT expose a restore action.

#### 浏览计数

- **FR-029**: Only 06 may record a student content view by calling the 10 producer's `record_policy_view` or `record_news_view`; government management and dashboard reads MUST NOT increment either counter.
- **FR-030**: A successful view record MUST increment the matching counter exactly once for each distinct `view_event_id`.
- **FR-031**: Repeated opens of the same policy or news by the same student MUST count as separate views when 06 supplies a new view event; retrying the same `view_event_id` MUST NOT increment again.
- **FR-032**: View recording MUST be rejected for deleted content and MUST NOT create a count for a non-existent or unpublished target.
- **FR-033**: A view-counter failure MUST NOT hide otherwise valid content; 06 may show the content and report that the count could not be recorded.
- **FR-034**: Unpublishing and re-listing a policy MUST preserve its cumulative view count; deleting policy or news MUST remove its cumulative view count with the content.

#### 数据看板

- **FR-035**: The government dashboard MUST be read-only and MUST display exactly these business metric groups:
  - employment: `在招岗位数`, `累计投递量`;
  - policy: `在架政策数`, `下架政策数`, `政策累计点击浏览量`;
  - news: `新闻总数`, `新闻累计点击浏览量`.
- **FR-036**: `在招岗位数` MUST mean the count of all platform-published active jobs and MUST be supplied by 09's employment statistics provider, not queried from a 09-owned table.
- **FR-037**: `累计投递量` MUST mean the cumulative number of successful application records and MUST be supplied by 09's employment statistics provider.
- **FR-038**: `累计投递量` MUST NOT deduplicate by student; one student applying to multiple positions contributes multiple counts, while failed attempts and idempotent retries of the same application MUST NOT contribute.
- **FR-039**: The policy dashboard total MUST equal `在架政策数 + 下架政策数`; deleted policies MUST be excluded from both totals and view totals.
- **FR-040**: The news dashboard total MUST count only undeleted news and MUST equal the number of currently published news records.
- **FR-041**: The dashboard response and rendered page MUST NOT contain or expose total users, user-role distribution, student region/direction distribution, user details, course counts, learning-behaviour counts, progress, completion rate, learner records or certificate data.
- **FR-042**: User-class and training-class metrics MUST be absent from the government response contract, not merely hidden by CSS or frontend conditions.
- **FR-043**: If 09's provider is not implemented or unavailable, both employment cards MUST show `就业数据暂不可用` and the rest of the dashboard MUST remain usable.
- **FR-044**: Dashboard metric reads MUST NOT mutate policy/news state or increment any view counter.

#### 跨模块 Producer 契约

- **FR-045**: 010 MUST provide the registration slots `set_policy_news_provider(app, provider)` and `get_policy_news_provider()` and MUST provide the optional convenience entry `configure_government_providers(app, *, policy_news=None, employment_statistics=None)`.
- **FR-046**: The 10 policy/news producer MUST expose this provisional Protocol for 06:

```python
class PolicyNewsProvider(Protocol):
    def list_published_policies(self, category: str | None = None) -> list[dict]: ...
    def get_published_policy(self, policy_id: str) -> dict | None: ...
    def list_published_news(self, category: str | None = None) -> list[dict]: ...
    def get_published_news(self, news_id: str) -> dict | None: ...
    def record_policy_view(self, policy_id: str, view_event_id: str) -> int: ...
    def record_news_view(self, news_id: str, view_event_id: str) -> int: ...
```

- **FR-047**: The final policy/news consumer signature owner is 06. The 010 spec freezes the producer implementation and registration shape; 06 MUST adopt it or formally revise the signature in its own spec before consumer implementation. No consumer may import 010 tables or private helpers.
- **FR-048**: Policy/news stable IDs MUST be non-empty strings; list results MUST be complete and ordered by `published_at` descending then stable ID ascending; no page/page-size fields may be exposed.
- **FR-049**: Published policy records MUST expose at least `id`, `title`, `content`, `category_code`, `category_label`, `published_at`, `updated_at` and `version`; news records MUST expose at least `id`, `title`, `content`, `category_code`, `category_label`, `published_at`, `updated_at` and `version`.
- **FR-050**: 06-facing reads MUST return only `在架` policies and undeleted news. `get_*` MUST return `None` for missing, unpublished, or deleted content; list methods MUST return an empty list when no content matches.
- **FR-051**: All 010 provider times MUST be timezone-aware ISO 8601 strings normalized to `+08:00`; consumers MUST parse before ordering.
- **FR-052**: All 010 provider boundary errors MUST use the frozen `ProviderError` hierarchy and its `validation`, `not_found`, `conflict`, `unavailable` and `access_denied` semantics; consumers MUST NOT receive raw database errors.
- **FR-053**: 010 MUST NOT query or depend on 09-owned tables. It MUST consume employment statistics only through `set_employment_statistics_provider` / `get_employment_statistics_provider`.
- **FR-054**: The provisional employment statistics Protocol MUST be:

```python
class EmploymentStatisticsProvider(Protocol):
    def get_active_job_count(self) -> int | None: ...
    def get_cumulative_application_count(self) -> int | None: ...
```

- **FR-055**: Before 09 is merged, the default employment statistics provider MUST implement the full Protocol and return `None` for both methods, causing the two cards to display `就业数据暂不可用`; it MUST NOT return fake counts or query a speculative table.
- **FR-056**: When 09 lands, its statistics provider MUST be installed only through the existing 010 registration slot. The dashboard consumer MUST NOT branch on placeholder status and MUST NOT be edited to know 09 internals.
- **FR-057**: 010 MUST NOT consume 11's user/training/full-platform statistics for the government dashboard and MUST NOT expose a hidden route that returns those metrics.

### State and Visibility Contracts

#### Policy State Machine

| State | Student-visible | Allowed government actions | Subscription push | Retained data |
| --- | --- | --- | --- | --- |
| `在架` | Yes | 下架、删除 | First publication only | Content, view count, subscriptions, notifications |
| `下架` | No | 重新上架、删除 | None on re-list | Content, view count, subscriptions, notifications |
| `删除` | No | None | None | Content and view count removed; subscriptions and historical notifications retained |

#### News State Machine

| State | Student-visible | Allowed government actions | Unpublish/re-list |
| --- | --- | --- | --- |
| `已发布` | Yes | 删除 | Not available |
| `已删除` | No | None | Not available |

#### Category Contracts

| Content | Exact categories |
| --- | --- |
| 政策 | 补贴、电商、非遗、培训、认证、综合、创业支持 |
| 新闻 | 新闻、灾害预警、政策更新 |

### Key Entities

- **Policy**: A government-published policy with stable string ID, title, content, one of seven categories, three-state lifecycle, version, publication time and cumulative view count.
- **News**: A government-published news item with stable string ID, title, content, one of three manually selected categories, two-state lifecycle, version, publication time and cumulative view count.
- **Policy Subscription Relationship**: A student's current subscription to a policy category; owned by the subscription source, retained across policy lifecycle changes, and used by 02 only at publication time.
- **Policy Publication Event**: An idempotent source event containing stable event ID, policy ID, title and category; accepted by 02 and never recreated by re-listing.
- **Content View Event**: An idempotent 06-originated event that increments one policy/news view count once per distinct event ID.
- **Government Dashboard Snapshot**: A read-only aggregation containing only employment, policy and news metrics; it contains no user or training data.
- **Employment Statistics Provider**: A replaceable read-only source supplied by 09 for all-platform active-job and cumulative-application counts.
- **Policy/News Provider**: The 010-owned producer interface consumed by 06 for published content reads and view recording.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a policy lifecycle test, 100% of state/visibility results match the policy matrix; no unpublished or deleted policy is visible to 06.
- **SC-002**: In a first-publication test with fixed subscribers, 100% of matching enabled students receive exactly one notification containing the policy title and category, and zero non-subscribers receive it.
- **SC-003**: Retrying the same policy publication event 10 times produces one policy and at most one notification per subscriber; re-listing produces zero new notifications.
- **SC-004**: In a news lifecycle test, 100% of published news is visible in its selected category and 100% of deleted news is absent from list and detail reads; no unpublish/re-list action is accepted.
- **SC-005**: Repeating a content view with a new view event increments the counter by one, while retrying the same view event 10 times increments it exactly once.
- **SC-006**: On fixed data, every dashboard metric equals its specified source value, and the policy total equals active plus unpublished counts.
- **SC-007**: Dashboard contract tests find exactly zero forbidden user-class and training-class keys, routes and rendered metric labels.
- **SC-008**: With no 09 provider installed, both employment cards show `就业数据暂不可用`, return no fabricated numbers, and all policy/news metrics still render.
- **SC-009**: Registering a fake 09 statistics provider changes only the two employment values; no dashboard consumer code or provider-specific branch is changed.
- **SC-010**: The 06 consumer test can list and read published policy/news, receives deterministic ordering and `+08:00` times, and cannot read unpublished or deleted content.
- **SC-011**: Static and runtime tests find zero AI calls and zero `ContentReviewProvider` dependencies in the 010 feature path.
- **SC-012**: In authorization tests, 100% of non-government attempts to publish, change lifecycle, read the dashboard or access user/training data are rejected.

## Assumptions

- Policies and news are created directly in their published state; there is no draft workflow or pre-publication approval.
- Editing published policy or news is not required for this release unless separately specified; if editing is added, it remains subject to the same no-review boundary, does not change the state, and does not repeat a policy subscription push.
- Re-listing a policy restores the same record and does not re-notify subscribers; this avoids duplicate notifications for an already-published policy.
- Policy deletion is a hard delete because the product states that deletion removes the record completely; historical notification content is a snapshot and is not deleted.
- News deletion is also a hard delete; news has no subscription-push event to retain.
- Each distinct student view event counts once even when the same student repeats the view; only transport retries carrying the same event ID are deduplicated.
- The 09 employment provider is authoritative for all-platform active-job and cumulative-application counts. Until 09 lands, missing values are shown as unavailable rather than zero.
- The 06 policy/news consumer is not implemented in this feature. Its signature owner remains 06, and 010 supplies the provisional producer shape above without creating a second consumer contract.
- The government dashboard excludes user and training metrics at the response-schema boundary. 11 remains the owner of super-admin-only full-platform statistics.
