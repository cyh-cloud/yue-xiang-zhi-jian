# Feature Specification: 03-农业技能

**Feature Branch**: `v2/lixKRT/003-agri-skills`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "agri-skills: 农业技能子系统。基于 `docs/粤乡智匠——需求输入.md` 的 03-农业技能章节及相关 v1/v2/v3 细化口径，实现农时智能日历、语音/文字 AI 农技问答、点选式病虫害多轮诊断、诊断自测与复诊记录、农业课程区块和 AI 课后测验作答；严格复用 01 的账户、会话、角色路由、兴趣标签与课程聚合能力，复用 02 的消息通知与农事提醒通道，课程和预置内容分别消费 08、11 的权威数据。"

## Clarifications

### Session 2026-09-15

- Q: 一个已完成的诊断会话可以关联多条复诊记录吗？ → A: 可以；每次复诊提交都新增一条独立记录，任一条记录均可用于再次发起诊断。
- Q: 农时日历的空态是否要区分“该产品有产品数据但当前月无数据”和“该产品完全没有预置日历数据”？ → A: 区分；产品无数据时显示“暂无该产品农时数据”，产品有数据但当月无记录时显示“当月无该产品农时”。
- Q: “进行中”的诊断会话是否有自动超时或保留期限？ → A: 连续 365 天无活动后自动标记为“已放弃”，历史继续可查。
- Q: AI 课后测验的多次提交应如何计入正式成绩和学习统计？ → A: 保留每次提交历史；最近一次有效得分作为正式成绩、覆盖旧正式成绩并计入学习统计与技能档案。
- Q: “为你推荐”的最小规则应采用哪些兴趣标签和学习行为，并按什么优先级排序？ → A: 排除已完成课程；先按作物类目、技能兴趣、岗位类别三个标签组的精确匹配数量排序，再按已有观看但未完成的学习行为排序，最后按上架时间倒序。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 完成语音或文字农技问答 (Priority: P1)

学员可以输入文字，或通过语音按钮说出农业问题。系统展示识别后的文字，流式输出回答，并在回答结束后提供三个可点击的追问建议；学员可连续追问并回看历史记录。AI 服务不可用时，只有本功能自动检索本地病虫害知识库。

**Why this priority**: 农技问答是学员进入农业技能模块后最直接的知识获取能力，也是唯一允许离线知识降级的 AI 功能。

**Independent Test**: 分别使用文字、语音成功、语音识别失败、AI 可用、AI 不可用且本地知识库有匹配、AI 不可用且无匹配等输入，验证回答方式、追问建议、历史记录和固定提示。

**Acceptance Scenarios**:

1. **Given** 学员已登录并进入农技问答，**When** 提交非空文字问题且 AI 可用，**Then** 回答逐步显示，结束后提供恰好三个追问建议。
2. **Given** 回答已提供追问建议，**When** 学员点击任一建议，**Then** 系统以该建议开启新一问答轮次，并再次提供三个后续建议。
3. **Given** 学员使用语音提问且识别成功，**When** 识别完成，**Then** 系统展示识别文字，学员可确认或修改后提交，并得到与文字提问一致的问答结果。
4. **Given** 语音因噪音或不可识别而失败，**When** 识别结束，**Then** 系统提示“未能识别，请重试或改用文字输入”，文字输入仍可使用。
5. **Given** AI 服务不可用且本地知识库存在匹配条目，**When** 学员提交问题，**Then** 系统返回最匹配的知识库内容并标注“离线知识库回答”，且不生成追问建议。
6. **Given** AI 服务不可用且本地知识库无匹配条目，**When** 学员提交问题，**Then** 系统提示“暂无法回答，建议稍后再试”。
7. **Given** 学员已完成多轮问答，**When** 打开问答历史，**Then** 问答记录按最后更新时间倒序展示，并可查看完整问答轮次。

---

### User Story 2 - 通过点选和追问完成病虫害诊断 (Priority: P1)

学员先选择农产品、发病部位和多个症状表现，再由 AI 引导补充细节。系统最多进行五轮追问，在信息充分时输出病因分析和防治方案；中途退出后可继续或放弃重开。

**Why this priority**: 点选式诊断降低农业知识门槛，是连接症状识别、AI 推理和防治建议的核心流程。

**Independent Test**: 使用不同产品、部位、症状组合完成充分信息、达到五轮上限、中途退出、放弃重开、AI 不可用等路径，并检查结论及历史记录。

**Acceptance Scenarios**:

1. **Given** 学员开始新诊断，**When** 依次选择农产品、发病部位和一个或多个症状，**Then** 系统保存点选信息并进入 AI 引导追问。
2. **Given** 诊断进行中，**When** AI 要求补充细节，**Then** 学员可用文字或语音转文字回答，系统据此生成下一轮追问。
3. **Given** AI 在五轮内判断信息充分，**When** 本轮回答完成，**Then** 系统输出病因分析、防治方案和本轮所依据的症状信息。
4. **Given** 达到五轮上限但 AI 仍无法确认充分性，**When** 第五轮回答完成，**Then** 系统基于已有信息给出明确标注为“信息有限”的结论，并停止继续追问。
5. **Given** 学员中途关闭或离开诊断，**When** 再次进入历史，**Then** 会话保持“进行中”，学员可以继续追问或明确放弃后重新开始。
6. **Given** AI 服务不可用，**When** 学员进入诊断或继续回答，**Then** 系统提示“AI 服务暂时不可用”，不提供离线诊断结果，并保留已填写的点选信息和回答供恢复后继续。
7. **Given** 诊断已有历史，**When** 学员查看记录，**Then** 可查看点选信息、全部追问回答、结论和会话状态。
8. **Given** 进行中的诊断连续 365 天没有任何新回答或状态更新，**When** 系统执行会话生命周期检查，**Then** 会话自动变为“已放弃”且历史仍可查看，不自动删除。

---

### User Story 3 - 查看农时日历并订阅农事提醒 (Priority: P1)

学员查看农产品在当月的农事任务、管理要点和节气提示，切换产品或月份时内容同步刷新。学员可订阅关注的农产品，在每月初通过既有消息中心收到当月农事提醒，并可随时取消。

**Why this priority**: 日历把预置农时知识转化为按产品、月份驱动的可执行提醒，是农业技能模块的日常入口。

**Independent Test**: 使用有历史选择和无历史选择的学员，验证默认产品、默认月份、产品与月份切换、数据范围空态、订阅、取消订阅、月初推送和重复触发。

**Acceptance Scenarios**:

1. **Given** 学员曾选择过农产品，**When** 再次进入农时日历，**Then** 默认显示该产品及当前月份；无历史时显示农产品目录首项。
2. **Given** 当前产品存在当月预置数据，**When** 页面加载，**Then** 展示农事任务、管理要点、节气标注和当月农事提示。
3. **Given** 学员切换产品或前后翻月，**When** 选择完成，**Then** 日历内容按所选产品和月份重新加载。
4. **Given** 所选农产品没有任何月份的预置日历数据，**When** 页面加载，**Then** 显示“暂无该产品农时数据”。
5. **Given** 所选农产品存在其他月份的日历数据但当前月没有记录，**When** 页面加载，**Then** 保留产品和月份选择并显示“当月无该产品农时”。
6. **Given** 学员未订阅某农产品，**When** 点击订阅，**Then** 该产品和当前学员之间建立有效订阅关系。
7. **Given** 学员已订阅某农产品且订阅仍有效，**When** 每月初触发农事提醒，**Then** 系统通过 02 的消息中心发送该产品当月农事要点；取消订阅后不再收到后续提醒。

---

### User Story 4 - 完成诊断自测并记录复诊效果 (Priority: P2)

诊断形成结论后，学员可选做基于本次诊断文本的 AI 自测，获得判分与逐题讲解；也可记录防治后的好转、无变化或恶化状态及备注，并在复诊记录基础上再次诊断。

**Why this priority**: 该流程把一次诊断延伸为可追踪的学习和防治闭环，但不阻塞诊断主流程。

**Independent Test**: 分别从已有诊断发起或拒绝自测、答对答错、AI 不可用、记录三种复诊状态、查看复诊历史和基于复诊再次诊断，验证记录、评分和预填信息。

**Acceptance Scenarios**:

1. **Given** 诊断已有结论，**When** 学员选择“AI 自测”，**Then** 系统依据诊断文本生成 3 至 5 道选择题或判断题。
2. **Given** 自测已生成，**When** 学员提交答案且 AI 可用，**Then** 系统给出总分、逐题正误和讲解，并把成绩保存为可供技能档案和学习统计读取的学习成果。
3. **Given** AI 服务不可用，**When** 学员尝试生成、提交或判分自测，**Then** 系统提示“AI 服务暂时不可用”，不提供离线出题或离线判分，已有诊断记录不受影响。
4. **Given** 诊断已有结论，**When** 学员提交复诊状态“好转”“无变化”或“恶化”及可选备注，**Then** 系统生成一条复诊记录并挂接到原诊断会话。
5. **Given** 原诊断已有复诊记录，**When** 学员查看历史，**Then** 可查看全部复诊状态、备注和时间，并可基于选定复诊记录再次发起诊断。
6. **Given** 学员基于复诊再次诊断，**When** 新会话创建，**Then** 系统预填上轮产品、部位、症状和适用上下文，学员仍可在提交前调整。

---

### User Story 5 - 学习农业课程并完成 AI 课后测验 (Priority: P2)

学员在农业课程区块浏览 08 提供的农业方向已上架课程，查看基于兴趣标签和学习行为的“为你推荐”，记录观看进度与断点，并在完成课程后进入教师已配置的 AI 课后测验。

**Why this priority**: 课程区块把农技知识、学习行为和测验成绩连成可统计的学习闭环，但课程发布、审核和题库配置仍由 08 负责。

**Independent Test**: 准备已上架、待审核、下架课程和无测验、有测验课程，验证筛选、推荐、进度、断点续播、完成判定、测验解锁、判分、历史成绩及空态。

**Acceptance Scenarios**:

1. **Given** 平台存在多个方向的课程，**When** 学员进入农业课程区块，**Then** 只展示农业方向的已上架课程，并使用 08 的同一课程数据。
2. **Given** 学员兴趣标签或农业课程学习行为发生变化，**When** “为你推荐”刷新，**Then** 系统排除已完成课程，先按三个兴趣标签组的精确匹配数量、再按未完成观看行为、最后按上架时间倒序生成结果；无可用推荐时显示“暂无推荐”。
3. **Given** 学员播放课程后离开，**When** 再次打开同一课程，**Then** 播放器从上次有效进度继续。
4. **Given** 学员课程观看进度达到或超过 80%，**When** 进度完成，**Then** 该课程标记为已完成，重复上报不产生重复完成记录。
5. **Given** 已完成课程由教师开启 AI 课后测验，**When** 学员进入课程，**Then** 测验入口点亮；未开启测验的课程不显示可用测验入口。
6. **Given** 学员提交 AI 课后测验且 AI 可用，**When** 判分完成，**Then** 显示得分、逐题结果和讲解，保留本次提交历史，并把最近一次有效得分作为可覆盖旧正式成绩的成绩供技能档案和学习统计读取。
7. **Given** AI 服务不可用，**When** 学员提交需 AI 判分的课后测验，**Then** 系统提示“AI 服务暂时不可用”，课程浏览、进度和已完成状态不受影响。
8. **Given** 农业方向没有已上架课程或当前没有推荐，**When** 打开课程区块，**Then** 对应区域分别显示“暂无课程”或“暂无推荐”。

---

### Edge Cases

- 11 尚未提供预置内容、预置目录为空、产品没有任一日历数据或产品有数据但指定月份无记录时，日历必须分别显示“暂无该产品农时数据”或“当月无该产品农时”；本地知识库必须按空态或明确占位响应，不得伪造为正式业务数据。
- 学员上次选择的农产品后被 11 下架或删除时，日历回退到当前目录首项，并提示原选择已不可用。
- 同一学员重复订阅同一产品时只保留一个有效订阅；重复触发的同月农事提醒不得向同一学员重复送达。
- AI 问答流式输出中途失败时，不把不完整内容当作完整答案；系统按农技问答降级策略返回本地知识库结果或明确提示。
- 语音识别成功但结果为空、仅含空白或属于误识别时，不得提交空问题；识别失败与取消录音均不得创建问答记录。
- 诊断达到五轮上限时不得出现第六轮 AI 追问；存在未提交回答时，退出前必须保留草稿状态。
- 进行中的诊断连续 365 天无活动后必须转为“已放弃”；自动放弃不得删除点选信息、问答或结论属性，也不得允许继续向 AI 追问。
- 已放弃的诊断不得继续使用 AI，但历史记录仍可查看；重新诊断必须创建独立会话，不覆盖原记录。
- 自测题目少于 3 道、超过 5 道、题干无效或缺少数值时，不得向学员发布不完整测试，并提示稍后重试。
- 课程进入待审核、下架或删除状态后，不得继续出现在农业课程区块；已有学习进度和测验成绩保留，并按来源对象当前可用性展示。
- 重复、乱序或跨设备上报观看进度时，完成状态只可前进不可回退；已达标课程不得因后续较短进度而变成未完成。
- 学员修改兴趣标签后，后续推荐必须使用最新标签，不得继续使用旧缓存结果。
- 本地知识库存在多条同等匹配时使用稳定排序返回唯一结果，不向学员同时展示互不相关的答案。
- 非学员角色或会话无效时不得访问农业技能数据，也不得通过直接输入记录标识读取他人问答、诊断或学习进度。

## Requirements *(mandatory)*

### Functional Requirements

**访问与跨模块边界**

- **FR-001**: System MUST restrict all agricultural-skill features to authenticated student users and MUST reuse 01 的账户、会话和角色路由，不得建立独立账户或登录机制。
- **FR-002**: System MUST read the student’s current interest tags, learning direction and profile values through 01 的既有能力；农业技能不得创建、复制或修改兴趣标签目录。
- **FR-003**: System MUST deliver agricultural subscription reminders only through 02 的统一消息通道和未读管理，不得建立第二套通知、公告或消息中心。
- **FR-004**: System MUST consume agricultural courses from 08’s published-course source and MUST NOT implement course creation, review, publication, withdrawal or question-bank authoring.
- **FR-005**: System MUST read agricultural products, farming-calendar entries and pest knowledge through the future 11 preset-content contract; 03 MUST NOT provide a competing production authoring capability.
- **FR-006**: System MUST validate that every record read or changed belongs to the current student and MUST reject access to another student’s Q&A, diagnosis, follow-up, self-test, learning progress or subscription data.
- **FR-007**: System MUST use the same agricultural course records as 01’s course aggregation and 08’s course source, with no duplicated course catalog or divergent publication status.
- **FR-008**: System MUST preserve recorded learning outcomes for later consumption by 07’s skill archive and 08’s learning statistics without treating either downstream module as required for the immediate learning flow.

**农时日历与订阅**

- **FR-009**: System MUST default the calendar to the student’s last selected agricultural product when it remains available; otherwise it MUST use the first item in the current product catalog.
- **FR-010**: System MUST default the calendar month to the current month in the platform’s configured time zone.
- **FR-011**: System MUST display the selected product and month’s agricultural tasks, management guidance, solar-term annotations and monthly agricultural reminder when preset data exists.
- **FR-012**: System MUST refresh calendar content when the student changes product or moves to a previous or later month.
- **FR-013**: System MUST show “暂无该产品农时数据” when the selected agricultural product has no preset calendar entry in any month, and MUST show “当月无该产品农时” while retaining the selected product and month controls when the product has entries in other months but none for the selected month.
- **FR-014**: System MUST persist the student’s last selected product independently from product subscription state.
- **FR-015**: System MUST allow a student to subscribe to or unsubscribe from any currently available agricultural product.
- **FR-016**: System MUST maintain at most one effective subscription per student and product; repeated subscribe or unsubscribe requests MUST be idempotent.
- **FR-017**: System MUST expose the current agricultural-product subscriber set to 02 at reminder-trigger time, so monthly reminders reach students with an effective subscription and exclude students who unsubscribed before the trigger.
- **FR-018**: System MUST ensure a repeated trigger for the same student, product and reminder month produces at most one user-visible reminder notification.
- **FR-019**: System MUST preserve historical subscriptions used for delivery history while ensuring only currently effective subscriptions receive future reminders.

**AI 服务调用点与统一降级**

| AI 调用点 | 主要用途 | 降级策略 |
| --- | --- | --- |
| 语音识别 | 将农技问答、诊断补充回答的语音转为文字 | 识别失败提示“未能识别，请重试或改用文字输入”；AI 服务不可用时提示“AI 服务暂时不可用”；文字输入始终保留 |
| 农技问答回答 | 生成流式回答 | 仅在 AI 服务不可用时降级到本地病虫害知识库；有匹配时标注“离线知识库回答”，无匹配时提示“暂无法回答，建议稍后再试” |
| 农技问答追问建议 | 根据本轮回答生成三个建议 | 不单独降级；AI 服务不可用时沿用农技问答的本地知识库降级，且不生成追问建议 |
| 诊断追问与结论 | 生成下一轮追问、病因分析和防治方案 | 不降级；提示“AI 服务暂时不可用”，保留点选和回答数据，恢复后继续 |
| 诊断自测生成 | 依据诊断文本生成 3 至 5 道题 | 不降级；提示“AI 服务暂时不可用” |
| 诊断自测判分与讲解 | 判分、逐题讲解 | 不降级；提示“AI 服务暂时不可用” |

- **FR-020**: System MUST support both text and voice input for agricultural Q&A and diagnostic follow-up answers.
- **FR-021**: System MUST display the speech-recognition result before submitting it and MUST reject empty or whitespace-only recognized text.
- **FR-022**: System MUST show exactly “未能识别，请重试或改用文字输入” when voice recognition fails because of noise, cancellation or an unusable result.
- **FR-023**: System MUST use exactly “AI 服务暂时不可用” for every non-问答 AI failure in this feature, including diagnosis, diagnostic self-test and AI-graded course quiz.
- **FR-024**: System MUST preserve user-entered text, point selections and completed records when an AI call fails; an AI failure MUST NOT delete or corrupt manual data.

**农技问答**

- **FR-025**: System MUST accept a non-empty agricultural question from text or confirmed speech-recognition text.
- **FR-026**: System MUST stream an AI answer progressively rather than withholding the complete answer until generation finishes.
- **FR-027**: System MUST provide exactly three clickable follow-up suggestions after a complete AI-generated answer.
- **FR-028**: System MUST treat a selected follow-up suggestion as a new question in the same conversation and continue the same streamed-answer and three-suggestion behavior.
- **FR-029**: System MUST support multiple Q&A rounds without truncating prior turns.
- **FR-030**: System MUST list the student’s Q&A conversations in reverse chronological order by latest activity and allow every retained turn to be reviewed.
- **FR-031**: System MUST automatically use the local pest knowledge base when the AI answer call is unavailable, and MUST select the most relevant available entry using the submitted question.
- **FR-032**: System MUST label every local knowledge-base answer as “离线知识库回答” and MUST NOT return follow-up suggestions for that answer.
- **FR-033**: System MUST show “暂无法回答，建议稍后再试” when the local knowledge base has no usable match.

**病虫害诊断**

- **FR-034**: System MUST begin a diagnosis with point-based selection in the fixed order: agricultural product, affected plant part, and one or more symptom expressions.
- **FR-035**: System MUST provide predefined affected-part and symptom choices and MUST NOT require an image or photograph.
- **FR-036**: System MUST allow multiple symptoms to be selected for one diagnosis.
- **FR-037**: System MUST send the selected product, part and symptoms to AI as the initial diagnosis context.
- **FR-038**: System MUST show one AI-guided question at a time and accept the student’s answer as text or confirmed speech-recognition text.
- **FR-039**: System MUST limit AI-guided diagnosis questioning to five answered rounds.
- **FR-040**: System MUST end diagnosis when AI determines the available information is sufficient or when the five-round limit is reached.
- **FR-041**: System MUST output both an etiological analysis and a prevention-and-treatment plan in every completed diagnosis.
- **FR-042**: A conclusion reached solely because the five-round limit was reached MUST be visibly marked “信息有限”.
- **FR-043**: System MUST persist an interrupted diagnosis as “进行中” and allow the same student to resume it or explicitly abandon it; a session with no new answer or status update for 365 consecutive days MUST automatically transition to “已放弃”.
- **FR-044**: System MUST NOT send an abandoned diagnosis to AI again, and MUST keep its prior information readable in history.
- **FR-045**: System MUST retain every diagnosis session’s point selections, ordered questions and answers, conclusion, status and timestamps for history review.
- **FR-046**: System MUST create a new diagnosis session when the student restarts after abandonment; it MUST NOT overwrite the abandoned session.
- **FR-047**: System MUST return the fixed AI-unavailable message when diagnosis AI is unavailable and MUST NOT use the local pest knowledge base as a diagnosis conclusion.

**诊断自测与复诊**

- **FR-048**: System MUST offer an optional AI self-test after a diagnosis has a conclusion.
- **FR-049**: System MUST instruct the self-test generation call to produce 3 to 5 multiple-choice or true/false questions based only on the diagnosis text.
- **FR-050**: System MUST reject and regenerate or defer an invalid self-test that has fewer than 3 questions, more than 5 questions, missing prompts, invalid options or missing answers.
- **FR-051**: System MUST allow the student to answer the generated self-test and, when AI is available, return a score, per-question correctness and an explanation.
- **FR-052**: System MUST persist every submitted self-test result as a learning outcome associated with the originating diagnosis.
- **FR-053**: System MUST NOT generate, grade or explain a self-test through a local knowledge-base fallback; AI unavailability uses the fixed message from FR-023.
- **FR-054**: System MUST allow the student to add one or more follow-up records to a completed diagnosis, each with status “好转”, “无变化” or “恶化” and an optional note; every submission MUST create a new independent record rather than overwrite an earlier one.
- **FR-055**: System MUST attach every follow-up record to its originating diagnosis and retain all records in chronological history.
- **FR-056**: System MUST allow the student to start a new diagnosis from a selected follow-up record.
- **FR-057**: A diagnosis started from a follow-up record MUST prefill the previous product, affected part, symptoms and applicable context while remaining editable before submission.
- **FR-058**: System MUST retain self-test and follow-up records even if a later diagnosis session is abandoned or AI becomes unavailable.

**农业课程区块与 AI 课后测验**

- **FR-059**: System MUST display only published courses whose learning direction is agriculture and whose authoritative status is supplied by 08.
- **FR-060**: System MUST provide a deterministic “为你推荐” area from eligible uncompleted published agricultural courses: courses MUST be ranked first by the count of exact matches across the student’s current crop-category, skill-interest and job-category tags, then by recent or existing viewing behavior for courses not yet completed, and finally by publication time descending; completed courses MUST be excluded.
- **FR-061**: System MUST show “暂无推荐” when no recommendation signal produces eligible courses, independently from the general course empty state.
- **FR-062**: System MUST show “暂无课程” when there are no eligible published agricultural courses.
- **FR-063**: System MUST record course viewing progress and total viewing duration for the current student and course.
- **FR-064**: System MUST resume playback from the last valid recorded position when the same course is reopened.
- **FR-065**: System MUST mark a course complete when effective viewing progress reaches at least 80%, and MUST treat later duplicate or lower progress updates as idempotent.
- **FR-066**: System MUST prevent viewing progress and completion state from moving backwards after a higher valid progress has been recorded.
- **FR-067**: System MUST expose the completed state and course quiz availability required by 08’s learning statistics without making course browsing depend on statistics availability.
- **FR-068**: System MUST activate the AI quiz entry only when the completed course has an enabled and valid quiz configured by 08.
- **FR-069**: System MUST consume the 08-owned question bank and MUST NOT allow the student to edit questions, options, answers or scoring rules.
- **FR-070**: System MUST submit quiz answers for AI grading and return a score, per-question correctness and explanations when AI is available.
- **FR-071**: System MUST persist every submitted course-quiz attempt and its learning outcome; the most recent valid scored attempt MUST become the formal course-quiz result, replace the prior formal result for learning statistics and skill-archive consumption, and all earlier attempts MUST remain available as history.
- **FR-072**: System MUST preserve course browsing, progress, completion and earlier results when the AI quiz-grading call is unavailable, while showing the fixed FR-023 message for the failed quiz operation.
- **FR-073**: System MUST use the existing course-video comment area for course questions and teacher replies and MUST NOT create a forum, discussion module or separate comment store.
- **FR-074**: System MUST show course and recommendation empty states independently and MUST NOT count unavailable, unpublished or out-of-direction courses as either.

### Key Entities *(include if feature involves data)*

- **Agricultural Product**: 11 维护的农产品目录项；具有稳定标识、名称、顺序和可用状态，是日历与产品订阅的表达对象。
- **Farming Calendar Entry**: 11 维护的产品与月份农事内容，包含农事任务、管理要点、节气和月度提示；03 只读。
- **Pest Knowledge Entry**: 11 维护的本地病虫害知识条目，用于农技问答的 AI 不可用降级；包含问题特征、匹配信息和回答内容。
- **Q&A Conversation**: 学员的一组连续农技问答，具有创建时间、最后更新时间和多个有序轮次。
- **Q&A Turn**: 一次问题、输入来源、回答内容、回答模式、是否离线降级、时间及可选三个追问建议。
- **Diagnosis Session**: 一次病虫害诊断，包含产品、部位、症状集合、状态、最多五轮问答、结论、结论充分性和时间信息。
- **Diagnosis Answer**: 对某轮诊断追问的文字回答及其语音转文字来源。
- **Diagnostic Self-Test**: 由诊断文本生成的 3 至 5 道题、答案、评分规则和生成状态。
- **Diagnostic Self-Test Attempt**: 学员对诊断自测的提交、得分、逐题结果、讲解和时间。
- **Follow-Up Record**: 诊断后的防治效果记录，包含状态、备注、记录时间和原诊断关联。
- **Product Subscription**: 学员与农产品之间的有效订阅关系及订阅历史，用于 02 触发月度农事提醒。
- **Course Learning Progress**: 学员在农业课程上的观看位置、有效进度、累计观看时长、完成状态和最后更新时间。
- **Course Quiz Attempt**: 学员对 08 所配置课程测验的一次作答、得分、逐题结果、讲解和时间；每次提交都保留，最近一次有效评分提交为正式成绩。

## Scope Boundaries

- 本 feature 只面向已登录学员；账户、会话和角色权限由 01 负责。
- 兴趣标签目录、标签选择和标签持久化由 01 负责；03 只读取最新偏好用于推荐。
- 消息发送、公告、订阅推送、未读状态和清除规则由 02 负责；03 只提供农产品订阅关系并向 02 提供触发时受众。
- 课程发布、审核、上下架、课程简介、教师配置的 AI 课后测验题库和学习统计由 08 负责；03 只消费已发布课程和测验配置，并产生学员作答与学习行为。
- 技能档案的汇总、可见范围和简历附带由 07 负责；03 只在自身范围内保留可被 07 消费的学习成果。
- 农产品目录、农时日历、病虫害知识库和预置内容维护由 11 负责；03 不提供正式预置内容管理后台。
- 课程视频评论区由 08/现有课程能力负责；03 不建设论坛、独立讨论区、评论存储或举报处理。
- 本 feature MUST NOT provide 病虫害图片识别、拍照诊断、图片上传分析或视觉模型识别。
- 本 feature MUST NOT provide 农产品价格行情、买卖撮合、订单、支付或交易能力。
- 本 feature MUST NOT provide 施肥或灌溉物联网设备接入、远程控制、传感器数据或自动灌溉。
- 本 feature MUST NOT provide AI 学伴、通用聊天机器人、教师课程发布、管理员内容审核或消息中心。
- 本 feature MUST NOT provide 离线诊断、离线自测、离线课程测验判分或离线语音识别。

## Dependencies and Placeholder Contracts

- **01-账户与门户（已实现，复用）**: 提供学员身份、有效会话、角色路由、最新兴趣标签、学习方向和课程聚合基础能力。
- **02-消息与通知（已实现，复用）**: 提供系统通知、订阅推送、未读管理与触发时受众接口；农事提醒不得绕过该通道。
- **08-教师工作台（尚未实现，前向依赖）**: 生产环境应提供农业课程、发布状态、课程简介、学习统计所需接口和可选 AI 课后测验配置；在 08 尚未实现时，03 只消费 01 现有的已上架课程读取契约，并把测验能力视为“未配置/不可用”，不得在 03 内建立课程或题库编辑器。
- **11-系统管理后台（尚未实现，前向依赖）**: 生产环境应提供农产品目录、农时日历和病虫害知识库读取契约；在 11 尚未实现时，03 使用只读、明确标记为演示用途的最小占位数据，覆盖代表性产品和月份，并能返回“知识库无匹配”。占位数据不得被描述为正式业务数据，不得在 03 内提供增删改维护功能，并必须在 11 接入后由权威来源透明替换。
- **共享语音识别能力（尚未实现，前向依赖）**: 03 消费统一的语音转文字结果，不定义方言分类或语音业务规则；在底层能力尚未接入时，使用可替换的占位适配器覆盖识别成功、失败和 AI 不可用路径。
- **外部 AI 服务**: 提供流式问答、追问建议、诊断追问、诊断结论、诊断自测生成与判分、课程测验判分和语音识别等调用；服务可用性不得阻塞日历、订阅、诊断数据编辑、课程浏览、学习进度或历史查看。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在有历史和无历史两种初始状态下，100% 的日历会话正确选择默认产品与当前月份；产品切换、前后翻月、产品级无数据和月份级无数据空态全部符合规格。
- **SC-002**: 对有效、重复、取消和再次订阅路径，100% 的月度提醒只发送给触发时有效订阅的学员，同一学员同一产品同一月份至多收到一条提醒。
- **SC-003**: 在文字、语音成功、语音失败、AI 可用、本地知识库命中、本地知识库未命中和流式中断测试中，100% 的问答结果、三个追问建议规则及固定提示符合规格。
- **SC-004**: 在诊断充分、恰好五轮上限、中途恢复、连续 365 天无活动自动放弃、主动放弃重开、自测和 AI 不可用测试中，100% 的会话不超过五轮、状态转换正确、历史可查、结论含病因分析与防治方案。
- **SC-005**: 100% 的有效诊断自测包含 3 至 5 道题；每次提交均返回得分、逐题结果和讲解，并可在历史中重新读取。
- **SC-006**: 每条复诊记录均可从原诊断查看；100% 的基于复诊再诊断会话正确预填上轮信息，同时保持字段可编辑。
- **SC-007**: 在课程筛选、推荐、播放中断、重复进度、达到或超过 80% 完成、测验未开启、测验已开启、多次测验提交和 AI 不可用测试中，100% 的正式成绩均等于最近一次有效提交得分，且历史提交不丢失。
- **SC-008**: 100% 的农业课程区块课程均为农业方向已上架课程，且与 08/01 使用的权威课程记录一致；100% 的推荐结果排除已完成课程，并严格按标签匹配数、未完成观看行为、上架时间倒序排序；无课程和推荐为空时显示对应空态。
- **SC-009**: 账户、标签、消息、课程发布和非课程评论能力复用测试中，03 产生的重复实现数量为 0；跨学员读取或修改尝试的拒绝率达到 100%。
- **SC-010**: 对依赖尚未实现的场景，100% 的系统响应可区分正式数据与演示占位，且占位能力不会阻塞问答、诊断、日历、订阅、课程浏览或进度记录的手动路径。

## Assumptions

- 农业技能模块的交互角色限定为已登录学员；管理员、教师、企业、政府和超管通过各自模块管理来源数据，不直接操作本模块的学员记录。
- 当前月份、月初提醒和所有时间顺序均按平台配置时区计算；默认时区为中国标准时间 `Asia/Shanghai`。
- “达到五轮上限但信息仍不足”按合理的强制作结口径处理：输出基于现有信息的最佳可用病因分析与防治方案，并标注“信息有限”，不再追问第六轮。
- 本地病虫害知识库降级只用于农技问答；匹配结果以单条最相关知识条目返回，不生成追问建议，也不用于诊断结论。
- AI 流式回答只有形成完整内容后才触发三个追问建议；中途失败不得把不完整文本标记为完整回答。
- 课程观看进度以学员账号跨会话保存；有效进度单调不回退，达到 80% 后完成状态永久保留。
- “学习行为”用于推荐时使用本模块已记录的农业课程观看、观看进度和完成状态；已完成课程不进入推荐池，未完成观看行为作为标签匹配之后的次级排序信号。
- 诊断自测、复用课程测验和复诊记录属于学习成果来源；具体技能档案汇总、可见范围和简历附带规则由 07 决定。
- 预置数据占位仅服务于 11 尚未实现时的可开发、可验收状态，生产口径始终以 11 台账为准；一旦 11 接入，03 不保留第二份正式数据维护入口。
- 课程评论沿用既有课程视频评论区；如果评论能力尚未实现，03 只保留入口或不可用状态，不自行建立评论系统。
