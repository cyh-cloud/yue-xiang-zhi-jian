# 非遗项目到手工技艺映射

状态: draft

日期: 2026-10-19

本文覆盖国家级非遗项目采集到 `crafts` 的展示映射。来源是 `ihchina`，已验证列表 JSON 返回 3610 个子项，详情页可直接打开。3610 子项进入 crawler std，只有通过发布审核的部分进入业务 `crafts`。

## 项目与子项

- 3610 是国家级非遗名录的“子项”数，按申报地区或单位、扩展批次和保护单位形成独立记录。
- 1557 是项目数。同一项目名可以有多个子项，不能按名称去重。
- 每个子项保留详情 ID、项目编号和申报地区或单位。`project_num` 是来源内部编号，不等于项目编号。
- 一个项目名对应多个子项时，`crafts` 的主记录仍可按子项建立，避免错误合并保护单位和地区。
- `crafts.id` 是字符串主键。建议使用 `ich-{来源详情ID}`，在转换器中稳定生成；不要用项目名做 id。

## 字段映射

现有表 `crafts` 只有 `id`、`name`、`origin`、`history`、`level`、`sort_order`、`extra`。以下扩展字段建议保存在 `crafts.extra` JSON 或新增关联表，不修改当前 schema。

| 业务字段 | `ihchina` 来源 | crawler std 层 | 建议业务落点 | 说明 |
| --- | --- | --- | --- | --- |
| 项目名称 | 列表 `title` 或详情标题 | `std_ich_projects.name` | `crafts.name` | 保留原文 |
| 正文 | 详情 `.article-mod2 .text .p` / 列表 `content` | `std_ich_projects.description_text`、`description_html` | `crafts.history` | 业务库只放审核后的基础资料或短正文 |
| 项目编号 | 列表 `num` 或详情“项目编号：” | `std_ich_projects.ich_code` | `crafts.extra.ich_code` | 如 `Ⅰ-1`，不是详情 ID |
| 类别 | 列表 `type` 或详情“类别：” | `std_ich_projects.category` | `crafts.extra.category` | 十类非遗类别之一 |
| 批次 | 列表 `rx_time` 或详情“公布时间：” | `std_ich_projects.announcement_batch` | `crafts.extra.announcement_batch` | 去掉 HTML 标签，保留“第五批”等原文 |
| 类型 | 列表 `cate` 或详情“类型：” | `std_ich_projects.project_type` | `crafts.extra.project_type` | 新增项目或扩展项目 |
| 申报地区或单位 | 列表 `unit` 或详情“申报地区或单位：” | `std_ich_projects.declaration_region` | `crafts.origin` 或 `extra.declaration_region` | `origin` 适合展示地名；单位名放扩展字段 |
| 保护单位 | 列表 `protect_unit` | `std_ich_projects.protection_unit` | `crafts.extra.protection_unit` | 可能为空 |
| 省份 | `address` 代码结合 `province` 展示名 | `std_ich_projects.province` | `crafts.extra.province` | 有证据才拆分 |
| 城市 | 列表 `city` 行政区划代码 | `std_ich_projects.city`、`city_code` | `crafts.extra.city`、`city_code` | 代码和名称分开 |
| 县区 | 列表 `area` 行政区划代码 | `std_ich_projects.county`、`county_code` | `crafts.extra.county`、`county_code` | 不从展示名猜代码 |
| 传承人 | 详情传承人表或 `/ccr_detail/{id}.html` | `std_ich_inheritors` | 新增关联建议表 | 姓名、性别、出生日期、民族、项目编号、详情 URL |
| 相关项目 | 详情“相关项目”表 | `std_ich_related_items` | 新增关联建议表 | 有向关系，保留关系方向 |
| 相关资讯 | 详情“相关资讯”区块 | `std_ich_articles`；项目关联关系待评审 | 建议新增资源表或只展示链接 | 区块最多 5 条，不能视为全量 |
| 相关学术 | 详情“相关学术”区块 | 建议新增学术资源表（未冻结） | 建议新增资源表或只展示链接 | 保存标题、日期、URL、作者/来源 |
| 详情 URL | `https://www.ihchina.cn/project_details/{id}.html` | `std_ich_projects.source_url` | `crafts.extra.detail_url` | 必须可直接打开 |
| source_url | 来源详情 URL，或发现该项目的列表接口 URL | `std_ich_projects.source_url` | `crafts.extra.source_url` | 与详情 URL 分开记录发现入口 |
| is_teachable | 当前来源没有教学步骤字段 | `std_ich_projects.is_teachable` | `crafts.extra.is_teachable` | 由运营审核或从步骤表派生，不根据正文猜测 |

## 教学步骤

`craft_steps` 是现有教学步骤表。`ihchina` 的项目正文、传承人和相关项目不是教学步骤，不能自动拆成步骤。

建议规则:

- 只有运营新增了至少一条有效 `craft_steps`，或有视频、采购指南时，`is_teachable=1`。
- 只有项目正文、传承人和来源链接时，`is_teachable=0`。
- 转换器不根据段落数量或关键词伪造步骤标题、材料、工时和工具。
- 重新导入时保护人工编辑过的步骤、视频和采购指南。

## 没有教学步骤时前台如何展示

- `GET /api/crafts/list` 仍展示全部已发布项目，使用 `name`、`origin` 和可用的 `level`。
- 详情页展示项目名称、正文摘要、类别、批次、类型、申报地区、保护单位、传承人、相关项目和来源链接。
- 详情页不渲染空步骤区、空视频区或“即将上线”的伪步骤。
- 页面明确提示“该项目暂未提供教学步骤，以下为项目基础资料”，并给出 `detail_url`。
- 采购指南只在确有 `craft_budgets` 或采购项时展示。
- 列表和详情应显示来源为“中国非物质文化遗产网”，遵守其署名和商业使用限制。

## 落层

| 内容 | crawler 层 | 粤乡智匠 |
| --- | --- | --- |
| 原始列表 JSON、详情 HTML、传承人和资讯页面 | raw | 不进入业务库 |
| 单来源的列表项、详情键值、关联块 | stage | 不直接进入业务库 |
| 子项、传承人、相关项目、资讯/学术元数据 | std | 基础字段进 `crafts` 和 `extra`，关系进建议关联表 |
| 教学步骤、视频、采购指南 | 人工维护或授权资料 | `craft_steps`、`craft_videos`、采购表 |

## 自然键与转换

- 建议自然键: `ich_code + declaration_region + name`，并以来源详情 ID 作为来源内唯一键。
- 同名的 1557 项目聚合视图可以按 `ich_code` 或规范化项目名聚合，但不能写回覆盖 3610 子项。
- 详情 ID 来自列表 `id`，不混用 `auto_id`、`num`、`project_num`。
- `is_teachable` 属于业务决定，不由采集器自动置为真。
- 正文哈希用于变更检测，不用正文哈希替代自然键。

## 已知缺口

- 相关资讯和相关学术每块最多展示 5 条，是否存在全量接口待验证。
- 独立传承人列表是否覆盖全部项目详情中的传承人待验证。
- 正文、图片、音视频的转载范围和商业使用需按站点版权声明处理。
- `province`、`city`、`area` 的代码到名称映射需要权威行政区划表，当前文档不内置猜测映射。

## 待验证

- 3610 个详情页是否全部可打开。
- `is_teachable` 的运营判定标准和最小步骤数。
- 没有教学步骤的项目是否需要在列表中加独立筛选。
- 现有前端是否已能处理空 `steps` 和空 `videos` 而不渲染空壳。
