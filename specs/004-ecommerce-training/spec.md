# Feature Specification: 04-电商运营实训

**Feature Branch**: `v2/lixKRT/004-ecommerce-training`

**Created**: 2026-09-16

**Status**: Draft

**Input**: User description: "电商运营实训子系统。实现直播话术生成、文字直播间模拟训练与四维评分、文案提示词训练、店铺装修指导、客服模拟训练，以及仅面向电商方向的课程筛选、推荐、学习进度和 AI 课后测验。严格复用 01 的账户、会话、兴趣标签和学习成果边界，复用 03 建立的课程 provider 机制与课程学习机制；所有 004 AI 功能均无降级，不可用时统一提示“AI 服务暂时不可用”。"

## Clarifications

### Session 2026-09-16

- Q: 01 当前未定义技能档案写入契约时，004 应如何写入技能档案？ → A: 等待 07 定义统一写入接口；在接口明确前，004 只保存自身训练与学习源记录，不建立竞争性档案存储，也不把成果标记为已写入技能档案。
- Q: 直播间模拟训练的四维评分应采用什么刻度、权重和总分规则？ → A: 每个维度采用 0–100 整数分，四维等权各占 25%；总分按四维加权平均后取整数；每个维度单独给出改进建议。
- Q: 一次直播间模拟训练应如何组织五个预设场景？ → A: 一次训练只选择一个场景；该场景可包含一个或多个有序环节；所有环节完成后对整次训练统一评分并生成一条训练记录。
- Q: 直播话术重新生成或换风格后应如何处理旧成功版本？ → A: 保留全部成功版本；最新成功版本作为模块当前结果；每个成功版本均作为独立学习成果，待 07 接口就绪后分别进入技能档案。
- Q: 文案提示词训练如何评价评判一致性与提示词优化效果？ → A: 学员评判与 AI 参考评判的一致性按 0–100 分评价；提示词优化效果也按 0–100 分评价；两项均须给出文字理由和对应证据。
- Q: 客服模拟训练如何结束，是否设置轮数上限？ → A: AI 判定练习目标是否达成并建议结束，学员确认后才结束并生成总结；不设轮数上限，AI 不得自行终止训练。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 生成完整直播话术 (Priority: P1)

学员输入商品名称、卖点和价格等信息，选择热情、专业或幽默风格，生成包含开场白、产品介绍、互动话术和促单话术的完整直播脚本；学员可重新生成或切换风格，并在历史记录中回看输入与输出。

**Why this priority**: 直播话术生成是电商实训最直接的内容生产入口，也是学员进入其他训练前的首个可独立交付能力。

**Independent Test**: 使用三种风格、多次重新生成、AI 成功和 AI 不可用路径，验证脚本结构、风格切换、最新结果、记录留存和固定错误提示。

**Acceptance Scenarios**:

1. **Given** 学员输入有效商品信息并选择任一支持风格，**When** AI 可用且生成成功，**Then** 系统展示同时包含开场白、产品介绍、互动话术和促单话术的非空完整脚本。
2. **Given** 已有一份生成结果，**When** 学员使用同一输入重新生成或更换风格，**Then** 新结果成为当前结果，原成功记录仍可在历史中回看。
3. **Given** AI 不可用或返回无效结构，**When** 学员提交生成请求，**Then** 系统不展示残缺脚本、不创建成功成果，保留输入并提示“AI 服务暂时不可用”。

---

### User Story 2 - 完成文字直播间模拟训练并获得四维评分 (Priority: P1)

学员选择直播间场景；所选场景可包含一个或多个有序环节。学员以文字逐环节提交话术，在提交前可修改内容；全部环节完成后，对整次训练统一给出语速节奏、情绪感染力、互动引导和卖点突出四个维度的量化评分、总分与改进建议，并可在历史中回看。

**Why this priority**: 模拟训练将话术知识转化为可评价的练习闭环，是电商实训与普通课程浏览之间的核心差异能力。

**Independent Test**: 分别完成五个预设场景，验证文字编辑、提交、四维评分、改进建议、记录回看及 AI 不可用路径。

**Acceptance Scenarios**:

1. **Given** 学员进入模拟训练，**When** 查看预设场景，**Then** 可选择开场白、产品介绍、互动引导、促单话术或异议处理之一开始一次独立训练。
2. **Given** 学员选择了一个包含多个环节的场景，**When** 查看训练流程，**Then** 系统按固定顺序展示该场景的全部环节，并保存每个环节的文字话术。
3. **Given** 学员正在编辑某环节文字话术，**When** 尚未提交，**Then** 可反复修改；提交后该环节按训练规则固定。
4. **Given** 学员完成所选场景的全部环节且 AI 可用，**When** 提交训练，**Then** 系统基于全部环节统一给出四个维度的 0–100 整数分、逐维改进建议，并展示等权加权平均后的整数总分。
5. **Given** 学员尚未完成所选场景的全部环节，**When** 尝试结束训练，**Then** 系统不得生成统一评分或完成记录，并保留已提交环节和未提交草稿。
6. **Given** AI 不可用或评分结构无效，**When** 学员提交训练，**Then** 系统不提供伪造评分、不完成训练，保留当前文字输入并提示“AI 服务暂时不可用”。

---

### User Story 3 - 通过文案案例和提示词优化训练提升判断能力 (Priority: P2)

学员选择商品类型或场景，由 AI 现场生成劣质文案案例；学员先指出问题并说明理由，再查看 AI 参考评判，随后编写优化提示词，由 AI 生成新版文案并点评新旧版本差异和提示词优化效果。

**Why this priority**: 该训练强调判断和提示词设计，而不是替学员一键产出成品文案，补齐电商文案能力的学习闭环。

**Independent Test**: 完成一次从案例、学员评判、参考评判、优化提示词到新版文案对比点评的五步流程，并覆盖每一步 AI 失败。

**Acceptance Scenarios**:

1. **Given** 学员选择商品类型或场景，**When** 开始训练且 AI 可用，**Then** 系统生成一份明确标记为教学案例的劣质或失败文案。
2. **Given** 学员已阅读案例，**When** 提交包含问题和理由的文字评判，**Then** 系统保留学员评判、展示 AI 参考评判，并给出 0–100 分的一致性与对应文字理由。
3. **Given** 学员提交优化提示词且 AI 可用，**When** 新文案生成并完成点评，**Then** 系统同时展示新旧两版文案、可见差异、0–100 分优化效果及支撑该评分的文字证据。
4. **Given** 任一 AI 步骤不可用或返回无效内容，**When** 学员执行该步骤，**Then** 系统停留在当前步骤、保留已完成内容和当前输入，并提示“AI 服务暂时不可用”。
5. **Given** 学员查看可用操作，**When** 尝试绕过案例评判和提示词训练，**Then** 不存在一键生成成品文案的入口。

---

### User Story 4 - 获取完整店铺装修指导 (Priority: P2)

学员输入店铺类型、目标平台和风格偏好，获得包含首页布局、色彩方案、详情页结构和导航分类的装修方案，并可回看历史方案。

**Why this priority**: 店铺装修指导为电商运营提供可执行的结构化方案，但不依赖真实平台或店铺连接。

**Independent Test**: 使用不同平台和风格输入生成方案，验证四部分结构、记录回看和 AI 不可用路径。

**Acceptance Scenarios**:

1. **Given** 学员输入有效的店铺类型、平台和风格偏好，**When** AI 可用且方案有效，**Then** 系统展示首页布局、色彩方案、详情页结构和导航分类四部分。
2. **Given** 学员已生成方案，**When** 打开历史记录，**Then** 可回看原始输入和完整方案。
3. **Given** AI 不可用或方案结构不完整，**When** 学员请求生成，**Then** 系统不创建成功方案记录、保留输入并提示“AI 服务暂时不可用”。

---

### User Story 5 - 完成客服模拟训练 (Priority: P2)

学员选择预设咨询场景，AI 扮演客户发起咨询，学员逐轮以文字回复；系统在每轮回复后、下一轮客户消息之前分析回复质量、给改进建议并判定目标是否达成。目标达成后 AI 建议结束，学员确认后才结束并获得整场总结；训练不设轮数上限，全部对话和总结可回看。

**Why this priority**: 客服模拟把逐轮反馈引入多轮业务对话，是电商实训中具有独立价值的交互闭环。

**Independent Test**: 完成至少三轮咨询，验证客户发言、学员回复、逐轮分析、结束操作、整场总结、历史记录及 AI 各阶段失败。

**Acceptance Scenarios**:

1. **Given** 学员选择预设咨询场景，**When** 开始训练且 AI 可用，**Then** AI 生成符合场景的首条客户咨询。
2. **Given** 学员提交一轮文字回复，**When** AI 可用，**Then** 系统在下一轮客户消息之前展示问题、对应证据、至少一条改进建议及每个场景目标的达成状态，并可继续下一轮。
3. **Given** AI 判定练习目标已达成并建议结束，**When** 学员确认结束且总结生成成功，**Then** 系统展示包含整场表现、主要问题、优先改进项和目标完成情况四部分的总结果并保存完整对话记录。
4. **Given** 任一客户发言、单轮分析或总结调用不可用，**When** 对应操作执行，**Then** 系统不伪造客户回复、分析或总结，保留已确认对话和当前草稿并提示“AI 服务暂时不可用”。

---

### User Story 6 - 学习电商课程并完成 AI 课后测验 (Priority: P2)

学员在电商课程区块浏览由课程来源提供的已上架电商课程，查看基于兴趣标签和学习行为的“为你推荐”，记录观看进度与断点。课程达到完成条件且教师配置有效测验后，学员可作答并由 AI 判分和讲解。

**Why this priority**: 课程区块把电商方向内容、学习行为和测验成绩接入平台统一学习闭环，并验证 03 建立的课程机制能够被 004 按方向复用。

**Independent Test**: 准备已上架、非电商、未上架和无有效测验课程，验证筛选、推荐、进度、完成判定、测验、成绩历史、空态及 AI 不可用路径。

**Acceptance Scenarios**:

1. **Given** 课程来源包含多个方向课程，**When** 学员进入电商课程区块，**Then** 只展示已上架的电商方向课程。
2. **Given** 学员存在兴趣标签或电商课程学习行为，**When** 查看“为你推荐”，**Then** 系统按与 03 一致的去重、筛选和排序规则展示未完成课程。
3. **Given** 学员播放课程后离开，**When** 重新打开课程，**Then** 从最近有效位置继续，最远进度和完成状态不因较低位置回退。
4. **Given** 有效观看进度达到或超过 80%，**When** 进度记录保存，**Then** 课程标记为完成。
5. **Given** 课程已完成且课程来源启用了有效测验，**When** 学员提交答案且 AI 可用，**Then** 系统展示得分、逐题结果和讲解，并保存本次提交。
6. **Given** AI 不可用，**When** 学员提交课后测验，**Then** 课程浏览、进度和既有成绩不受影响，当前答案保留，提示“AI 服务暂时不可用”，且不生成新成绩。

### Edge Cases

- 商品信息、评判、提示词、店铺输入为空或仅含空白时，不得发起对应 AI 调用，并提示需要补充的字段。
- AI 返回超时、空内容、缺少必需结构、重复字段或不可解析内容时，一律按 AI 不可用处理，不得把残缺内容保存为成功成果。
- 同一生成或训练操作被重复提交时，不得重复创建成功成果、重复计入技能档案或覆盖无关历史记录。
- 直播话术重新生成或切换风格时，最新成功结果成为当前结果；历史成功结果仍保留各自输入和输出。
- 模拟训练提交前允许修改文字；提交后不得通过重新提交静默覆盖已评分记录。
- 一次模拟训练只能属于一个预设场景；场景包含多个环节时，所有环节必须按固定顺序完成后才能统一评分。
- 场景内尚有未提交环节时，不得生成训练总分、逐维评分或完成记录。
- 四维评分任一维度缺失、非数值、超出约定范围或缺少改进建议时，整次评分视为无效。
- 文案训练任一步失败时，已确认的案例、学员评判、优化提示词和新旧文案不得被删除；失败步骤可在服务恢复后重试。
- 一致性评分或优化效果评分缺失、非整数、超出 0–100、缺少理由或缺少对应证据时，对应步骤视为失败，不得展示残缺评分。
- 教学文案案例少于两个预定义缺陷类别时不得发布给学员，必须重新生成；第二次仍无效时按 AI 服务不可用处理。
- 文案训练生成的“新版文案”只作为训练对比材料，不得脱离训练记录成为独立的一键成品文案入口。
- 店铺装修平台不在当前支持目录时，不得自行映射到其他平台，应提示重新选择。
- 客服模拟中途离开时保留已确认的对话轮次和草稿，但只有主动结束且总结成功后才标记为已完成。
- 客服单轮分析失败时，学员刚提交的回复保留为待处理，不进入下一轮，也不生成无依据分析。
- AI 判定目标未达成时不得建议结束；AI 判定目标已达成但学员未确认时，训练保持进行中并允许继续对话。
- 客服模拟不设轮数上限，AI 不得自动结束、自动确认或仅凭判定结果生成总结。
- 客服预设场景必须至少定义两条可观察的达成标准；缺少有效目标定义时不得开始训练。
- 每轮客服分析必须包含至少一个问题、对应对话证据、至少一条改进建议和全部目标标准的当前状态；缺失任一项时整轮分析视为失败。
- 客服总结缺少整场表现、主要问题、优先改进项和目标完成情况任一部分时不得标记训练完成。
- 课程标记为未上架、非电商方向、已删除或来源不可用时，不得出现在列表、推荐和测验入口。
- 课程标签无法唯一解析或不属于 01 标签目录时，该标签不参与推荐匹配，不影响课程通过其他有效信号出现。
- 观看位置为负数、超过视频时长、视频时长无效或必要字段缺失时，不改变最远位置、断点、完成状态或学习行为。
- 课后测验未启用、题目配置无效或课程尚未完成时，不展示可用测验入口。
- 测验配置缺少稳定题目 ID、合法题型、非空题干、非空选项、选项内答案或评分规则时，整份测验视为无效。
- AI 判分结果与题目集合不一致、分数无效或缺少逐题讲解时，整次判分失败，且不得覆盖最近一次有效正式成绩。
- 会话过期、账户被禁用或角色不符时，按 01 的既有会话和角色路由处理，不建立 004 独立登录机制。
- 学员尝试读取或修改他人的话术、训练、方案、客服对话、进度或测验记录时，必须拒绝。
- 08 尚未提供课程时，只使用明确标记为占位用途的课程数据；不得伪造为正式教师发布数据。

## Requirements *(mandatory)*

### Functional Requirements

**访问、复用与边界**

- **FR-001**: System MUST restrict all e-commerce training features to authenticated student users and MUST reuse 01's account, session, disabled-account and role-routing behavior.
- **FR-002**: System MUST reuse 01's current interest-tag values and catalog for course recommendations and MUST NOT create or modify a second tag catalog.
- **FR-003**: System MUST reuse 01's existing session-expiry behavior, including redirect and return-to-operation handling, and MUST NOT define a second authentication or session mechanism.
- **FR-004**: System MUST produce learning outcomes for 07's skill archive without creating a competing skill-archive store, visibility setting, resume attachment or employer-facing archive view.
- **FR-005**: System MUST wait for 07 to define and provide the unified skill-archive write interface before integrating archive writes. Until that interface exists, 004 MUST retain its own training and learning source records for history, MUST NOT create a competing archive store or outcome projection, and MUST NOT claim that an outcome has been written to the skill archive. The future 004 handoff set MUST include every successful live-script version, every completed simulation training record, every course-quiz attempt with its formal-result marker, and every course-learning/completion record. Copy-prompt training, store-decoration plans and customer-service conversations remain module-local history unless 07 explicitly extends the shared contract.
- **FR-006**: System MUST reuse 03's single course-provider registration, default placeholder mechanism and replaceable provider hook, generalizing the shared provider contract to accept a course direction. 004 MUST NOT use an agriculture-only provider method for e-commerce courses, create a second provider registry or duplicate the e-commerce course source.
- **FR-007**: System MUST reuse the same course learning, progress, recommendation and quiz semantics as 03, with the only course-direction difference being `ecommerce`.
- **FR-008**: System MUST keep all backend source under `backend/` and MUST NOT reference, import or migrate the frozen legacy root application, database module or legacy HTML pages.
- **FR-009**: System MUST reject cross-student access to all 004 records and MUST bind every read or change to the current student identity.

**直播话术生成**

- **FR-010**: System MUST accept product name, product selling points, price information and one of exactly three styles: 热情、专业、幽默.
- **FR-011**: System MUST require a non-empty product name and at least one non-empty selling point before invoking AI.
- **FR-012**: System MUST generate a script containing four non-empty, clearly labeled sections: 开场白、产品介绍、互动话术、促单话术.
- **FR-013**: System MUST treat a missing or empty section, unsupported style or malformed AI result as generation failure.
- **FR-014**: System MUST allow successful regeneration with the same input and regeneration after changing style.
- **FR-015**: System MUST make the latest successful generation the current module result while retaining every prior successful generation record and its original input. Every successful version MUST be treated as an independent learning outcome eligible for the future 07 skill-archive handoff.
- **FR-016**: System MUST persist each successful generation record with product input, selected style, generated script and creation time.
- **FR-017**: System MUST allow the student to open historical generation records containing their original input and complete output.
- **FR-018**: System MUST NOT use a local knowledge base, template, rule-based generator or previous result as a fallback when live-script generation AI is unavailable.

**直播间模拟训练**

- **FR-019**: System MUST provide exactly five preset training scenes: 开场白、产品介绍、互动引导、促单话术、异议处理. Each scene MUST define one or more ordered training segments and each training MUST select exactly one scene.
- **FR-020**: System MUST present the selected scene's segments in their fixed order, collect each segment as text and allow editing before that segment is submitted.
- **FR-021**: System MUST prevent modification of a submitted segment unless the student starts a new training record.
- **FR-022**: System MUST evaluate all submitted segments of the selected scene jointly after every required segment is complete, using exactly four dimensions: 语速节奏、情绪感染力、互动引导、卖点突出.
- **FR-023**: System MUST score each dimension as an integer from 0 to 100, weight the four dimensions equally at 25% each, calculate the total as their weighted average rounded to an integer, and return at least one improvement suggestion for each dimension.
- **FR-024**: System MUST treat a missing dimension, non-integer score, score outside 0–100, non-equal weighting rule or missing improvement suggestion as a failed evaluation.
- **FR-025**: System MUST persist each successfully scored simulation with its scene, submitted text, four dimension scores, total score, suggestions and creation time.
- **FR-026**: System MUST allow the student to review completed simulation records and their scores.
- **FR-027**: System MUST NOT accept voice input, audio recording, recording-based scoring or audio-derived scoring in this feature.
- **FR-028**: System MUST NOT complete or score a simulation through any non-AI fallback when the evaluation service is unavailable.

**文案提示词训练**

- **FR-029**: System MUST let the student select a product type or training scene from a platform-provided catalog before generating a teaching case.
- **FR-030**: System MUST use AI to generate a clearly labeled poor or failed copy case containing at least two distinct predefined defect categories from: missing key information, unclear value proposition, unsupported claim, lack of interaction or lack of action guidance. System MUST validate the hidden defect categories before presenting the case and MUST NOT reveal the defect list before the student submits a critique.
- **FR-031**: System MUST require the student to submit a text critique containing identified problems and supporting reasons.
- **FR-032**: System MUST show an AI reference critique after the student critique is submitted, without replacing or hiding the student's own critique; it MUST also return a 0–100 integer consistency score and a text explanation grounded in the compared critiques.
- **FR-033**: System MUST require the student's optimized prompt before generating the revised copy.
- **FR-034**: System MUST generate a revised copy from the student's prompt and compare it with the original case.
- **FR-035**: System MUST provide a critique of the visible differences and score the effectiveness of the student's prompt optimization from 0 to 100, with text evidence from the old and revised copies supporting the score.
- **FR-036**: System MUST persist the complete successful training chain: context, original case, student critique, AI reference critique, consistency score and reason, optimized prompt, revised copy, comparison critique, optimization score and evidence.
- **FR-037**: System MUST preserve previously completed steps and the current input when a later AI step fails.
- **FR-038**: System MUST NOT skip critique or prompt-design steps and MUST NOT expose a standalone one-click finished-copy generation path.
- **FR-039**: System MUST NOT use local rules, stored examples or the original case as a fallback for any failed copy-training AI step.

**店铺装修指导**

- **FR-040**: System MUST accept a store type, a supported platform and a style preference.
- **FR-041**: System MUST support at least 淘宝、拼多多 and 抖音小店 as platform choices and MUST reject unsupported values.
- **FR-042**: System MUST generate a plan containing four non-empty sections: 首页布局、色彩方案、详情页结构、导航分类.
- **FR-043**: System MUST treat any missing plan section or malformed result as generation failure.
- **FR-044**: System MUST persist each successful decoration plan with its inputs, four plan sections and creation time.
- **FR-045**: System MUST allow the student to review historical decoration plans.
- **FR-046**: System MUST NOT connect to, query or modify a real e-commerce platform or store account.
- **FR-047**: System MUST NOT provide a non-AI decoration-plan fallback when AI is unavailable.

**客服模拟训练**

- **FR-048**: System MUST let the student choose a preset customer-service consultation scenario before beginning a simulation. Every preset scenario MUST define at least two observable goal criteria, and training MUST NOT start when that definition is missing or invalid.
- **FR-049**: System MUST use AI to generate the customer's opening consultation and subsequent customer messages for the selected scenario.
- **FR-050**: System MUST allow the student to reply with text over multiple turns.
- **FR-051**: Before the next customer message, System MUST analyze every submitted student reply and return: at least one identified problem, supporting dialogue evidence, at least one improvement suggestion, each goal criterion's status and one overall goal status indicating whether all mandatory criteria have been met.
- **FR-052**: System MUST preserve turn order and associate each analysis with the exact student reply it evaluates.
- **FR-053**: When AI judges that the training objective has been reached, System MUST suggest ending the simulation and MUST wait for the student's explicit confirmation; AI MUST NOT end the simulation automatically. No fixed maximum number of student turns is imposed.
- **FR-054**: System MUST generate a whole-session summary only after the student confirms the AI end suggestion. The summary MUST contain four non-empty parts: overall performance, main problems, prioritized improvements and goal completion outcome.
- **FR-055**: System MUST persist each successfully completed simulation with its scenario, goal criteria, ordered customer and student messages, per-turn problem/evidence/suggestion/goal-status records and final summary.
- **FR-056**: System MUST preserve confirmed dialogue and pending student input when any customer-message, per-turn-analysis or summary call fails.
- **FR-057**: System MUST mark a simulation complete only after AI suggests that the goal is reached, the student confirms ending, and the final summary is successfully generated.
- **FR-058**: System MUST NOT fabricate customer messages, analyses or summaries and MUST NOT use a rule-based script as fallback when AI is unavailable.

**电商课程区块与 AI 课后测验**

- **FR-059**: System MUST display only published courses whose direction is e-commerce and whose authoritative data is supplied through the shared course-provider contract.
- **FR-060**: This feature MUST use the same replaceable course-provider hook established by 03 and MUST NOT add an e-commerce-only provider registry or duplicated course catalog.
- **FR-061**: Until 08 is implemented, System MUST use the existing database-backed placeholder course source and seed a fixed acceptance fixture containing at least two published e-commerce courses with stable identifiers, positive video durations and references to at least two active 01 interest tags; at least one fixture course MUST have no enabled quiz. The same fixture set MUST also include one unpublished e-commerce course, one published non-e-commerce course and one course with invalid duration for filtering tests.
- **FR-062**: When 08 becomes available, the same provider hook MUST be replaceable with the 08-authoritative e-commerce courses and optional quiz configuration without changing 004 course-consumer behavior.
- **FR-063**: System MUST require provider responses to expose at least course stable identifier, title, summary, teacher name, publication time, direction, status, video duration, tag references and optional quiz configuration. When a quiz is present, its configuration MUST expose `enabled`, a non-empty `questions` array and a scoring rule; every question MUST contain a unique stable `id`, `type` equal to `single_choice` or `true_false`, a non-empty `prompt`, a non-empty `options` array and an `answer` contained in that array.
- **FR-064**: System MUST exclude unpublished, deleted, unavailable, malformed, non-e-commerce or duration-invalid courses from course lists, recommendations and progress actions.
- **FR-065**: System MUST provide a deterministic “为你推荐” area for eligible uncompleted published e-commerce courses.
- **FR-066**: Recommendation MUST deduplicate course and student tags by stable identifier, calculate exact tag-intersection count, exclude completed courses and sort by: intersection count descending; previously watched but incomplete before never watched; latest valid viewing time descending; effective progress descending; publication time descending; stable course identifier ascending.
- **FR-067**: If a tag reference cannot be resolved unambiguously against 01's catalog, System MUST ignore that tag for matching while allowing the course to remain eligible through other valid signals.
- **FR-068**: System MUST show “暂无课程” when no eligible published e-commerce course exists and “暂无推荐” when the recommendation result contains no eligible course.
- **FR-069**: System MUST record for each student and course the furthest valid position, most recent valid resumable position, effective progress, active cumulative viewing time, completion state and timestamps.
- **FR-070**: Effective progress MUST equal the furthest valid position divided by valid video duration, rounded down to an integer percentage from 0 to 100.
- **FR-071**: System MUST reject missing, negative or over-duration positions, invalid duration and other malformed progress updates without changing prior learning data.
- **FR-072**: System MUST resume from the most recent valid position while preserving the furthest position and completion state from regressing.
- **FR-073**: System MUST mark a course complete when effective progress reaches at least 80%, and duplicate, out-of-order or cross-device lower updates MUST NOT reduce completion or double-count learning time.
- **FR-074**: System MUST expose completed state and course-quiz availability consistently with the shared learning mechanism used by 03.
- **FR-075**: System MUST activate the AI course-quiz entry only when the course is complete and the provider supplies an enabled, valid quiz.
- **FR-076**: System MUST consume provider-owned quiz questions, options, answers and grading rules without allowing the student to edit them.
- **FR-077**: System MUST submit quiz answers to AI and require a valid score, per-question correctness and an explanation for every question.
- **FR-078**: System MUST persist every submitted course-quiz attempt and preserve all attempt history.
- **FR-079**: System MUST make the most recent valid scored attempt the formal course-quiz result, replacing the previous formal result for learning statistics and skill-archive consumption.
- **FR-080**: System MUST leave progress, completion and existing formal quiz results unchanged when a new quiz-grading attempt is unavailable or invalid.
- **FR-081**: System MUST preserve course browsing, recommendations, progress and completion when AI quiz grading is unavailable.
- **FR-082**: System MUST NOT provide local grading, answer keys, stored explanations or other non-AI fallback for a failed course-quiz grading operation.

**AI 调用点与统一失败表现**

- **FR-083**: All 004 AI calls MUST use the fixed user-facing failure message “AI 服务暂时不可用” for unavailable, timeout, malformed or incomplete provider responses.
- **FR-084**: System MUST NOT expose raw provider errors, credentials, internal identifiers or partial AI content to the student.
- **FR-085**: System MUST NOT use 03's local pest knowledge-base fallback, offline diagnosis, offline grading or any other domain fallback in 004.
- **FR-086**: System MUST treat every AI call point below as a no-fallback operation with the exact failure behavior stated below.

| ID | AI Call Point | Required Success Result | Failure Behavior |
| --- | --- | --- | --- |
| AI-01 | 直播话术生成 | 四段完整直播脚本 | 保留输入；不生成脚本或成功记录；提示“AI 服务暂时不可用” |
| AI-02 | 直播间模拟四维评分 | 四维数值评分与改进建议 | 保留待评分话术；不生成评分；不完成训练；提示“AI 服务暂时不可用” |
| AI-03 | 劣质文案案例生成 | 含至少两个已校验缺陷类别的教学原案例 | 保留商品类型或场景选择；不创建成功训练成果；提示“AI 服务暂时不可用” |
| AI-04 | 文案参考评判与一致性评分 | 参考评判、0–100 一致性分和文字理由 | 保留学员评判；停顿在当前步骤；不展示残缺评分；提示“AI 服务暂时不可用” |
| AI-05 | 按优化提示词生成新文案 | 可对比的新版文案 | 保留优化提示词；不生成新文案；提示“AI 服务暂时不可用” |
| AI-06 | 新旧文案差异与提示词优化评分 | 差异列表、0–100 优化效果分和证据点评 | 保留已完成的新旧文案；不完成训练；不展示残缺评分；提示“AI 服务暂时不可用” |
| AI-07 | 店铺装修方案生成 | 首页布局、色彩方案、详情页结构、导航分类 | 保留店铺输入；不创建成功方案记录；提示“AI 服务暂时不可用” |
| AI-08 | 客服客户咨询生成 | 场景一致的开场或后续客户发言 | 保留已确认对话；不追加伪造客户发言；提示“AI 服务暂时不可用” |
| AI-09 | 客服单轮回复分析与目标判定 | 问题、对话证据、改进建议、各目标标准状态和整体 `目标未达成/目标已达成` 状态 | 保留当前回复为待处理；不进入下一轮；不完成训练；提示“AI 服务暂时不可用” |
| AI-10 | 客服整场总结 | 含整场表现、主要问题、优先改进项和目标完成情况的四部分总结 | 保留完整对话；不生成总结；不标记完成；提示“AI 服务暂时不可用” |
| AI-11 | 电商课程测验判分 | 得分、逐题正误与讲解 | 保留当前答案；不生成新成绩、不覆盖正式成绩；提示“AI 服务暂时不可用” |

- **FR-087**: Each failed AI operation MUST remain retryable after AI service recovery without requiring the student to recreate unrelated completed records.
- **FR-088**: Non-AI actions MUST remain available during AI failure, including viewing records, browsing courses, updating valid course progress and editing current unsaved input.
- **FR-089**: All 004 AI calls MUST return complete, validated request-response payloads; 004 MUST NOT use token-by-token streaming for live scripts, simulation scoring, copy training, decoration plans, customer-service turns, course-quiz grading or any other AI output.
- **FR-090**: Customer-service simulation is turn-based: each accepted student reply MUST receive one complete analysis and goal-status response before the next customer message; turn boundaries MUST NOT be implemented as token streaming.
- **FR-091**: Each 004 record type MUST remain available in its module-local history list. The future 07 skill archive consumes the handoff outcomes defined in FR-005 and does not replace module-local histories or their ownership.

### Key Entities *(include if data is involved)*

- **Live Script Generation Record**: 学员一次成功直播话术生成的输入参数、风格、四段脚本、当前结果标记和创建时间。
- **Simulation Training Record**: 一次直播间文字模拟训练选中的一个场景、该场景按顺序保存的全部环节话术、四维 0–100 分数、等权总分、逐维改进建议和完成时间。
- **Copy Prompt Training Record**: 一次文案训练的商品类型或场景、含至少两个已校验缺陷类别的原案例、学员评判、AI 参考评判、0–100 一致性分及理由、优化提示词、新版文案、差异点评、0–100 优化效果分及证据和完成时间。
- **Store Decoration Plan**: 店铺类型、平台、风格偏好、四部分装修方案和创建时间。
- **Customer Service Simulation**: 含至少两条目标标准的预设场景、按顺序保存的客户与学员消息、每轮问题/证据/建议/各目标状态、整体目标状态、AI 结束建议、学员确认、四部分整场总结、完成状态和完成时间。
- **E-commerce Course Progress**: 学员在电商课程上的最远有效位置、最近有效位置、有效进度、累计观看时间、完成状态和更新时间。
- **E-commerce Course Quiz Attempt**: 学员一次课后测验提交的答案、得分、逐题结果、讲解、正式成绩标记和提交时间。
- **E-commerce Course Provider Snapshot**: 课程 provider 返回的稳定课程字段、方向、时长、标签引用及可选结构化测验配置。
- **Learning Outcome Handoff**: 004 向共享技能档案边界提供的成果引用；不包含 004 自建的档案、可见范围或企业展示状态。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In valid generation tests across all three styles, 100% of successful live scripts contain all four required non-empty sections, regeneration produces a current result while retaining every prior version, and every successful version is independently eligible for the future skill-archive handoff.
- **SC-002**: In all five simulation scenes, 100% of successful completions contain every required segment in order, four integer dimension scores from 0 to 100, an equally weighted integer total and improvement advice for every dimension, with zero voice or recording inputs accepted.
- **SC-003**: In copy-training tests, 100% of generated cases contain at least two validated defect categories and 100% of successful records contain all five stages, a 0–100 consistency score with reason, and a 0–100 optimization-effect score with evidence.
- **SC-004**: In store-decoration tests, 100% of successful plans contain all four required sections and preserve the original input.
- **SC-005**: In multi-turn customer-service tests, 100% of preset scenarios have at least two goal criteria; every accepted reply has problem, evidence, suggestion and criterion-status analysis before the next message; 100% of completions contain AI end suggestion, student confirmation and a four-part summary; and no fixed turn cap is imposed.
- **SC-006**: In provider-reuse verification, 004 creates zero additional course-provider registries, zero duplicated e-commerce course catalogs and zero alternate interest-tag catalogs.
- **SC-007**: In e-commerce course tests, 100% of listed and recommended courses are eligible, published e-commerce courses; completed courses are excluded from recommendations; and recommendation ordering follows the specified deterministic sequence.
- **SC-008**: At the 79%, 80% and 90% progress boundaries, 100% of courses below 80% remain incomplete and 100% of courses at or above 80% become complete without later regression.
- **SC-009**: In quiz tests, only completed courses with schema-valid enabled provider quizzes expose an entry; all attempts remain available; and the latest valid score alone is formal.
- **SC-010**: For all 11 listed AI call points, unavailable, timeout and malformed-response tests show exactly “AI 服务暂时不可用” in 100% of attempts, create zero fabricated results and preserve retryable user work.
- **SC-011**: In 004 AI-failure tests, zero calls use the 03 local pest knowledge-base fallback or any other non-AI business fallback.
- **SC-012**: In authorization tests, 100% of cross-student attempts to read or modify 004 records are rejected, and expired sessions follow 01's existing recovery behavior.
- **SC-013**: In course-provider replacement tests, substituting an 08-compatible provider changes the course and quiz source without requiring changes to 004's student-facing learning flow.
- **SC-014**: In placeholder acceptance tests, the fixed fixture contains the specified published/unpublished/direction/duration/quiz variants, and 100% of course, recommendation and quiz filtering results match the fixture metadata.

## Dependencies and Placeholder Contracts

- **01-账户与门户（已实现，复用）**: Provides student identity, session validity, disabled-account behavior, role routing and current interest tags.
- **03-农业技能（已实现，机制复用）**: Provides the established replaceable course-provider hook and shared course learning/recommendation/quiz semantics. 004 reuses those mechanisms with direction set to e-commerce and does not reuse 03's local pest knowledge-base fallback.
- **08-教师工作台（尚未实现，前向依赖）**: Owns authoritative course publication, review, summary, tags, duration and optional quiz configuration. Until it exists, the fixed placeholder fixture defined in FR-061 is clearly marked for development/demonstration use and is replaceable through the same direction-aware provider hook.
- **07-就业对接（尚未实现，前向依赖）**: Owns the assembled skill archive, the unified write interface, visibility controls, resume attachment and employer-facing presentation. 004 waits for the unified write interface before integrating archive writes and otherwise retains only its own source records.
- **External AI service**: Provides all generation, analysis, scoring, simulation and grading calls listed in FR-086. No 004 AI call has a fallback.

## Scope Boundaries

- This feature MUST NOT provide a standalone one-click final-copy generator; copy creation exists only inside the case-critique and prompt-optimization training flow.
- This feature MUST NOT support voice input, audio recording, recording-based scoring or audio analysis; simulation scoring is based on text only.
- This feature MUST NOT integrate with real Taobao, Pinduoduo, Douyin Shop or other platform/store APIs.
- This feature MUST NOT provide forums, community discussions or a separate discussion area.
- This feature MUST NOT implement account creation, login, session management, role permissions or password recovery.
- This feature MUST NOT create or modify interest tags; it only reads 01's catalog and the student's current tags.
- This feature MUST NOT create an independent skill archive, visibility setting, resume attachment or employer-view record; 07 owns those capabilities.
- This feature MUST NOT implement course creation, teacher review, publication, withdrawal, video upload, tag authoring or quiz authoring; 08 owns those capabilities.
- This feature MUST NOT create a second course-provider mechanism or duplicate the e-commerce course source.
- This feature MUST NOT use local knowledge bases, rule-based generators, answer keys or stored templates as AI fallbacks.
- This feature MUST NOT implement real live streaming, store operations, orders, payments, logistics, product listing or trading capabilities.
- This feature MUST NOT reference, import or migrate the frozen legacy root application, legacy database module or legacy HTML pages.

## Assumptions

- 004 is available only to authenticated students; teachers, administrators, enterprises and government users do not operate its learning records.
- Product name and at least one selling point are required for live-script generation; price is optional and may be omitted when unknown.
- Each simulation dimension uses an integer score from 0 to 100; the four dimensions have fixed equal weights of 25% each, and the total is the weighted average rounded to an integer. The four dimension scores remain available alongside the total.
- A simulation scene owns its ordered segment definition; a training record selects exactly one scene and cannot mix segments from different scenes.
- Historical successful AI outputs are immutable records; retrying or regenerating creates a new attempt and does not silently rewrite past successful outcomes.
- Copy-training consistency and optimization-effect scores are integers from 0 to 100 and are never displayed or persisted without their required reason or evidence.
- AI-generated customer messages, cases, copies, plans and feedback are training artifacts and do not represent real customers, stores or platform recommendations.
- The supported store-platform catalog is platform-maintained and may include more platforms than the minimum three accepted in FR-041.
- Course-provider placeholder data is the fixed development/demonstration fixture defined in FR-061 and must be transparently replaced when 08 supplies the authoritative source.
- The quiz configuration remains unavailable when the placeholder provider cannot supply a valid enabled quiz; absence of a quiz is not an error.
- The shared course-provider contract accepts direction as an input while preserving the single 03-established registration and replacement mechanism.
- Customer-service scenarios own explicit observable goal criteria; AI returns statuses against those criteria rather than applying an undocumented general objective.
- The recommendation implementation consumes the same learning-behavior fields as 03 and follows the same completion threshold and ordering.
- AI response validation occurs before displaying or persisting any success artifact; malformed output is treated as service failure rather than repaired through domain fallback.
- All 004 AI calls are non-streaming and return complete structured results; customer-service turn interactions remain multi-turn but not token-streamed.
- Skill-archive integration is a forward dependency on 07 and may remain unimplemented until 07 publishes the unified write interface; 004-owned training and learning records are not blocked by that dependency.
