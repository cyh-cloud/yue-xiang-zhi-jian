# Feature Specification: 05-手工传承

**Feature Branch**: `v2/lixKRT/005-heritage-craft`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "手工传承子系统。实现四大非遗技艺学习、材料采购指南、教学视频交互、AR 分步操作指引、平台级积分体系，以及奖品兑换与履约管理；复用 01 的账户、会话、兴趣标签与技能档案边界，复用 02 的通知通道，复用 03/004 的方向感知课程机制；08 和 11 未实现期间按明确的占位与替换契约交付。"

## Clarifications

### Session 2026-09-17

- Q: 现有 003 课程观看和 004 训练是否在本期回填积分写入？ → A: 不追溯回填历史。本期接入 005 的有效学习行为，并把 004 新产生的四类成功训练记录接入积分服务；003 农业课程、004 电商课程和既有 004 训练历史进入待接入或后续补录边界，不伪造历史积分。
- Q: 08 未实现时，005 是否实现教师上传教学视频的 API？ → A: 不实现。005 本期只提供教学视频展示、审核状态过滤、待审核编辑语义和评论交互边界；教师上传、待审核编辑入口及文件管理归 08。
- Q: 11 未实现时，审核动作、奖品库、履约管理、预置内容和积分规则如何交付？ → A: 11 继续拥有管理端入口、审核动作和权威配置；005 提供可替换的只读内容/规则来源，并实现奖品兑换与履约领域状态，测试通过占位来源和受权限约束的领域契约完成。
- Q: 积分折算比率与每日上限没有给定具体数值时，占位系统如何验收？ → A: 规则数值必须由配置来源提供，占位值只用于演示和测试，不视为产品承诺；账号流水、每日封顶、有效期和并发规则必须可验证。
- Q: 是否接受非生产演示积分值？ → A: 接受。演示规则采用每 10 分钟有效学习折算 1 分、每个唯一成功训练记录 10 分、每日获取上限 60 分；这些值不构成正式业务常量。
- Q: 004 的直播话术、模拟评分、文案训练和客服训练是否计入积分？ → A: 计入。每位学员的每个唯一成功训练源记录在完成时获得一次训练积分，受每日上限约束；不追溯修改 004 历史记录，不伪造历史积分。
- Q: 学习时长采用什么计量与防挂机口径？ → A: 采用后端权威累计的活跃学习段。前端每 30 秒发送一次心跳，连续 3 分钟无心跳后暂停计分，单次连续学习段最多计 120 分钟；断点间隔不计，恢复后开启新的学习段并保留此前有效累计。
- Q: 普通管理员可以看到哪些兑换相关数据？ → A: 普通管理员可以查看用户详情和完整兑换记录；该口径覆盖此前 v1/v2 仅开放业务字段视图的限制。普通管理员仍不可配置积分规则或执行账号管理。
- Q: 08/11 尚未实现时，本期教学视频交付到哪一层？ → A: 只交付已审核视频的展示与播放。视频元数据和演示播放地址来自可替换的只读占位来源；上传和待审核编辑归 08，审核归 11；本期不实现教师上传、审核动作、评论举报或独立评论系统。
- Q: 积分自然年过期采用何种触发与通知机制？ → A: 定时任务与访问时补偿结算并用。自然年边界后由平台定时触发幂等批量结算；若定时未执行，学员访问积分账户时先补偿清零；每位受影响学员只能生成一次过期流水和一条含清零积分数量的 02 通知。
- Q: 学员确认收货采用什么交互和超时规则？ → A: 学员在已发放履约单上单击“确认收货”即完成核销，不要求二次确认，不设置超时自动核销；管理员仍可手工核销，未确认的履约单长期保持“已发放”。
- Q: 多人并发兑换同一奖品时如何解决冲突？ → A: 使用单次原子条件更新完成积分余额、库存和履约单变更；竞争失败请求不自动重试，返回“库存或积分已变化，请刷新后重试”，且不得产生积分或库存的部分扣减。
- Q: 需求文档与当前 005 spec 冲突时以哪份为准？ → A: 以本次会话确认后的 005 spec 为准，并同步修改 `docs/粤乡智匠——需求输入.md`，消除积分行为和积分规则配置中的旧口径。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 学习四大非遗技艺并断点续学 (Priority: P1)

学员选择广绣、潮汕木雕、石湾陶艺或阳江漆器，查看项目介绍与六个有序步骤，阅读每步的操作描述和实用技巧，查询材料采购指南，并在离开后从已完成步骤继续学习。

**Why this priority**: 技艺学习是 005 的核心学员价值，也是积分和后续履约体系的主要学习行为来源。

**Independent Test**: 使用四大技艺的占位内容分别完成查看介绍、完成 0 至 6 个步骤、离开后返回、查看材料指南和切换项目，验证进度、断点、步骤顺序与内容完整性。

**Acceptance Scenarios**:

1. **Given** 学员已登录，**When** 打开手工传承首页，**Then** 可看到且只能看到当前来源提供的四大非遗技艺及各自介绍。
2. **Given** 学员选择任一技艺，**When** 打开学习页，**Then** 系统按固定顺序展示恰好六个步骤，每步包含描述和实用技巧。
3. **Given** 学员完成若干步骤后离开，**When** 再次进入同一技艺，**Then** 显示已完成步骤数和断点，并允许继续未完成步骤。
4. **Given** 学员查看材料采购指南，**When** 打开指南，**Then** 每项材料包含名称、参考价格、购买渠道、注意事项和淘宝搜索关键词。
5. **Given** 学员重复提交已完成步骤或乱序提交，**When** 系统处理结果，**Then** 已完成步骤不回退、不重复计分，且学员仍可继续学习未完成步骤。
6. **Given** 学员中断学习超过 3 分钟，**When** 再次开始同一技艺，**Then** 中断间隔不计入学习时长，恢复后从新的活跃学习段继续累计。

---

### User Story 2 - 获取并管理平台积分 (Priority: P1)

学员通过有效学习行为获得积分，包括手工学习、课程观看以及 004 已完成的直播话术、模拟、文案和客服训练；系统查看当前余额和获取、消耗、退款和过期流水，按照超级管理员配置的行为折算规则和每日上限累计积分，并按配置的永久或自然年有效期规则处理到期积分。

**Why this priority**: 积分账户和流水是平台级共享基础设施，兑换商城依赖其余额、流水和有效期正确性。

**Independent Test**: 使用显式占位规则完成多条有效学习记录和四类 004 训练记录、跨日记录、重复事件、超过每日上限、兑换扣减、取消回退和自然年过期，验证余额、流水和通知。

**Acceptance Scenarios**:

1. **Given** 学员开始任一技艺步骤或 AR 指引并产生有效学习时长，**When** 学习时长达到积分折算条件，**Then** 系统生成获取流水并更新余额。
2. **Given** 学员当日已达到每日获取上限，**When** 继续产生有效学习时长，**Then** 超出部分不再折算积分，已获得积分和既有流水不变。
3. **Given** 同一学习事件因重试或重复上报被提交多次，**When** 系统处理，**Then** 只产生一次积分获取流水。
4. **Given** 学员查看积分页，**When** 加载账户与流水，**Then** 显示余额及按时间倒序排列的获取、消耗、退款和过期记录。
5. **Given** 积分规则配置为默认永久，**When** 学员获得积分，**Then** 该积分不自动过期。
6. **Given** 积分规则配置为按自然年过期，**When** 到达配置年度边界，**Then** 定时结算自动清零到期积分；若定时结算未执行，学员下次访问时补偿清零；余额同步减少，并只通过 02 发送一条含清零积分数量的通知。
7. **Given** 超级管理员修改有效期规则，**When** 规则保存，**Then** 只影响此后的到期计算，不追溯重算或扣减已发积分。
8. **Given** 学员完成一次 004 直播话术、模拟训练、文案训练或客服训练并形成唯一成功源记录，**When** 该完成事件首次进入积分服务，**Then** 系统按当前行为规则只奖励一次，重复上报不重复计分。

---

### User Story 3 - 兑换奖品并跟踪履约状态 (Priority: P1)

学员浏览已上架奖品，在余额和库存满足条件时兑换；系统原子扣减积分与库存并生成待发放履约单，之后按待发放、已发放、已核销流转，待发放状态允许取消并回退积分与库存。

**Why this priority**: 兑换与履约形成积分体系的闭环，涉及余额、库存、状态机、通知和管理员权限边界。

**Independent Test**: 分别覆盖积分不足、奖品下架、库存为零、并发兑换、待发放发放、待发放取消、已发放禁止取消、确认收货和通知；再以普通管理员与超级管理员分别检查字段可见性。

**Acceptance Scenarios**:

1. **Given** 奖品已上架且库存大于零，**When** 学员余额不足，**Then** 不创建兑换或履约单，并提示“积分不足，还差 N 分”。
2. **Given** 奖品已下架，**When** 学员查看或尝试兑换，**Then** 奖品置灰不可兑换。
3. **Given** 奖品库存为零，**When** 学员查看或尝试兑换，**Then** 奖品置灰并显示“已抢完”。
4. **Given** 余额与库存均满足，**When** 学员确认兑换，**Then** 系统在同一业务操作中扣减积分和库存、生成待发放履约单，并通过 02 通知学员。
5. **Given** 履约单处于待发放，**When** 管理员执行发放，**Then** 状态变为已发放并通过 02 通知学员。
6. **Given** 履约单处于已发放，**When** 学员单击确认收货，**Then** 状态立即变为已核销，不弹出二次确认，也不因时间经过自动核销。
7. **Given** 履约单处于待发放，**When** 学员或管理员取消，**Then** 状态变为已取消、积分回退、库存回滚并通过 02 通知学员。
8. **Given** 履约单已发放或已核销，**When** 任一方尝试取消，**Then** 系统拒绝且不改变积分、库存或状态。
9. **Given** 普通管理员打开履约或兑换视图，**When** 查看相关记录，**Then** 可查看用户详情、联系方式、完整兑换与履约信息，但不能配置积分规则或管理账号。
10. **Given** 超级管理员打开兑换记录，**When** 查看记录，**Then** 可查看完整兑换与履约信息并执行其权限范围内的全部管理操作。

---

### User Story 4 - 浏览教学视频并验证审核可见性 (Priority: P2)

学员在指定技艺详情页看到审核通过的教学视频并进行播放；待审核、已驳回和已下架资源不可见。待审核资源保持可编辑且不改变状态，已上架资源编辑后重新进入待审核并在审核期间不可见。

**Why this priority**: 教学视频补充技艺步骤内容，并验证先审后发、02 通知和跨模块边界。

**Independent Test**: 使用已通过、待审核、已驳回和已编辑待重审的视频记录，以及可播放/不可播放媒体来源，分别验证学员可见性、播放、状态保持和审核通知。

**Acceptance Scenarios**:

1. **Given** 视频已审核通过并挂接到指定技艺且媒体来源可用，**When** 学员打开该技艺，**Then** 视频可见并可播放。
2. **Given** 视频处于待审核或已驳回，**When** 学员打开技艺详情，**Then** 视频不出现在学员端。
3. **Given** 视频处于待审核，**When** 提交者通过 08 修改其内容，**Then** 修改生效且状态保持待审核。
4. **Given** 已上架视频被编辑，**When** 修改提交成功，**Then** 视频重新进入待审核并在审核期间从学员端不可见。
5. **Given** 审核动作产生通过或驳回结果，**When** 结果生效，**Then** 通过结果通知提交者已上架，驳回结果通过 02 通知并附审核意见。
6. **Given** 共享评论能力尚未接入，**When** 学员打开已通过视频，**Then** 不对学员展示可用的评论或举报入口，005 不建立独立评论、举报或讨论区实现。

---

### User Story 5 - 获取 AR 分步操作指引 (Priority: P2)

学员选择手工项目，AI 根据项目生成工具准备、操作要点和常见错误提示，并以步骤化方式展示；不存在 3D 模型或真实摄像头空间追踪。

**Why this priority**: AR 体验是手工实践的数字辅助能力，但明确属于 AI 无降级组，必须隔离 AI 失败对手动学习的影响。

**Independent Test**: 覆盖 AI 成功、空响应、超时、结构缺失、重复字段和 AI 不可用，验证只发布完整指引、失败保留项目选择且手动技艺学习不受影响。

**Acceptance Scenarios**:

1. **Given** 学员选择有效手工项目且 AI 可用，**When** 请求 AR 分步指引，**Then** 返回至少包含工具准备、操作要点和常见错误提示的完整步骤化结果。
2. **Given** AI 返回缺少任一部分、空内容、重复字段或不可解析结构，**When** 学员请求指引，**Then** 不展示残缺结果、不创建成功成果，并提示“AI 服务暂时不可用”。
3. **Given** AI 超时或服务不可用，**When** 学员请求指引，**Then** 保留所选项目和当前页面上下文，提示“AI 服务暂时不可用”，且技艺步骤学习仍可继续。
4. **Given** AI 指引成功展示，**When** 学员有效使用该指引，**Then** 使用时长可按积分规则计入获取积分。

---

### User Story 6 - 学习手工方向课程并产出学习成果 (Priority: P2)

学员浏览手工方向的已上架课程，查看推荐、记录观看进度与断点，并在完成后参加来源提供的有效 AI 课后测验。

**Why this priority**: 手工课程补全 005 的学习闭环，并验证 005 正确复用 03/004 已建立的方向感知课程机制。

**Independent Test**: 准备手工、非手工、未上架、无测验和有效测验课程，验证过滤、推荐、进度、完成、测验与成果边界。

**Acceptance Scenarios**:

1. **Given** 课程来源包含多个方向，**When** 学员进入手工课程区块，**Then** 只展示当前来源提供的已上架手工方向课程。
2. **Given** 学员存在兴趣标签或手工课程学习行为，**When** 查看“为你推荐”，**Then** 排序规则与 003/004 的共享课程机制一致，且排除已完成课程。
3. **Given** 学员观看课程后离开，**When** 再次打开课程，**Then** 从最近有效位置继续，最远进度和完成状态不回退。
4. **Given** 有效观看进度达到或超过 80%，**When** 保存进度，**Then** 课程标记为完成。
5. **Given** 课程已完成且来源启用了有效测验，**When** 学员提交答案且 AI 可用，**Then** 显示得分、逐题结果和讲解，并保留提交历史。
6. **Given** 课程测验 AI 不可用，**When** 学员提交答案，**Then** 保留当前答案，不生成或覆盖成绩，并提示“AI 服务暂时不可用”。
7. **Given** 005 产生学习成果，**When** 07 的统一技能档案接口尚未提供，**Then** 005 只保留可供交接的成果引用并明确未写入档案，不创建竞争性技能档案。

### Edge Cases

- 四大技艺中任一预置内容不足六个有效步骤、步骤顺序冲突或缺少说明时，该技艺不得作为完整可学习内容发布，并显示明确不可用状态。
- 材料指南缺少淘宝搜索关键词、参考价格或购买渠道时，不伪造缺失值；平台不参与采购交易，也不对价格和质量作担保。
- 重复、乱序、负数、超长或伪造的学习时长不得增加积分；跨设备重复事件只计入一次。
- 同一自然日累计获取达到上限后，后续有效学习仍保留进度，只停止新增积分。
- 自然年过期任务失败后，由重试或学员访问补偿完成结算；重复运行不得重复扣减或重复通知，余额不足时不得产生负余额。
- 积分规则来源不可用时，若存在最后有效规则则以只读方式使用；若不存在最后有效规则，则暂停积分累计、积分消耗、兑换和有效期清零，保留学习进度与既有余额，并提示“积分规则暂不可用，请稍后重试”。不得使用学员侧可修改值。
- 同一奖品并发兑换必须保证库存和积分不超扣；最多只有一个请求成功占用同一库存单元，失败请求不自动重试且不产生部分扣减，并提示“库存或积分已变化，请刷新后重试”。
- 履约状态转换重复提交时保持幂等；已发放或已核销状态不能被较低状态覆盖。
- 取消待发放履约时，积分回退和库存回滚必须同时成功；任一步失败时不得留下部分生效状态。
- 审核中的视频被再次编辑时仍保持待审核；已上架视频编辑后立即对学员隐藏，复审通过后恢复可见。
- 预置内容、奖品或视频来源替换后，直接使用稳定标识，旧记录仍可读取并标记来源不可用，不得因替换删除学员历史。
- AI 指引或课程测验失败不得删除技艺步骤进度、积分流水、课程进度、既有成绩或兑换记录。
- 会话过期、账户禁用或非学员角色访问时，按 01 的既有会话和角色路由处理，不创建 005 独立认证机制。
- 普通管理员从兑换或履约上下文查看用户详情、联系方式和完整兑换记录时必须成功；尝试配置积分规则或管理账号时必须拒绝。
- 08 或 11 替换来源提交不完整、重复或越权数据时，005 拒绝写入并以现有有效数据继续运行。

## Requirements *(mandatory)*

### Functional Requirements

**访问、复用与模块边界**

- **FR-001**: 学员面向的技艺学习、自有积分、兑换和履约接口 MUST 只允许已登录学员访问；管理员履约视图 MUST 通过独立且受 01 角色权限约束的接口暴露。005 MUST reuse 01 的账户、会话、禁用账户和角色路由。
- **FR-002**: 005 MUST 读取 01 当前兴趣标签用于手工课程推荐，MUST NOT 创建、复制或修改兴趣标签目录。
- **FR-003**: 审核结果、兑换成功、履约发放、履约取消和积分过期通知 MUST 通过 02 统一消息通道发送，MUST NOT 建立第二套通知、未读或公告机制。
- **FR-004**: 手工课程 MUST 复用 03 建立、004 扩展的单一方向感知课程 provider，005 MUST NOT 创建手工专用课程注册表或重复课程目录。
- **FR-005**: 005 的全部 AI 调用 MUST 使用 03/004 的调用点注册和字段 allowlist 模式，MUST NOT 发送密码、会话令牌、联系方式、账户标识或其他学员数据。
- **FR-006**: 005 MUST NOT 创建竞争性技能档案、可见范围、简历附带或企业展示存储；学习成果只保留为 07 可消费的交接记录。
- **FR-007**: 005 MUST NOT 实现教师上传、文件管理或待审核编辑入口；这些能力归 08，005 只定义其记录进入学员端的可见状态规则。
- **FR-008**: 005 MUST NOT 实现 11 的审核动作入口、奖品维护、履约管理后台、预置内容维护后台或积分规则配置界面。
- **FR-009**: 普通管理员与超级管理员 MUST 继续使用 01 的两类现有管理员角色；005 MUST NOT 发明额外角色或权限组。
- **FR-010**: 005 MUST reject cross-student access to all learning progress, point accounts, ledgers, redemptions and fulfillment records.
- **FR-011**: 08/11 尚未实现时，005 MUST 使用明确标记为演示用途、只读、可替换的来源提供手工内容、奖品目录、积分规则和教学视频状态。
- **FR-012**: 替换来源 MUST 使用稳定标识；来源不可用时，既有学员进度、积分和履约历史 MUST remain readable and require no data migration by students.
- **FR-013**: 005 MUST NOT 参考、导入或迁移冻结的旧系统代码、数据库或页面。
- **FR-014**: 手工方向在课程、兴趣和推荐中 MUST 统一使用现有 `handcraft` 语义，避免与电商文案产品类型或展示模块标识混淆。

**非遗技艺、步骤与材料指南**

- **FR-015**: System MUST provide exactly four crafts: 广绣、潮汕木雕、石湾陶艺、阳江漆器.
- **FR-016**: Each craft MUST expose an introduction covering origin/history and technical characteristics before its learning steps.
- **FR-017**: Each available craft MUST expose exactly six ordered learning steps, and each step MUST contain a non-empty description and practical tip.
- **FR-018**: System MUST record current completed-step count as an integer from zero to six for each student and craft.
- **FR-019**: System MUST save the learner's resume point so the next visit continues from the furthest completed step without losing earlier progress.
- **FR-020**: A repeated completed-step submission or out-of-order submission MUST NOT reduce progress, duplicate progress history or duplicate points.
- **FR-021**: Learning time for craft steps, AR guidance and course video MUST be accumulated by the platform from active learning segments. The learner experience MUST send a heartbeat every 30 seconds while active; a gap of 3 minutes without a heartbeat MUST pause accumulation; and one continuous learning segment MUST count at most 120 minutes. The gap between interrupted and resumed learning MUST NOT count, and previously accumulated valid time MUST remain.
- **FR-022**: Each craft MUST expose a material guide whose entries include material name, reference price, purchase channel, cautions and Taobao search keyword.
- **FR-023**: Material guidance MUST remain informational only; 005 MUST NOT place orders, process payments, guarantee prices, warrant quality or mediate procurement.
- **FR-024**: Missing or malformed craft content MUST produce an explicit unavailable state and MUST NOT be replaced with fabricated official content.
- **FR-025**: Replacing the preset craft source MUST preserve stable craft and step identifiers, learner progress and historical readability.
- **FR-026**: 005 MUST NOT provide craft attendance, assignments, grading, certificates or a craft-work trading marketplace.

**教学视频状态与评论边界**

- **FR-027**: Teaching videos MUST be associated with one craft using its stable craft identifier.
- **FR-028**: A teaching video MUST expose title, craft association, review status, source availability and a provider-supplied playback source. In placeholder mode, the playback source MUST be a non-production demo asset or external demonstration URL marked as replaceable.
- **FR-029**: Only videos whose review status is approved/published MUST be visible to students for a craft.
- **FR-030**: Pending, rejected, offline and unavailable teaching videos MUST NOT appear in student-facing craft pages.
- **FR-031**: A rejected video MUST expose its rejection opinion to the submitter through 02; rejection opinion MUST NOT be shown as part of the student-facing video experience.
- **FR-032**: A pending video MUST remain editable through the future 08-owned submission flow and MUST remain pending after an edit. In this release, 005 MUST validate this status contract through the replaceable source without exposing a teacher edit UI or API.
- **FR-033**: Editing an approved/published video MUST return it to pending review and make it unavailable to students until approval is recorded again.
- **FR-034**: Review approval/rejection actions remain owned by 11; 005 MUST only apply the resulting status and visibility behavior.
- **FR-035**: 005 MUST NOT implement teacher video upload, replacement-file upload, delete-file management, review actions, comment reporting or a second teacher submission workflow.
- **FR-036**: If a shared course/video comment capability is later available, comments and teacher replies MUST use it; 005 MUST NOT create a forum, a standalone discussion area or a second comment store.
- **FR-037**: Comment reporting and moderation MUST remain owned by 11. In this release 005 MUST NOT implement a report entry, report queue, moderation action or replacement comment workflow.
- **FR-038**: While the shared comment capability is unavailable, 005 MUST show the approved video without usable comment/report controls and MUST NOT silently create a replacement implementation.

**平台积分服务**

- **FR-039**: 005 MUST own the platform-level points account, immutable ledger, rule evaluation, daily-cap enforcement, expiry processing, spend, refund and balance calculation.
- **FR-040**: 11 MUST remain the authoritative source and entry for super-admin configuration of conversion ratio, discrete training weights, daily earning limit and expiry policy; 005 MUST read the latest effective rule before each affected operation and MUST NOT own a second editable rule configuration.
- **FR-041**: The points-service boundary MUST accept a valid learning event containing student identity, source module, source event identifier, event type and event time. Duration-based events MUST additionally contain server-validated active duration; discrete training events MUST additionally contain the validated training type. The boundary MUST return whether points were awarded and the resulting balance. Client-reported wall-clock duration alone MUST NOT be accepted.
- **FR-042**: A source event identifier MUST be idempotent per student and event type so retries cannot award duplicate points.
- **FR-043**: The platform earning policy MUST recognize craft-step active learning, AR-guidance active use, course-video viewing in any learning direction, and successful 004 live-script, simulation, copy-training and customer-service training records. In this release, craft learning, AR guidance, handcraft-course viewing and all four 004 training record types are integrated; other course directions remain pending integration.
- **FR-044**: 003 agriculture-course viewing and 004 e-commerce course viewing MUST NOT be retroactively backfilled with points in this release; no historical points may be fabricated.
- **FR-045**: Each unique successful 004 live-script generation, completed simulation, completed copy-training session and completed customer-service session MUST earn training points once. Historical 004 records existing before integration MUST NOT be backfilled unless a later specification explicitly requires it.
- **FR-046**: The pending integration list MUST include 003 agriculture-course viewing, 004 e-commerce-course viewing, and any future educational video source authorized by 08/11; each integration MUST call the shared points boundary rather than write balances directly.
- **FR-047**: Duration-based points MUST be derived from valid active duration using the current effective conversion ratio. Discrete training points MUST be derived from the current effective behavior weight for the exact training type, and both calculations MUST use deterministic documented rounding.
- **FR-048**: Daily earning MUST be constrained by the current effective daily limit using the platform time zone `Asia/Shanghai`; reaching the limit MUST stop further awards for that day without deleting learning progress. The learner experience MUST show one non-blocking notice per natural day that today's earning limit has been reached and learning progress will continue.
- **FR-049**: The ledger MUST contain one immutable entry for every successful award, spend, refund or expiration and MUST distinguish the source module and source event.
- **FR-050**: Ledger history MUST be returned newest first and MUST allow the student to distinguish earning, spending, expiration and cancellation refunds.
- **FR-051**: A student's points balance MUST never become negative through normal or concurrent operations.
- **FR-052**: The default expiry policy MUST be permanent when no natural-year expiry is configured.
- **FR-053**: When natural-year expiry is configured, points MUST expire at the platform-time-zone boundary of the applicable natural year, and the expired amount MUST be removed atomically.
- **FR-054**: Expiry MUST use a platform-scheduled idempotent batch settlement plus a lazy compensation check before account balance display or mutation. If scheduled settlement has not completed, the next account access MUST settle overdue amounts before continuing.
- **FR-055**: Expiry retries and lazy compensation MUST be idempotent. A successful expiry MUST create one expiration ledger entry per affected account and send exactly one 02 notification per affected student containing the cleared point amount; it MUST NOT create a batch summary notification.
- **FR-056**: Changing the expiry policy MUST apply only to future expiry calculations and MUST NOT alter or retroactively expire already awarded points.
- **FR-057**: Students MUST NOT be able to configure conversion ratio, discrete training weights, daily limit or expiry policy through the student experience.
- **FR-058**: If the authoritative points-rule source is unavailable, placeholder mode MUST use a clearly identified demo policy of 1 point per 10 valid minutes, 10 points per unique successful training record and a daily cap of 60 points. In production, 005 MUST use the last valid read-only rule when available; if no valid rule exists, it MUST pause point accrual, spending, redemption and expiry, preserve learning progress and existing balances, and show “积分规则暂不可用，请稍后重试”.

**奖品、兑换与履约**

- **FR-059**: System MUST expose only published rewards with reward name, required points, current stock and availability state to students.
- **FR-060**: 11 MUST remain the authoritative entry for reward creation, editing, publishing/offline status and stock maintenance; 005 MUST consume that source and MUST NOT provide a production reward-authoring capability.
- **FR-061**: A reward with insufficient stock MUST be non-selectable and marked “已抢完”; a reward that is offline MUST be non-selectable.
- **FR-062**: When a student lacks points, 005 MUST reject redemption and show “积分不足，还差 N 分”.
- **FR-063**: When all redemption validations pass, 005 MUST atomically deduct points, deduct stock and create one pending-fulfillment record in one transaction boundary.
- **FR-064**: Concurrent redemption requests MUST use an atomic conditional update and MUST NOT overdraw points or stock. Each successful request MUST reserve exactly one available stock unit; losing requests MUST NOT auto-retry or leave partial deductions and MUST show “库存或积分已变化，请刷新后重试”.
- **FR-065**: Successful redemption MUST send one 02 notification containing the consumed points and reward information.
- **FR-066**: Fulfillment state MUST support exactly 待发放 → 已发放 → 已核销, plus 待发放 → 已取消.
- **FR-067**: A pending fulfillment MAY be canceled by the student or an authorized administrator. Fulfillment state, points restoration and stock rollback MUST change in one atomic domain transaction; notification delivery MUST occur as a post-commit idempotent effect and MUST NOT be counted as part of the same storage transaction.
- **FR-068**: A canceled fulfillment MUST eventually produce one 02 notification containing the restored-points information. Retrying notification delivery MUST NOT repeat the rollback or create a duplicate user-visible notification.
- **FR-069**: Issued and verified fulfillments MUST NOT be cancellable, and no lower-state update may overwrite 已发放 or 已核销. A student MUST verify an issued fulfillment with one explicit confirmation action and MUST NOT be asked for a second confirmation; issued fulfillments MUST NOT auto-verify on a timer, and authorized administrators MUST retain manual-verification capability.
- **FR-070**: Repeated issue, cancel or verify requests MUST be idempotent and MUST NOT create duplicate ledger or notification events.
- **FR-071**: A student MUST be able to view their own redemption and fulfillment history with current status.
- **FR-072**: A normal administrator MUST be able to view user details and the complete redemption/fulfillment record from redemption-management contexts, including contact details and point flow. This visibility supersedes the earlier business-only fulfillment view.
- **FR-073**: A normal administrator MUST NOT configure points rules or perform account management, including user list, account status and password operations; those capabilities remain outside the normal-administrator role.
- **FR-074**: A super administrator MAY view complete redemption records and access all platform data permitted by the 01 role model.
- **FR-075**: Fulfillment cancellation, issuance and verification authorization MUST distinguish normal administrator and super administrator without redefining the two roles owned by 01.

**AR 分步操作指引**

- **FR-076**: The student MUST be able to select a valid craft or handcraft project before requesting AR guidance.
- **FR-077**: A successful AR-guidance result MUST be an object containing `craft_key`, a non-empty `tool_preparation` string list, a non-empty `operating_points` string list, a non-empty `common_errors` string list, and a non-empty ordered `steps` list. Each step MUST contain a contiguous positive `step_no`, a non-empty `title` and a non-empty `instruction`. The AI MAY choose the number of steps.
- **FR-078**: Any missing section, empty content, duplicated field, unsupported structure, timeout or unparsable response MUST be treated as AI unavailability and MUST NOT be published as a partial guide.
- **FR-079**: AI failure MUST preserve the selected project and current craft learning context, use the exact message “AI 服务暂时不可用”, and MUST NOT block manual craft-step learning.
- **FR-080**: Valid active AR-guidance use time MAY earn points through the shared points boundary, subject to conversion and daily-cap rules.
- **FR-081**: 005 MUST NOT provide 3D models, real camera device integration, spatial tracking or true augmented-reality rendering.

**手工课程与学习成果**

- **FR-082**: 005 MUST display only published courses whose direction is `handcraft` and whose authoritative data is supplied through the shared course-provider contract.
- **FR-083**: Course eligibility MUST validate published status, stable identifier, positive duration and usable tag references before display or progress actions.
- **FR-084**: The recommendation order MUST match 03/004: exact interest-tag intersection count descending, previously watched but incomplete before never watched, latest valid viewing time descending, effective progress descending, publication time descending, stable course identifier ascending.
- **FR-085**: 005 MUST record furthest valid position, latest resumable position, effective progress, active cumulative viewing time, completion state and timestamps.
- **FR-086**: Effective progress MUST be floor(furthest valid position / valid course duration × 100), clamped from 0 to 100; completion MUST occur at 80% or above.
- **FR-087**: Invalid course duration, negative/over-duration position and malformed progress MUST be rejected without changing existing progress.
- **FR-088**: Lower, duplicate or out-of-order progress reports MUST NOT reduce furthest progress, completion, active viewing time or course-learning points.
- **FR-089**: The AI course-quiz entry MUST be available only when the course is complete and the provider supplies an enabled, valid quiz.
- **FR-090**: A successful quiz submission MUST persist every attempt and mark only the latest valid score as formal, preserving all earlier attempts.
- **FR-091**: AI quiz failure MUST preserve course progress, completion and previous formal results, use the exact message “AI 服务暂时不可用”, and MUST NOT reveal stored answers as a fallback.
- **FR-092**: 005 MUST NOT create, publish, withdraw or author courses or quizzes; these actions remain owned by 08.
- **FR-093**: 005 MUST produce learning-outcome handoff references for step progress, AR usage and handcraft course completion/quiz results, but MUST NOT write them into a skill archive until 07 provides the unified interface. Every reference MUST expose `outcome_type`, stable `source_id`, `created_at`, `source_available`, `summary`, optional `score`, `is_formal` and `archive_written=false`.
- **FR-094**: Every 005 source record MUST remain available in its module-local history even when the future 07 skill archive becomes available.

**AI 调用点与统一失败表现**

- **FR-095**: All 005 AI calls MUST use the existing call-point registration and field allowlist model with the exact stable keys and fields listed below, and MUST NOT send sensitive account, contact or session fields.
- **FR-096**: All 005 AI calls MUST use the complete-response validation model where partial or token-streamed content cannot be published as a successful artifact.
- **FR-097**: All 005 AI calls MUST use the fixed user-facing failure message “AI 服务暂时不可用” for unavailable, timeout or malformed responses.
- **FR-098**: 005 MUST NOT use the 003 local pest knowledge base or any domain fallback for AR guidance or course-quiz grading.
- **FR-099**: Each AI point below MUST be independently testable and retryable after service recovery without deleting unrelated data.
- **FR-100**: The shared AI-call domain registry MUST classify `handcraft_ar_guidance_generate` as handcraft and `course_quiz_grade` by its actual course direction; 005 MUST NOT inherit an agriculture-only domain label for handcraft quiz grading.

| ID | Stable Call-Point Key | Allowlisted Fields | Required Success Result | Failure Behavior |
| --- | --- | --- | --- | --- |
| AI-01 | `handcraft_ar_guidance_generate` | `craft_key`, `craft_name`, `project_label` | 返回 FR-077 定义的完整对象：工具准备、操作要点、常见错误提示和有序步骤均有效 | 保留所选项目；不展示或保存残缺指引；提示“AI 服务暂时不可用”；无本地知识库或其他降级 |
| AI-02 | `course_quiz_grade` | `course_direction`, `course_summary`, `questions`, `answers` | 得分、逐题正误和逐题讲解完整 | 保留当前答案；不生成新成绩、不覆盖正式成绩；提示“AI 服务暂时不可用”；无本地答案或规则判分降级 |

**管理与占位操作契约**

- **FR-101**: Teaching-video review MUST expose a replaceable management-action contract accepting video stable identifier, `approve` or `reject`, reviewer role and optional rejection opinion. The placeholder adapter MUST allow tests to drive pending → approved/rejected and edited-approved → pending transitions; production wiring remains owned by 11.
- **FR-102**: Fulfillment management MUST expose a replaceable management-action contract accepting fulfillment identifier and `issue`, `cancel_pending` or `manual_verify`. The placeholder adapter MUST allow role-authorized tests to exercise all legal and illegal transitions; production wiring remains owned by 11.

### Key Entities *(include if feature involves data)*

- **Heritage Craft**: 四大非遗技艺之一，具有稳定标识、名称、介绍、顺序、来源状态和六个学习步骤。
- **Craft Step**: 某个技艺中的有序步骤，包含描述、实用技巧和学员完成状态来源。
- **Material Guide Entry**: 某项技艺的材料采购信息，包含名称、参考价格、购买渠道、注意事项和淘宝搜索关键词。
- **Teaching Video**: 挂接到一个技艺的教学视频记录，包含标题、审核状态、来源可用性、可替换播放来源和未来评论关联；上传和待审核编辑归 08。
- **Teaching Video Review Result**: 11 产生的通过、驳回或重审结果，包含审核意见和影响学员可见性的状态。
- **Learning Progress**: 学员对某个技艺步骤或手工课程的有效学习进度、断点、有效时长和完成状态。
- **Points Account**: 学员的平台级积分余额，所有模块获得、消耗、回退和过期均汇总到此账户。
- **Points Policy**: 11 权威维护、005 读取的折算比率、离散训练权重、每日获取上限和有效期规则。
- **Points Transaction**: 不可变的获取、消耗、回退或过期流水，包含来源模块、来源事件、数量、时间和余额影响。
- **Points Earn Event**: 其他模块向平台积分服务提交的有效学习事件，以稳定事件标识实现幂等。
- **Reward**: 11 维护的奖品目录项，包含名称、所需积分、库存、上架状态和来源状态。
- **Redemption**: 学员对奖品的一次兑换，关联积分消耗、库存占用和履约单。
- **Fulfillment**: 兑换后的履约状态记录，支持待发放、已发放、已核销和已取消。
- **AR Guidance Result**: AI 根据手工项目生成的完整分步操作指引，不属于真实 3D 或空间追踪资产。
- **Handcraft Course Progress**: 学员在手工方向课程上的进度、断点、完成状态和有效观看时长。
- **Handcraft Course Quiz Attempt**: 一项手工课程测验提交，保留得分、逐题结果、讲解和正式成绩标记。
- **Learning Outcome Handoff**: 005 提供给未来 07 技能档案的成果引用，不包含 005 自建的档案或可见性设置。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 四大非遗技艺在占位来源下 100% 具备介绍、恰好六个有效步骤和包含淘宝关键词的材料指南；步骤进度、断点和重复提交行为 100% 符合要求。
- **SC-002**: 在心跳计量、3 分钟空闲暂停、120 分钟单段上限、断点恢复、四类 004 成功训练、重复事件、乱序事件、跨日、达到每日上限、上限提示和规则变更测试中，100% 的积分余额、流水、提示和每日封顶结果正确，重复事件产生零重复积分。
- **SC-003**: 在默认永久、定时过期、定时失败后访问补偿、重试和重复触发测试中，100% 的到期清零、过期流水和逐人 02 通知正确，重复处理产生零重复扣减和零重复通知，余额不出现负数。
- **SC-004**: 本期积分获取覆盖 005 学习行为以及四类 004 新产生的成功训练记录；003 农业课程、004 电商课程和既有 004 训练历史记录的回填数量为 0，待接入清单完整可追踪。
- **SC-005**: 积分不足、奖品下架和库存为零三类校验在 100% 测试中正确拦截，并显示规定文案。
- **SC-006**: 并发兑换测试中，100% 成功请求均保持积分与库存一致，竞争失败请求得到规定提示且零自动重试、零部分扣减；超额兑换、负库存和负余额数量均为 0。
- **SC-007**: 履约状态机全分支测试中，100% 合法流转成功，100% 非法取消被拒绝；取消时积分回退和库存回滚在同一业务事务内完成，02 通知作为幂等提交后效果最终送达且不重复。
- **SC-008**: 普通管理员查看用户详情和完整兑换记录的可见率为 100%，积分规则配置和账号管理拒绝率为 100%；超级管理员完整记录和管理操作可见率、可用率均为 100%。
- **SC-009**: 教学视频状态测试中，100% 已通过且媒体可用的视频对学员可见并可播放，100% 待审核/已驳回/下架/媒体不可用视频不可播放，待审核编辑契约保持状态，已上架编辑后重新进入审核。
- **SC-010**: 本期教师上传、审核动作、评论、举报和独立讨论实现数量均为 0；共享评论未接入时评论/举报入口数量为 0，005 新建第二套评论存储数量为 0。
- **SC-011**: AI-01 和 AI-02 在不可用、超时、空内容、结构缺失和重复字段测试中，100% 显示“AI 服务暂时不可用”，创建残缺成果数量为 0，既有手动数据丢失数量为 0；AI-01 的成功结果 100% 符合 FR-077 字段结构。
- **SC-012**: 手工课程过滤、推荐、进度和测验测试中，100% 使用共享方向感知课程机制；005 新建课程 provider 注册表、重复课程目录或独立认证机制数量为 0。
- **SC-013**: 07 接口未接入时，005 写入技能档案的记录数量为 0，每条 handoff reference 的 FR-093 必填字段完整率为 100%，模块源记录可追踪率为 100%；未来接口接入后不删除任何模块历史。
- **SC-014**: 08/11 替换来源测试中，通过稳定标识替换预置内容、奖品、规则和视频状态来源后，学员体验无需修改，历史进度、积分和履约记录均可继续读取。
- **SC-015**: 跨学员读取或修改学习进度、积分账户、流水、兑换和履约记录的拒绝率为 100%，响应中泄露其他学员数据的数量为 0。
- **SC-016**: 对 005 全部 AI 调用执行请求捕获时，100% 字段来自对应 call-point allowlist，敏感字段和越界字段数量为 0，AR 指引与课程测验使用本地知识库或其他降级的次数为 0。
- **SC-017**: 教学视频审核和履约管理占位操作契约覆盖通过、驳回、发放、待发放取消、手工核销及全部非法转换，合法操作成功率 100%，非法操作拒绝率 100%。
- **SC-018**: 积分规则来源不可用测试中，有最后有效规则时只读复用率 100%；无最后有效规则时积分变更暂停率 100%，学习进度和既有余额丢失数量为 0，并显示规定提示。

## Dependencies and Placeholder Contracts

- **01-账户与门户（已实现，复用）**: Provides student, teacher, super-admin and normal-admin identity; session validity; disabled-account behavior; role routing; current interest tags; and the existing resume association. 005 MUST NOT redefine these capabilities.
- **02-消息与通知（已实现，复用）**: Owns delivery, unread/read state and notification presentation for review results, redemption, issuance, cancellation and points expiration. 005 only submits the required business event and payload.
- **03-农业技能（已实现，机制复用）**: Provides the single direction-aware course provider, generic recommendation/progress/quiz semantics, AI-call allowlist pattern and learning-outcome handoff precedent. 005 MUST NOT reuse 03’s local pest knowledge-base fallback.
- **04-电商运营实训（已实现，机制复用并接入平台积分）**: Demonstrates the same course mechanism with `ecommerce` and the pattern for module-local outcome references with no skill-archive write. Successful live-script, simulation, copy-training and customer-service records MUST connect to the shared points boundary without writing balances directly.
- **07-就业对接（尚未实现，前向依赖）**: Owns the assembled skill archive, unified write interface, visibility controls, resume attachment and employer-facing presentation. Until it exists, 005 retains only source records and handoff references.
- **08-教师工作台（尚未实现，前向依赖）**: Owns teaching-video upload, file management, teacher submission UI/API and editing while pending. In this release 005 provides only read-only video display/playback after approval, review-status filtering and the pending-edit state contract. The replaceable teaching-video source is the only integration point for authoritative 08 records.
- **11-系统管理后台（尚未实现，前向依赖）**: Owns review actions, rejection opinions, reward authoring/stock, fulfillment-management UI, preset-content maintenance and points-rule configuration. In this release 005 uses replaceable read-only providers for craft presets, teaching-video status, rewards and points rules, while 005 owns the redemption and fulfillment domain state machine and permission constraints.
- **External AI service**: Provides AR guidance generation and handcraft course-quiz grading. Both calls are no-fallback operations.

### Replaceable Provider Boundaries

- **Craft preset source**: One replaceable read-only source supplies the four crafts, six steps and material guides; default data is clearly marked as a demo source and is replaced by 11 without changing learner records.
- **Teaching video source**: One replaceable read-only source supplies approved video metadata/status and a demo playback source, and supports the status changes produced by 08/11; 005 exposes no competing teacher upload, review or moderation source.
- **Teaching-video review action source**: One replaceable management-action adapter accepts `approve`/`reject` with actor role and optional opinion, allowing the real 11 wiring or a test placeholder to drive status transitions required by FR-101.
- **Reward catalog source**: One replaceable read-only source supplies reward name, required points, stock and publication state; 11 remains the authoring authority.
- **Fulfillment admin action source**: One replaceable management-action adapter accepts `issue`, `cancel_pending` and `manual_verify`, allowing the real 11 wiring or a test placeholder to drive authorized transitions required by FR-102.
- **Points policy source**: One replaceable read-only source supplies duration conversion ratio, discrete training weights, daily earning limit and expiry policy; 005 always reads the latest effective value and does not expose student configuration. Demo values are 1 point per 10 valid minutes, 10 points per unique successful training and 60 points per day.
- **Course source**: The existing 03/004 course-provider registration is reused unchanged in contract shape, with `handcraft` as the requested direction.

## Assumptions

- This release does not implement the 08 teacher-upload API or the shared comment/report flow. Seeded/read-only teaching-video records with a demo playback source are sufficient to prove visibility filtering, playback and pending-edit contract behavior; upload, comments and reporting are verified when their owning modules exist.
- This release does not implement 11’s admin UI or authoring actions. Acceptance uses the domain state contract and permission rules with seeded/replaceable data, while the final admin entry remains in 11.
- Normal administrators may perform fulfillment operations and view user details plus complete redemption records; they still cannot configure points rules or manage accounts.
- The numeric duration ratio, discrete training weights and daily earning cap are deployment/configuration values, not product constants. Accepted demo values are 1 point per 10 valid minutes, 10 points per unique successful training and 60 points per day.
- A valid learning duration comes from server-validated active segments using a 30-second heartbeat, a 3-minute inactivity pause and a 120-minute per-segment cap. Arbitrary manual point entry, page-open duration, idle time, gap time and client-asserted future events are invalid.
- The daily cap notice is shown at most once per learner per natural day; it does not require a modal action and does not interrupt ongoing learning.
- The platform time zone for daily limits and natural-year expiration is `Asia/Shanghai`.
- Rewards and points are independent of real payments; no cash, shipping fee, refund, procurement order or external commerce transaction is involved.
- Existing course/video comment capability is owned by the relevant course/video system. If unavailable, 005 reserves the interface but does not create a second comment implementation.
- AR guidance has no fixed step count; the AI chooses a positive number of ordered steps while all three required sections remain structurally valid.
- 003 and 004 historical records are not backfilled in this release. New successful 004 training records are integrated into the shared points service; future agriculture/e-commerce course-viewing connections remain pending integration work.
- Learning outcomes produced by 005 remain module-local until 07 publishes the unified write interface; `archive_written` must not be claimed before then.
