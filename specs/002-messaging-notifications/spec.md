# Feature Specification: 02-消息与通知

**Feature Branch**: `v2/lixKRT/002-messaging-notifications`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "messaging: 消息与通知子系统，实现站内私信、系统通知、订阅推送、未读角标与已读管理；复用 01 已提供的登录会话与角色路由，不重新定义账户、会话或门户能力。"

## Clarifications

### Session 2026-09-15

- Q: 已读/未读状态应按用户账号跨登录会话和设备持久保存，还是仅在当前会话或设备内有效？ → A: 按用户账号跨登录会话和设备持久保存；一端标记已读后，其他端同步更新。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 在允许的关系范围内进行站内私信 (Priority: P1)

教师和学员可以直接沟通；学员与已投递岗位对应企业可以围绕投递关系沟通。用户在消息中心查看会话、发送消息、接收回复，并按时间顺序保留完整往来记录。范围外用户看不到发起入口，直接请求也会被拒绝。

**Why this priority**: 私信是平台内跨角色沟通的基础，同时必须严格守住投递关系和教师学员关系边界。

**Independent Test**: 准备教师、多个学员、多个企业及不同投递关系的账户，分别验证允许组合、禁止组合、多轮回复、时间顺序和未读变化。

**Acceptance Scenarios**:

1. **Given** 任意教师和任意学员，**When** 任一方发起私信，**Then** 双方可以建立会话并多轮回复。
2. **Given** 学员已向某企业投递岗位，**When** 学员或该企业任一方发起私信，**Then** 双方可以建立会话并多轮回复。
3. **Given** 学员与企业之间不存在投递关系，**When** 任一方尝试发起私信，**Then** 发起入口不可见且直接请求被拒绝。
4. **Given** 学员与学员、企业与企业、教师与教师，**When** 任一方尝试发起私信，**Then** 不允许建立会话。
5. **Given** 双方已建立私信会话，**When** 查看线程，**Then** 消息按发送时间正序展示，且后续回复不会覆盖历史消息。
6. **Given** 一方发送私信，**When** 接收方进入消息中心，**Then** 接收方多一条未读消息，发送方未读数不因自己发送而变化。

---

### User Story 2 - 接收关键业务事件通知 (Priority: P1)

用户在审核、求职、兑换履约和账户重置等关键事件发生后，收到与自身业务关系匹配的系统通知。通知明确说明结果、对象和必要业务信息，驳回或取消等结果包含原因或影响。

**Why this priority**: 业务状态变化必须可靠触达相关用户，否则审核、投递和履约流程无法形成完整闭环。

**Independent Test**: 在预置业务数据中依次触发每一种已定义事件，检查通知接收者、类型、内容要素和未读状态；触发无关账户不得收到通知。

**Acceptance Scenarios**:

1. **Given** 教师提交课程视频、非遗教学视频或企业提交职位，**When** 审核通过，**Then** 提交者收到“已通过并上架”的通知；审核驳回时，提交者收到包含审核意见的通知。
2. **Given** 学员成功投递职位，**When** 投递完成，**Then** 对应企业收到含学员姓名和岗位标题的通知。
3. **Given** 企业标记或改标申请状态，**When** 状态保存为新值，**Then** 对应学员收到包含最新状态的通知。
4. **Given** 企业删除职位并导致未处理申请关闭，**When** 删除完成，**Then** 每位受影响的学员收到“岗位已关闭”的通知。
5. **Given** 学员兑换奖品、管理员发放或取消履约，或学员积分到期清零，**When** 事件完成，**Then** 学员收到对应通知，并包含积分消耗、发放结果、积分回退或清零数额等适用信息。
6. **Given** 超级管理员通过消息方式告知用户密码已重置，**When** 重置完成，**Then** 对应用户收到密码重置通知；线下告知不作为账号是否可登录的依据。

---

### User Story 3 - 管理未读角标与已读消息 (Priority: P1)

用户在全局顶栏或门户看到未读私信与未读通知的总数。打开单条内容、一键全部已读或清除已读后，列表与角标按规则立即更新。

**Why this priority**: 未读管理和清除行为决定消息中心是否可持续使用，也是用户感知新事件的主要入口。

**Independent Test**: 准备不同组合的未读私信与通知，依次执行单条点开、全部已读、清除已读和再次接收消息，核对角标、列表和保留范围。

**Acceptance Scenarios**:

1. **Given** 用户同时有未读私信和未读通知，**When** 查看顶栏或门户，**Then** 角标显示两类未读条目的总和。
2. **Given** 某条消息未读，**When** 用户打开该条，**Then** 仅该条变为已读且角标减少一。
3. **Given** 用户存在任意未读条目，**When** 执行一键全部已读，**Then** 所有私信和通知均变为已读且角标归零。
4. **Given** 用户同时有已读和未读条目，**When** 执行清除已读，**Then** 已读条目从该用户列表移除，未读条目继续保留。
5. **Given** 用户清除了某会话的已读消息，**When** 该会话收到新消息，**Then** 会话重新显示且新消息保持未读。

---

### User Story 4 - 接收公告与订阅推送 (Priority: P2)

管理员发布系统公告、教师发布教学公告，以及政策或农事订阅产生的新内容，通过同一消息中心触达正确受众，不另建公告栏或独立推送入口。

**Why this priority**: 公告和订阅是平台统一触达能力，但依赖模块 06、08、10 和 11 的业务触发。

**Independent Test**: 分别发布两类公告和两类订阅更新，核对触发时点、受众集合、通知内容及后续订阅变更对既有通知的影响。

**Acceptance Scenarios**:

1. **Given** 管理员发布系统公告，**When** 公告生效，**Then** 触发时存在的全部用户均收到系统通知。
2. **Given** 教师发布教学公告，**When** 公告生效，**Then** 触发时存在的全部学员收到系统通知，非学员不收到。
3. **Given** 政府发布新政策，**When** 政策上架，**Then** 触发时订阅对应政策类别的学员收到含政策标题和类别的通知。
4. **Given** 进入新自然月且学员订阅了农产品，**When** 月度农事提醒触发，**Then** 该学员收到对应农产品和月份的农事提醒。
5. **Given** 用户已收到某次订阅推送，**When** 随后取消订阅，**Then** 既有通知不被撤回，后续触发不再向该用户发送。

### Edge Cases

- 范围外私信通过直接请求绕过入口时，不得创建会话或消息，也不得改变任何未读数。
- 会话双方中的一方账户被禁用时，既有消息仍保留；禁用账户的访问限制由 01 的会话与账户规则处理。
- 学员投递过的职位后续关闭、离职状态改变或申请历史化时，先前的私信与会话留存不变。
- 同一业务事件因重复触发被处理时，同一接收者不应收到重复的用户可见通知。
- 业务对象后续被编辑、下架或删除时，历史通知仍可阅读，其业务引用需要标明不可用状态。
- 公告或订阅事件发生时不在目标受众中的用户，不得因之后变更角色或订阅状态而补收历史通知。
- 清除已读只影响当前用户自己的可见列表，不改变其他参与者、通知历史或角标统计口径。
- 未读条目不能通过“清除已读”被移除；只有明确标记已读后，才进入可清除范围。
- 用户尝试管理他人的消息、会话、通知或已读状态时必须被拒绝。
- 消息中心没有可见内容时显示空态，不得把已清除的历史条目重新计入未读或列表。

## Requirements *(mandatory)*

### Functional Requirements

**站内私信**

- **FR-001**: System MUST provide authenticated users with a unified message center for private messages and system notifications.
- **FR-002**: Teacher-to-student and student-to-teacher private messaging MUST be allowed for any teacher-student pair.
- **FR-003**: Student-to-enterprise and enterprise-to-student private messaging MUST be allowed when the student has submitted an application to that enterprise.
- **FR-004**: The only permitted private-message combinations are teacher-student and student-enterprise with an existing application relationship; all other combinations MUST be unavailable.
- **FR-005**: System MUST hide private-message entry points for prohibited combinations and MUST reject direct attempts without creating a conversation or message.
- **FR-006**: Administrator and government roles MUST be able to receive system notifications and announcements but MUST NOT participate in private messaging under this scope.
- **FR-007**: A permitted first message MUST create or reuse one private conversation for the two participants.
- **FR-008**: Participants MUST be able to send and reply multiple times within an existing conversation.
- **FR-009**: System MUST retain private messages as a conversation thread and display them in chronological order.
- **FR-010**: Sending a private message MUST increment the recipient’s unread count and MUST NOT change the sender’s unread count.
- **FR-011**: Private messages MUST NOT be recalled or edited after sending.
- **FR-012**: Changes to an underlying application or position, including closure, MUST NOT remove previously retained private-message history.

**系统通知**

- **FR-013**: System MUST create one notification for each defined business event and deliver it only to the event’s intended recipient or recipients.
- **FR-014**: Course-video, job-position, and intangible-heritage-video review approval MUST notify the submitter that the content passed and is published.
- **FR-015**: Review rejection MUST notify the submitter and include the reviewer’s rejection opinion.
- **FR-016**: A successful student job application MUST notify the corresponding enterprise and include the student name and job title.
- **FR-017**: Every enterprise application-status mark or change MUST notify the corresponding student with the latest status.
- **FR-018**: Deleting a position that closes unprocessed applications MUST notify every affected student that the position is closed.
- **FR-019**: Successful prize redemption MUST notify the student with the points consumed and prize information.
- **FR-020**: Fulfillment issuance MUST notify the student that the prize has been issued.
- **FR-021**: Fulfillment cancellation MUST notify the student and include the restored-points information.
- **FR-022**: Point expiration and clearing MUST notify the affected student with the cleared point amount.
- **FR-023**: When account password reset is communicated through the platform, the affected user MUST receive a password-reset notification; the reset operation itself remains owned by module 11.
- **FR-024**: Every notification MUST expose an event category, readable content, creation time, read state, and a source reference when the event concerns another business object.
- **FR-025**: Each occurrence of a status change or distinct business event MUST produce its corresponding notification without duplicating an otherwise identical event for the same recipient.
- **FR-026**: A historical notification MUST remain readable even if its referenced business object is later changed, unpublished, or deleted; the referenced object’s current availability MUST be determined by its owning module.

**公告与订阅推送**

- **FR-027**: A system announcement from an administrator MUST create a notification for every user account existing when the announcement takes effect.
- **FR-028**: A teaching announcement from a teacher MUST create a notification for every student account existing when the announcement takes effect.
- **FR-029**: A newly published policy MUST notify each student subscribed to its policy category at publication time and MUST include the policy title and category.
- **FR-030**: A monthly agricultural reminder MUST notify each student subscribed to the relevant agricultural product and MUST identify the product and reminder month.
- **FR-031**: Announcement and subscription delivery MUST use only the unified message center and MUST NOT require a separate announcement page.
- **FR-032**: Delivery MUST use the subscription audience that exists at trigger time; later subscribers MUST NOT receive previously triggered notifications.
- **FR-033**: Unsubscribing after a notification is delivered MUST NOT remove the existing notification but MUST prevent future subscription notifications after the change takes effect.
- **FR-034**: Announcement and subscription notifications MUST enter the same unread and read-management rules as other system notifications.

**未读角标与已读管理**

- **FR-035**: The global unread badge MUST equal the current user’s unread private-message count plus unread system-notification count.
- **FR-036**: The unread badge MUST be available from the global top bar or portal-level message entry.
- **FR-037**: Opening one private message or notification MUST mark only that item read for the current user.
- **FR-038**: A user MUST be able to mark all of their private messages and notifications read in one action, reducing the unread badge to zero.
- **FR-039**: A user MUST be able to clear read private messages and notifications from their own visible list while retaining every unread item.
- **FR-040**: Clearing read items MUST be a per-user visibility action and MUST NOT remove or alter another user’s data or the underlying business event.
- **FR-041**: A cleared private conversation that receives a new message MUST become visible again with the new item unread and earlier cleared items remaining hidden.
- **FR-042**: A user MUST NOT be able to view or change another user’s conversations, messages, notifications, or read state.
- **FR-043**: Empty message-center views MUST show an empty state and MUST NOT report cleared items as unread.
- **FR-044**: Read state MUST persist per user account across login sessions and devices; marking an item read in one session or device MUST make that read state visible in the same account’s other sessions and devices.
- **FR-045**: Private messages and system notifications MUST be the only two top-level message types. Business-event notices and business reminders, announcements, and subscription pushes MUST be system-notification categories, sharing the same message center, unread badge, and read-management rules.
- **FR-046**: Teacher and enterprise workspaces MUST own their business actions, status transitions, source records, and the eligibility context and entry points for communication actions. This feature MUST own conversations, notification delivery records, message-center presentation, unread totals, and read state; those workspaces MUST NOT maintain separate message centers, delivery records, unread totals, or read states.
- **FR-047**: Clearing read items MUST mean only that previously read items are hidden from the acting user’s visible list. It MUST NOT recall a sent private message, permanently remove it for another participant, or clear any unread item; no message recall or editing operation is available.

### Key Entities

- **Private Conversation**: A two-participant messaging thread established under a permitted teacher-student or student-enterprise relationship.
- **Private Message**: A text message within one conversation, with sender, send time, recipient read state, and retained history.
- **System Notification**: A recipient-specific platform message in one of three categories: business-event notice or reminder, announcement, or subscription push. All categories share the same message center and read rules; includes event category, content, creation time, read state, and optional source reference.
- **Delivery Audience**: The recipients selected when an event triggers, such as all users, all students, subscribers to one policy category, or subscribers to one agricultural product.
- **Application Relationship**: The evidence that a student submitted an application to an enterprise; it determines student-enterprise private-message eligibility and may outlive an individual application status.
- **Subscription Relationship**: A student’s current interest in an agricultural product or policy category; it determines future subscription pushes but does not rewrite previously delivered notifications.
- **Read State**: The per-message or per-notification, per-recipient-account state that persists across login sessions and devices and determines unread totals and whether an item is eligible for the user’s clear-read action.

## Scope Boundaries

- Account identity, login state, sessions, disabled-account enforcement, and role routing remain owned by module 01 and MUST NOT be redefined by this feature.
- Source modules own the business events and source records for reviews, applications, fulfillment, password reset, announcements, policy publication, and monthly agricultural reminders; this feature owns delivery, notification presentation, unread accounting, and read state.
- This feature MUST NOT send SMS, email, or other off-platform messages.
- This feature MUST NOT provide AI-assistant conversations; module 12 owns those interactions.
- This feature MUST NOT provide message recall, message editing, group private chat, forums, or community discussions.
- This feature MUST NOT process business state changes such as review decisions, application changes, redemption, fulfillment, or policy publication.
- This feature MUST NOT provide a separate announcement page; announcements are delivered as system notifications in the message center.
- This feature MUST NOT define user identity, role permissions, or account lifecycle behavior beyond applying the current authenticated user and role supplied by module 01.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the complete relationship-matrix test, 100% of permitted combinations can start and continue a conversation, and 100% of prohibited combinations are both hidden and rejected.
- **SC-002**: In scripted event tests, 100% of defined events reach exactly the intended recipients, with required names, titles, statuses, reasons, points, or categories present where specified.
- **SC-003**: Under normal operation, recipients can see a newly triggered system notification within 30 seconds of the business event taking effect.
- **SC-004**: After a sequence of at least 100 mixed send, receive, open, mark-all, and clear-read actions, the displayed unread badge exactly matches the remaining unread items.
- **SC-005**: In management tests, opening one item decrements the badge by exactly one, marking all read reaches zero, and clearing read removes only previously read items.
- **SC-006**: In delivery-audience tests, system announcements reach 100% of users at trigger time, teaching announcements reach 100% of students and zero non-students, and subscription pushes reach 100% of matching current subscribers and zero non-subscribers.
- **SC-007**: In authorization tests, 100% of attempts to access or change another user’s message data are rejected.
- **SC-008**: In conversation-history tests, 100% of retained messages appear in chronological order, and no later event removes history from the other participant’s view.
- **SC-009**: In usability tests, a first-time user can locate an unread item and mark it read within three interactions from their portal.
- **SC-010**: In account-level consistency tests, 100% of read-state changes made in one login session or device are reflected for the same account in another session or device, and logout or session expiration MUST NOT reset a read item to unread.
- **SC-011**: In message-type and ownership tests, 100% of business-event notices and reminders, announcements, and subscription pushes appear as system-notification categories, and teacher and enterprise workspaces expose no independent message center or unread state.
- **SC-012**: In clear-read and recall tests, 100% of cleared items remain hidden only for the acting user, other participants retain their conversation history and unread items, and no recall or edit operation is accepted.

## Assumptions

- Module 01 already provides a valid authenticated identity, role, session, and disabled-account behavior; this feature does not implement or redefine them.
- Teacher-student and student-enterprise messaging eligibility is based on the relationship having existed: a student may communicate with any teacher, and an enterprise relationship remains eligible after a student has submitted an application even if that application or position later closes.
- Private messaging is limited to two participants; announcements and subscription pushes are one-way notifications.
- Direct messages and notification bodies are text-first; attachments, images, audio messages, and other rich message types are outside this scope.
- Read state is tracked independently per recipient account and persists across login sessions and devices. Senders do not receive read receipts under this scope.
- “Clear read” removes items from the current user’s visible list but does not globally erase them or change any other user’s view; if a cleared conversation receives a new item, the conversation reappears with only the new unread item visible from that point onward.
- Broadcast audiences are captured at trigger time and are not retroactive for users who later change role or subscription status.
- Notifications remain available for future reading unless the recipient clears their read items; source-object changes do not delete or rewrite notification content.
- A single business event produces at most one user-visible notification per recipient even if the source operation is retried.
- Monthly agricultural reminders use the platform’s configured time zone and represent the applicable calendar month.
