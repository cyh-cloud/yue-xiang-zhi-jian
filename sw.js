// 粤乡智匠 Service Worker — 离线缓存策略
// v4：农时日历重构（节气改由后端算法下发、任务细化到日期）随本版本发布
// v11：新增「常见病虫害速查」（前端 script.js / styles.css / index.html 均有改动）
// v12：速查条目配图后，弹窗署名栏补显示「许可协议 / 拍摄日期」（script.js）
// v13：诊断结果不再展示「置信度」（index.html / script.js / styles.css）
// v14：速查配图入库（18 条虫害），弹窗图注支持「虫态 / 具体种」说明（script.js / styles.css）
// v15：所有输入框补齐 name / autocomplete 标注 —— 修「速查搜索框初始被浏览器自动填充成
//      student_demo、界面显示匹配 0 条」的问题（index.html）
// v16：农业技能板块终检 A1–A7 处置（index.html / script.js / js/core.js / app.py / farming_data.py）：
//      A1 顶部作物变化时诊断面板跟随；A2 用药数值强制补免责声明；A3 顶部作物卡补柑橘/香蕉并
//      补两套农时数据；A4 速查筛选跟随顶部作物；A5 未知 product 明确 400；A6 严重程度角标默认值留空；
//      A7 移除 calendarYear 与 data-sim 死标记、方言语音接口补限流
// v17（2026-10-05，EC1–EC8）：直播带货实训改造 —— 话术改「AI 初稿 + 我的稿」双稿对照、
//      评分对象改为「我的稿」并如实标注分数来源（AI/规则）、去掉评分随机数、直播间改为
//      事件驱动（朗读反应 + 冷场流失）、新增朗读实录分析与实训记录（作业链路落库）
// v18（2026-10-05 第二轮）：文案/客服「我的稿+提交+记录」闭环（kind=copy/cs）、直播间
//      进阶（难度分级 + AI 观众提问 + 挑战突发状况）、AI 评分每维度给命中证据、
//      小清理（animateNumber 去重、去掉综合分 '+' 尾缀、apiCall 带错误码）
// v19（2026-10-05）：直播间左上角商品标签改为可切换下拉（与顶部作物卡双向联动）
// v20（2026-10-05）：修复 v19 回归 —— generateLiveScript 仍引用已删除的 tag span
//      导致 TypeError、生成按钮无响应；现改为读 #live-product 下拉值
// v21（2026-10-05）：直播带货实训学员视角走查修复 8 项（P1 切换商品清空内容/评分引导、
//      P2 评分口径区分/计时器清理/价格命中假阳性、P3 冷场统计/评论计数/AI 提问上下文）
// v22（2026-10-05）：商品文案创作 6 项修复（degraded 角标、规则评分闭环、产品名归一到白名单、
//      采用保留 markdown、换一版反馈、格式描述单一来源）
// v23（2026-10-05）：商品文案体验优化（步骤条+环节状态驱动、待填写实时高亮、AI初稿vs我的稿评分对比、
//      复制 Markdown、采用后滚动定位、评分/提交按钮状态驱动）
// v24（2026-10-06）：客户服务模拟走查修复（整场均分替代最后一句分、答非所问判定、
//      难度加权、失败可见不污染历史、限流提示、评分口径说明）
// v25（2026-10-06）：客户服务模拟体验优化（气泡旁该句得分徽标+扣分原因、最弱维度高亮+可行动建议、
//      输入框内联参考话术 chip、场景任务卡开场引导）
// v26（2026-10-06）：客户服务模拟体验优化第二轮（整场复盘卡、客户情绪温度条）
// v32（2026-10-06）：非遗 3D 走查修复 —— 教师上传模型加类型/大小校验+真实 file_size、
//      教师端模型列表状态中文徽标+类型中文映射、管理员审核加 3D 预览弹窗（不再盲审）、
//      修复 portal.css 徽标被 styles.css 通知红点样式泄漏（position:absolute 飞出表格）
// v33（2026-10-06）：方言语音交互完善 —— 语音识别语言跟随方言（粤语 zh-HK）、
//      识别错误分类提示、AI 回答加语音合成朗读（TTS 按钮）、方言回答加诚实标注（AI/降级话术库区分）
// v34（2026-10-06）：修复 TTS「点暂停却重头读」—— 改用 pause()/resume() 保留播放进度，
//      三态按钮（朗读→暂停→继续）+ 独立停止按钮；发新消息/清空对话自动停止朗读；
//      补 Chrome 长文本自动静默暂停的 keep-alive
// v35（2026-10-06）：修复麦克风错误提示常驻 —— 错误文案写进输入框 placeholder 后从不恢复，
//      导致插上麦克风、识别成功后仍显示「未检测到麦克风设备」；现于重新录音/识别成功/6s 超时后恢复
// v36（2026-10-06）：本地成功案例整体换成**真实可核实数据** —— 新增 cases_data.py 为唯一事实源
//      （5 条案例：梅县南福村金柚电商 / 潮州湘桥非遗电商 / 遂溪农村电商领跑县 / 饶平农村电商 /
//      潮安淘宝村群），逐条标注公开来源；删除数据库与 case-detail.html 中编造的案例与时间线
//      （含"未知标题自动现编内容"的 fallback）；首页卡片改为从接口动态渲染；详情页新增
//      「资料来源」区块，时间线改为有报道支撑的真实节点
// v37（2026-10-06）：政策信息推送整体换成**真实可核实数据** —— 新增 policies_data.py 为唯一事实源
//      （5 条政策：农业补贴 / 农村电商 / 非遗传承人 / 农业技术培训 / 农产品质量安全认证），
//      全部带文号与公开来源；移除原正文中的编造案例与未经核实的咨询电话；数据库改为按内容签名
//      自动重灌（修「改了政策界面上永远不变」）；首页政策卡片改为从接口动态渲染；政策弹窗新增
//      「资料来源」与免责声明区块
// v38（2026-10-06）：本地成功案例接入**超级管理员审核** —— 案例内容仍在 cases_data.py，
//      但"是否可见"改由 content_reviews（content_type='success_case'）的 status 决定：
//      首页/详情页只下发 approved 的案例；新增案例自动落一条 pending，需在管理员端
//      「内容审核」通过后才展示；全部待审时首页显示"审核中"而非"加载失败"
// v39（2026-10-06）：本土资源终检修复 —— ①政策分类归一化（政府端表单「综合」的 value 是英文
//      general，后端原先直接入库 → 学员端显示英文标签且回退成"补贴"绿、任何分类筛选都筛不到）；
//      ②政策筛选按钮改为按接口真实分类动态生成（不再写死 5 类），筛选后 0 条时给空态提示；
//      ③方言助手：点麦克风在浏览器不支持语音识别时会自动发送一条学员从未说过的固定问题
//      （伪造用户输入），改为如实提示改用文字输入；④方言切换失败时卡片高亮与内容不一致
//      （原 catch 静默失败，点「潮汕话」内容还停在粤语）→ 失败可见 + 渲染前清空旧方言；
//      ⑤方言助手补用药免责声明（与农技问答/诊断同一红线）
// v40（2026-10-06）：就业对接板块重构 —— ①**删除 30 条预置编造岗位**（假公司名/假薪资），
//      旧的 job_listings 预置行会被 init_db() 一次性清理（判定 enterprise_id 为空串）；
//      ②新增 jobs_data.py：收录**真实公开招聘（招募）公告**（省人社厅三支一扶、事业单位集中招聘、
//      农业农村局特聘动物防疫专员、乡镇乡村公益性岗位、省农科院科研辅助等），逐条标注官方来源与
//      **报名截止日期**，过期如实标注「已过报名期」；③修掉审核门禁漏洞：学员端职位查询原先
//      不过滤 review_status → 企业发布（pending）即可见，现只下发 approved；④修掉 _seed_jobs()
//      无条件清空 job_listings/job_applications/saved_jobs 的隐患（岗位数跌破阈值会静默抹掉
//      企业数据与学员投递）；⑤管理员审核职位时显示完整内容（原先只有标题＝盲审）
// v41（2026-10-06）：就业对接「对齐平台定位」+ 供应链求购下线 ——
//      ①删除 3 条与「农村本土人才」定位不符的公告（省事业单位集中招聘、省农科院资环所、
//      省农科院作物所 —— 均为城市/研究生高门槛岗），改为**只收乡镇与涉农基层岗**；
//      ②新补 7 条当前仍在报名期的广东基层岗位（信宜/博罗/江城/高州公益性岗位、
//      台山白沙镇合同制、连南三江镇网格员、连平绣缎镇编外人员），过期公告改为默认折叠；
//      ③「供应链求购」整块下线：企业端「求购管理」入口与页面、统计卡、管理端审核筛选，
//      以及 /api/enterprise/procurements 与 /api/employment/procurements 接口一并移除；
//      ④板块标题「就业与供应链对接」→「就业对接」，注册身份「企业用户（招聘收购）」→
//      「企业用户（发布岗位）」；⑤清掉已无条目的「科研辅助/综合」死筛选项
// v42（2026-10-06）：就业对接打通完整求职链路（能力档案 → AI 简历 → 岗位匹配 → 投递/报名）——
//      ①新增「我的简历」面板：结构化在线简历 + 左右分栏展示**平台真实学习数据**组成的能力档案
//      （证书/学习进度/实训成绩/积分），并提供 AI 逐段起草/润色与「打印导出 PDF / 复制纯文本」；
//      ⚠️ AI 只做「组织与表达」，未提供的信息一律【待补充】占位，且被显式禁止把「学习中」的证书
//      写成「已获得」——与全项目「不编造」红线一致；用过 AI 的段落会如实标注。
//      ②公开招聘公告接入链路：公告详情新增「登记求职意向」（平台只记录意向、**不代办报名**，
//      主按钮仍是官方原文外链）；「我的投递」扩为「我的求职」，分两组展示「公开招聘意向」与
//      「企业岗位投递」，并修掉原先「去投递心仪的职位吧」的空态死循环引导。
//      ③企业岗位表此前为 0 条（30 条编造岗位上版已删）导致投递无载体 → 预置 2 条**明确标注
//      演示**的岗位（公司名带「（演示）」+ 卡片角标 + 详情页说明 + is_demo 字段），
//      仅用于演示发布→审核→投递→看简历全流程，不冒充真实招聘信息。
// v43（2026-10-07）：就业对接「学员视角走查」修复 —— 全部是「筛不出/看不懂」类问题：
//      ①**薪资筛选彻底修掉**：旧实现是 `salary LIKE '%5000%'`，而库里存的是 `5K-8K`
//      → 永远匹配不到，学员**选任意薪资都得到 0 条**；改为把薪资文本解析成数字区间求交集
//      （`4K-6K` 在筛选「3K-5K」时命中）。同时 `12000+` 那条错误的 `LIKE '%1%'` 一并去掉。
//      ②薪资筛选隐藏公告这件事**必须说出来**：新增说明条「薪资筛选只作用于企业招聘岗位，
//      N 条公告没有薪资字段已暂时隐藏」，空态也按「分类 0 条 / 薪资无结果 / 关键词无结果」
//      分别给不同解释，不再一律「未找到匹配的职位」。
//      ③分类下拉：按后端下发的**真实条数**重建，并拆成「企业招聘岗位 / 公开招聘公告」两组
//      optgroup（此前两套词混在一格里，学员不知道「基层服务」筛的是公告）；0 条的标「（暂无）」
//      而不是从下拉里消失。④「共 N 条信息」补上构成（企业岗位 x · 公开招聘 y）。
//      ⑤投递卡片时间线「投递简历 / 简历审核中」→「提交申请 / 企业查阅中」：学员可以一条简历
//      都不写就申请成功，旧文案会让人以为简历已经投出去了；并新增「你还没有填写简历，
//      企业看不到简历内容」的持久提示 + 申请成功提示追加同一句。
//      ⑥未登录态补齐：简历页说明改成「填写的内容不会被保存」并给「去登录」按钮；
//      「收藏职位」未登录时不再是一片空白，补与「我的求职」一致的空态 + 去登录。
//      ⑦板块副标题「岗位匹配」→「相似职位推荐」（学员端并无匹配产物，属过度承诺）。
// v44（2026-10-07）：企业岗位与「企业端发布 + 管理员审核」这条链路真正接上 ——
//      ①两条演示岗位**不再由平台直接塞进库并写死 approved**，改为归属真实企业演示账号
//      （enterprise_demo）、初始 `review_status='pending'` 并同时生成待审记录：
//      企业端「岗位管理」能看到它们，管理端「内容审核」能审它们，
//      **管理员点「通过」之前学员端一条都看不到**（app.py / database.py）。
//      ②种子逻辑**不再覆盖 `review_status`** —— 否则管理员驳回后一重启就被重置回待审。
//      （唯一例外是一次性迁移：早期挂在 sentinel `__demo__` 名下的行会被就地改成
//      企业账号 + 待审，id 不变，学员已有的投递记录不会变成孤儿。）
//      ③学员端在企业岗位全部待审时，空态改为「企业岗位正在审核中（N 条）」
//      而不是「未找到匹配的职位」（script.js）。
//      ④企业端岗位列表补「驳回理由」列 —— 此前 `reject_review` 只改审核表、不回写岗位状态，
//      被驳回的岗位在企业端一直显示「待审核」，企业只能干等（database.py / enterprise.html）。
//      ⑤岗位详情页的演示说明改为「由平台演示企业账号发布、经审核通过后展示」，与实际链路一致。
// v56（2026-10-07）：教师端链路整改第三批 ——「名册 ↔ 平台账号」打通 + 学情口径换真实数据：
//      ①名册与账号原本是两套数据：添加学员只写名册行（登不进来、收不到通知）。
//        现在「添加学员」可选 关联已有账号 / 新建账号 / 暂不关联（index.html / teacher.html / app.py）。
//      ②「编辑学员」由 5 连 prompt 改成表单（姓名/方向/状态/账号关联），并修掉
//        「关闭 prompt 会把已填进度清零」的问题；方向下拉会兜住不在选项表里的现有值。
//      ③消息中心「写消息」收件人此前用**名册号**当收件人（学员永远收不到），改为
//        只列已关联平台账号的学员、按 username 发送；该入口只对教师开放。
//      ④学情分析 / AI 教学报告 / 仪表板统计不再使用**手填**的 students.progress，
//        改用「证书真实完成度」（学员名下证书进度的平均值），无证书记录的学员单独说明。
//      ⑤修复学情柱状图宽度写死 count*10（3 人顶满、8 人溢出）；方向详情表里两列
//        恒为 undefined（接口从不下发 student_count/avg_score），无数据源的列直接不渲染。
//      ⑥移除 teacher.html 顶栏点了没有任何反应的「消息通知」铃铛（死控件）。
// v57（2026-10-07）：「发布作业」整块下架（用户拍板）——
//      ①删除 `POST|GET /api/teacher/assignments`、`GET /api/teacher/assignments/<id>`、
//        `GET /api/teacher/submissions/<student_id>`、`GET /api/student/submissions` 五条路由，
//        及 database.py 里对应的 create/get/submit assignment 五个函数（前端本来就零调用）。
//      ②**保留** `POST /api/teacher/assignments/grade`：三种电商实训（直播/文案/客服）
//        仍复用 `assignments` 表当题目载体、`assignment_submissions` 存提交，教师端「实训提交」批改走它。
//        表结构一律不动；批改通知文案「作业已批改」→「实训已批改」。
//      ③消息中心通知映射删掉已无来源的 `assignment` 分支（tag/icon 两张表），
//        `grade` 标签「作业批改」→「实训批改」；styles.css 清理 .assignment-* / .attendance-* 死样式。
// v58（2026-10-07）：政府端政策链路走查修复（app.py / database.py / script.js / styles.css / government.html）——
//      ①**P0 下架陷阱**：`/api/resources/policies` 去掉「政府表为空就降级读旧 policies 表」的分支
//        （预置 5 条政策在两张表各有一份，政府端全部下架后旧表会把它端回学员端 → 下架看起来完全无效）。
//        学员端政策从此只认 government_policies 里 is_published=1 的行。
//      ②学员端 `loadPolicies` 把「空列表」从 throw 错误态改为**空态**（含说明 + 刷新按钮），
//        与「加载失败」明确区分；styles.css 补 .policies-empty-sub。
//      ③产物残缺：`create_policy` 现在一并写 summary/date/source；POST 缺 summary 由正文首段派生、
//        缺 date 补当天；表单新增「摘要 / 发布日期 / 资料来源」，分类「综合」的 value 由英文
//        general 改回中文；PUT 也支持改资料来源（走 source_text → JSON 转换）。
//      ④溯源口径：`showPolicyModal` 只在**该政策确实有 sources** 时才显示
//        「文号与数据均可溯源」；无来源时只留免责声明（原来无条件挂全局口径 = 替无出处内容背书）。
//      ⑤政府端政策列表加「已上线/已下架」徽标 + 发布日期/录入日/发布者/来源条数，
//        新增「编辑」（复用 PUT，含取消编辑与分类值保护）、预览只在超长时加省略号且压缩换行、
//        三个加载函数补 .catch（原来接口失败会永远转圈）、列表字段全部 escapeHtml（原来是 XSS 注入点）。
//      ⑥「发布」按钮下方明示「发布后立即在学员端可见」，操作反馈由 alert 改为内联提示条。
// v59（2026-10-07）：政府端「新闻资讯」整块下架（用户拍板「如果只有政府端有，就把它去掉」）——
//      实测确认 `news_articles` 的唯一消费者就是政府端那一个页面：写入只有 `/api/government/news`，
//      公开的 `/api/resources/news` 虽存在但 script.js / index.html 零调用 → 发出去的资讯只有政务自己看得见。
//      ①政府.html：删侧栏「新闻资讯」入口 + `#page-news` 整页 + loadNews/pubNews/delNews/newsMsg
//        + onPageChange 的 news 分支；数据大屏「内容生产」卡片去掉「新闻 N」。
//      ②app.py：删 `/api/government/news`(GET/POST/PUT/DELETE) 4 条 + `/api/resources/news`(GET/详情) 2 条。
//      ③database.py：删 create_news/get_news/get_news_by_id/update_news/delete_news，
//        `get_dashboard_overview()` 去掉 total_news 与 `content.news`。
//        ⚠️ `news_articles` 表**保留**（不 DROP，历史数据仍在），已无读写入口。
//      ④script.js：删死代码里的 loadGovNews/govDeleteNews/setupGovNewsPublish 及其在 setupNewFeatures
//        / setupAdminSubTabs 的挂载；styles.css 去掉 `.news-card` 三处零引用选择器。
// 注（**未提版本**，无需 bump）：政府端 / 企业端门户页不在 STATIC_ASSETS 预缓存清单内，
//      改 government.html / enterprise.html 不影响缓存。
//      v59 之后：「数据大屏」重做为**工作概览**＝政策发布情况 + 本地成功案例，
//      由 `database.get_government_overview()` 提供（上面 v59 ③ 提到的 `get_dashboard_overview()`
//      及其 region/direction 两个统计函数**已整体删除**，仅作历史记录）。
//        · 政策拆「本级发布 / 平台预置」两类 —— 预置政策用 gov_demo 身份灌入，只按 author_id 分不开，
//          直接 COUNT 会把平台内容算成本级政绩（复用 POLICIES_DATA 标题白名单区分）。
//        · 岗位数移出政府端，归企业端「工作台」；该处「在招职位」改为只统计
//          `review_status='approved'`（原来含未审核岗位），另加「待审核岗位」卡。
// v60（2026-10-08）：超级管理员端「轮播图」整块下架（用户拍板）——
//      首页轮播早在 v54 就已整块移除（index.html 零引用），管理端的增删改因此没有任何产出；
//      且图片只能填外链 URL（库内 3 条均为 placehold.co，实测加载失败、管理端列表全是裂图）。
//      ①admin.html：删侧栏入口 + #page-carousels 整页 + loadCarousels/addCarousel/toggleCar/delCar；
//      ②app.py：删 4 条 /api/admin/carousels* 与公开的 /api/carousels（前端本就零调用）；
//      ③database.py：删 get/add/update/delete_carousel（carousels 表与种子保留，不 DROP）；
//      ④script.js：删 loadAdminCarousels/adminToggleCarousel/adminDeleteCarousel/setupAdminCarouselAdd
//        及 setupAdminSubTabs 分支与 setupNewFeatures 里的挂载；⑤styles.css 删 .home-carousel* 死样式。
// v61（2026-10-08）：清理 script.js 中「超级管理员功能」整块死代码 ——
//      admin.html 只加载 js/core.js + portal.js，根本不加载 script.js，
//      这批函数依赖的 admin-* DOM id 在 index.html 也全部不存在（双重不可达）。
//      删除 11 个函数（loadAdminUsers/adminUpdateUser/adminSuspendUser/adminUnsuspendUser/
//      adminDeleteUser/loadAdminReviews/adminApproveReview/adminRejectReview/
//      loadAdminAnnouncements/adminDeleteAnnouncement/setupAdminAnnouncementPublish）
//      及其 4 处挂载（setupAdminSubTabs 分支 ×3、setupNewFeatures、switchTab 的
//      admin 分支、角色首次加载链首、末尾管理员搜索 IIFE），共 -158 行。
//      ⚠️ 保留 showPublishAnnouncementModal / loadAnnouncements —— 它们用的是
//         teacher-publish-ann-btn / teacher-announcements-list，属教师端活功能。
// v62（2026-10-09）：修复 super_admin / government / enterprise 登录主站整页空白 ——
//      这三个角色的工作台是独立门户页（admin.html / government.html / enterprise.html），
//      而 ROLE_DEFAULT 指向的 admin/government/enterprise tab 在 index.html 里并不存在，
//      登录后所有面板都被隐藏 → 一片空白。现加一张「工作台引导卡」把他们送过去
//      （index.html 新增 #role-portal-card、styles.css 新增 .role-portal-*、
//       script.js 新增 ROLE_PORTAL / hasMainSitePanel() / applyRolePortalCard()）。
// v63（2026-10-09）：打通「企业 ↔ 学员」沟通闭环相关改动 ——
//      script.js：投递/消息两处状态映射补齐第四种状态 interview（原先会把英文原文显示给学员）；
//      styles.css：新增 .emp-app-status.interview 徽标色。
//      （企业端消息页、简历查看在 enterprise.html 内，不在预缓存清单，不影响本版本号。）
// v65：script.js 未读红点实时刷新（打开消息中心 / 窗口重获焦点 / 15s 轮询三条通道），
//      修复「对方发来新消息但铃铛红点不出现」。
// v66：会话内消息实时刷新 —— script.js（主站会话弹窗 openConversation / doSend）+ enterprise.html
//      （企业端消息页 openConv / renderConv）新增 4s 轮询，对方发来新消息在聊天页自动出现，无需刷新页面；
//      backend 配合：database.send_message 显式生成 uuid 并返回，/api/messages/send 下发 id 供前端去重。
// v67（2026-10-09）：index.html 按板块拆成独立页面 —— 农业技能 / 电商运营 / 手工传承 /
//      本土资源 / 就业对接各自成页（index.html 只留 Hero + 角色引导卡），
//      教师管理面板独立为 teacher-panel.html；导航按钮由 tab 改成真实链接，整页跳转。
//      script.js 的 switchTab 改为「按板块名跳对应页面」，原先切板块时才拉的数据
//      （3D 模型 / 案例 / 政策 / 职位 / 教师仪表板）改由 initPageExtras 在首屏加载。
//      面包屑导航整块下线；农时日历有农事的日期改为整格背景加深（去掉日期下方小圆点）。
// v68（2026-10-09）：消息中心「未读 / 已读」改造 + 滚动链修复 ——
//      ① 新增 notification_reads 旁路表，给 system_announcements / job_applications
//         两个自身没有 is_read 的数据源补按用户的已读记录，未读/已读从此覆盖全部四个来源
//         （此前只覆盖 notifications + messages，「全部已读」点不掉企业通知和系统公告）；
//      ② 页签由「通知 / 我的对话」改为「未读(N) / 已读 / 我的对话」，未读页签只列未读，
//         点击即归档并从未读列表消失；
//      ③ 消息中心条目整盒可点（此前只有「回复」小按钮可点），有对话对象的进会话窗口；
//      ④ 头部「全部已读」左侧新增红底白字未读按钮，点击跳到未读页签；
//      ⑤ 未读红点口径改为按会话数（此前按消息条数，红点 15 而可见条目只有 9）；
//      ⑥ .msg-dropdown-body 补 overscroll-behavior: contain，修「在通知列表里滚动
//         主页面跟着滚」的滚动链。
// v69（2026-10-09）：消息中心两处体验修正 ——
//      ① 「未读」页签按钮右侧的未读条数角标去掉（头部红底按钮与铃铛红点已能表达数量，
//         页签上再放一个属于重复信息）；
//      ② 无对话对象的通知（系统公告 / 公告 / 实训批改）点击后弹详情弹窗，展示完整标题、
//         类型标签、正文与时间 —— 列表里只有两行截断摘要，公告正文与批改评语点开才能看全。
//         有对话对象的（企业通知 / 互动）仍跳会话窗口。
const CACHE_NAME = 'yuexiang-v69';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/agriculture.html',
    '/ecommerce.html',
    '/crafts.html',
    '/resources.html',
    '/employment.html',
    '/teacher-panel.html',
    '/case-detail.html',
    '/styles.css',
    '/script.js',
    '/js/core.js',
    'https://cdn.bootcdn.net/ajax/libs/font-awesome/6.0.0/css/all.min.css'
];

// 安装：预缓存核心静态资源
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('[SW] 缓存核心资源');
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('[SW] 部分资源缓存失败:', err);
            });
        })
    );
    self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
            );
        })
    );
    self.clients.claim();
});

// 请求拦截：HTML/JS/CSS网络优先，其余静态资源（图片等）缓存优先
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response(
                    JSON.stringify({ success: false, message: '离线模式：请检查网络连接' }),
                    { status: 503, headers: { 'Content-Type': 'application/json' } }
                );
            })
        );
        return;
    }

    // HTML / JS / CSS：网络优先，失败才用缓存（保证代码更新即时生效）
    const isFresh = event.request.mode === 'navigate' ||
                    url.pathname === '/' ||
                    url.pathname.endsWith('.html') ||
                    url.pathname.endsWith('.js') ||
                    url.pathname.endsWith('.css');
    if (isFresh) {
        event.respondWith(
            fetch(event.request).then(response => {
                if (response.ok && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            }).catch(() => caches.match(event.request).then(cached => cached || caches.match('/')))
        );
        return;
    }

    // 其他静态资源（图片/字体等）：缓存优先
    event.respondWith(
        caches.match(event.request).then(cached => {
            if (cached) return cached;
            return fetch(event.request).then(response => {
                if (response.ok && response.type === 'basic') {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
                }
                return response;
            });
        })
    );
});
