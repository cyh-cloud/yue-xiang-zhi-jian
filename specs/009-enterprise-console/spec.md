# Feature Specification: 09-企业工作台

**Feature Branch**: `v2/lixKRT/009-enterprise-console`

**Created**: 2026-09-18

**Status**: Frozen

**Input**: User description: "enterprise-console: 企业工作台子系统。实现职位发布与管理、审核状态流转、求职申请筛选与状态标记、申请详情、求职沟通和数据看板；复用 01 的账户与会话，复用 02 的消息通知，接入 11 的通用内容审核 provider，并向 07 暴露岗位读取 provider。"

## Clarifications

### Session 2026-09-18

- Q: 职位删除后，已处理申请在企业和学员端如何处理？ → A: 申请记录保留为历史。企业端转为只读；学员端“我的投递”继续显示，原状态保持不变并附加“岗位已关闭”标识；仍为待处理的申请转为学员可见的“岗位已关闭”，不允许再次改标。
- Q: 职位删除采用软删除还是物理删除？ → A: 采用可审计的逻辑删除。删除后企业当前职位列表和学员岗位来源均不可见，但职位数据、申请关系、简历与技能档案快照保留；本期企业端不提供恢复入口。
- Q: 投递时间筛选和默认排序采用什么粒度？ → A: 按 `Asia/Shanghai` 自然日区间筛选，起止日期均包含；默认按投递时间倒序，时间相同按申请稳定标识正序。
- Q: 企业私信可触达哪些学员？ → A: 只能是已向本企业投递过的学员；关系在职位删除后继续有效，以保留历史沟通，但不得搜索未投递学员或主动邀约。
- Q: 学员未附带技能档案时如何展示？ → A: 仅展示结构化简历，不推断、不读取当前技能档案补造快照；若附带快照但学员没有可见成果，也按未附带处理。
- Q: 职位类别与 07 的推荐匹配使用什么维度？ → A: 职位类别选用 01 已维护的 `job` 兴趣标签稳定 ID；07 以该稳定 ID 与学员岗位类别标签做精确匹配，不以名称或自由文本匹配。
- Q: 岗位 provider 的签名归属与实现归属如何划分？ → A: 根据冻结登记表，07 是最终签名所有者，09 负责生产实现和注册；09 spec 中冻结的具体形状是本期实现承诺，07 spec 落地时必须原样确认或将差异通过适配器化处理，07 只依赖协议签名，不读取 09 的表、内部类或数据库。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 发布、编辑和删除职位 (Priority: P1)

企业填写职位标题、薪资、地点、类别和描述后提交审核。企业可以查看本企业全部职位及其审核状态，在待审核时直接修改，在被驳回后修改重提，也可以删除职位；职位通过审核后才进入学员岗位来源。

**Why this priority**: 职位生命周期是企业工作台的主入口，也是模块 07 获取可投递岗位的唯一权威来源。

**Independent Test**: 使用两个企业账户创建、编辑、删除不同状态职位，并由测试审核提供者驱动通过与驳回；验证学员来源可见性、版本、审核状态和跨企业隔离。

**Acceptance Scenarios**:

1. **Given** 企业已登录，**When** 提交有效职位表单，**Then** 创建唯一职位记录并进入待审核，学员岗位来源不可见，企业端显示“待审核”。
2. **Given** 职位待审核，**When** 企业编辑有效字段，**Then** 最新内容保存且仍为待审核，旧版本不能覆盖新版本。
3. **Given** 职位已通过并已上架，**When** 企业编辑任一可编辑字段，**Then** 职位立即回到待审核并从学员岗位来源移除，再次通过后恢复上架。
4. **Given** 职位已驳回，**When** 企业查看职位并修改后重新提交，**Then** 清除旧驳回意见并回到待审核。
5. **Given** 企业删除任一未删除职位，**When** 确认删除，**Then** 该职位立即从当前职位列表、学员岗位列表和学员详情中消失，并执行申请关闭矩阵。

---

### User Story 2 - 处理求职申请 (Priority: P1)

企业按职位、申请状态和投递日期筛选并排序本企业收到的申请，查看求职者简历快照和可选技能档案，并把申请标记为已查看、意向沟通或不合适；状态允许随时改标。

**Why this priority**: 申请处理把学员投递转化为企业可跟进的人才线索，并决定学员“我的投递”的最新状态。

**Independent Test**: 准备多职位、多状态、跨企业和跨日期的申请，验证筛选、排序、详情、状态改标、历史快照和通知，不使用其他企业的数据。

**Acceptance Scenarios**:

1. **Given** 企业收到多个申请，**When** 打开申请列表，**Then** 只显示投递到本企业职位的申请，并展示学员姓名、职位、投递时间和当前状态。
2. **Given** 申请具有不同职位、状态和投递日期，**When** 组合筛选并按投递时间排序，**Then** 结果完全匹配筛选条件，默认倒序且稳定。
3. **Given** 申请附带技能档案，**When** 企业查看详情，**Then** 展示投递时冻结的结构化简历和学员当时允许展示的技能档案。
4. **Given** 申请未附带技能档案或没有可见成果，**When** 企业查看详情，**Then** 仅展示结构化简历，不显示伪造或当前补取的档案内容。
5. **Given** 申请当前为任一可改标状态，**When** 企业改标为另一状态，**Then** 最新状态立即生效、学员端同步，并产生一条对应通知。
6. **Given** 企业未手动改标申请，**When** 企业只查看详情，**Then** 申请仍保持原状态，状态标记不强制。

---

### User Story 3 - 与投递学员沟通 (Priority: P2)

企业从申请记录或申请详情进入与投递学员的私信会话，查看历史线程并继续回复。

**Why this priority**: 沟通是投递后的自然下一步，但必须严格限制在本企业已收到的申请关系内。

**Independent Test**: 使用已投递、未投递、已关闭职位和跨企业账户验证入口、发送、回复、历史保留与拒绝行为。

**Acceptance Scenarios**:

1. **Given** 学员已向本企业投递过申请，**When** 企业打开该申请并进入私信，**Then** 可创建或复用双方唯一会话。
2. **Given** 学员与当前企业不存在投递关系，**When** 企业尝试构造私信请求，**Then** 请求被拒绝且不创建会话或消息。
3. **Given** 学员投递的职位后来被删除，**When** 企业或学员查看原会话，**Then** 历史消息保留，双方仍可按 02 的既有关系规则继续沟通。

---

### User Story 4 - 查看本企业数据看板 (Priority: P2)

企业查看在招职位数和累计收到简历数，统计口径只包含当前企业。

**Why this priority**: 看板提供职位库存和投递规模的稳定业务信号，且必须与职位、申请状态保持一致。

**Independent Test**: 为一个企业准备待审核、已通过、已驳回、已删除职位和多类申请，另准备第二个企业数据；验证两个指标和隔离性。

**Acceptance Scenarios**:

1. **Given** 本企业存在多个职位状态，**When** 查看看板，**Then** 在招职位数只等于当前已通过且未删除的职位总数。
2. **Given** 本企业收到待处理、已处理、岗位已关闭和历史职位申请，**When** 查看看板，**Then** 收到简历数等于累计唯一申请总数，包含全部处理状态和已删除职位产生的申请。
3. **Given** 其他企业存在职位和申请，**When** 本企业查看看板，**Then** 任何指标均不包含其他企业数据。

---

### User Story 5 - 向 07 提供已上架岗位 (Priority: P1)

模块 07 通过岗位 provider 读取当前已通过审核且未删除的岗位，用于岗位列表、详情、收藏和推荐；07 不依赖企业工作台内部数据结构。

**Why this priority**: 09 是岗位生产者，没有稳定只读契约，07 无法在不复制数据的情况下交付学员就业链路。

**Independent Test**: 替换 provider 注册槽后，07 兼容消费者无需修改即可读取相同的已上架岗位；验证状态、排序、稳定 ID、类别和不可见项。

**Acceptance Scenarios**:

1. **Given** 多个企业存在待审核、已通过、已驳回和已删除职位，**When** 消费者调用岗位 provider 列表和详情，**Then** 只返回已通过且未删除职位。
2. **Given** 已上架职位按发布时间和稳定 ID 可排序，**When** 调用列表，**Then** 默认按发布时间倒序、稳定 ID 正序，不使用数据库主键作为稳定 ID。
3. **Given** 已上架职位被编辑或删除，**When** 下一次调用岗位 provider，**Then** 编辑后的职位不再返回直至再次通过，删除后的职位永久不再返回。
4. **Given** 测试替换岗位 provider，**When** 07 兼容消费者重新读取，**Then** 调用签名和返回形状不变化。

### Edge Cases

- 职位必填字段为空、只有空白、类别不存在或已停用、长度超限时，拒绝保存且不改变已有有效版本。
- 两个并发编辑使用同一旧版本号时，只允许一个成功；失败方不覆盖新内容，不改变学员可见性，也不产生额外审核轮次。
- 待审核或已驳回职位无实际字段变化时，不创建新版本、不产生新审核轮次，状态保持不变。
- 已通过职位编辑提交审核失败时，旧已通过版本保持上架，新修改不能部分生效。
- 职位删除与申请改标并发时，只允许一种线性结果：先改标则申请作为已处理历史冻结；先删除则待处理申请转为岗位已关闭且不可再改标。
- 职位删除时没有申请、只有已处理申请、只有待处理申请或混合申请，均不得删除历史快照或产生跨职位通知。
- 同一待处理申请因重复删除请求处理时，只关闭一次、只产生一组学员通知。
- 已处理申请的对应职位删除后仍可查看历史申请详情，但改标入口不可用。
- 申请状态改成相同值时视为无变化，不写状态历史、不发送通知。
- 申请详情中的简历、技能档案和职位标题使用投递时快照；后续资料修改不得回写历史申请。
- 已附带技能档案但可见成果为零时按未附带展示，不报错、不回退到学员当前完整档案。
- 终止日期早于起始日期、非法日期或跨平台时区边界时，拒绝筛选请求并提示修正条件。
- 审核 provider 不可用、版本冲突或状态不可转换时，09 返回明确错误；不得伪造审核状态、上架职位或重复审核通知。
- 02 通知投递失败时，业务状态仍以已提交的数据为准；重试不得产生重复的用户可见通知。
- 企业令牌中的企业身份与请求中的职位、申请或会话归属不一致时，一律拒绝，不泄露对象是否存在。

## Requirements *(mandatory)*

### Functional Requirements

**身份、所有权与安全**

- **FR-001**: 企业工作台的所有职位、申请、私信和看板操作 MUST 只允许已登录且状态为 `active` 的 `enterprise` 角色访问，并复用 01 的账户、会话、禁用账户和角色路由规则。
- **FR-002**: 企业身份 MUST 从 01 的当前会话取得；客户端提交的企业标识不得改变数据所有权。
- **FR-003**: 职位、申请、状态历史和通知的读取与写入 MUST 强制按当前企业命名空间隔离；跨企业或不存在对象的访问必须拒绝且不得泄露对象存在性。
- **FR-004**: 09 MUST NOT 创建、编辑或绕过账户、会话、角色、密码或禁用状态规则。

**职位发布与审核状态**

- **FR-005**: 企业 MUST 能创建包含标题、薪资、地点、类别和描述的职位；所有字段均为必填，去除首尾空白后不得为空。
- **FR-006**: 职位类别 MUST 引用 01 中 `group_key = job` 的活动兴趣标签稳定 ID，并保存用于展示的类别名称快照；09 MUST NOT 建立第二套职位类别目录。
- **FR-007**: 成功创建职位时，09 MUST 先建立具有稳定 `job_id` 和当前版本的权威职位记录，再通过 11 的 `ContentReviewProvider` 以 `content_type = job_position` 提交首次审核。
- **FR-008**: 首次提交成功后，职位审核状态 MUST 为 `pending`；企业端显示“待审核”，学员岗位 provider、列表和详情均不得返回该职位。
- **FR-009**: 审核 `approved` 时，职位 MUST 变为学员可发现、可查看和可投递的已上架状态，并具有非空发布时间；审核结果通知由 11 的审核 provider 触发，09 MUST NOT 再发送一份重复通知。
- **FR-010**: 审核 `rejected` 时，职位 MUST 保持学员不可见；企业端显示“已驳回”和最新非空审核意见，并允许修改后重提。
- **FR-011**: 企业 MUST 可按待审核、已通过、已驳回筛选查看本企业全部未删除职位；删除职位不进入当前职位状态筛选结果。
- **FR-012**: 待审核职位 MUST 可直接编辑；有实际字段变化时保持 `pending` 并前进版本，无字段变化时返回原状态和原版本，不创建新审核轮次。
- **FR-013**: 已通过职位被编辑时 MUST 原子地进入 `pending`、清除发布时间，并在下一次岗位 provider 读取前立即从学员来源移除；再次通过后才恢复上架。
- **FR-014**: 已驳回职位修改并重新提交时 MUST 进入 `pending` 并清除旧驳回意见；提交失败时不得产生部分更新。
- **FR-015**: 所有创建、编辑和审核转换 MUST 使用 `expected_version` 乐观并发控制；旧版本、非法状态转换或 provider 冲突必须拒绝覆盖。
- **FR-016**: 09 MUST 只消费 11 的 `ContentReviewProvider` 签名，MUST NOT 实现 `approve`、`reject`、审核意见编辑或 05 视频专用 action 分支，也 MUST NOT 提供审核员入口。
- **FR-017**: 审核 provider 不可用时，创建或编辑 MUST 返回明确失败，且不得创建成功假象、改变旧已上架版本或部分写入学员可见状态。

**职位删除与历史**

- **FR-018**: 企业 MUST 能在确认后逻辑删除本企业未删除职位；删除后企业当前职位列表和学员岗位来源立即不再返回该职位。
- **FR-019**: 删除 MUST 保留职位审计数据、申请、简历快照、技能档案快照、状态历史和私信关系；本期 MUST NOT 提供企业恢复入口或物理清除入口。
- **FR-020**: 删除职位时，业务状态仍为 `pending` 且从未人工改标的申请 MUST 被设置为岗位关闭状态，冻结后续改标，并在学员端有效显示为“岗位已关闭”。
- **FR-021**: 删除职位时，已经改标为已查看、意向沟通或不合适的申请 MUST 保留最新业务状态并冻结为历史，同时附加“岗位已关闭”可用性标识。
- **FR-022**: 删除职位 MUST 为每位受影响的未处理申请学员产生一条“岗位已关闭”通知；重复删除或重试不得产生重复用户可见通知。
- **FR-023**: 删除职位 MUST NOT 改变职位关闭前已经合法产生的状态通知、会话、消息或历史申请内容。

### 职位状态机与学员可见性矩阵

| 职位状态 | 企业端标识 | 学员列表/详情 | 学员可投递 | 岗位 provider | 允许的企业动作 |
| --- | --- | --- | --- | --- | --- |
| `pending` | 待审核 | 不可见 | 否 | 不返回 | 编辑保持待审核；删除 |
| `approved` | 已通过/已上架 | 可见 | 是 | 返回 | 编辑转 `pending` 并临时下架；删除 |
| `rejected` | 已驳回 | 不可见 | 否 | 不返回 | 查看驳回意见；修改重提转 `pending`；删除 |
| 逻辑删除 | 当前列表不显示；历史申请可读 | 不可见 | 否 | 不返回 | 无恢复；申请按关闭矩阵冻结 |

状态转换 MUST 仅为：

```text
pending -> pending       # 有实际变化的编辑
pending -> approved      # 11 审核通过
pending -> rejected      # 11 审核驳回
approved -> pending      # 有实际变化的编辑，立即临时下架
rejected -> pending      # 修改并重提
any active state -> deleted  # 企业确认逻辑删除
```

**申请列表、筛选与详情**

- **FR-024**: 企业申请列表 MUST 只显示投递到本企业职位的申请，并至少显示学员姓名、职位标题、投递时间和当前业务状态。
- **FR-025**: 申请 MUST 支持按职位筛选、按待处理、已查看、意向沟通、不合适筛选，以及按投递日期区间筛选；职位筛选项必须包含仍有历史申请的逻辑删除职位，并使用投递时职位标题快照。
- **FR-026**: 投递日期筛选 MUST 使用 `Asia/Shanghai` 自然日，起始日和结束日均包含；非法或倒置日期范围必须拒绝。
- **FR-027**: 申请 MUST 支持按投递时间升序或降序排序；默认倒序，时间相同时按申请稳定标识正序作为确定性 tie-breaker。
- **FR-028**: 申请列表和详情 MUST 显示职位关闭可用性标识；职位关闭后，历史状态仍可见，但改标入口和直接改标请求必须被拒绝。
- **FR-029**: 申请详情 MUST 使用投递时冻结的结构化简历快照，不得读取并替换为学员当前简历。
- **FR-030**: 申请详情 MUST 只展示投递时附带且学员当时允许企业查看的技能档案快照；未附带或可见项为空时仅展示简历。
- **FR-031**: 09 MUST NOT 搜索人才库、按条件发现未投递学员、主动邀约、导出全量人才数据或建立第二套简历/技能档案存储。

**申请状态与通知**

- **FR-032**: 新申请的业务状态 MUST 为 `pending`；企业查看申请详情本身 MUST NOT 自动改标。
- **FR-033**: 企业 MUST 可把 `pending` 申请标记为 `viewed`、`intent` 或 `unsuitable`，并在这些已处理状态之间随时改标。
- **FR-034**: `pending` MUST NOT 作为人工二次改标目标；显示为已查看、意向沟通或不合适的申请不得由企业改回待处理。
- **FR-035**: 每次业务状态真实变化 MUST 以最新状态为准、立即在学员端生效，并通过 02 的 `emit_application_status_changed` 生成一条通知；相同值重复提交不通知。
- **FR-036**: 状态更新与通知触发 MUST 使用稳定事件 ID 和幂等边界；业务提交成功后通知投递失败不得回滚状态，后续重试不得重复通知。
- **FR-037**: 状态历史 MUST 保留每次真实变化的前后状态、操作企业、操作时间和版本；申请当前状态始终取最新成功变化。
- **FR-038**: 如果职位已关闭，`pending` 申请 MUST 冻结为学员有效状态“岗位已关闭”；已处理申请 MUST 冻结原业务状态并附加关闭标识，全部不得再次改标。
- **FR-039**: 学员端“我的投递” MUST 保留所有历史申请：未处理关闭项显示“岗位已关闭”；已处理关闭项显示最新已查看/意向沟通/不合适状态，并附加“岗位已关闭”标识。

**私信沟通**

- **FR-040**: 企业申请记录和详情 MUST 只为已投递到本企业的学员提供私信入口。
- **FR-041**: 09 MUST 通过 02 的现有消息与关系契约判断 `student-enterprise` 私信资格，MUST NOT 创建第二套会话、消息、未读或通知存储。
- **FR-042**: 企业 MUST NOT 对未向本企业投递的学员发起私信；入口隐藏和直接请求拒绝必须同时生效。
- **FR-043**: 投递关系一旦建立，即使职位后来删除，仍 MUST 满足 02 已定义的私信关系保留规则。
- **FR-044**: 企业 MUST NOT 群发私信、向全部申请人批量发送、发送公告或用私信替代系统通知。

**数据看板**

- **FR-045**: 在招职位数 MUST 等于当前企业审核状态为已通过且未删除的职位总数。
- **FR-046**: 收到简历数 MUST 等于当前企业累计收到的唯一申请总数，包含待处理、已查看、意向沟通、不合适、岗位已关闭和已删除职位产生的历史申请。
- **FR-047**: 看板 MUST 只读取当前企业数据；职位状态变化、申请新增、申请改标或职位删除后，下一次读取 MUST 反映最新口径。
- **FR-048**: 09 MUST NOT 在企业看板展示农产品求购数、其他企业聚合数据、人才库指标、招聘漏斗之外的入职/签约/面试数据或 AI 生成指标。

### 岗位 Provider 对外契约

- **FR-049**: 09 MUST 作为岗位生产者实现只读 `JobPositionProvider`，通过唯一注册槽 `job_position_provider` 暴露给 07；07 是协议签名所有者，09 是实现与注册所有者。
- **FR-050**: 09 MUST 提供 `set_job_position_provider(app, provider) -> None` 和 `get_job_position_provider() -> JobPositionProvider`，未注册时返回完整协议相符的默认数据库 provider。
- **FR-051**: 09 MAY 提供 `configure_enterprise_providers(app, *, job_position_provider=None) -> None` 作为启动期便利层；该函数只能委托唯一 setter，不得建立第二注册表。
- **FR-052**: Provider MUST 至少实现以下只读签名：

```python
class JobPositionProvider(Protocol):
    def list_published_positions(self) -> list[dict]: ...

    def get_published_position(self, *, job_id: str) -> dict | None: ...
```

- **FR-053**: Provider 列表和详情 MUST 只返回审核状态为已通过、未逻辑删除且发布时间有效的职位；待审核、已驳回、编辑重审中的职位和已删除职位必须不可见。
- **FR-054**: `get_published_position` 未找到可见职位时 MUST 返回 `None`；不得返回空字典、内部数据库行或隐式抛出“未找到”供消费者分叉。
- **FR-055**: Provider 职位记录 MUST 至少包含以下稳定字段：

```text
job_id                  # 非空字符串稳定标识
enterprise_id           # 正整数
enterprise_name         # 投递展示所需企业名称
title                   # 职位标题
salary                  # 薪资展示文本
location                # 工作地点
category_id             # 01 的 job 兴趣标签稳定正整数 ID
category_name           # 派发时的类别名称快照
description             # 职位描述
review_status           # 固定为 approved
version                 # 正整数版本
published_at            # 带时区的 ISO 8601 时间
updated_at              # 带时区的 ISO 8601 时间
```

- **FR-056**: Provider 列表 MUST 完整返回当前规模的列表，不暴露分页参数；默认按 `published_at` 倒序，再按 `job_id` 正序排列。
- **FR-057**: Provider 时间 MUST 使用带明确时区的 ISO 8601 字符串；新记录统一采用 `YYYY-MM-DDTHH:MM:SS+08:00` 形状。
- **FR-058**: Provider 边界错误 MUST 可按 `code`、`message`、`details` 识别，并区分校验、未找到、冲突、不可用和拒绝访问；不得把内部数据库异常直接暴露给 07。
- **FR-059**: 07 的推荐 MUST 仅使用稳定 `category_id` 与学员岗位类别标签精确匹配；09 MUST NOT 实现 07 的推荐排序或复制学员兴趣标签目录。
- **FR-060**: 替换 provider 时 MUST 只替换注册槽，07 兼容消费者不得因来源替换而修改调用分支或识别占位实现。

**ContentReviewProvider 接入**

- **FR-061**: 09 MUST 通过 11 的通用 `ContentReviewProvider` 接入审核，调用 `submit_for_review`、`get_review_status` 和 `edit`，不得复制 05 的视频专用 `apply` action 或本模块自建审核状态机。
- **FR-062**: 09 MUST 在首次审核前持久化职位并传入稳定 `job_id`、企业提交者 ID、最新 `expected_version` 和职位审核 payload；审核 provider 不负责创建职位或生成岗位 ID。
- **FR-063**: `job_position` 审核 payload MUST 至少包含标题、薪资、地点、类别稳定 ID 和描述，并与企业当前可编辑版本一致。
- **FR-064**: 审核状态、版本、驳回意见和发布时间 MUST 以 provider 返回的通用审核记录为准；进入待审核或通过状态时清除旧驳回意见，通过时必须有发布时间，驳回或编辑重审时清除发布时间。
- **FR-065**: 09 MUST NOT 调用 02 发送审核通过或驳回通知；审核状态与通知 outbox 的提交边界、去重和重试归 11 的 provider。
- **FR-066**: 审核身份 MUST 由 01 会话覆盖；09 不得信任客户端传入的审核员 ID 或角色，也不得提供普通企业绕过审核直接上架职位的路径。

**通知与复用边界**

- **FR-067**: 09 MUST 通过 02 的现有事件函数发送申请投递成功、申请状态变化和职位关闭通知，MUST NOT 直接写 02 的通知表或建立第二消息中心。
- **FR-068**: 09 MUST 通过 02 当前 `MessagingSourceProvider` 桥接关系向私信模块提供本企业申请关系与投递学员集合，不得让 02 读取 09 内部数据库实现。
- **FR-069**: 09 MUST 复用 01 的企业账户、会话、角色、标签目录和路由；MUST NOT 为企业工作台建立第二套身份或类别数据。
- **FR-070**: 09 MUST 复用 02 的会话、消息、通知、未读、清除已读和去重规则；本模块只拥有业务状态变化和触发事件。
- **FR-071**: 09 MUST 复用 11 的审核 provider；在 11 尚未实现的测试或占位阶段，只允许注入完整协议相符的审核 adapter，替换时不得修改 09 的业务分支。
- **FR-072**: 09 MUST consume 07-owned structured resume and skill-profile snapshots; it MUST NOT create a competing resume, skill archive, visibility, or application-snapshot authority.

**AI 边界与范围**

- **FR-073**: 09 MUST NOT call any AI model or AI gateway for job creation, review, application filtering, status marking, messaging, dashboard calculation, or any other behavior in this feature.
- **FR-074**: 09 MUST NOT implement talent search, proactive invitations, interviews, offers, electronic contracts, onboarding, employee management, or purchase-information management.
- **FR-075**: 09 MUST NOT expose review decisions, review queues, platform-wide job management, comment moderation, or super-admin data-management capabilities; those remain owned by 11.

### Key Entities

- **Job Position**: 企业拥有的职位记录，包含稳定岗位 ID、企业归属、标题、薪资、地点、类别稳定 ID 与名称快照、描述、审核状态、版本、发布时间、逻辑删除时间和时间戳；其状态决定学员可见性和投递资格。
- **Job Review Record**: 由 11 通用审核 provider 拥有的职位审核状态快照，与职位稳定 ID 一对一关联，包含审核状态、版本、驳回意见、发布时间和提交者。
- **Job Application**: 学员向某一职位提交的一次申请，包含非空字符串稳定申请 ID、企业、职位、学员、投递快照、业务状态、职位关闭状态、当前版本和投递时间。
- **Resume Snapshot**: 投递时冻结的结构化简历内容，后续简历编辑不得改写历史申请。
- **Skill Profile Snapshot**: 可选附带且已按学员可见范围过滤的技能档案快照；缺失时为空，不表示申请无效。
- **Application Status History**: 每次真实状态改标的前后状态、操作企业、事件 ID、版本和时间；当前状态取最新成功记录。
- **Applicant Relationship**: 学员至少向某企业提交过一次申请的持久证据，用于私信资格并在职位删除后继续保留。
- **Enterprise Dashboard Metrics**: 当前企业范围内、可随时从职位和申请权威记录重算的在招职位数与累计收到简历数。
- **Job Position Provider Record**: 面向 07 的只读已上架职位投影，包含稳定标识、企业展示名、职位字段、稳定类别 ID、版本和发布时间。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 职位状态测试覆盖 `pending -> pending`、`pending -> approved`、`pending -> rejected`、`approved -> pending`、`rejected -> pending` 和删除分支，100% 合法转换成功，100% 非法或旧版本转换被拒绝。
- **SC-002**: 对每种职位状态验证学员列表、详情、投递资格和岗位 provider，100% 的待审核、已驳回、编辑重审和已删除职位不可见，100% 的已通过职位可见且可投递。
- **SC-003**: 删除职位时覆盖无申请、仅待处理、仅已处理和混合申请四类场景，100% 待处理申请关闭并通知一次，100% 已处理申请保留原状态和关闭标识。
- **SC-004**: 学员“我的投递”测试中，100% 的未处理关闭项显示“岗位已关闭”，100% 的已处理关闭项保留最新状态并附加关闭标识，历史申请不丢失。
- **SC-005**: 申请列表的职位、状态、日期组合筛选和升降序测试中，结果正确率为 100%；默认排序始终为投递时间倒序、申请稳定 ID 正序。
- **SC-006**: 每次真实人工改标都在学员端同步最新状态并产生恰好一条通知；重复相同状态、旧版本或关闭后请求的通知增量为零。
- **SC-007**: 申请详情测试中，100% 附带且可见的技能档案正确展示，100% 未附带或无可见成果的申请只展示简历，隐藏成果泄露数为零。
- **SC-008**: 跨企业与未投递学员测试中，职位、申请、看板、详情、改标和私信越权访问拒绝率为 100%。
- **SC-009**: 看板测试中，在招职位数与已通过未删除职位数一致率为 100%，收到简历数与累计唯一申请数一致率为 100%，其他企业数据混入数为零。
- **SC-010**: 岗位 provider 替换测试中，100% 的消费者调用保持相同签名和字段；可见岗位集合、排序和状态过滤结果不变，待审核/驳回/删除项泄露数为零。
- **SC-011**: 审核接入测试中，100% 的创建、编辑和重提使用通用审核记录与版本，09 产生的重复审核通知数为零。
- **SC-012**: 通知失败和重试测试中，业务状态不因投递失败回滚，重试后每位接收者的用户可见通知重复数为零。
- **SC-013**: 500 个职位和 5,000 个申请的目标测试规模下，企业列表、筛选和看板操作在常规演示环境 2 秒内给出结果，不加载其他企业明细。
- **SC-014**: 该功能自动化验证中，AI 调用次数为零；人才库搜索、主动邀约、面试、签约和入职功能入口数量为零。
- **SC-015**: 每次成功创建申请都为对应企业产生恰好一条投递通知；重复提交、重试或同一幂等请求产生的通知增量为零。

## Scope Boundaries

- 01 owns enterprise account creation, login, session validity, disabled-account handling, role routing, and the authoritative `job` interest-tag catalog.
- 02 owns private conversations, message retention, notification delivery, unread state, clear-read behavior, and deduplication. 09 owns only job and application business state plus event triggers.
- 07 owns job browsing and recommendation for students, structured resume editing, skill-profile aggregation and visibility, application creation, application snapshots, favorites, and student-facing “我的投递”.
- 11 owns the generic content-review provider, review decisions, review queues, review notifications, and platform-wide overrides. 09 never performs an approval or rejection itself.
- This feature does not implement a student-facing job list, recommendation ranking, resume editing UI, skill-profile maintenance, favorites, or application submission UI; those remain with 07.
- This feature does not implement agriculture purchase requests, interviews, electronic contracts, onboarding, employment records, or any post-application recruitment workflow.
- This feature does not hard-delete jobs or provide job restoration. Logical deletion preserves history and closes or freezes applications according to the state rules.
- This feature does not add AI calls, AI-generated job descriptions, AI applicant ranking, or AI communication assistance.

## Assumptions

- Enterprise accounts and enterprise profile display names are created or maintained by 11 and authenticated by 01; enterprise self-registration remains outside this feature.
- Until 07 is implemented, application records required to prove 09 behavior may be supplied through a replaceable test fixture or intake adapter that preserves the specified snapshots; 07 remains the production producer of applications.
- Until 11 is implemented, a complete `ContentReviewProvider` test adapter can drive submit, approve, reject, edit and conflict outcomes; the production registration is replaced once without changing 09 business branches.
- A stable job identifier is a non-empty string and is independent from any internal SQLite primary key.
- A stable application identifier is a non-empty string and is independent from any internal SQLite primary key.
- All new timestamps are stored and returned as timezone-aware values; natural-day filters and display boundaries use `Asia/Shanghai`.
- A job has exactly one current category selected from the active `job` interest-tag catalog. If the category later becomes inactive, the stored display-name snapshot remains visible but the category no longer gains recommendation matches.
- “Unprocessed application” means an application whose business status is still `pending` and which was never manually marked by the enterprise.
- A job is considered on-sale only while its review status is approved, it is not logically deleted, and it has a valid publication time.
- Application statistics count unique application records, not students, messages, résumé edits, or repeated requests.
