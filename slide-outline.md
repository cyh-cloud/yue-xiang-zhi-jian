# Slide Outline

## Meta
- Topic: 粤乡智匠——面向广东乡村的 AI 实训人才赋能平台：背景、思路、技术实现与成果
- Scenario: 竞赛/评奖评审（评委关注痛点真实性、创新点可信度、技术实现难度、落地价值）
- Content Source: provided（项目申报材料 + 代码库事实） + web research（light）
- Research: light — 仅 3 次检索，全部采用一手可回查来源（农业农村部官网、商务部商务大数据监测、央视网/南方日报）；检索不到可靠出处的数字一律不写入
- Style: 岭南田园科技风 — 深墨绿渐变底 × 稻黄高光 × 禾绿辅助；梯田/水波纹/稻穗 SVG 装饰；标题衬线（Noto Serif SC）承载文化温度，正文无衬线（Noto Sans SC）保证投影可读
- Slide Count: 15
- Generated At: 2026-10-22T00:52:00+08:00

## Source Materials
**项目内部事实（可回查，来源：代码库与申报材料）**
- 定位：以「AI 实训」为主线的农村本土人才赋能平台，服务学员/教师/企业/政府/运营/超管六类角色
- 后端：Flask 2.3.3，21 个领域蓝图（backend/core/app_factory.py 第 117—138 行），约 57 张业务表（backend/db_schema.py）
- 前端：Vue 3.5 + TypeScript 5.7 + Vite 6 + Pinia + Vue Router，36 个视图，覆盖 6 类角色后台
- AI：OpenAI 兼容 Chat Completions 接口，默认 SiliconFlow（Qwen3-32B / Qwen3-VL-32B-Instruct / stepaudio-2.5-chat）
- 数据：SQLite 3 单文件库（data/yuexiang.db），无独立数据库服务
- 部署：nginx 伺服前端产物 + 反代 /api/*；单机部署，最低 2 核 4G，本机无需 GPU
- 测试：46 个测试文件（Python 单测 + Playwright 端到端 + 架构机械检查）
- 核心机制：结论可溯源、风险口径前置、实训评价可复现、治理机制成体系、工程可验证（申报材料第 3—5 项）

**外部调研（light，全部标注出处）**
1. 农业农村部（2025-08-19 答复摘要，moa.gov.cn）：2024 年培育高素质农民 64 万人次，45 岁以下青年农民 29.2 万人次
2. 《全国高素质农民发展研究报告(2025)》（第七届全国农民教育培训发展论坛发布，中国网/中国经济网/人民日报平台转载）：2024 年全国开展高素质农民培育 63.38 万人次；队伍平均年龄 45.4 岁；36—54 岁占 56.76%；高中及以上文化程度占 63.22%，大专及以上占 24.06%；获得农民技术人员职称比例 64.06%；63.97% 通过互联网购销农产品；2024 年高素质农民农业生产经营人均纯收入 3.17 万元，是农村居民人均可支配收入的 1.37 倍；70.47% 能带动周边农户发展
3. 商务部商务大数据监测（2026-02-05 发布，央视网/经济参考报）：2025 年农村网络零售额 3 万亿元，农产品网络零售额 7833.1 亿元，同比分别增长 6.7%、9.9%；头部电商平台全年助农直播超 400 万场；截至 2025 年底全国农村网商数 2007.4 万家，农村「直播+社交」网商数 747.7 万家；「农村电商高质量发展大讲堂」全年 12 期覆盖超 14 万人次
4. 广东「百千万工程」（南方日报/南方+，2025-12）：57 个县（市）GDP 增速连续两年快于全省平均水平；城乡居民收入比由 2.41:1 缩小至 2.31:1
5. 广东「网络强村」工程（深圳新闻网，2026-05）：2023 年「一镇两村」试点，2024 年拓展至 5 个地市 30 个村，2025 年实施「六个 100」——100 个乡村直播间、100 场直播实训、100 部乡村短视频、100 名乡村网红带头人、100 名网络名人、100 家互联网企业下乡进村
6. 广东农村科技特派员（南方日报，2025-12-23）：新一轮选派 984 个团队、2960 名特派员，截至 2025 年 10 月服务带动农户超 10.1 万户

## Slide-by-Slide Outline
1. **Slide 1 — Cover** — 「粤乡智匠：AI 实训，让乡村人才接上产业」封面陈述 | Layout hint: L02 BoldCover | Image provided: yes (AI 生成稻田/梯田氛围底图) | Chart: no
2. **Slide 2 — Agenda** — 四个章节导航：作品背景 / 核心思路 / 技术实现 / 成果与价值 | Layout hint: L19 List + 编号卡 | Image provided: no | Chart: no
3. **Slide 3 — 背景·断层** — 培训完成了，人与产业却没接上：组织难、持续难、评价难 | Layout hint: L15 Matrix4 | Image provided: no | Chart: no
4. **Slide 4 — 背景·数据** — 三组官方数据说明赛道体量与断点位置 | Layout hint: L17 Data+Insight | Image provided: no | Chart: yes (SVG 柱状图 + 指标块)
5. **Slide 5 — 核心命题** — 第一原则不是「AI 能生成什么」，而是「AI 说的哪一句可以信」 | Layout hint: L04 KeyStatement（深色强调页） | Image provided: no | Chart: no
6. **Slide 6 — 思路·总体设计** — 角色 × 场景 × 可验证反馈：六类角色是同一条人才流水线上的六个位置 | Layout hint: L07 3Pillars | Image provided: no | Chart: yes (SVG 闭环流程)
7. **Slide 7 — 创新·三层可信机制（核心创新页 1/2）** — 生成交给 AI，评价交给规则，来源交给界面：三者分工，既保留生成能力，又不把不确定性藏起来 | Layout hint: L15 Matrix4（左三层结构 SVG + 右职责说明） | Image provided: no | Chart: yes (SVG 三层分工图，占据视觉主导)
8. **Slide 8 — 创新·四条创新特点（核心创新页 2/2）** — 结论可溯源 / 风险口径前置 / 评价可复现 / 治理成体系 | Layout hint: L15 Matrix4（2×2 创新卡片，每卡 32px 标题 + 24px 描述 + 图标） | Image provided: no | Chart: yes (SVG 图标组)
9. **Slide 9 — 技术·系统架构** — 四层架构：Vue3 SPA / Flask 领域蓝图 / SQLite 单文件库 / 云端模型推理 | Layout hint: L05 Concept+Visual | Image provided: no | Chart: yes (SVG 分层架构图，占据视觉主导)
10. **Slide 10 — 技术·三道收口** — ① AI 出口唯一、OpenAI 兼容接口可换服务商；② 未配密钥降级本地知识库并标注来源、带图诊断不可用直接报错；③ 内容超 183 天未复核降级标注 | Layout hint: L08 Compare2 或 L13 Process 三段式 | Image provided: no | Chart: yes (SVG 三道收口流程)
11. **Slide 11 — 技术·可验证工程** — 21 蓝图 / 约 57 表 / 按「能力」鉴权 / 领域边界由机械检查约束 / 46 个测试文件（单测 + e2e + 架构检查） | Layout hint: L11 ThreeKPIs（数字作论据，技术细节仅作支撑文案） | Image provided: no | Chart: yes (SVG 指标卡)
12. **Slide 12 — 成果·量化指标** — 可核验的工程数字 | Layout hint: L11 ThreeKPIs / L10 TwoKPIs | Image provided: no | Chart: yes (SVG 指标卡)
13. **Slide 13 — 成果·可复现验证** — 规则算分保证同一输入同一结果；单测 + 端到端 + 架构检查三道防线 | Layout hint: L18 BeforeAfter 或 L15 | Image provided: no | Chart: yes (SVG 对比)
14. **Slide 14 — 成果·应用价值** — 农户用拍照或方言提问即可得可执行建议；单机部署适合县域镇级落地 | Layout hint: L07 3Pillars（用户视角） | Image provided: no | Chart: no
15. **Slide 15 — Closing** — 让每一句结论都能被追问来源 | Layout hint: L20 Closing（深色收尾页） | Image provided: yes (AI 生成田间暮色底图) | Chart: no

## Visual Rhythm Notes
- 深色强调页位置：1、5、15（封面/命题/收尾），另有 4、9、12 为数据/架构页用深色底衬托图表
- 图表承载页位置：4（柱状图 + 指标块）、6（闭环流程 SVG）、7（三层分工 SVG，视觉主导）、8（创新图标组 SVG）、9（分层架构 SVG，视觉主导）、10（三道收口流程 SVG）、11（指标卡 SVG）、12（指标卡 SVG）、13（前后对比 SVG）
- **创新重点配比**：Slide 7—8 为全篇视觉重心（创新页），Slide 11 工程页仅作可信度论据，不抢叙事重心
- 所有页保持标题 ≥56px、正文 ≥28px、标签 ≥22px；内容距边缘 ≥100px
- 装饰母题：梯田等高线、水波纹、稻穗剪影；每页 ≥2 个装饰元素
- 页脚统一：左侧「粤乡智匠 · AI 实训人才赋能平台」，右侧页码；深色页用稻黄页码
- 数据页脚必须带数据出处行（22px，弱化色）
