# Feature Specification: 就业对接

**Feature Branch**: `v2/lixKRT/007-job-matching`

**Created**: 2026-09-19

**Status**: Draft

**Input**: User description: "job-matching: 就业对接子系统。实现简历维护与可选 AI 优化、技能档案聚合与可见范围、岗位浏览与规则推荐、投递及前置校验、我的投递状态跟踪和岗位收藏；岗位读取与申请写入复用 09 provider，技能成果复用 03/04/05 既有 outcome 读取函数。"

## Clarifications

### Session 2026-09-19

- Q: 投递后学员修改简历，企业看到的是当前简历还是投递时版本？ → A: 企业始终看到投递成功时冻结的简历快照；后续编辑不改变历史申请。
- Q: 技能档案可见范围按整档开关还是按成果项控制？ → A: 按单个成果项控制；无可见设置的新成果默认仅自己可见，未勾选项在投递快照和企业端均不出现。
- Q: 未附带技能档案或没有可见成果时，企业端如何显示？ → A: 仅显示投递时简历，不读取当前技能档案补造内容，也不以空档案替代简历。
- Q: “推荐岗位”采用什么维度与优先级？ → A: 只推荐当前已上架职位；先按学员 `job` 兴趣标签与职位稳定类别 ID 的精确匹配分组，再按最近 90 天学习行为活跃度、最近学习时间、发布时间倒序和稳定职位 ID 正序。
- Q: 投递前置校验中的“无简历”如何判定？ → A: 只有至少一个已保存且内容非空的结构化区块才算有简历；01 自动建立但从未保存内容的关系记录和未保存草稿不算。
- Q: “岗位已关闭”与企业的“不合适”等状态如何并存？ → A: 未处理申请在职位删除后有效状态改为“岗位已关闭”；企业已处理过的申请保留最新人工状态，并额外显示“岗位已关闭”标识，关闭标识不覆盖人工状态历史。
- Q: 已收藏职位被删除后保留多久？ → A: 收藏记录不自动过期，保留到学员手动移除；关闭后不可投递，并显示收藏时的职位展示快照。
- Q: 简历 AI 改写在采纳后是否保留原版以便回退？ → A: 采纳前可放弃并完整保留原稿；采纳后旧版本仅供内部审计和历史申请快照使用，本期不提供历史简历回退入口。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 简历维护与可选 AI 优化 (Priority: P1)

学员创建或编辑包含教育经历、工作经历和技能特长的结构化简历。学员可请求 AI 给出优化建议和改写稿，明确选择采纳或放弃；采纳替换当前优化工作稿后保存，放弃保留原稿，手动编辑和保存始终独立可用。

**Why this priority**: 简历是投递的强制性前提，也是 09 企业申请详情的核心输入；没有稳定简历契约，岗位投递链路无法成立。

**Independent Test**: 以学员身份完成“创建简历 → 保存 → 请求 AI → 采纳 → 保存”和“请求 AI → 放弃 → 手动编辑 → 保存”两条独立路径；再用 AI 不可用情况验证手动路径不受影响。

**Acceptance Scenarios**:

1. **Given** 学员尚无已保存简历，**When** 填写至少一个非空结构化区块并保存，**Then** 简历成为可投递版本并保留教育经历、工作经历和技能特长的有序内容。
2. **Given** 学员已有已保存简历，**When** 编辑字段但未保存，**Then** 当前已保存版本不被草稿覆盖，投递仍读取最后一次成功保存的版本。
3. **Given** AI 可用且请求有效，**When** AI 返回建议和完整改写稿，**Then** 系统显示预览，在学员确认前不替换已保存简历。
4. **Given** 学员查看 AI 优化预览，**When** 选择采纳，**Then** 改写内容替换当前简历并形成新的已保存版本，且学员可明确看到采纳结果已生效。
5. **Given** 学员查看 AI 优化预览，**When** 选择放弃，**Then** 已保存简历和当前手动编辑内容保持原值，优化稿不写入简历。
6. **Given** AI 服务不可用、超时或返回非法结构，**When** 学员请求优化，**Then** 显示“AI 服务暂时不可用”，手动编辑和保存路径继续可用。

---

### User Story 2 - 技能档案聚合与可见范围 (Priority: P1)

系统自动聚合 03/04/05 已产生的直播话术脚本、模拟训练评分、测验成绩和学习记录，形成统一技能档案。学员按成果项勾选可见范围，默认全部仅自己可见；投递时只可将当前可见成果组成快照附带。

**Why this priority**: 技能档案定义“培训成果 → 就业证据”的桥接契约，07 必须作为唯一聚合与可见性权威，09 只消费投递时快照。

**Independent Test**: 分别插入 03、04、05 的成果源记录，验证四类归一结果、跨学员隔离、逐项勾选、默认隐藏、来源不可用降级和附带投递快照；确认隐藏项在 09 详情中零泄露。

**Acceptance Scenarios**:

1. **Given** 学员在 03/04/05 已产生成果，**When** 打开“我的技能档案”，**Then** 系统自动汇总来源记录并归入直播话术、模拟训练、测验成绩和学习记录四类，不要求学员手工复制。
2. **Given** 学员已有成果但从未设置可见范围，**When** 查看档案和企业可见结果，**Then** 全部成果默认仅自己可见，企业可见项为零。
3. **Given** 学员勾选部分成果项，**When** 保存可见范围，**Then** 仅勾选项进入可附带集合，未勾选项保持私密。
4. **Given** 来源模块新增成果，**When** 学员刷新档案，**Then** 新成果自动出现且默认隐藏，既有勾选状态不被重置。
5. **Given** 来源成果已不可用，**When** 读取技能档案，**Then** 该项目显示不可用状态或从快照中排除，不伪造替代内容。
6. **Given** 学员选择附带技能档案，**When** 投递成功，**Then** 09 只保存投递时勾选且来源可用的成果快照，之后修改可见范围不回写历史申请。

---

### User Story 3 - 岗位浏览、推荐、详情与投递 (Priority: P1)

学员浏览当前已上架岗位和顶部推荐岗位，查看职位详情并执行投递。系统依次校验职位仍可见、简历已保存且不重复，允许可选附带技能档案，再把不可变快照交给 09 生成申请并触发企业通知。

**Why this priority**: 这是就业对接的主交易路径，连接 01 学员身份、09 真岗位、07 简历/技能档案和 09 投递接收。

**Independent Test**: 使用可替换的真实 09 provider 和测试岗位完成列表、推荐、详情、三类前置分支及成功投递；验证重复请求、过期详情和并发投递不会产生第二份申请。

**Acceptance Scenarios**:

1. **Given** 09 provider 返回已上架职位，**When** 学员打开岗位页，**Then** 列表显示标题、公司、薪资、地点和描述，顶部单独显示推荐岗位区；无数据时分别显示“暂无岗位”和“暂无推荐”。
2. **Given** 学员修改岗位兴趣标签或学习行为，**When** 刷新推荐，**Then** 推荐顺序按冻结规则重新计算，已下架职位不进入结果。
3. **Given** 学员打开已上架职位详情，**When** 点击投递，**Then** 系统先完成不可见职位兜底、无简历和重复投递校验。
4. **Given** 学员没有已保存的非空简历，**When** 尝试投递，**Then** 请求被拦截并引导跳转简历编辑，不创建申请。
5. **Given** 学员已经投递同一职位，**When** 再次尝试投递，**Then** 显示“已投递该岗位”，不创建第二份申请或通知。
6. **Given** 职位在列表或详情打开后变为待审核、已驳回或已删除，**When** 学员再次刷新或提交，**Then** 职位不可见或投递被拒绝，不产生申请。
7. **Given** 学员需要附带技能档案，**When** 投递成功，**Then** 请求包含当前已保存简历快照和只含可见成果的技能档案快照，申请进入“我的投递”，09 负责向企业发送唯一投递通知。

---

### User Story 4 - 我的投递与状态跟踪 (Priority: P1)

学员在“我的投递”查看全部历史申请及最新状态，状态随 09 企业操作更新；职位删除后按 09 冻结矩阵显示关闭结果，历史申请和快照不丢失。

**Why this priority**: 投递后状态透明是就业闭环的完成条件，并直接消费 09 的状态权威记录。

**Independent Test**: 构造五种有效展示状态、人工改标历史和职位删除场景，验证学员只能看到自己的申请、状态按 09 最新记录展示，且不存在撤回入口。

**Acceptance Scenarios**:

1. **Given** 学员只有自己的申请记录，**When** 打开“我的投递”，**Then** 每项显示职位标题、公司、投递时间和当前状态，默认按投递时间倒序、申请稳定 ID 正序。
2. **Given** 企业将申请从待处理改为已查看、意向沟通或不合适，**When** 学员刷新，**Then** 显示 09 返回的最新人工状态。
3. **Given** 未处理申请的职位被删除，**When** 学员查看“我的投递”，**Then** 有效状态显示“岗位已关闭”。
4. **Given** 已处理申请的职位被删除，**When** 学员查看“我的投递”，**Then** 保留最新人工状态并额外显示“岗位已关闭”标识。
5. **Given** 学员位于任一投递状态，**When** 查看列表和详情操作，**Then** 不存在撤回、删除申请或重新提交入口。

---

### User Story 5 - 岗位收藏 (Priority: P2)

学员收藏或取消收藏岗位，在集中列表查看收藏；职位被企业删除后保留收藏展示快照并标记“岗位已关闭”，禁止投递，学员可手动移除。

**Why this priority**: 收藏提升岗位回访效率，但不阻塞首次浏览和投递主链路。

**Independent Test**: 对已上架、重复收藏、取消、职位消失和关闭后移除分别验证收藏唯一性、列表状态、投递禁用与历史保留。

**Acceptance Scenarios**:

1. **Given** 学员查看已上架职位，**When** 点击收藏，**Then** 收藏唯一创建，再次点击可取消，不创建重复项。
2. **Given** 学员打开收藏列表，**When** 职位仍已上架，**Then** 展示最新岗位信息并可进入详情或投递。
3. **Given** 已收藏职位不再由 09 provider 返回，**When** 学员刷新收藏列表，**Then** 使用收藏时展示快照标记“岗位已关闭”并禁用投递。
4. **Given** 收藏项已关闭，**When** 学员手动移除，**Then** 收藏项消失且不影响历史申请。

---

### Edge Cases

- 三个简历结构化区块全部为空或仅含空白时，不得保存为可投递简历；字段级错误需保留用户输入。
- 同时编辑、采纳优化和保存时，旧版本不得覆盖新版本；冲突必须提示刷新或重新确认。
- AI 返回缺失区块、重复字段、超长非文本或部分改写时按不可用处理，不得写入残缺简历。
- AI 优化请求不得包含姓名、联系方式、账户 ID、会话令牌、兴趣标签或其他非简历字段。
- 同一成果源记录被重复读取时按稳定成果项 ID 去重；课程测验的多次有效提交按来源正式成绩口径保留来源返回的各项，不由 07 改写正式性。
- 来源模块不可用或单条成果读取异常时，其他来源仍可展示；单条失败不得让整个技能档案永久不可用。
- 学员勾选后源记录被删除或来源不再可用时，不泄露历史私有内容；新投递快照排除不可用项。
- 投递时附带技能档案但可见成果为零时按未附带处理，不发送空对象冒充已附带。
- 学员在详情页停留期间职位状态变化、简历被另一会话修改或重复点击投递时，服务端必须重新校验并以 09 的最新记录为准。
- 09 投递 provider 已创建申请但响应丢失时，同一 `idempotency_key` 重试必须返回原申请，不创建第二个申请或第二条企业通知。
- 职位删除和人工改标并发时，07 不自行决定最终状态，只展示 09 返回的最新人工状态和关闭标识。
- 收藏列表中的职位暂时离开已上架来源时不得删除收藏；若后续重新出现，使用 provider 最新信息刷新展示快照。
- 跨学员读取或修改简历、优化稿、技能可见项、收藏和投递列表必须拒绝，错误响应不得泄露对象是否存在。

## Requirements *(mandatory)*

### Functional Requirements

#### 角色、范围与会话

- **FR-001**: 本 feature MUST 只允许 `active` 状态的 `student` 角色访问简历、技能档案、岗位、投递和收藏功能。
- **FR-002**: 学员身份 MUST 只取自 01 当前会话 `load_session()`，客户端传入的 `student_id`、角色或归属字段一律忽略。
- **FR-003**: 07 MUST 复用 01 的账户、会话、学习方向和 `job` 兴趣标签目录，MUST NOT 建立第二套登录、角色或标签数据。
- **FR-004**: 07 MUST NOT 实现农产品求购信息、线上面试、电子签约、入职流程管理、企业人才库搜索、主动邀约或投递撤回。
- **FR-005**: 07 MUST NOT 提供企业审核动作、职位发布、企业申请改标或 11 的管理功能；职位生命周期和申请状态只在 09 权威记录中变化。
- **FR-006**: 07 MUST NOT 直接写入 `job_positions`、`job_applications` 或 `job_application_status_history`，也不得导入 09 的内部业务服务绕过 provider。

#### 结构化简历

- **FR-007**: 学员 MUST 能查看、创建和编辑一份与账户一对一关联的结构化简历，至少包含教育经历、工作经历和技能特长三个有序区块。
- **FR-008**: 教育经历、工作经历中的每个条目 MUST 使用结构化字段保存，不得只保存不可编辑的整段自由文本；技能特长 MUST 支持多个去重非空条目。
- **FR-009**: 系统 MUST 区分未保存草稿、最后一次成功保存版本和 AI 优化预览；未保存内容不得被投递使用。
- **FR-010**: 学员手动保存时，系统 MUST 校验并持久化当前完整表单；保存成功后返回版本号和保存时间。
- **FR-011**: 至少一个结构化区块去除空白后非空时，简历才算“已保存且可投递”；01 建立的空关系记录、全空表单和未保存草稿均不算。
- **FR-012**: 简历保存 MUST 使用版本控制；基于旧版本的保存不得覆盖较新版本，并应提示用户刷新或重新确认。
- **FR-013**: 07 MUST 保留已保存简历版本的内部修订记录用于并发控制和审计，但本期 MUST NOT 提供用户可操作的历史回退入口。
- **FR-014**: 投递时使用的简历快照 MUST 只包含投递成功时最后一次保存的简历内容，不包含未保存草稿、AI 会话上下文、联系方式或内部审计字段。
- **FR-015**: 简历快照 MUST 至少包含：

```text
resume_version       # 正整数快照版本
saved_at             # 带时区 ISO 8601 时间
education_experiences
work_experiences
skills
```

- **FR-016**: 简历保存、读取和投递快照读取 MUST 拒绝跨学员访问；同一学员在多个会话中的冲突按版本号处理。

#### AI 简历优化

- **FR-017**: AI 简历优化 MUST 是可选能力；手动创建、编辑和保存简历 MUST 不依赖 AI 可用性。
- **FR-018**: 系统 MUST 仅在学员显式点击“AI 优化”后调用一次 AI，调用点为 `resume_optimize`，不得在其他岗位、推荐、收藏或状态路径调用 AI。
- **FR-019**: AI 请求上下文 MUST 只允许以下字段：

```text
education_experiences
work_experiences
skills
```

- **FR-020**: AI 请求 MUST NOT 发送姓名、联系方式、用户 ID、会话令牌、投递记录、技能档案可见设置、兴趣标签或其他学员数据。
- **FR-021**: AI 成功结果 MUST 规范化为可预览的非空建议列表；改写稿允许缺省，若存在则只能包含三个允许的简历区块且必须完整。
- **FR-022**: AI 建议和改写稿 MUST 先进入预览状态，确认前 MUST NOT 修改最后保存版本或影响投递。
- **FR-023**: 当 AI 结果包含完整改写稿时，学员选择“采纳”必须由系统以同一原子操作验证优化稿归属、基础简历版本和当前版本，再将改写内容保存为新版本；仅有建议时不得伪造改写稿或自动修改简历。
- **FR-024**: 学员选择“放弃”时，系统 MUST 保持当前简历原值，优化稿不得部分写入。
- **FR-025**: AI 超时、不可用、空内容、结构缺失、字段越界或版本冲突时，系统 MUST 返回“AI 服务暂时不可用”或明确版本冲突，且不得破坏已保存简历。
- **FR-026**: AI 优化稿 MUST 记录脱敏后的状态、基础版本、结果摘要、创建时间和处理结果，不得记录敏感会话或账户数据。

#### 技能档案聚合契约

- **FR-027**: 07 MUST 是技能档案聚合口径、成果归一结构、可见范围和投递快照的唯一定义者；03/04/05 是成果生产者，09 只消费 07 投递快照。
- **FR-028**: 07 MUST 复用以下已存在的 outcome 读取函数，不新造第二套成果存储或跨模块成果 provider：

```python
app.agri_skills.outcomes.list_learning_outcomes(
    user_id: int,
    kind: str | None = None,
) -> list[dict]

app.ecommerce_training.course_learning.list_ecommerce_learning_outcomes(
    user_id: int,
) -> list[dict]

app.handcraft_inheritance.outcomes.list_handcraft_learning_outcomes(
    user_id: int,
) -> list[dict]
```

- **FR-029**: 07 MUST 把来源成果归一为以下四类：

| Unified category | 03 source | 04 source | 05 source |
| --- | --- | --- | --- |
| `live_script` | 无 | `live_script` | 无 |
| `simulation_training` | 无 | `simulation_training` | 无 |
| `quiz_score` | `diagnostic_self_test`、`course_quiz` | `course_quiz` | `course_quiz` |
| `learning_record` | 无 | `course_completion` | `course_view`、`course_completion`、`craft_step`、`ar_usage` |

- **FR-030**: 03 的 `diagnostic_self_test` MUST 作为测验类成果保留 `is_formal=false`；03 的复诊记录本身 MUST NOT 进入四类成果，除非生产者未来另行暴露为 outcome。
- **FR-031**: 每个统一成果项 MUST 至少包含：

```text
item_id              # 由模块、来源类型和来源稳定 ID 组成的非空字符串
category             # live_script | simulation_training | quiz_score | learning_record
source_module        # agriculture | ecommerce | handcraft
source_type          # 生产者原始 kind/outcome_type
title
summary
score                # int | None，0-100 或来源既有口径
is_formal            # bool
occurred_at          # 带时区 ISO 8601
source_available     # bool
```

- **FR-032**: `item_id` MUST 在单一学员内稳定且可重复读取时去重，不得使用每次请求生成的随机 ID。
- **FR-033**: 技能档案列表 MUST 按 `occurred_at`、`category`、`item_id` 形成确定性排序；不得直接把 SQLite 行对象返回给前端或 09。
- **FR-034**: 单个来源不可用、无记录或返回非法记录时，系统 MUST 保留其他来源可用性，并对该来源返回空列表或明确不可用状态。

#### 技能档案可见范围与快照

- **FR-035**: 学员 MUST 能按单个统一成果项勾选或取消“企业可见”；本期 MUST NOT 以整档一个开关替代逐项控制。
- **FR-036**: 任意成果项首次出现时 MUST 默认不可见；缺少可见记录必须解释为不可见，而不是默认公开。
- **FR-037**: 可见范围保存 MUST 只影响该学员自己的可见项，MUST NOT 删除或修改 03/04/05 的来源记录。
- **FR-038**: 学员取消可见后，未来投递和技能档案企业投影 MUST 立即排除该项；已经创建的申请快照 MUST 保持不变。
- **FR-039**: 学员自己查看技能档案时 MUST 能看到全部可用成果及可见状态，可明确区分公开项和私密项。
- **FR-040**: 投递时若学员选择附带技能档案，07 MUST 只读取当前可见且 `source_available=true` 的成果生成快照。
- **FR-041**: 若附带选项开启但没有可附带成果，07 MUST 向 09 传递 `None`，并在界面按未附带处理。
- **FR-042**: 技能档案快照 MUST 使用以下顶层结构，且不得包含隐藏项、完整来源原始记录或内部审计字段：

```python
{
    "schema_version": 1,
    "generated_at": str,  # 带时区 ISO 8601
    "items": list[dict],  # FR-031 的可见成果字段
    "summary": {
        "live_script": int,
        "simulation_training": int,
        "quiz_score": int,
        "learning_record": int,
    },
}
```

- **FR-043**: 09 企业端 MUST 只展示投递时附带快照；学员后续可见范围、来源成果或当前技能档案变化 MUST NOT 回写历史申请。

#### 岗位浏览与规则推荐

- **FR-044**: 07 MUST 只读取当前由 09 `JobPositionProvider` 返回的已通过、未删除且有效发布时间职位；不得读取 09 表或缓存发布状态自行推断。
- **FR-045**: 岗位列表 MUST 至少展示标题、公司、薪资、地点和描述，并复用 provider 的 `published_at DESC, job_id ASC` 原始排序作为普通列表排序。
- **FR-046**: 页面顶部 MUST 提供独立“推荐岗位”区；推荐为空时显示“暂无推荐”，普通列表为空时显示“暂无岗位”。
- **FR-047**: 推荐候选池 MUST 只包含当前已上架职位，同一职位最多出现一次；推荐区与普通列表可使用同一 provider 结果但不得重复创建岗位数据。
- **FR-048**: 推荐排序 MUST 按以下优先级从高到低执行：

```text
1. 学员活动 job 兴趣标签与 job.category_id 精确匹配数量降序
2. 最近 90 天内产生任一 03/04/05 学习成果的活跃标记降序
3. 最近学习成果时间降序
4. job.published_at 降序
5. job.job_id 正序
```

- **FR-049**: 推荐匹配 MUST 以稳定类别 ID 计算，不得以公司名、职位标题或类别名称做模糊匹配。
- **FR-050**: 学习行为 MUST 只来自 07 已可读取的 03/04/05 outcome；不得为推荐新造浏览埋点、人才画像或第二套学习行为来源。
- **FR-051**: 学员没有任何 `job` 标签时，所有职位匹配数量按 0 处理；不得报错，仍可按学习行为、发布时间和稳定 ID 排序返回普通推荐。
- **FR-052**: 学员修改学习方向或兴趣标签后，下一次推荐读取 MUST 使用 01 最新值，不得缓存旧标签超过该次请求。
- **FR-053**: 职位详情 MUST 以 `job_id` 从 `get_published_position()` 读取；返回 `None` 时 MUST 显示不可用空态或返回未找到，不得回退到收藏快照、申请快照或旧列表。
- **FR-054**: 07 MUST NOT 生成、改写或审核职位描述，也不得调用 AI 对职位内容进行推荐或排序。

#### 投递前置校验与写入

- **FR-055**: 学员 MUST 能从已上架职位详情发起一次投递，并明确选择是否附带当前技能档案。
- **FR-056**: 投递前 MUST 按以下顺序执行服务端校验：

```text
1. 当前会话为 active student
2. get_published_position(job_id) 仍返回有效职位
3. 当前存在 FR-011 定义的已保存非空简历
4. 学员尚无同一 job_id 的申请
5. 从 09 状态读取 provider 重新读取申请集合后再次确认无重复
```

- **FR-057**: 无简历分支 MUST 拦截投递、返回可识别的 `resume_required` 结果并引导跳转简历编辑，不得创建申请。
- **FR-058**: 重复申请分支 MUST 返回“已投递该岗位”并禁止创建第二份申请或第二份企业通知。
- **FR-059**: 职位不再可见时 MUST 返回不可投递错误，列表和详情请求也不得返回该职位；过期页面提交失败后应刷新岗位来源。
- **FR-060**: 校验通过后，07 MUST 生成 FR-015 简历快照，并按学员选择传递 FR-042 技能档案快照或 `None`。
- **FR-061**: 07 MUST 只通过 09 `JobApplicationIntakeProvider.submit_application()` 创建申请，唯一注册入口为 `set_job_application_intake_provider()` / `get_job_application_intake_provider()`。
- **FR-062**: 09 当前冻结投递签名 MUST 原样复用：

```python
class JobApplicationIntakeProvider(Protocol):
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict: ...
```

- **FR-063**: `idempotency_key` MUST 由服务端根据学员和职位生成稳定值；同一学员重复提交同一职位或请求超时重试 MUST 复用同一键。
- **FR-064**: `submit_application()` 成功返回后，申请 MUST 出现在“我的投递”；企业通知由 09 在 provider 内触发，07 MUST NOT 再调用 02 发送投递通知。
- **FR-065**: 09 provider 返回的冲突、未找到、校验或不可用错误 MUST 映射为明确用户结果，不得把内部数据库异常或 provider 实例类型暴露给前端。
- **FR-066**: 07 MUST NOT 提供撤回、取消、删除申请、复制新申请或绕过重复校验的接口。

#### 学员侧申请状态读取

- **FR-067**: 07 MUST 复用 09 的申请状态权威记录展示“我的投递”，MUST NOT 建立第二套申请状态、状态历史或岗位关闭事实。
- **FR-068**: 09 MUST 增加并实现以下只读消费者契约，注册入口与现有企业 provider 使用同一 `backend/app/enterprise_console/providers.py` 模块及唯一扩展槽：

```python
class JobApplicationStatusProvider(Protocol):
    def list_student_applications(
        self,
        *,
        student_id: int,
    ) -> list[dict]: ...

    def get_student_application(
        self,
        *,
        student_id: int,
        application_id: str,
    ) -> dict | None: ...
```

- **FR-069**: 09 MUST 提供 `set_job_application_status_provider(app, provider) -> None` 与 `get_job_application_status_provider() -> JobApplicationStatusProvider`，并在 `configure_enterprise_providers()` 增加可选替换参数。
- **FR-070**: `list_student_applications()` MUST 只返回指定学员的申请，完整返回当前规模列表，按 `submitted_at DESC, application_id ASC` 排序。
- **FR-071**: 状态读取记录 MUST 至少包含：

```text
application_id
job_id
enterprise_id
enterprise_name
student_id
student_name
job_title
status
status_version
position_closed
position_closed_at
effective_status
effective_status_label
submitted_at
```

- **FR-072**: `effective_status` MUST 直接采用 09 的冻结规则：职位关闭且业务状态为 `pending` 时为 `closed`；职位关闭但业务状态已处理时为最新人工状态；未关闭时等于业务状态。
- **FR-073**: 学员侧五态标签 MUST 固定为：

```text
pending       -> 待处理
viewed        -> 已查看
intent        -> 意向沟通
unsuitable    -> 不合适
closed        -> 岗位已关闭
```

- **FR-074**: 已处理申请在 `position_closed=true` 时 MUST 同时保留最新人工状态和独立“岗位已关闭”标识，不得用 `closed` 覆盖企业已表达的“不合适”等状态。
- **FR-075**: `get_student_application()` 未找到或不属于当前学员时 MUST 返回 `None` 或标准未找到错误，不得泄露其他学员申请是否存在。
- **FR-076**: 07 MUST 不保存、推断或修改 09 的状态版本；每次读取直接使用 provider 最新结果，跨学员或未知申请必须拒绝。

#### 岗位收藏

- **FR-077**: 学员 MUST 能收藏或取消任一当前可见岗位，同一学员与 `job_id` 只能有一条有效收藏。
- **FR-078**: 收藏记录 MUST 保存收藏时间及收藏时的职位标题、公司、薪资、地点等展示快照，以便职位删除后仍可显示。
- **FR-079**: 收藏列表 MUST 集中展示全部未手动移除的收藏；默认按收藏时间倒序、`job_id` 正序。
- **FR-080**: 当职位仍由 `JobPositionProvider` 返回时，收藏列表 MUST 使用 provider 最新职位信息刷新展示快照并允许进入详情或投递。
- **FR-081**: 当收藏 `job_id` 不再由 provider 返回时，系统 MUST 标记“岗位已关闭”、禁用投递并保留收藏展示快照；若职位以后重新上架，下一次读取 MUST 恢复可用状态。
- **FR-082**: 已关闭收藏 MUST 保留到学员手动移除，不得按时间自动删除；移除收藏 MUST NOT 影响历史申请或通知。
- **FR-083**: 收藏和取消收藏 MUST 使用幂等结果；重复收藏不得产生重复项，重复取消不得报服务器错误。

#### 跨模块 provider、错误、时间与复用

- **FR-084**: 岗位读取 MUST 使用 09 已落地的：

```python
class JobPositionProvider(Protocol):
    def list_published_positions(self) -> list[dict]: ...
    def get_published_position(self, *, job_id: str) -> dict | None: ...
```

- **FR-085**: 07 MUST 把 09 岗位记录中的 `job_id`、`enterprise_id`、`enterprise_name`、`title`、`salary`、`location`、`category_id`、`category_name`、`description`、`review_status`、`version`、`published_at`、`updated_at` 原样视为生产投影字段；不得新增重复岗位表。
- **FR-086**: 岗位、投递和状态 provider MUST 都通过唯一 `set_*_provider` / `get_*_provider` 槽替换；07 MUST NOT 判断实现是否为占位或数据库实现。
- **FR-087**: provider 错误 MUST 保留可识别的 `code`、`message`、`details` 语义；07 不直接把 09 数据库错误文本或 traceback 返回用户。
- **FR-088**: 新增时间字段 MUST 使用带明确时区的 ISO 8601；新记录规范为 `+08:00`，排序和最近 90 天计算前 MUST 解析为带时区时间。
- **FR-089**: 跨模块稳定 ID MUST 使用非空字符串；来源 outcome 的既有整数稳定 ID 通过模块、来源类型和 ID 组合编码，不直接暴露为全局裸整数。
- **FR-090**: 07 MUST 复用 01 的 `get_profile_preferences()`、会话和兴趣标签；MUST NOT 读取或复制标签目录到本地配置。
- **FR-091**: 07 MUST 复用 03/04/05 的 outcome 读取函数以及 03 的 AI client/call-point 机制；MUST NOT 修改来源模块的成果语义或回写 `archive_written`。
- **FR-092**: 07 MUST 只通过 09 provider 创建和读取申请；MUST NOT 写入 02 通知表、建立第二消息中心或绕过 09 触发企业通知。

#### AI 边界与不做范围

- **FR-093**: 07 的唯一 AI 调用点 MUST 为 `resume_optimize`；推荐岗位、技能档案聚合、投递校验、状态读取和收藏 MUST 为零 AI 调用。
- **FR-094**: AI 不可用时 MUST 使用统一文案“AI 服务暂时不可用”，且简历手动编辑、岗位浏览、投递和状态查看路径全部保持可用。
- **FR-095**: 07 MUST NOT 提供 AI 自动投递、AI 自动修改保存、AI 岗位匹配说明生成、AI 面试或 AI 人才搜索。
- **FR-096**: 07 MUST NOT 实现企业主动搜索人才库、投递撤回、线上面试、电子签约、入职流程管理或农产品求购信息。

### Key Entities

- **Resume Draft**: 当前编辑中的三个结构化区块，未保存前不影响已保存版本或投递。
- **Saved Resume Revision**: 学员最后一次成功保存的结构化简历，包含版本、三个有序区块和保存时间；旧版本仅供并发控制与审计。
- **Resume Optimization Offer**: 一次 AI 优化的建议、完整改写稿、基础简历版本、状态和生成时间；学员采纳或放弃前不具有当前简历效力。
- **Skill Outcome Item**: 07 对 03/04/05 来源成果归一后的统一项目，包含稳定 `item_id`、四类之一、来源模块、来源类型、标题、摘要、得分、正式性、发生时间和来源可用性。
- **Skill Visibility Setting**: 学员对单个统一成果项的“企业可见”设置；缺失记录表示不可见。
- **Skill Profile Snapshot**: 投递时由当前可见且可用成果生成的不可变快照，包含结构版本、生成时间、去重项目和分类计数。
- **Published Job Projection**: 09 `JobPositionProvider` 返回的只读已上架职位，07 只消费不复制。
- **Job Recommendation Result**: 对已上架职位按兴趣标签匹配和学习行为信号计算出的确定性排序结果。
- **Job Application Request**: 一次由 07 发起、经 09 provider 接收的投递意图，包含职位 ID、学员 ID、简历快照、可选技能档案快照和幂等键。
- **Job Application Status Projection**: 09 `JobApplicationStatusProvider` 返回的学员侧申请记录，区分业务状态、有效状态和岗位关闭标识。
- **Job Favorite**: 学员与岗位的收藏关系，含收藏时间和用于删除后展示的职位快照，不包含当前申请状态。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 简历三区块创建、编辑、保存和读取测试中，100% 有效保存可再次读取；全空简历被拒绝率为 100%，未保存草稿进入投递快照的次数为 0。
- **SC-002**: AI 优化采纳、放弃、非法响应、超时和不可用测试中，100% 采纳只在显式确认后生成新保存版本，100% 放弃保持原版本，AI 自动覆盖已保存简历次数为 0。
- **SC-003**: AI 请求字段捕获测试中，100% 字段来自 `resume_optimize` allowlist；联系方式、账户 ID、令牌和技能可见设置泄露数为 0。
- **SC-004**: 03/04/05 四类成果归一测试中，来源记录覆盖率 100%，重复读取 `item_id` 去重率 100%，未处理来源异常隔离率 100%。
- **SC-005**: 技能可见范围测试中，默认隐藏项企业可见数为 0，未勾选项进入快照数为 0，跨学员读取拒绝率为 100%。
- **SC-006**: 投递快照测试中，100% 申请固定投递时简历和可见技能成果；投递后修改简历、可见设置或来源成果造成的历史快照变化数为 0。
- **SC-007**: 推荐排序测试中，兴趣标签精确匹配、90 天学习活跃、最近学习时间、发布时间和稳定 ID 五级顺序正确率为 100%；下架职位进入推荐数为 0。
- **SC-008**: 投递三分支测试中，无简历、重复投递和不可见职位均 100% 被拦截且申请增量为 0；有效投递成功并进入“我的投递”的比例为 100%。
- **SC-009**: 投递幂等测试中，同一学员和职位的重复请求、并发请求和超时重试导致第二次申请或第二条企业通知的数量为 0。
- **SC-010**: 学员申请隔离测试中，其他学员申请泄露数为 0，跨学员查看和修改申请拒绝率为 100%。
- **SC-011**: 申请状态测试中，待处理、已查看、意向沟通、不合适和岗位已关闭五种展示状态正确率为 100%；已处理关闭项保留人工状态并附加关闭标识的比例为 100%。
- **SC-012**: 收藏测试中，重复收藏产生重复项数为 0，关闭岗位投递次数为 0，关闭收藏在手动移除前的丢失数为 0。
- **SC-013**: provider 替换测试中，09 岗位、投递和状态 provider 替换后 07 调用签名不变率为 100%，07 直接写 09 表的次数为 0。
- **SC-014**: AI 边界测试中，除 `resume_optimize` 外的 07 路径 AI 调用次数为 0；AI 不可用时手动简历、岗位浏览、投递、状态和收藏可用率均为 100%。
- **SC-015**: 500 个已上架职位、5,000 个历史申请和每位学员 200 条成果的目标规模测试中，岗位列表、推荐、我的投递和技能档案在常规演示环境 2 秒内返回，且不使用分页或跨学员数据。

## Scope Boundaries

- 01 owns account identity, session validity, learning direction, `job` interest-tag catalog, and the initial resume association.
- 02 owns notification, unread state, message center, conversations and delivery deduplication. 07 only displays application outcomes after 09 triggers 02 events.
- 03/04/05 own source outcomes and their producer semantics. 07 reads existing outcome functions, defines the unified aggregation and visibility contract, and does not rewrite source records.
- 09 owns job lifecycle, review projection, application records, application status history, job-closed behavior, and the submission/status provider implementations.
- 11 owns job review actions and content moderation. 07 does not consume or replicate the review queue.
- This feature does not implement purchase requests, interviews, electronic contracts, onboarding, enterprise talent search, proactive invitations, application withdrawal, or resume export.
- AI resume optimization is the only AI capability in this feature and never writes the saved resume without an explicit student adoption action.

## Assumptions

- A student has exactly one resume association; 07 owns its structured content while 01 continues to create the association.
- “Saved resume” means a version with at least one non-empty education, work, or skills section; an empty association is not a resume for preflight purposes.
- Resume adoption creates a new saved revision after explicit confirmation; previous revisions remain internal audit data and are not exposed as a rollback feature in this release.
- Outcome functions can be called within the current authenticated student context and already enforce source-specific access or return only the requested student’s records.
- Diagnostic follow-up notes are not skill-profile outcomes; only a diagnostic self-test score returned by `list_learning_outcomes()` enters the unified `quiz_score` category.
- Job recommendation learning activity is a recency signal only. Category matching remains based exclusively on the stable active `job` interest-tag ID intersection; no category-name inference is allowed.
- A job missing from `JobPositionProvider` is treated as unavailable in lists, details, and favorites. Favorites retain their display snapshot and recover if the job later reappears.
- 09 currently implements `JobPositionProvider` and `JobApplicationIntakeProvider`; `JobApplicationStatusProvider` is the missing read contract this feature freezes and adds through the same provider module and registration pattern.
- The stable application ID remains a non-empty string independent from SQLite primary keys.
- All new timestamps use timezone-aware ISO 8601 values and natural-day or 90-day calculations use `Asia/Shanghai`.
