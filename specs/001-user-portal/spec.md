# Feature Specification: 01-账户与门户

**Feature Branch**: `v2/lixKRT/001-user-portal`

**Created**: 2026-09-14

**Status**: Draft

**Input**: User description: "user-portal: 实现 01-账户与门户，包括学员和教师注册、六类角色登录与会话管理、角色门户路由、兴趣标签引导、首次使用蒙层引导、学员个人资料及课程聚合入口。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 学员与教师自助注册 (Priority: P1)

新学员或教师从注册入口选择自助注册角色，填写账户和身份信息。系统逐项校验后创建账户；学员先完成或跳过兴趣标签引导，再进入学员门户，教师直接进入教师工作台。

**Why this priority**: 自助注册是学员和教师进入平台的第一条可用路径；没有该路径，依赖账户的其余功能无法独立开始使用。

**Independent Test**: 在无现有账户的环境中，分别使用有效学员信息和有效教师信息完成注册；验证所有错误分支、学员兴趣标签步骤、默认学习方向、自动进入门户的结果。

**Acceptance Scenarios**:

1. **Given** 新用户进入注册页，**When** 查看角色选项，**Then** 只能选择“学员”或“教师”，其他角色不可自助注册。
2. **Given** 用户填写有效学员信息，**When** 提交注册，**Then** 创建学员账户和默认学习方向为“综合”的个人资料，并进入可跳过的兴趣标签引导页。
3. **Given** 学员位于兴趣标签引导页，**When** 选择并保存标签或选择跳过，**Then** 系统自动登录学员并进入学员门户。
4. **Given** 用户填写有效教师信息，**When** 提交注册，**Then** 创建教师账户并自动登录教师工作台。
5. **Given** 任一必填字段为空、格式不符、用户名已被占用或两次密码不一致，**When** 提交注册，**Then** 不创建账户，并在对应字段显示明确错误和焦点。

---

### User Story 2 - 登录、会话与角色门户路由 (Priority: P1)

六类角色使用用户名和密码登录。系统根据账户状态和角色决定拒绝登录或进入对应门户；会话到期后，用户重新登录即可继续原操作。

**Why this priority**: 登录、会话和角色路由是所有受保护功能的共同入口，也是权限隔离的基础。

**Independent Test**: 使用六类角色的有效账户及无效凭证、禁用账户、过期会话分别验证登录结果、门户归属和原操作恢复。

**Acceptance Scenarios**:

1. **Given** 任一类角色拥有有效且启用的账户，**When** 使用正确凭证登录，**Then** 学员、教师、企业、政府分别进入对应门户，超级管理员和普通管理员进入管理后台。
2. **Given** 用户名不存在或密码错误，**When** 提交登录，**Then** 始终显示“用户名或密码错误”，不暴露具体错误项，并允许重试。
3. **Given** 账户已被禁用，**When** 使用正确凭证登录，**Then** 拒绝登录并显示“账户已被禁用，请联系管理员”。
4. **Given** 用户点击忘记密码，**When** 查看提示，**Then** 显示“请联系管理员重置密码”，且不提供自助重置入口。
5. **Given** 已登录会话达到有效期或失效，**When** 用户执行需登录的操作，**Then** 自动跳转登录页；重新登录成功后返回原操作位置。

---

### User Story 3 - 学员维护个人资料与兴趣偏好 (Priority: P2)

学员查看并编辑姓名、联系方式、学习方向和兴趣标签。变更后的方向与标签成为课程推荐、岗位推荐、方向统计和 AI 学情报告的最新输入。

**Why this priority**: 学员偏好决定个性化内容；该流程同时支撑课程聚合和多个下游学习模块。

**Independent Test**: 使用已有学员资料分别修改学习方向和标签，随后检查个人资料、课程推荐池、岗位推荐区及方向统计入口是否读取最新值。

**Acceptance Scenarios**:

1. **Given** 学员已登录，**When** 打开个人资料，**Then** 可查看姓名、联系方式、学习方向和现有兴趣标签。
2. **Given** 学员编辑任一可编辑字段，**When** 保存有效内容，**Then** 新值持久保留并在当前会话后续视图中可见。
3. **Given** 学员修改学习方向或增删兴趣标签，**When** 进入课程推荐、岗位推荐、方向统计或 AI 学情报告相关视图，**Then** 对应结果使用修改后的方向和标签。
4. **Given** 学员尚无兴趣标签，**When** 浏览推荐内容，**Then** 系统仍可提供普通课程或岗位，不把标签缺失视为错误。

---

### User Story 4 - 学员课程聚合入口 (Priority: P2)

学员通过门户中的“课程”聚合页按农业、电商、手工方向浏览全部已上架课程；兴趣标签匹配的课程获得推荐优先展示。

**Why this priority**: 聚合入口为学员提供跨课程模块的统一发现路径，并验证推荐偏好是否真正生效。

**Independent Test**: 准备三个方向的已上架、待审核和已下架课程，以不同标签的学员账户打开各方向页签，验证过滤、排序、同源一致性与空态。

**Acceptance Scenarios**:

1. **Given** 平台存在多个方向的已上架课程，**When** 学员切换农业、电商或手工页签，**Then** 仅显示对应方向且已上架的课程。
2. **Given** 学员拥有与课程匹配的兴趣标签，**When** 查看某方向课程列表，**Then** 匹配课程位于普通课程之前。
3. **Given** 多个课程具有相同推荐层级，**When** 查看列表，**Then** 按上架时间倒序排列。
4. **Given** 所选方向没有已上架课程，**When** 打开聚合页，**Then** 显示“暂无课程”空态。

---

### User Story 5 - 首次使用分步蒙层引导 (Priority: P2)

任一角色首次登录其门户时看到分步蒙层引导。完成全部步骤或主动跳过后不再出现；中途关闭或离开则不记录完成状态。

**Why this priority**: 新手引导降低首次使用的学习成本，但不应重复打扰已经完成或明确跳过的用户。

**Independent Test**: 对每类角色分别执行完成、跳过、刷新离开和关闭离开，再次登录验证引导状态。

**Acceptance Scenarios**:

1. **Given** 某角色首次登录，**When** 进入其门户，**Then** 分步高亮该门户核心功能入口并显示对应说明。
2. **Given** 用户完成全部引导步骤，**When** 再次登录，**Then** 不再出现该门户引导。
3. **Given** 用户在任一步骤点击跳过，**When** 再次登录，**Then** 不再出现该门户引导。
4. **Given** 用户在引导未完成时关闭、刷新或离开，**When** 再次进入门户，**Then** 引导再次出现。

### Edge Cases

- 用户名仅含首尾空白时按去除空白后的值校验和查重。
- 同一用户名已被占用时，无论该账户角色或状态如何，都拒绝重复注册。
- 账户在会话有效期内被禁用时，下一次需登录操作必须拒绝继续访问并要求联系管理员。
- 会话到期前的原操作目标已不存在或无权限时，重新登录后进入该角色默认门户，而不是访问无效目标。
- 注册兴趣标签页无任何选择时，允许跳过并保留空的标签集合。
- 课程同时具有多个方向和多个匹配标签时，只在对应方向页签展示，并以最高推荐层级参与排序。
- 学员修改标签后，尚未完成的推荐计算应使用最新标签，不得继续使用注册时的旧值。
- 已记录引导完成的账户更换角色门户后，应按目标门户各自的引导状态决定是否显示。

## Requirements *(mandatory)*

### Functional Requirements

**Registration and account initialization**

- **FR-001**: System MUST provide self-service registration only to student and teacher roles.
- **FR-002**: The registration role selector MUST present exactly the student and teacher options and MUST reject any other submitted role.
- **FR-003**: System MUST trim field values as appropriate and reject an empty or format-invalid username with a field-specific error and field focus.
- **FR-004**: System MUST reject a username already assigned to any account and show “用户名已被占用”.
- **FR-005**: System MUST reject an empty password or a password shorter than the platform minimum and show a field-specific error.
- **FR-006**: System MUST reject a confirmation value that differs from the password and require the user to enter it again.
- **FR-007**: System MUST reject an empty name after trimming and show a field-specific error and field focus.
- **FR-008**: System MUST NOT create an account when any registration validation fails and MUST keep entered values available for correction.
- **FR-009**: On valid submission, System MUST create one active account with the selected role and provided identity fields.
- **FR-010**: On student account creation, System MUST initialize a student profile whose learning direction defaults to “综合” and MUST initialize the student’s resume record association.
- **FR-011**: After student creation, System MUST present optional interest-tag selection grouped into crop categories, skill interests, and job categories.
- **FR-012**: System MUST allow students to save any selected interest tags or skip the interest-tag step without selecting a tag.
- **FR-013**: After saving or skipping student interest tags, System MUST automatically authenticate the student and route the student to the student portal.
- **FR-014**: After valid teacher registration, System MUST automatically authenticate the teacher and route the teacher to the teacher workspace.

**Login, session, and routing**

- **FR-015**: System MUST authenticate enabled accounts using username and password.
- **FR-016**: For a nonexistent username or incorrect password, System MUST show only “用户名或密码错误” and MUST allow retry.
- **FR-017**: For an otherwise valid but disabled account, System MUST reject login and show “账户已被禁用，请联系管理员”.
- **FR-018**: On successful authentication, System MUST route students, teachers, enterprises, and government users to their role portals, and both administrator roles to the management backend.
- **FR-019**: System MUST create a login session after successful authentication with a default validity of 24 hours and a platform-configurable duration.
- **FR-020**: System MUST require a valid session for authenticated portal actions and MUST provide explicit logout.
- **FR-021**: When a session is missing, expired, or invalid, System MUST redirect the user to the login page and retain the originally requested operation target.
- **FR-022**: After successful re-authentication, System MUST return the user to the retained target when it remains valid and authorized; otherwise System MUST route to the role’s default portal.
- **FR-023**: The login page MUST state “请联系管理员重置密码” for password recovery and MUST NOT expose a self-service password-reset path.
- **FR-024**: A disabled account MUST lose authenticated access no later than its next protected action.

**First-use guidance**

- **FR-025**: System MUST present first-use, step-based overlay guidance when a role first enters its portal.
- **FR-026**: Each guidance step MUST identify a core portal entry and provide a plain-language explanation for that entry.
- **FR-027**: System MUST mark guidance complete when the user reaches the end or explicitly skips it.
- **FR-028**: System MUST NOT mark guidance complete when the user closes, refreshes, or leaves before completion or skip.
- **FR-029**: System MUST suppress completed guidance on future logins and MUST show interrupted guidance again on the next portal entry.

**Student profile and preference propagation**

- **FR-030**: Student users MUST be able to view and edit their name, contact information, learning direction, and interest tags.
- **FR-031**: Learning direction MUST support agriculture, e-commerce, handcraft, and comprehensive, with comprehensive as the default for newly registered students.
- **FR-032**: Students MUST be able to add or remove interest tags from the platform-provided tag catalog.
- **FR-033**: System MUST persist valid profile changes and expose the latest learning direction and interest tags to course recommendation, job recommendation, direction statistics, and AI learning-report inputs.
- **FR-034**: System MUST keep the student’s resume record associated with the profile; structured resume editing and AI resume optimization remain outside this feature.
- **FR-035**: Missing contact information or interest tags MUST NOT block profile access, course browsing, or login.

**Course aggregation**

- **FR-036**: System MUST provide students with a course aggregation page containing only currently published courses.
- **FR-037**: The course aggregation page MUST provide agriculture, e-commerce, and handcraft direction tabs.
- **FR-038**: Courses shown in the aggregation page MUST be the same published course records used by the relevant course sections in modules 03, 04, and 05.
- **FR-039**: Within each direction, courses whose tags match the student’s interest tags MUST rank before nonmatching courses.
- **FR-040**: Within the same recommendation level, System MUST order courses by publication time descending.
- **FR-041**: When a selected direction has no published course, System MUST show “暂无课程”.

### Key Entities

- **User Account**: A person’s login identity, including username, password credential, name, one of six roles, and enabled/disabled status.
- **Login Session**: An authenticated interaction period associated with one account, with a validity period and an optional retained operation target.
- **Student Profile**: The student-specific profile linked one-to-one with a student account; includes learning direction, contact information, and the current resume association.
- **Interest Tag**: A platform-defined preference belonging to a crop category, skill-interest, or job-category group; students may select zero or more.
- **First-use Guidance State**: The completion state for one account and one role portal; records whether that portal’s guidance was completed or skipped.
- **Course Summary**: A published course representation used by the aggregation page, including direction, publication time, and recommendation-relevant tags.
- **Resume Record**: The student’s employment-profile record; this feature creates and associates it but delegates structured editing and optimization to module 07.

## Scope Boundaries

- Enterprise, government, and administrator accounts MUST NOT be self-registered; module 11 creates them.
- This feature MUST NOT implement role qualification approval.
- This feature MUST NOT provide self-service password recovery.
- This feature MUST NOT implement forums.
- This feature MUST NOT implement business functions owned by modules 03 through 12.
- This feature owns profile and preference values as inputs; course matching, job matching, direction statistics, and AI learning-report generation remain with their owning modules.
- Onboarding MUST cover portal core entries only and MUST NOT replace detailed module tutorials.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In scripted acceptance tests, 100% of specified registration validation branches show the expected field error and focus, and no invalid submission creates an account.
- **SC-002**: A first-time user with valid data completes student registration through the interest-tag step and reaches the student portal, or completes teacher registration and reaches the teacher workspace, in one uninterrupted flow.
- **SC-003**: In a seeded six-role routing test, 100% of valid accounts reach the correct role portal or management backend.
- **SC-004**: In invalid-credential tests, 100% of nonexistent-username and wrong-password attempts show the same message; disabled-account and forgotten-password paths show their specified distinct messages.
- **SC-005**: In session-expiry tests, 100% of protected operations redirect to login, and valid re-authentication restores the retained target or safely falls back to the role portal.
- **SC-006**: In completion-state tests, completed and skipped guidance never reappears, while 100% of interrupted guidance reappears on the next portal entry.
- **SC-007**: After a student changes direction or tags, the next relevant course recommendation, job recommendation, direction statistic, and AI-report input reflects the new values without a separate re-registration or manual refresh step.
- **SC-008**: For every direction tab, 100% of displayed courses are published, belong to the selected direction, use module 03/04/05 source records, and follow recommendation-first then newest-first ordering; an empty direction shows the exact empty state.
- **SC-009**: No automated registration path exists for enterprise, government, or administrator roles.

## Assumptions

- Usernames are trimmed before validation and uniqueness checks, contain 3 to 32 characters, start with a letter, and use only letters, digits, or underscores.
- Passwords are not trimmed and must contain at least 8 characters.
- Names and contact information are trimmed before storage; name is required, while contact information is optional and may be cleared.
- Interest tags come from a platform-maintained catalog in three groups; students can select any number of existing tags but cannot create arbitrary tags in this feature.
- An account without a completed or skipped guidance record is treated as first use for its current role portal.
- The default session duration is 24 hours; administrators control the configured value, not individual users.
- Courses with equal recommendation levels and the same publication time use a deterministic secondary order defined by the course source.
- Empty interest tags remove the recommendation boost but do not prevent ordinary course or job results.
- Recommendation ranking, job ranking, statistics, and AI-report generation consume the latest student profile values from their owning modules; this feature guarantees current input values rather than duplicating those downstream calculations.
