# Feature Specification: 本土资源

**Feature Branch**: `v2/lixKRT/006-local-resources`

**Created**: 2026-09-19

**Status**: Frozen

**Input**: User description: "从零定义 local-resources：本土资源子系统。依据 06-本土资源章节，提供三大方言语音交互、成功案例、政策与新闻浏览、政策类别订阅和浏览计数；复用既有 ASR、02 通知、01 兴趣标签、10 政策/新闻真 provider。"

## Clarifications

### Session 2026-09-19

- Q: TTS 使用同一大模型接入点还是独立服务？ → A: 使用独立音频语音端点与模型配置 `AI_TTS_URL`、`AI_TTS_MODEL`，复用 `AI_API_KEY`（可由 `AI_TTS_API_KEY` 显式覆盖）；与聊天模型接入点解耦。
- Q: 三大方言如何映射语言代码和音色？ → A: 平台代码固定为粤语 `yue`、客家话 `hak`、潮汕话 `nan`；音色由 `AI_TTS_VOICE_YUE`、`AI_TTS_VOICE_HAKKA`、`AI_TTS_VOICE_TEOCHEW` 映射，部署必须为三项提供非空值。
- Q: 方言语音与普通话对照如何展示？ → A: 同一回答区域同时展示“方言原文”和“普通话对照”，音频控件紧随方言原文；合成完成后尝试播放，浏览器阻止自动播放时保留可手动播放控件。
- Q: 方言交互会话记录保留到什么范围？ → A: 保留成功完成的方言、识别文本、方言回答、普通话对照、创建时间和状态，直至用户账户删除；不保存原始录音、合成音频或音频缓存，也不提供独立历史列表。
- Q: ASR 是否完全沿用 03 的输入口径？ → A: 是。请求仍使用同一 003 转写管线和 `audio` 文件字段，传原始音频字节与文件名，不传方言参数；06 仅把识别失败提示映射为原文“未能识别，请重说或改用文字”。
- Q: 政策下架后的“数据保留”包括什么？ → A: 沿用 010 冻结契约：政策内容、版本、浏览量、订阅关系和历史通知保留；删除时政策内容与浏览量硬删除，订阅关系和历史通知快照保留。
- Q: 类别订阅何时推送、同类多条是否合并？ → A: 沿用 010 冻结契约：每条政策首次发布立即逐条推送，不批量合并；重新上架不补推，当前订阅者在发布时决定受众。
- Q: 新闻三类由谁打标？ → A: 政府发布者在发布时手工选择，06 只按该类别读取，不自动改类。
- Q: 浏览计数如何去重？ → A: 06 为每次成功打开详情生成新的 `view_event_id`；同一学员重复打开会再次计数，同一事件的传输重试不重复计数。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 三大方言语音问答 (Priority: P1)

学员选择粤语、客家话或潮汕话，按住醒目的放大语音按钮提问。系统先复用 003 的语音识别能力展示可编辑文字，再将文字交给 AI 生成方言回答和普通话对照，最后用对应方言语音播放回答。

**Why this priority**: 方言交互是 06 的技术核心和区别于其他模块的主要用户价值。

**Independent Test**: 对三种方言分别完成“录音 → 识别文字 → 提交 → 方言回答 → 普通话对照 → 方言音频播放”；再分别注入噪音识别失败、AI 不可用和 TTS 不可用，核对固定提示和手动路径不受影响。

**Acceptance Scenarios**:

1. **Given** 学员已登录并选择粤语，**When** 完成一次可识别录音，**Then** 页面先展示识别文本，提交后展示粤语回答、普通话对照和可播放的粤语音频。
2. **Given** 学员选择客家话或潮汕话，**When** 完成相同流程，**Then** 分别使用 `hak` 或 `nan` 语言代码与对应音色，回答不退回普通话语音。
3. **Given** 录音为噪音、空白或不可识别，**When** 转写结束，**Then** 显示“未能识别，请重说或改用文字”且不创建成功轮次。
4. **Given** 文本生成或语音合成服务不可用，**When** 学员提交问题，**Then** 显示“AI 服务暂时不可用”，不生成替代回答且文字输入仍可使用。
5. **Given** 一个成功回答已生成，**When** 学员再次播放，**Then** 可重复播放同一方言音频且不重复追加会话轮次。

---

### User Story 2 - 政策浏览、订阅与浏览量 (Priority: P1)

学员按补贴、电商、非遗、培训、认证、综合、创业支持七类浏览政策，只看到政府已上架政策；可订阅或取消订阅类别，并打开详情。每次成功打开详情通过 10 的 provider 记录一次浏览事件。

**Why this priority**: 政策触达是政府供稿与 02 订阅推送的核心闭环，且浏览数据直接服务 10/11 看板。

**Independent Test**: 固定上架、下架、删除和七类政策数据，验证列表与详情可见性、类别筛选、订阅/取消、02 受众读取、同一/不同浏览事件计数和重新上架行为。

**Acceptance Scenarios**:

1. **Given** 政策类别为创业支持且状态为上架，**When** 学员选择创业支持筛选，**Then** 仅显示上架创业支持政策。
2. **Given** 某政策已下架或删除，**When** 学员访问列表或详情，**Then** 两者均不可见；重新上架后恢复可见且不产生新推送。
3. **Given** 学员未订阅电商类别，**When** 订阅后政府首次发布电商政策，**Then** 02 在发布时将该学员纳入该类别的接收者；取消后不再接收后续政策。
4. **Given** 学员成功打开政策详情，**When** 同一 `view_event_id` 重试，**Then** 累计浏览量只增加一次；再次打开生成新事件则再加一。
5. **Given** 访问已下架或已删除政策，**When** 请求记录浏览量，**Then** 不新增计数并返回不可见结果。

---

### User Story 3 - 新闻分类浏览与浏览量 (Priority: P1)

学员按新闻、灾害预警、政策更新三类浏览政府已发布新闻。新闻发布即可见、删除即不可见，没有下架或重新上架操作；详情浏览以幂等事件累计。

**Why this priority**: 灾害预警需要与政策区分的最小、直接可见路径，且不能误用政策订阅逻辑。

**Independent Test**: 发布三类新闻，验证分类可见、详情读取、删除后列表和详情不可见、无上下架动作，以及不同浏览事件的累计。

**Acceptance Scenarios**:

1. **Given** 政府发布灾害预警，**When** 学员选择灾害预警类别，**Then** 新闻立即出现且可打开详情。
2. **Given** 任一新闻已删除，**When** 学员访问列表或详情，**Then** 不存在可见或可恢复入口。
3. **Given** 学员打开新闻详情，**When** 同一事件重试或生成新事件，**Then** 分别表现为不重复计数和累计加一。
4. **Given** 新闻发布或删除，**When** 观察政策订阅通知，**Then** 新闻不触发政策类别推送。

---

### User Story 4 - 本地成功案例浏览 (Priority: P2)

学员浏览预置本地成功创业案例列表，并进入详情查看背景、创业历程和经验启示。本期没有用户投稿、收藏或评论。

**Why this priority**: 成功案例提供低门槛的本土化学习内容，但不依赖方言或政府实时供稿。

**Independent Test**: 使用固定案例数据验证列表、详情、排序、空态和来源边界；尝试写操作不得存在。

**Acceptance Scenarios**:

1. **Given** 存在预置案例，**When** 学员进入案例列表，**Then** 按确定顺序显示标题和摘要。
2. **Given** 学员打开案例详情，**When** 页面加载完成，**Then** 显示背景、历程和经验启示三个内容区。
3. **Given** 无案例数据，**When** 打开列表，**Then** 显示明确空态而不是错误。

---

### User Story 5 - 兴趣标签驱动的政策类别提示 (Priority: P3)

学员的 01 兴趣标签用于提示可订阅的政策类别，并影响类别顺序；系统不会自动订阅，学员仍须明确选择。

**Why this priority**: 复用 v2 兴趣标签体系可降低订阅发现成本，但不阻断核心浏览和订阅。

**Independent Test**: 分别使用作物、电商、手工和岗位标签，核对推荐类别集合、排序和“不自动订阅”行为；跳过标签时按固定默认顺序。

**Acceptance Scenarios**:

1. **Given** 学员选择荔枝、电商直播和手工艺标签，**When** 打开政策订阅区，**Then** 补贴/培训/综合、电商/创业支持和非遗类别按固定推荐顺序提示。
2. **Given** 推荐结果出现，**When** 学员未点击订阅，**Then** 订阅关系保持为空。
3. **Given** 学员没有兴趣标签，**When** 打开政策订阅区，**Then** 按七类固定顺序展示且无推荐标记。

---

### Edge Cases

- 未选择方言、录音为空、浏览器无录音能力或用户拒绝麦克风权限时，不得调用 AI；应保留文字输入并给出识别失败提示。
- ASR 返回空白或仅含空白字符时，不提交空问题。
- AI 返回缺少方言文本、普通话对照、空字段或非法结构时，整轮失败并提示“AI 服务暂时不可用”，不得拼接残缺回答。
- TTS 返回空音频、错误内容类型或上游失败时，整轮语音播放失败并提示“AI 服务暂时不可用”；已生成的文字不得冒充可播放语音。
- 三种方言请求必须使用对应语言代码和音色映射；未知方言不得回退为粤语或普通话。
- 政策类别不是七个允许值、新闻类别不是三个允许值时，06 查询必须拒绝，不自行映射为综合或新闻。
- 政策或新闻在打开后被政府删除时，详情不可继续可见；并发状态由 10 的状态与版本规则负责。
- 浏览量写入失败不得隐藏已成功读取的政策或新闻正文；计数失败不得被视为内容读取失败。
- 同一 `view_event_id` 重试返回同一累计计数；不同内容类型可以复用相同字符串事件标识而不互相误去重。
- 政策下架保留浏览量；重新上架从原累计值继续；删除后该政策对应的浏览量随 10 的硬删除一起消失。
- 新闻删除后对应浏览量随 10 的硬删除一起消失，没有恢复路径。
- 成功案例来源为空时显示空态；来源不可用时显示“案例数据暂不可用”，不得伪造正式数据。
- 兴趣标签为空或含有未知名称时不产生推荐，不影响七类政策浏览。
- 02 在政策首次发布时未找到订阅者应返回零接收者且不阻塞发布；新增订阅者不得收到历史政策推送。

## Requirements *(mandatory)*

### Functional Requirements

#### 身份、角色与边界

- **FR-001**: 006 MUST 仅允许 `student` 角色访问本土资源页面和 API；身份、角色、启用状态与门户路由 MUST 复用 01 当前会话，不得建立第二套账户、会话或学员身份。
- **FR-002**: 006 MUST 复用 01 的兴趣标签目录、当前学员标签和资料读取能力，不得建立第二套标签目录或注册引导。
- **FR-003**: 006 MUST 复用 02 的系统通知、订阅接收者读取和投递通道；不得建立第二套通知、未读角标或推送存储。
- **FR-004**: 006 MUST 只通过 10 已注册的 `PolicyNewsProvider` 读取政策/新闻并记录浏览，不得读取、写入或复制 `government_policies`、`government_news`、浏览量或发布事件表。
- **FR-005**: 006 MUST 复用 003 既有语音转写能力，不得建立第二套 ASR 客户端、模型配置或转写路由。
- **FR-006**: 006 MUST NOT 提供用户投稿资讯、方言语音包离线使用、补贴线上申领/办理、论坛、案例收藏/评论、政策或新闻自助发布。
- **FR-007**: 006 MUST NOT 消费 11 的审核 provider；政策、新闻和成功案例均不进入先审后发流程。

#### 方言助手与 ASR 复用

- **FR-008**: 方言助手 MUST 支持且仅支持 `yue`、`hak`、`nan` 三种方言代码，分别对应粤语、客家话、潮汕话；进入助手前必须明确选择一种。
- **FR-009**: 语音入口 MUST 使用放大的按住/点击录音控件，图标与文字标签同时标识“语音提问”，并满足键盘焦点与 44px 最小触控目标。
- **FR-010**: ASR MUST 调用 003 的同一转写服务入口，输入为原始音频字节和文件名，使用 `audio` multipart 文件字段，不得向底层 ASR 传方言代码或复制转写实现。
- **FR-011**: ASR 成功时 MUST 先向学员展示识别文本并允许修改后再提交；空白、噪音、取消录音、权限拒绝和不可识别均不得提交问题。
- **FR-012**: 06 的 ASR 失败用户提示 MUST 为“未能识别，请重说或改用文字”；该文案转换不得改变 003 对 03 页面使用的原始提示。
- **FR-013**: ASR 上游不可用时 MUST 显示“AI 服务暂时不可用”，不得降级为本地识别或伪造文本。
- **FR-014**: 方言回答生成 MUST 使用文本大模型并按单一结构化调用返回方言回答和普通话对照；不得为普通话对照再建立第二套翻译服务。
- **FR-015**: 方言回答调用 MUST 只包含当前学员已确认的问题文本、方言代码和生成双语回答所需指令；不得包含账号标识、联系方式、会话令牌、其他学员数据或无关历史。
- **FR-016**: AI 回答结构和字段非法、必填文本为空或响应被截断时，整轮 MUST 失败并提示“AI 服务暂时不可用”。
- **FR-017**: 回答展示必须同时包含“方言原文”和“普通话对照”，两者不得互相替代；方言音频控件必须与方言原文绑定。

#### 方言语音合成（TTS）

- **FR-018**: TTS MUST 使用独立音频语音端点与模型配置 `AI_TTS_URL` 和 `AI_TTS_MODEL`，并复用 `AI_API_KEY`；`AI_TTS_API_KEY` 存在时必须覆盖共享凭据。
- **FR-019**: TTS 方言映射 MUST 固定为：粤语 `language_code=yue`、音色 `AI_TTS_VOICE_YUE`；客家话 `language_code=hak`、音色 `AI_TTS_VOICE_HAKKA`；潮汕话 `language_code=nan`、音色 `AI_TTS_VOICE_TEOCHEW`。
- **FR-020**: 部署必须为三种音色配置提供非空值；任一配置缺失时该方言的语音合成 MUST 按服务不可用处理，不得使用其他方言音色或普通话音色。
- **FR-021**: TTS MUST 对完整方言回答执行非流式合成。请求 MUST 使用 `POST AI_TTS_URL`、`Authorization: Bearer <key>` 和 JSON 字段 `model/input/voice/language/response_format`，其中 `response_format` 固定为 `mp3`；成功响应 MUST 为 `audio/*` 非空字节。完整音频对象校验成功后交给前端播放，本期不要求逐音频片段流式播放。
- **FR-022**: TTS 请求 MUST 使用调用点 `local_resources_dialect_tts`，只发送方言回答文本、固定语言代码、配置音色和模型；不得发送普通话对照、用户名或账户信息。
- **FR-023**: TTS 返回空音频、非法内容类型或上游错误时 MUST 显示“AI 服务暂时不可用”，不得降级为浏览器语音、普通话语音或静默失败。
- **FR-024**: 合成完成后 MUST 尝试播放对应音频；浏览器自动播放受限时 MUST 保留可重复手动播放的控件，且重复播放不得新增会话轮次。
- **FR-025**: 原始录音和合成音频 MUST NOT 持久化为文件、BLOB 或缓存；成功轮次只保存文本字段、方言代码和状态。

#### AI 调用点与统一失败

- **FR-026**: 006 的全部 AI 调用点 MUST 无降级；任一调用失败 MUST 使用“AI 服务暂时不可用”，只有 ASR 的不可识别分支使用“未能识别，请重说或改用文字”。
- **FR-027**: 006 MUST NOT 调用 003 的本地病虫害知识库，也不得把任何方言请求路由到 003 问答降级、诊断、课程测验或 12 AI 学伴。
- **FR-028**: AI 失败 MUST NOT 删除已识别文本、已选方言或非 AI 手动内容；允许学员修改后重试或改用文字。
- **FR-029**: AI 失败日志 MUST NOT 包含原始音频、合成音频、密码、会话令牌、联系方式、账户标识或完整私有问题正文。

#### 政策浏览、可见性与订阅

- **FR-030**: 政策类别 MUST 固定为：`subsidy=补贴`、`ecommerce=电商`、`heritage=非遗`、`training=培训`、`certification=认证`、`general=综合`、`entrepreneurship=创业支持`。
- **FR-031**: 学员列表和详情 MUST 只消费 10 provider 返回的上架政策；下架政策只能保留在政府管理数据中，06 不得提供绕过可见性的入口。
- **FR-032**: 06 MUST 提供按单一类别或全部类别读取政策的列表能力，并保留 10 的“发布时间倒序、稳定 ID 正序”确定性排序。
- **FR-033**: 政策重新上架后 MUST 恢复可见并使用同一稳定 ID；06 MUST NOT 自行生成新 ID、改变浏览量或重复发送通知。
- **FR-034**: 政策删除后 MUST 对 06 表现为不存在；下架不删除内容、浏览量、订阅关系或历史通知，删除只使内容与浏览量不可用，订阅和历史通知由各自权威源保留。
- **FR-035**: 学员 MUST 能查询七个类别的当前订阅状态，并分别订阅或取消订阅；重复订阅和重复取消 MUST 幂等。
- **FR-036**: 订阅关系 MUST 是软状态记录，取消订阅不得物理删除历史；下架或删除政策不得级联删除任何政策类别订阅。
- **FR-037**: 06 MUST 通过 02 的现有 `MessagingSourceProvider` 桥接接口提供 `list_policy_subscriber_ids(category: str) -> list[int]`，只返回触发时角色为 `student`、账户启用且当前订阅该中文类别标签的学员。
- **FR-038**: 06 MUST 接受 10 传入的中文类别标签并映射到对应 `category_code`；未知标签 MUST 返回空列表，不得模糊匹配或回退到综合。
- **FR-039**: 06 只提供发布时当前订阅者，不负责政策发布事件、推送时机、标题正文或通知留存；每条政策首次发布即时逐条推送、重新上架不补推的规则由 10/02 保持。
- **FR-040**: 取消订阅只影响后续发布；已经投递的历史通知 MUST 保持可读且不得由 06 撤回或清除。

#### 新闻浏览与可见性

- **FR-041**: 新闻类别 MUST 固定为 `news=新闻`、`disaster_warning=灾害预警`、`policy_update=政策更新`，类别由政府在发布时手工选择。
- **FR-042**: 已发布新闻 MUST 对学员立即可见；06 MUST 按单一类别或全部类别读取，并保持 10 的确定性排序。
- **FR-043**: 新闻 MUST 只有“已发布”和“已删除”两种对外状态；06 MUST NOT 提供下架、重新上架或恢复操作。
- **FR-044**: 新闻删除后 MUST 立即从列表和详情不可见；06 不得缓存可恢复正文或提供历史旁路。
- **FR-045**: 新闻 MUST NOT 触发政策订阅推送，也不得改变政策类别订阅关系。

#### 浏览计数

- **FR-046**: 政策详情和新闻详情每次成功打开 MUST 生成新的非空 `view_event_id`；首次加载和该次网络重试 MUST 复用同一个事件标识。
- **FR-047**: 浏览计数 MUST 通过 10 的 `record_policy_view(policy_id, view_event_id)` 或 `record_news_view(news_id, view_event_id)` 写入，不得直接修改计数表。
- **FR-048**: 去重口径 MUST 为 `(content_type, view_event_id)`；同一学员重复打开政策/新闻使用新事件时分别计数，同一事件重试 10 次只计一次。
- **FR-049**: 只有成功读取到当前可见详情后才能记录浏览；已下架政策、已删除政策或新闻 MUST NOT 新增计数。
- **FR-050**: 浏览计数写入返回 10 的累计整数；06 不维护第二份累计值、不自行加减、不在前端猜测计数。
- **FR-051**: 浏览计数失败 MUST NOT 隐藏已读取内容。前端 MUST 保留正文并显示非阻塞的“浏览量暂未记录”，允许用户继续阅读。
- **FR-052**: 10 看板的当前对外读取接口是 `GET /api/government/dashboard`，字段 `policy.view_count` 与 `news.view_count` 分别读取 10 权威累计值；06 不新增第二套看板统计接口。
- **FR-053**: 删除政策或新闻时，其浏览量必须由 10 随内容硬删除；下架政策保留原浏览量，重新上架继续累计。

#### 成功案例

- **FR-054**: 成功案例 MUST 为只读预置内容，列表至少暴露稳定 ID、标题和摘要，详情至少暴露背景、历程、经验启示和更新时间。
- **FR-055**: 成功案例列表顺序 MUST 稳定，默认按预置顺序或发布时间倒序后以稳定 ID 为 tie-breaker；无数据时显示空态。
- **FR-056**: 成功案例 MUST 通过可替换的只读 provider 边界读取；06 默认可以提供明确标记为演示用途的只读数据，但不得伪装为 11 的正式权威内容。
- **FR-057**: 成功案例 provider MUST 提供单一注册槽 `local_resource_case_provider`、`set_local_resource_case_provider(app, provider)` / `get_local_resource_case_provider()`，并冻结以下签名；11 接入后只替换 provider，不改变 06 页面或调用分支：

```python
class LocalResourceCaseProvider(Protocol):
    def list_success_cases(self) -> list[dict]: ...
    def get_success_case(self, case_id: str) -> dict | None: ...
```
- **FR-058**: 成功案例来源不可用时 MUST 显示“案例数据暂不可用”，不得用硬编码页面正文绕过 provider。

#### 兴趣标签复用

- **FR-059**: 06 MUST 读取 01 当前学员标签，不新增标签、不修改标签，也不把政策类别写成 `interest_tags` 目录记录。
- **FR-060**: 推荐类别映射 MUST 固定为：作物标签“荔枝/龙眼/水稻/水产”提示 `subsidy,training,general`；电商相关标签“电商直播/短视频/客服沟通/电商运营/客服专员”提示 `ecommerce,entrepreneurship`；手工标签“手工艺/手工艺人”提示 `heritage`；岗位标签“农业技术员”提示 `certification,entrepreneurship`。
- **FR-061**: 推荐只影响提示和排序，MUST NOT 自动创建订阅；未知标签或无标签时按七类固定顺序展示。

#### 跨模块 Provider 契约

- **FR-062**: 06 MUST 作为政策/新闻消费者，只调用注册槽 `government_policy_news_provider` 的 `get_policy_news_provider()`，不得依赖具体数据库实现或判断 provider 是否占位。
- **FR-063**: 06 MUST 接受并冻结以下 `PolicyNewsProvider` 签名；本 feature 不新增第二政策/新闻注册表或占位实现：

```python
class PolicyNewsProvider(Protocol):
    def list_published_policies(self, category: str | None = None) -> list[dict]: ...
    def get_published_policy(self, policy_id: str) -> dict | None: ...
    def list_published_news(self, category: str | None = None) -> list[dict]: ...
    def get_published_news(self, news_id: str) -> dict | None: ...
    def record_policy_view(self, policy_id: str, view_event_id: str) -> int: ...
    def record_news_view(self, news_id: str, view_event_id: str) -> int: ...
```

- **FR-064**: 政策记录 MUST 保留 `id/title/content/category_code/category_label/published_at/updated_at/version`，新闻记录 MUST 保留相同字段；跨模块 ID 为非空字符串，时间为带 `+08:00` 时区的 ISO 8601。
- **FR-065**: provider 未命中、未上架或已删除内容时，`get_*` MUST 返回 `None`，`list_*` MUST 返回空列表；consumer 未找到后映射为 404，不得返回伪造记录。
- **FR-066**: provider 不可用、冲突或校验失败时 MUST 映射到现有 `ProviderError` 层级语义，06 不得把数据库异常文本直接暴露给用户。
- **FR-067**: 06 MUST 通过 `register_messaging_source_provider(app, LocalResourcesMessagingProvider())` 注册政策订阅来源；该 provider 只实现 02 已冻结桥接形状，不建立第二消息源注册表。
- **FR-068**: `PolicyNewsProvider` 当前定义在 10 业务包 `backend/app/government_console/providers.py`，而共享审核契约位于 `backend/app/content_review/`；本 feature MUST NOT 为统一位置而迁移或复制任一契约。实现计划可消费当前 10 注册槽，同时将该位置不一致记录为后续治理问题。

### AI Call Point and Degradation Matrix

| Call point | Owner / reuse | Input | Failure behavior | Degradation |
| --- | --- | --- | --- | --- |
| ASR transcription | 003 reuse; same 003 transcription pipeline | audio bytes + filename; no dialect parameter | 识别不可用/空白：06 显示“未能识别，请重说或改用文字”；上游不可用：“AI 服务暂时不可用” | None |
| Dialect answer generation | `local_resources_dialect_answer`; 006 AI text call | confirmed question + dialect code | 显示“AI 服务暂时不可用”，不返回残缺回答 | None |
| Dialect speech synthesis | `local_resources_dialect_tts`; new 006 audio call | dialect answer + language code + configured voice + TTS model | 显示“AI 服务暂时不可用”，无浏览器/普通话/其他方言替代 | None |

### Content Visibility State Machines

#### Policy

| State | 06 student-visible | 06 allowed action | View counter | Subscriptions | Historical notification |
| --- | --- | --- | --- | --- | --- |
| 上架 | Yes | 浏览、记录浏览事件、订阅/取消类别 | Preserved and incrementable | Preserved | Preserved |
| 下架 | No | 无详情；不得记录浏览 | Preserved but not incrementable | Preserved | Preserved |
| 删除 | No | 无详情；不得记录浏览 | Deleted with 10 policy | Preserved | Snapshot retained; source marked unavailable by 02/10 |

#### News

| State | 06 student-visible | 06 allowed action | View counter | Policy push |
| --- | --- | --- | --- | --- |
| 已发布 | Yes | 浏览、记录浏览事件 | Incrementable | Never |
| 已删除 | No | 无详情；不得记录浏览 | Deleted with 10 news | Never |

### Key Entities

- **方言会话轮次**: 一次成功方言问答的方言代码、识别文本、方言回答、普通话对照、创建时间和完成状态；不保存音频。
- **政策类别订阅**: 学员与七类政策之一的软状态关系，包含启用/取消状态和时间；跨政策下架、删除和历史通知保留。
- **政策浏览事件**: 由 06 发起的稳定事件标识，交给 10 记录并按 `(content_type, view_event_id)` 去重。
- **新闻浏览事件**: 新闻详情的幂等浏览事件，交给 10 记录并与政策事件类型隔离。
- **成功案例**: 只读预置内容，包含稳定 ID、标题、摘要、背景、历程、经验启示、排序和更新时间。
- **政策/新闻 Provider**: 10 已实现并被 06 消费的跨模块只读与浏览量写入契约，注册槽为 `government_policy_news_provider`。
- **政策订阅 Messaging Provider**: 06 提供给 02 的桥接实现，按中文政策类别返回当前有效学员订阅者。
- **TTS 配置映射**: 方言代码、语言代码、音色配置键、模型和音频端点之间的固定关系。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 对粤语、客家话、潮汕话各执行一次有效流程，100% 成功展示识别文本、对应方言回答、普通话对照和对应音色音频，且三组语言代码映射零混用。
- **SC-002**: 对噪音、空录音、权限拒绝、空 AI 响应和 TTS 失败的每组测试，100% 显示规定文案，普通文字输入仍可用，0 条请求进入本地知识库降级。
- **SC-003**: 七类政策筛选与三类新闻筛选的每条固定数据均只出现在正确类别；下架政策和删除新闻在列表、详情和计数写入路径中的不可见率为 100%。
- **SC-004**: 政策订阅/取消测试中，02 在发布时返回的接收者与当前有效订阅者集合完全一致；重新上架和重复发布重试产生的新通知数为 0。
- **SC-005**: 同一 `view_event_id` 重试 10 次累计增加 1；同一学员使用 3 个新事件打开同一详情累计增加 3；政策下架再上架后的累计值不减少。
- **SC-006**: 删除政策或新闻后，10 看板中的对应浏览量和内容计数按 010 规则更新，06 无本地重复计数。
- **SC-007**: 成功案例固定数据下，列表、详情、稳定排序和空态测试通过率 100%；所有写操作请求返回不存在或方法不允许。
- **SC-008**: 兴趣标签映射测试覆盖作物、电商、手工、岗位和无标签五组输入，推荐类别与固定顺序 100% 匹配且自动订阅数为 0。
- **SC-009**: 06 的静态和运行时检查中，政策/新闻直接表访问为 0、第二 provider 注册表为 0、替代 ASR 实现为 0、AI 降级分支为 0。
- **SC-010**: 未登录或非学员访问全部 06 页面/API 的拒绝率为 100%；学员无法读取其他学员的会话或订阅数据。

## Assumptions

- `AI_TTS_URL`、`AI_TTS_MODEL` 和三个音色键由部署环境提供；测试环境使用可注入的假 TTS client，不把真实密钥写入仓库。
- `yue/hak/nan` 是平台内部的稳定语言路由代码；外部 TTS 供应商若要求其他标识，由部署映射或适配器转换，不改变浏览器、后端 API 和会话记录中的平台代码。
- 方言回答使用一次完整结构化文本调用；方言文本和普通话对照必须在同一次响应中满足契约。
- TTS 采用完整音频响应而不是实时流式音频，原因是本期交互顺序为“识别确认 → 完整回答 → 播放”，没有边生成边播放的验收要求。
- 会话文本保留到账户删除；原始音频和合成音频不保留。本期不提供独立历史列表，记录用于审计和后续能力扩展。
- 成功案例默认数据是 06 开发期的只读演示内容；11 接入后通过 `local_resource_case_provider` 替换，不把演示内容描述为正式业务数据。
- 浏览事件由浏览器在每次成功打开详情时生成；后端在事务或网络重试中复用同一事件标识。具体是否显示累计值不属于 06 的验收重点，正文展示不能被计数失败阻断。
- 11 的看板读取接口尚未在当前 provider 契约中定义；本期冻结 10 现有 `GET /api/government/dashboard` 作为政策/新闻浏览量的当前外部读取路径，11 接入时需要由 11/10 明确只读 provider，06 不新增替代统计源。
- `PolicyNewsProvider` 的接口位置不一致属于已知治理问题。本 feature 直接消费当前 10 注册槽，不复制签名、不新建共享包；后续若统一位置，应保留同一注册键和方法形状。

## Dependencies, Reuse, and Placeholder Boundaries

- **01-账户与门户（已实现，复用）**: 当前学员会话、角色、启用状态、个人资料与兴趣标签。不得建立第二套标签或身份。
- **02-消息与通知（已实现，复用）**: `MessagingSourceProvider.list_policy_subscriber_ids(category)`、通知持久化和未读管理。不得绕过或复制。
- **003-农业技能（已实现，复用）**: 同一语音转写管线、`audio` 文件输入、文件名和不可识别语义；06 只负责用户文案映射，不建立第二套 ASR。
- **10-政务工作台（已实现，消费）**: `PolicyNewsProvider` 六方法、`government_policy_news_provider` 注册槽、政策三态/新闻两态和浏览事件幂等。不得读取 10 表或写占位 provider。
- **11-系统管理后台（未来，延后）**: 成功案例的正式只读来源将在 11 接入时通过 `local_resource_case_provider` 替换；当前演示数据必须明确标识。
- **外部 AI 服务（外部依赖）**: 复用共享文本模型与 003 ASR；新增独立 TTS 音频端点。所有方言助手调用无降级。

## Out of Scope

- 方言语音包离线使用、浏览器本地 TTS/ASR、离线缓存音频。
- 用户自行发布资讯、案例或方言内容。
- 补贴申领、材料提交、审批或办理进度。
- 论坛、案例评论、收藏、分享排行。
- 政策或新闻的发布、编辑、上下架、删除和审核；这些继续由 10/11 负责。
- 为统一 provider 位置而迁移 `government_console.providers`、`content_review.providers` 或新建第三个共享包。
