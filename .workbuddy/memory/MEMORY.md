# 项目长期记忆（粤乡智匠）

## 前端图标（Font Awesome 6.0.0）

- `frontend/index.html` 锁的是 **Font Awesome 6.0.0**（bootcdn）。**6.1 才引入的图标名在页面里渲染成空白**，不报错、不留占位：实测 `fa-shield-halved` 的 `::before { content: none }`，侧栏「企业认证」「内容监管」两项因此长期没图标（2026-11-06 修）。
- 已换成 6.0.0 存在的名字：企业认证 `fa-id-card`、内容监管 `fa-gavel`；简历面板的 `fa-shield-halved` 一并换成 `fa-shield`。
- 判断某图标名是否可用：在页面里临时插 `<i class="fas fa-xxx">` 读 `getComputedStyle(el,'::before').content`，为 `none` 即不存在。别靠记忆猜版本。

## 社区内容治理（2026-11-06 上线）

- 敏感词只做**初筛**：`shared/sensitive_words.py`（NFKC 折半角 + 去分隔符 + 小写，词表 40 余个治理类词，不涉政治）。命中不拒绝，转人工。
- `discussions` / `comments` 加四列：`moderation_status`(published/pending/rejected)、`matched_words`、`moderated_by`、`moderated_at`，走 apply_schema 补列，历史行默认 published。
- 读路径只放 published：列表、详情、评论列表、管理端公开列表。详情**不**过滤 `is_deleted`（既有 e2e 契约），但过滤 moderation —— 待审/拒审必须断链。
- 评论计数：pending 入库时不计数，审核通过时补计；删除评论只有在 published 时才回减。
- 管理端 `/api/admin/content` 额外下发 `pending_discussions` / `pending_comments` / `pending`，另有四个 approve/reject 接口，重复裁定返 409。
- 学员端本就有讨论功能（列表/详情/发帖/评论），但顶栏此前没有入口，只能从「本土资源」进；2026-11-06 顶栏补了「社区讨论」。
- 演示帖：迁移 `0008_demo_discussions.py` 预置 8 帖 / 21 条评论，覆盖农业/电商/手工/综合；`discussions.is_demo=1` + 前端「演示」标，评论数按真实插入回写，浏览数是演示值。幂等：已有任一演示帖则跳过。

## 企业资质认证（2026-11-05 上线）

- 注册后置认证：注册页只加一行提示，不放上传控件；企业中心「企业资质」提交营业执照，超管「企业认证」队列审核。
- 表 `enterprise_qualifications`（一次提交一行、历史不覆盖）；数据层 `db_domains/qualifications.py`（`CAPABILITY='job'`，因 job.read 是公开读，企业域与超管域都能引用而不新增能力名）。
- 证件照存 `data/qualifications/`（私有，静态路由拒绝 data/ 整目录），只经鉴权接口下发；信用代码脱敏前 4 后 4；`.gitignore` 已挡。
- 门禁：未认证企业最多 1 个**在招**（approved）岗位，常量在 `shared/enterprise_limits.py`；公开岗位列表带 `enterprise_verified` 标。
- 审核权归 **super_admin**（`review.moderate`），运营不能审核，这是 `tests/test_permissions.py` 锁住的既有边界。
- 演示：迁移 `0007` 给 `enterprise_demo` 预置已认证（无证件照，extra.demo=true），并把账号 company_name 补成「粤乡优品农业发展有限公司（演示）」。
- 已知坑：`users.get_user_by_username()` 只 SELECT 6 列，没有 company_name/phone；要完整用户行用 `get_user_by_id()`（它其实按 username 查）。

## 技术栈与启动

- 分支 `frontend/vue-rebuild`：Flask 后端在 `backend/`（入口 `backend/run.py`），Vue3 + TS + Vite 前端在 `frontend/`，旧 MPA 只读存档在 `legacy/reference/`。
- 一键启动：根目录 `start-dev.bat`（起后端 + 前端并打开 5173）。手动：`OPEN_BROWSER=0 python backend/run.py` + `cd frontend && npm run dev`。
- 后端解释器优先用 `C:\Users\c'y'h\.workbuddy\binaries\python\envs\default\Scripts\python.exe`（有 flask 2.3.3）。
- 前端装依赖必须带可写缓存：`npm install --cache "%LOCALAPPDATA%\npm-cache-yx" --registry=https://registry.npmmirror.com`，否则 `C:\Program Files\nodejs\node_cache` 无写权限会 `EPERM -4048`。

## 数据库（最容易出事的地方）

- **`data/yuexiang.db` 自提交 `57822a0` 起被 force-add 进版本库**（3.4MB 快照），而 `.gitignore` 里仍有 `data/*.db`。后果：切分支/拉取会静默覆盖本地库，运行时会一直显示 ` M`。
- 现行运行库 = 本地业务数据 + 从上游快照搬来的 22 张内容表（696KB，59 表）。**切任何分支前先复制 `data/` 到仓库外。**
- 备份保留（勿删）：`yuexiang.db.upstream-57822a0.bak`（上游快照原件）、`mine-20261021-1922.bak`（用户原库）、`merged-20261021-1930.bak`（合并产物）、`from-main-20261020.bak`（最原始数据）、`seed-20261020-2245.bak`（空种子库）。
- 老库升新库靠 `backend/db_schema.py` 的 `ALTER TABLE` 链，`init_db()` 会自动补列补表；实测 36 表 → 59 表无损。
- 内容（手艺/病虫害/案例/招聘/方言）只存在于 SQLite，代码里没有副本（ADR 0002）；`data/baseline.db` 不入库，由 `migrations/0001_content_to_db.py --make-baseline` 从现库复制生成。

## 本机网络

- GitHub 不可达，用镜像：`git remote add mirror https://ghfast.top/https://github.com/cyh-cloud/yue-xiang-zhi-jian.git`（`gh-proxy.com` 亦可用）。

## 竞赛提交（第十四届 CMT，2026 报名截止 10-23 23:59:59）

- 提交三件套：**作品截图 5–10 张（JPG 格式）**、演示视频（MP4，≤5 分钟，16:9，≥1920×1080，≤300M）、作品介绍文档（开发平台/主要软件/操作方法/亮点特色）。官网 www.cmit.cn。
- 截图上传页为逐张图片上传（字段「7、作品截图（必填项）」，提示「上传10张以内作品截图」），**不收压缩包**。
- 已产出：`.workbuddy/shots10/`（PNG 定稿 10 张）+ `截图说明.html`（每图一句）→ 提交版在桌面 `粤乡智匠_作品截图_提交版/`（JPG，`NN_板块名.jpg`）与 `粤乡智匠_作品截图_10张.zip`。打包脚本 `_pack_shots.py`。
- 作品介绍文档（Word）已产出：`output/b8754779-6e7a-4d90-bbfb-33b5994f043f/stage3/粤乡智匠作品介绍文档.docx`（约 10000 字，封面/摘要+作品简介/目录/八章含附录；中间稿 md、html 在同目录 stage1、stage2）。生成方式：`workbuddy-docx` 插件 full_pipeline；2026-10-22 参照官方 AIC 模板做过美化返工（黑白正式风标题、页边距 2.5/3cm、补作品简介与附录），同日按用户要求扩充第三章（核心功能总览表 15 项 + 每功能操作路径/输入输出/异常与降级三层 + 公共支撑功能节），细节见当日日志。
- 六角色演示账号（`backend/db_seed_accounts.py`）：student/teacher/enterprise/gov/operator_demo 口令均为 123456，admin_demo 为 admin123。

## 对外材料的事实基线（写 PPT/文档时直接引用，勿凭印象）

- **21** 个领域蓝图（`backend/domains/` 目录数）｜**56** 张业务数据表（live DB 60 表 − 4 张 infra：sqlite_sequence / schema_migrations / seed_meta / farming_seed_meta）｜**33** 个 Vue 视图（`frontend/src/views/*.vue`）｜**46** 个测试文件（根目录 8 + `tests/` 38，另 25 个 e2e `.spec.ts`）
- 内容行数（2026-11-03 实测，直接读 `data/yuexiang.db`）：病虫害 **69**（迁移 0003 由 45 扩充）｜农事 123｜案例 5｜招聘 14｜方言 24｜技艺 4，六项合计 **239**；全库 56 张业务表 1679 行（含用户、会话等运行数据）。旧稿的「231 / 693」是另一套口径，对外材料不要再引用
- 病虫害速查覆盖度（同日实测）：**69 条 / 8 作物 / 25 个来源 / 191 条来源关联**；有授权实拍图 **29** 条（余 40 条显示「暂无实拍图」）；有用药参考表 **41** 条（余 28 条只有药剂名或空表）
- 跨域只读视图 **5 个**（2026-10-30 实测，此前记为 6 有误）：v_enterprise_applications / v_enterprise_job_stats / v_home_stats / v_reviewable_models / v_submission_context；全库 475 字段、业务数据约 762 行（1093 − 331 会话）
- 关键常量：`backend/shared/live_reading.py` 七项必卖点 + LIVE_SPEED_IDEAL=(180,300) 字/分；`review_freshness.py` REVIEW_STALE_DAYS=183；`agri_dosage.py` 10 条用药正则；`upload_limits.py` MAX_UPLOAD_BYTES=50MB；`backend/ai/client.py` 默认 SiliconFlow + Qwen/Qwen3-32B
- **铁律**：对外材料的所有数字必须先从代码库/数据库实测取数，加总口径要能被复算；发现与既有材料不符（如 36→33 视图、57→56 业务表、241→231 内容）一律就地纠正，不要沿用旧稿。

## 技术文档（第八届全球校园 AI 算法精英大赛，output/techdoc-yxzj-20261026）

- 唯一源文件是 `stage2/formatted-粤乡智匠技术文档.html`；PDF 与 DOCX 都从它派生，改内容只改 HTML。
- 现状（2026-10-30）：**26 页 / 16 表 / 13 图**，七章 47 个小节。`stage3/粤乡智匠.pdf` 与 `stage3/粤乡智匠.docx` 均已更新。
- PDF：Playwright(node, `frontend/node_modules`) + 系统 Edge，A4、页边距 22/25/22mm、`displayHeaderFooter` 出「第 X / Y 页」。本机无 poppler，版式只能靠 pypdf 抽文字体检（孤立图注、近空白页）。
- DOCX：`workbuddy-docx` 的 `convert_doc.py` **不处理 `<img>`**（转换出的 docx 无 media），图片须用 python-docx 单独插入；运行转换脚本时 **cwd 必须是 HTML 所在目录**，否则 `src="images/..."` 解析失败。
- 版心宽 **14.65cm**（21 − 3.17×2），插图按 14.60cm、图注 `space_before=0`、图片段 `keep_with_next=True`。
- 表号/图号一律按**文档顺序**重编号（正则匹配 `<p class="tab-caption">表 N　标题</p>`），正文引用先换占位符再回填，否则插表后必错位。

## 桌面交付稿 `粤乡智匠(4).docx`（技术文档定稿，2026-10-30 修复）

- 定稿规格：**27 页**（物理），封面+目录不计页码，正文页码 1–25；3 节（封面/目录、正文、末页），sec1 `pgNumType start=1` 重新起号，sec2 续排。
- **图题/表题编号规则统一为「章.节[.序]」**：单条目用 `图 3.1` / `表 3.2`，同节多条用 `图 5.4.1` / `表 3.4.1`。编号后统一跟**全角空格**（U+3000）。正文交叉引用须同步。
- 目录是**可刷新的 TOC 域**（`TOC \h \t "样式1,1,样式2,2"`，靠自定义样式 `样式1`/`样式2` 而非 Heading 1/2），含 32 条。改完正文后必须让 Word 刷新一次，再存盘（存盘才会写入缓存结果，保证 WPS 等其他阅读器也能看到）。

## 用 Word COM 修 DOCX 的实战经验（可复用）

- 环境齐全：本机有 Microsoft Word 2016（`C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`），且托管 venv 已装 pywin32 + python-docx + pymupdf。**页码必须以 Word 实际排版为准**，靠估算一律错——本稿肉眼/静态分析以为是 14 页，实测 27 页。
- 取真实页码：`doc.Repaginate()` 后 `doc.Range(p.Range.Start, p.Range.Start).Information(1)`（= 显示页码，随分节 start 调整），`Information(3)` 是物理页码。**`Document.Paragraphs` 含表格内段落**，用 `para.Range.Information(12)`（wdWithInTable）过滤掉才能和 python-docx 的段落序号对齐。
- `Document.Fields` **不含页眉页脚里的域**，必须单独遍历 `doc.Sections(i).Footers(k)/Headers(k).Range.Fields.Update()`。⚠️ 遍历 `Footers(2)/(3)`（首页/偶数页）会**凭空创建**空页脚部件，只遍历 `(1)` 即可。
- **TOC 域边界不能靠"找第一个 end"判定**：每条目录项内部嵌了 PAGEREF 子域，需按 fldChar begin/end 做**嵌套深度计数**。本稿 TOC 域的结束符还落在**分节符段落**里，删除时必须保留该段落、只摘掉孤儿 `end` fldChar，否则整节被删、页码体系崩溃。
- **⚠️ 文本框里的 PAGE 域会截断两位数**：本稿页脚页码放在 2in×2in 文本框（`mc:AlternateContent`），9pt 字，导出 PDF 后 10–24 页只印出首位数（"10"→"1"）。改为**普通居中段落 + PAGE 域（沿用 `footer` 样式 a3）**后完全正常，且位置/字号不变（x≈298.7、9.0pt）。以后遇到页脚页码异常优先怀疑文本框。
- 章节标题若带残留 `w:numPr` 自动编号，TOC 会生成"二、 二、xxx"式重复前缀，需摘掉 numPr。
- 验证闭环：改完 → Word 刷新并存盘 → `ExportAsFixedFormat(PDF, 17)` → pymupdf 逐页扫描底部 12% 区域的纯数字 span，比对序号连续性与坐标，比肉眼看可靠得多。
- 流程纪律：先 `shutil.copy2` 备份原件，所有编辑走**新文件名**输出（本机覆盖既有文件可能静默失败），确认无误后再用 md5 校验复制回原路径。
