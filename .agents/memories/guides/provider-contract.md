# 生产者 Provider 接口契约

Updated: 2026-09-18
Status: FROZEN
Scope: 08、09、10、11 与既有 01、02、03、04、05 的跨模块 provider 边界

## 1. 契约定位

本文件冻结跨 feature 的生产者 provider 形状，供后续 08、09、10、11
直接引用。它不替代任何 feature 的 `specs/<NNN>/spec.md`，也不复制
既有实现计划。需求基准仍是 `docs/粤乡智匠——需求输入.md`。

本文件只定义：

- provider 的跨模块签名、返回形状、错误形状和注册入口。
- 每个接口的生产者、消费者与签名归属。
- 既有实现与新契约的差异，以及是否要求回改既有代码。

本文件不定义：

- 页面、路由、数据库表、事务实现或任务顺序。
- 03、04、05 的业务规则。
- 08、09、10、11 的功能范围。

## 2. Provider 命名与注册

### 2.1 必需层

所有新 provider 必须有稳定、唯一的 snake_case provider key，并提供：

```python
def set_<provider_key>_provider(
    app: Flask,
    provider: <ProviderProtocol>,
) -> None: ...

def get_<provider_key>_provider() -> <ProviderProtocol>: ...
```

冻结规则：

- `set_*` 只负责替换 `app.extensions` 中的当前 provider。
- `get_*` 在 provider 未注册时返回符合完整 Protocol 的占位实现。
- 同一 provider key 只能有一个权威注册槽，不得建立第二张注册表。
- consumer 只调用 `get_*` 返回的契约方法，不得读取具体实现或数据库。

### 2.2 便利层

`configure_*_providers(app, *, x=None, y=None) -> None` 是可选的启动期便利入口。
它只能委托必需的 `set_*_provider`，不得成为第二套注册机制。

08、09、10 如提供多个相关 provider，应同时提供该便利入口。单 provider
模块可以只提供 `set/get`。

### 2.3 既有例外

- 03 已有 `configure_agri_providers(app, *, preset_provider=None,
  course_provider=None, ai_client=None) -> None`，继续作为已存在的便利层。
- 05 已有 `install_default_handcraft_services(app) -> None` 和各
  `set_*_provider`；其 set/get 名称继续有效，不要求回改为
  `configure_*_providers`。
- 02 的 `set_messaging_source_provider(app, provider)` 和
  `register_messaging_source_provider(app, provider)` 是桥接型 provider，
  语义是组合多个业务来源，不是普通单值 producer 替换。02 形状保持不动，
  登记为“已存在但形状不同”。

## 3. 内容审核 Provider

### 3.1 消费者与生产者

- consumer：08 课程视频、09 职位、05 非遗教学视频。
- producer：11。
- 签名所有者：11 的 spec。
- 当前事实基准：`backend/app/handcraft_inheritance/admin_actions.py`
  的 `DatabaseTeachingVideoReviewActionProvider.apply()` 和
  `backend/app/handcraft_inheritance/providers.py`。

11 必须提供统一的 `ContentReviewProvider` facade。08、09 从零直接接入
该 facade；05 保持现有视频专用 action provider，不改已合并代码，由 11
提供视频专用 action 到通用动作的适配器。

### 3.2 状态机（目标契约）

以下状态机是 08、09、11 的目标契约。05 当前实现是它的子集：已覆盖
`pending -> approved/rejected` 和 `pending/approved -> pending`，
尚未覆盖 `rejected -> pending`、首次 `submit_for_review`。

状态值冻结为：

```text
pending -> approved
pending -> rejected
pending -> pending        # 待审核期间编辑
approved -> pending       # 已通过后编辑，进入重新审核
rejected -> pending       # 修改后重新提交
```

约束：

- `pending` 内容学员端不可见。
- `pending` 编辑后仍为 `pending`；有实际字段变化时版本前进，无变化提交
  返回原状态与原版本，不创建新的审核轮次。
- `approved` 编辑后必须回到 `pending`。
- `rejected` 修改后重新提交进入 `pending`。
- `approve`、`reject`、`edit`、`submit` 都必须用版本号阻止旧写入覆盖新写入。
- `rejected` 必须带非空 `rejection_opinion`；进入 `pending` 或 `approved`
  时清空旧驳回意见。
- 审核通过时 `published_at` 必须有值；驳回或编辑重审时清除 `published_at`。

### 3.3 最终签名

```python
class ContentReviewProvider(Protocol):
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None: ...

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict: ...

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict: ...

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...
```

`submit_for_review()` 的对象必须是内容模块已经持久化、已有稳定
`content_id` 和当前 `expected_version` 的记录。审核 provider 不负责创建
课程、职位或非遗视频记录，也不生成跨模块稳定 ID。

- 首次提交时 `expected_version` 是内容记录当前版本；内容模块负责在提交前
  建立草稿。
- 编辑后重新提交时，`expected_version` 必须是读取到的最新版本。
- 旧版本、状态不允许转换或 provider 无法表达该动作时，抛出
  `ProviderConflictError`。

`content_type` 冻结值：

```text
course_video
job_position
handcraft_teaching_video
```

`reviewer_role` 只允许 01 已存在的 `admin`、`super_admin`。身份字段必须由
01 会话覆盖，client 传入的角色不构成授权。

### 3.4 通用返回形状

所有方法返回同一种审核记录：

```python
{
    "content_type": str,
    "content_id": str,
    "review_status": "pending" | "approved" | "rejected",
    "version": int,
    "submitter_id": int,
    "rejection_opinion": str | None,
    "published_at": str | None,
    "created_at": str,
    "updated_at": str,
}
```

`get_review_status()` 未找到内容时返回 `None`，不得用空字典代替。

### 3.5 共用字段与特有字段

共用字段：

```text
content_type
content_id
submitter_id
version
review_status
rejection_opinion
published_at
created_at
updated_at
```

`course_video` 的 payload 特有字段：

```text
title
direction                 # agriculture | ecommerce | handcraft
summary
tag_ids                   # list[int]
duration_seconds          # positive int
media_url
quiz_config               # optional dict
```

`job_position` 的 payload 特有字段：

```text
title
salary
location
category
description
```

`handcraft_teaching_video` 的记录特有字段：

```text
craft_key
source_available
```

`handcraft_teaching_video` 的可写 payload 字段：

```text
title
media_url
```

`craft_key` 是创建后不可通过审核动作改变的关联字段；`source_available`
是 producer 提供的只读状态，两者不属于可写审核 payload。
如写入 payload 试图改变 `craft_key`，适配器必须拒绝并抛出
`ProviderValidationError`；`source_available` 的写入值必须忽略或拒绝，
不得由 consumer 伪造。

### 3.6 通知触发归属

- 11 的审核 provider 拥有状态转换和审核结果通知触发。
- 状态转换与通知 outbox 写入必须属于同一业务提交边界。
- 通知在业务提交成功后经 02 投递，投递失败不得回滚审核状态。
- 08、09、05 不得自行再发一份审核通知，避免重复。
- 02 的现行接收签名是：

```python
emit_review_result(
    *,
    event_id: str,
    submitter_id: int,
    content_type: str,
    content_id: str,
    approved: bool,
    opinion: str | None = None,
) -> dict
```

### 3.7 05 适配映射

11 的兼容适配器按下表把通用 facade 映射到 05：

| 通用动作 | 05 动作 | 05 关键字段 |
| --- | --- | --- |
| `get_review_status` | `get_video` / `get_review_status` | `video_id` |
| `submit_for_review` | 已存在的 05 记录走 `edit` | `video_id`、`version`、`title`、`media_url` |
| `approve` | `apply` | `action="approve"`、`reviewer_role`、`submitter_id` |
| `reject` | `apply` | `action="reject"`、`opinion`、`submitter_id` |
| `edit` | `apply` | `action="edit"`、教师身份、`title`、`media_url` |

适配规则：

- 通用 `expected_version` 映射到 05 `version`。
- 05 action 结果的 `status` 映射为通用 `review_status`。
- 05 已存在的 `handcraft_teaching_video` 通知类型保持不变。
- 05 没有新建/提交入口；初始提交仍由 08 的教师工作台承担。11 适配器
  不得伪造 05 不存在的提交能力；`submit_for_review` 只可映射到 05 已存在
  且状态允许 `edit` 的记录，否则返回 `ProviderConflictError` 或
  `ProviderUnavailableError`。
- `reviewer_id` 必须由 11 从 01 会话覆盖并用于授权与审计。client 传入值
  无效；05 当前 action 不读取该字段，因此映射层可仅在 11 侧保留审计信息，
  但不得放弃身份校验。
- `course_video.content_id` 是通用审核层的字符串稳定标识；与既有课程
  provider 的整数 `course.id` 通过适配器做 `str(course_id)` / `int(...)`
  双向映射。课程 provider 自身继续使用整数 ID。

## 4. 通用 Provider 约定

### 4.1 占位规则

- 占位实现必须实现完整 Protocol，不允许只实现部分方法。
- 占位实现在数据缺失时返回空列表、`None` 或明确的 unavailable 错误。
- 占位数据如可写，必须是明确的演示状态，不能冒充生产权威数据。
- 生产者落地后通过一次 `set_<provider_key>_provider` 替换占位实现。
- consumer 不因来源是占位实现而改变调用分支或复制一套业务逻辑。

### 4.2 ID 类型

- 用户、提交者、审核者等 01 账户标识使用正整数 `int`。
- 课程稳定标识沿用 03/04 的现行正整数 `int` 契约，不回改。
- 新的跨模块内容稳定标识使用非空字符串 `str`，包括
  `content_id`、`video_id`、`reward_id`、`job_id`、政策/新闻 ID。
- provider 内部数据库主键不得成为跨模块稳定标识。
- 空字符串、布尔值伪装整数、未知类型必须由 provider 边界拒绝。

### 4.3 时间字段

- 时间字段必须是带明确时区的 ISO 8601/RFC 3339 字符串。
- 新 provider 使用 `YYYY-MM-DDTHH:MM:SS+08:00` 作为平台时间规范。
- 既有 UTC 时间可以继续返回 `Z` 形式，由适配器规范化。
- consumer 不得用字符串直接比较不同 offset 的时间，必须先解析为
  带时区时间；排序必须使用可比较的时间值。
- 平台自然日、自然年边界统一按 `Asia/Shanghai`。

### 4.4 列表、排序与分页

- 当前规模的 provider 列表返回完整 `list[dict]`，不暴露页码。
- 列表排序必须确定，至少包含稳定 ID 作为同值 tie-breaker。
- 既有课程 provider 的排序保持不回改；新增 provider 默认按发布时间倒序，
  再按稳定 ID 正序，除非签名所有者另有明确口径。
- 只有签名所有者的 spec 明确要求时才引入分页；分页返回形状固定为：

```python
{
    "items": list[dict],
    "next_cursor": str | None,
}
```

cursor 对 consumer 不透明，不把 `page/page_size` 暴露为 provider 契约。

### 4.5 错误目标形状

新增 08、09、10、11 的 provider 边界错误必须遵循以下形状：

```python
class ProviderError(RuntimeError):
    code: str
    message: str
    details: dict

class ProviderValidationError(ProviderError): ...
class ProviderNotFoundError(ProviderError): ...
class ProviderConflictError(ProviderError): ...
class ProviderUnavailableError(ProviderError): ...
class ProviderAccessDeniedError(ProviderError): ...
```

语义：

| 错误 | 使用场景 |
| --- | --- |
| `ProviderValidationError` | 输入字段、枚举、ID 或 payload 不合法 |
| `ProviderNotFoundError` | 已知稳定 ID 在授权命名空间中不存在 |
| `ProviderConflictError` | 乐观锁冲突、状态不可转换、幂等键冲突 |
| `ProviderUnavailableError` | producer 未实现、来源不可达或规则源不可用 |
| `ProviderAccessDeniedError` | 当前会话角色无权执行 provider 动作 |

新增 08、09、10、11 的 provider 边界必须直接使用该目标形状，或使用可被
consumer 按相同 `code/message/details` 识别的兼容子类。

此建议只冻结目标，不要求回改 03/04/05/02：

- 03/05 现行 `AgriSkillError` 系列保持不动。
- 02 现行消息错误保持不动。
- 旧 provider 由 consumer 适配器映射到目标形状。
- 是否创建共享错误基类属于后续建议，不在本次契约中实施。

### 4.6 09 岗位申请接收

09 是求职申请接收契约的签名所有者和生产实现，07 是唯一消费者。
注册入口固定为：

```python
def set_job_application_intake_provider(
    app: Flask,
    provider: JobApplicationIntakeProvider,
) -> None: ...

def get_job_application_intake_provider() -> JobApplicationIntakeProvider: ...
```

最终签名：

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

规则：

- 只允许对当前已通过且未删除职位创建申请。
- `(student_id, job_id)` 唯一；`(enterprise_id, idempotency_key)` 幂等。
- 简历快照必填；技能档案快照可选，空对象按未附带处理。
- 成功返回稳定申请记录；重复兼容请求返回原记录，不重复通知。
- 冲突、非法状态或来源不可用分别抛出本文件第 4.5 节的标准错误。
- 07 不得直接写 `job_applications`，不得导入 09 的 `applications.py`
  或其他内部实现。

## 5. 生产者到消费者接口登记表

| 生产者 → 消费者 | 接口 | 契约现状 | 签名所有者 | 实现/接入归属 |
| --- | --- | --- | --- | --- |
| 08 → 03/04/05 | 方向感知课程 | 已存在 | 03 spec 冻结的 `CourseProvider` | 08 实现真 provider；03/04/05 继续消费 |
| 09 → 07 | 岗位 | 09 spec 已冻结实现形状；待 07 spec 最终确认 | 07 spec | 09 实现 producer，07 接入 |
| 09 → 07 | 求职申请接收 | 新定义 | 09 spec 冻结 `JobApplicationIntakeProvider` | 09 实现 producer，07 只依赖签名提交 |
| 10 → 06 | 政策 / 新闻 | 未定义 | 06 spec | 10 实现 producer，06 接入 |
| 11 → 08/09/05 | 内容审核 | 05 视频专用形状已存在；通用契约新定义 | 11 spec | 08/09 直接接通用 facade；11 为 05 提供适配器 |
| 11 → 05 | 奖品库 | 已存在 | 11 spec | 11 实现生产来源；05 现行 `RewardCatalogProvider` 是消费契约 |
| 11 → 05 | 履约管理 | 已存在 | 11 spec | 11 实现生产来源；05 现行 `FulfillmentAdminActionProvider` 是消费契约 |
| 11 → 05 | 积分规则（含离散行为权重） | 已存在 | 11 spec | 11 实现规则源；05 现行 `PointsPolicyProvider` 是消费契约 |
| 11 → 06/12 | 预置内容、功能说明知识库 | 未定义 | 11 spec | 11 实现 producer；06/12 接入 |
| 11 → 10/11 | 全平台统计读取 | 未定义 | 11 spec | 11 实现 producer；10/11 为 consumer |
| 03/04/05 → 07 | 技能档案读取 | outcome 读取函数已存在；跨模块聚合 provider 未定义 | 07 spec | 03/04/05 保持现有 outcome 产出；07 定义聚合、可见范围和投递快照；09 消费 |
| 01 → 全部 | 会话与角色 | 已存在 | 01 spec | 全部模块复用，不建立第二套会话或角色 |
| 02 → 全部 | 通知投递 | 已存在 | 02 spec | 全部模块经 02 投递，不建立第二套通知 |

技能档案明确修正：不存在“01 已定义技能档案 provider”的事实。01 只关联
学生资料与 `resumes` 记录；技能档案由 07 定义，03/04/05 是产出方，09
是消费方。

## 6. 消费者接入规则

- consumer 只依赖本文件或签名所有者 spec 中的 Protocol 签名。
- consumer 不得 import producer 的数据库、表名、内部类或实现细节。
- producer 未实现时使用符合完整 Protocol 的占位 provider。
- consumer 不判断“是否占位”而分叉业务路径；来源状态应体现在返回记录或
  目标错误中。
- producer 落地后只做一次注册槽替换，不要求 consumer 修改。
- 旧模块作为 producer 时，由适配器转换稳定 ID、时间、错误和结果字段。
- 任何新增特征值、字段或动作必须先进入签名所有者 spec，再由 consumer
  使用；禁止先写私有约定再倒逼其他分支适配。

## 7. 现状 vs 目标

| 维度 | 现状形状 | 目标形状 | 是否要求回改既有代码 | 何时对齐 |
| --- | --- | --- | --- | --- |
| Provider 注册 | 03 有 `configure_*`；05 用 `install_default_*` + `set_*`；02 用 `set/register` | 必需 `set_<name>_provider` + `get_<name>_provider`；便利层可选 `configure_*_providers` | 否 | 新模块立即；旧模块保留 |
| 02 消息来源 | `Null` + `Composite` 桥接组合 | 保持不同形状，明确登记为桥接型 | 否 | 保持 |
| 占位实现 | 已有 empty/null/unavailable 三种风格 | 必须完整实现 Protocol；缺数据返回空、`None` 或 unavailable | 否 | 新模块立即 |
| 内容稳定 ID | 课程 `int`；视频、奖品等 `str`；混合存在 | 课程保留 `int`；新跨模块内容 ID 用非空 `str` | 否 | 新模块立即 |
| 用户 ID | 正整数 `int` | 正整数 `int` | 否 | 已一致 |
| 时间 | UTC `Z` 与 `+08:00` 混用 | 带时区 ISO 8601；新模块规范为 `+08:00`；比较前解析 | 否 | 新模块立即；旧来源由适配器规范 |
| 列表 | 完整列表，方法各自排序 | 完整列表；稳定 tie-breaker；仅 spec 授权时使用 cursor 分页 | 否 | 新模块立即 |
| Provider 错误 | 03/05 用 Agri 错误；02 用自己的错误；部分用 `ValueError` | 新增边界用 `ProviderError` 目标层级 | 否；新增模块强制 | 08/09/10/11 立即 |
| 内容审核 | 05 只有视频 action + `status` | 通用 `ContentReviewProvider` + `review_status`；11 适配 05 | 否 | 11 实现契约时 |
| 课程 Provider | `list_published_courses(student_id, direction)` 等已存在 | 保持现有形状 | 否 | 08 立即按其实现 |
| 05 奖品 / 积分 / 履约 | 05 内已有 Protocol 与 set/get | 11 spec 冻结 producer 形状；兼容现有消费签名 | 否 | 11 实现时 |
| 技能档案 | 03/04/05 各有 outcome 读取函数，无统一 provider | 07 定义聚合、可见范围和投递快照；producer 复用现有 outcomes | 否 | 07 定义时 |
| 会话 / 角色 | 01 已有应用级会话与角色契约 | 直接复用，不包装成第二套 provider | 否 | 已对齐 |
| 通知投递 | 02 已有统一事件签名与消息中心 | 直接复用，不依赖模块内部实现 | 否 | 已对齐 |

## 8. 冲突与建议

| 冲突 | 最小建议 | 本会话动作 |
| --- | --- | --- |
| 05 审核 provider 是视频专用，08/09 需要通用契约 | 保留 05；11 提供通用 facade 和兼容适配器 | 只写契约，不改代码 |
| 05 action 结果用 `status`，读取记录用 `review_status` | 适配器映射为 `review_status` | 只写映射，不改代码 |
| 03/05 的 provider 依赖 Agri 错误类型 | 新增共享 provider 错误目标；旧错误由适配器映射 | 只写建议，不改代码 |
| 时间字段 UTC 与上海时区混用 | 新模块统一 `+08:00`；consumer 解析后比较 | 只写规则，不改旧数据 |
| “技能档案由 01 定义”与事实不符 | 07 定义，03/04/05 产出，09 消费 | 已在本文件纠正 |
| 各模块注册函数命名不完全一致 | 新模块遵守两层命名；旧模块保留 | 只写规则，不改代码 |

## 9. 后续 08/09/10/11 的直接约束

- 08 按 03 已存在的方向感知课程签名实现真 provider，不新建课程注册表。
- 08、09 直接接入 11 的通用内容审核 facade，不复制视频专用 action。
- 09 按 09 spec 冻结的实现形状提供岗位 `set/get`，07 为最终签名所有者
  并在自身 spec 中确认；10 的政策/新闻 provider 按 10 producer spec 定义
  `set/get`，consumer 只依赖签名。
- 09 拥有 `JobApplicationIntakeProvider.submit_application()` 签名和实现；
  07 只通过该 provider 创建投递，不得直接写 09 的表或导入内部服务。
- 09 可在 11 尚未实现时通过 `set_content_review_provider()` 向唯一
  `content_review_provider` 槽安装协议完整的不可用占位实现；11 落地后
  用同一 `set/get` 槽替换，不得建立第二审核注册表。
- 11 是内容审核、奖品库、履约管理、积分规则、预置内容、功能知识库和
  全平台统计的生产者。
- 07 拥有技能档案聚合契约，09 只消费，03/04/05 不新造第二套档案结构。
- 01 会话/角色与 02 通知永远直接复用，不建立旁路。
