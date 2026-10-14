# 后端拆分事实勘察（只读勘察报告）

勘察对象：`app.py`（6032 行）、`database.py`（3346 行，实际 3866 行）。全程只读，未修改任何既有文件。
区块名取 `app.py` 内的 `# ==================== xxx ====================` 注释横幅。

## A. app.py 的横切依赖

### A1. 模块级 helper 函数与被调用区块

共 67 个非路由顶层函数（135 个路由）。按被几个区块调用分组列出。

**被 3 个及以上区块调用（跨领域，拆分后必然进入共享层）**

- `_get_session_user`（`app.py:81`）：会话取用户。调用点分布：会话与权限助手 `app.py:99`；农业技能API `app.py:1248,1260,1281,1315`；直播实训 `app.py:2113,2215`；就业能力档案 `app.py:4413`；消息系统API `app.py:5440,5450`；超级管理员 API `app.py:5966,5981,6018,6056,6081,6114,6168,6177,6194,6210,6219,6231,6242,6251`；政府人员 API `app.py:6264,6273,6296,6313,6324`；教师扩展 API `app.py:6336,6345,6358,6369,6386,6413,6429,6438`；企业用户 API `app.py:6485,6508,6535,6565,6592,6623,6640`；公开 API `app.py:6750,6775`。共 10 个区块。
- `_require_role`（`app.py:93`）：角色装饰器工厂。调用点：教师管理API `app.py:4707,4716,4734,4751,4801,4808,4820,4838,4848`；通知公告API `app.py:5387,5393,5410`；实训批改 API `app.py:5641,5661`；学情分析API `app.py:5717`；教师扩展 API `app.py:6427,6436,6469`。共 5 个区块。
- `_rate_limited`（`app.py:279`）：限流判定。调用点：农业技能API `app.py:1361,1411,1576`；电商运营API `app.py:1611,1748`；直播实训 `app.py:2053,2262,2486,2525`；P3-8 难度加权 `app.py:2921,2965`；病虫害诊断 `app.py:3496`；本土资源API `app.py:3833`；就业能力档案 `app.py:4548`。共 7 个区块。
- `_client_key`（`app.py:311`）：限流键构造。调用点与 `_rate_limited` 完全重合（`app.py:1361,1411,1576,1611,1748,2053,2262,2486,2525,2921,2965,3496,3833,4548`），共 7 个区块。
- `_chat_completion`（`app.py:544`）：同步 LLM 调用。调用点：农业技能API `app.py:1380`；直播实训 `app.py:2067,2630`；本土资源API `app.py:3867`；AI服务调用 `app.py:5870,5903`。共 4 个区块。
- `call_ai_service`（`app.py:5857`）：AI 统一出口。调用点：农业技能API `app.py:1523,1584`；电商运营API `app.py:1672,1825`；直播实训 `app.py:2311`；P3-8 难度加权 `app.py:2934,2977`；病虫害诊断 `app.py:3417`；本土资源API `app.py:3878`；就业能力档案 `app.py:4580`；教师管理API `app.py:4946`。共 8 个区块。
- `_chat_model`（`app.py:266`）：模型名解析。调用点：农业技能API `app.py:1381,1432,1528,1589`；电商运营API `app.py:1695,1843`；直播实训 `app.py:2078,2326,2633`；P3-8 难度加权 `app.py:2940,2995`；本土资源API `app.py:3872,3882`。共 5 个区块。
- `_has_chem_dosage`（`app.py:452`）：农药剂量正则判定。调用点：会话与权限助手 `app.py:476`（被 `_chem_dose_notice_for` 转发）；农业技能API `app.py:1391,1485`；病虫害诊断 `app.py:3393`。共 3 个区块。
- `_ai_configured`（`app.py:256`）：AI 配置检查。调用点：会话与权限助手 `app.py:263`；农业技能API `app.py:1372,1417,1579`；病虫害诊断 `app.py:3509,3523`；就业能力档案 `app.py:4552`；AI服务调用 `app.py:5868,5891`。共 5 个区块。
- `_messages_self_guard`（`app.py:5432`）：消息身份护栏。调用点：消息系统API `app.py:5473,5485,5502,5514`；系统通知API `app.py:5527,5538,5557,5583,5613,5623`。共 2 个区块但横跨两个不同业务域。
- `_training_status_label`（`app.py:2102`）：实训状态标签。调用点：直播实训 `app.py:2239`；实训批改 API `app.py:5705`。共 2 个区块（学员端 + 教师端）。

**被 2 个区块调用（局部共享，归属需判断）**

- `_ec_product_ok`（`app.py:203`）：电商运营API `app.py:1619`；直播实训 `app.py:2129,2265`。
- `_agriculture_product_name`（`app.py:351`）：会话与权限助手 `app.py:384`（被 `_agri_system_prompt` 转发）；农业技能API `app.py:1521,1582`。

**只被单一领域使用（可随领域搬走）**

- 病虫害诊断域：`_tag_diagnosis_source`（`app.py:247`，仅 `app.py:3528,3568`）、`_parse_diag_images`（`app.py:3263`，仅 `app.py:3332`）、`_parse_diag_request`（`app.py:3300`，仅 `app.py:3492`）、`_diag_system_prompt`（`app.py:3349`，仅 `app.py:3404`）、`_diag_user_message`（`app.py:3365`，仅 `app.py:3405`）、`_parse_ai_diagnosis`（`app.py:3377`，仅 `app.py:3423`）、`_diagnose_via_ai`（`app.py:3401`，仅 `app.py:3525`）、`_kb_bigrams`（`app.py:3433`，仅 `app.py:3450,3466`）、`_kb_overlap_ratio`（`app.py:3448`，仅 `app.py:3473,3475`）、`_match_kb_disease`（`app.py:3456`，仅 `app.py:3545`）。
- 病虫害速查域：`_pest_entry_view`（`app.py:3591`，仅 `app.py:3657`）。
- 农业问答域：`_agri_system_prompt`（`app.py:383`，仅 `app.py:1369,1426`）、`_parse_agri_request`（`app.py:479`，仅 `app.py:1357,1407`）、`_build_agri_messages`（`app.py:520`，仅 `app.py:1369,1426`）、`_generate_suggestions`（`app.py:1519`，仅 `app.py:1396,1500`）、`_static_agri_suggestions`（`app.py:1558`，仅 `app.py:1577,1580,1599`）。
- 二十四节气域：`_solar_delta_t_days`（`app.py:945`）、`_solar_julian_day`（`app.py:951`）、`_sun_apparent_longitude`（`app.py:963`）、`_solar_jd_to_ymd`（`app.py:977`）、`solar_terms`（`app.py:997`）、`solar_terms_of_month`（`app.py:1028`）、`_month_in_phase`（`app.py:1045`，被 `app.py:1114` 调用）。其中 `solar_terms_of_month` 被农业技能API `app.py:1120` 调用，`_month_in_phase` 被 `app.py:1114` 调用，是本域唯一外向接口。
- 农业日历域：`_farming_task_brief`（`app.py:1293`，仅 `app.py:1336`）。
- 直播朗读域：`_live_cjk`（`app.py:1934`，仅 `app.py:1980,1981,1986`）、`_live_speed_score`（`app.py:1939`，仅 `app.py:1988`）。
- 直播实训域：`_training_submit_core`（`app.py:2106`，被 `app.py:2194,2200,2206` 三个提交路由共用）、`generate_fallback_copywriting`（`app.py:2337`，仅 `app.py:2332`）、`_copy_score`（`app.py:2422`，仅 `app.py:2495`）、`_sentiment_from_score`（`app.py:2498`，仅 `app.py:2638,2647`）、`generate_dynamic_fallback`（`app.py:2652`，仅 `app.py:2645`）、`analyze_service_reply`（`app.py:2782`，仅 `app.py:2637,2646`）、`generate_dynamic_hint`（`app.py:3007`，仅 `app.py:3003`）。
- 本土资源域：`generate_dynamic_voice_answer`（`app.py:3926`，仅 `app.py:3916`）、`_chem_dose_notice_for`（`app.py:463`，仅 `app.py:3912,3922`，注意它转调 `_has_chem_dosage`，属跨域转调）。
- 就业岗位域：`_category_option_list`（`app.py:4268`，仅 `app.py:4257,4258`）、`_self_only`（`app.py:4408`，被同区块 7 处 `app.py:4428,4437,4446,4538,4616,4640,4655` 调用）。
- 就业能力档案域：`_profile_for_ai`（`app.py:4475`，仅 `app.py:4557`）、`_user_has_resume`（`app.py:4696`，被就业对接API `app.py:4342` 与能力档案 `app.py:4692` 调用，跨区块）。
- 教师管理域：`_normalize_roster_rows`（`app.py:5037`，仅 `app.py:5060,5124`）、`_build_fallback_overview`（`app.py:5058`，仅 `app.py:5023`）、`_build_fallback_report`（`app.py:5122`，仅 `app.py:5022`）。
- AI 服务域：`_ai_vision_configured`（`app.py:261`，被 `app.py:263` 即 `_ai_configured` 调用，仅此一处）、`call_ai_vision_service`（`app.py:5882`，仅 `app.py:3407`，即病虫害诊断的 `_diagnose_via_ai`）。
- 静态文件域：`_static_not_found`（`app.py:6830`，仅 `app.py:6840,6844,6848,6852,6856`）。

### A2. 只被单一领域 vs 3 个以上领域共用

- 可随领域搬走（单区块使用）：A1 末段列出的全部函数，覆盖病虫害诊断/速查、农业问答、节气、直播朗读、直播实训、本土资源、就业岗位、就业档案、教师管理、静态文件等区块。
- 必须留在共享层（>=3 区块）：`_get_session_user`（10 区块）、`call_ai_service`（8 区块）、`_rate_limited` 与 `_client_key`（各 7 区块）、`_chat_model`（5 区块）、`_require_role`（5 区块）、`_ai_configured`（5 区块）、`_chat_completion`（4 区块）、`_has_chem_dosage`（3 区块）。
- 边界情形：`_messages_self_guard`（2 区块：消息系统 + 系统通知）、`_training_status_label`（2 区块：直播实训 + 实训批改）、`_ec_product_ok`（2 区块）、`_agriculture_product_name`（2 区块）、`_user_has_resume`（2 区块）。

### A3. 模块级可变状态与读写位置

- `_rate_lock`（锁，`app.py:275`）：仅在 `_rate_limited` 内读用，`app.py:288`。
- `_rate_buckets`（dict，`app.py:276`）：仅在 `_rate_limited` 内读写，`app.py:289,291,298,299,300`。
- `_agri_name_cache_lock`（锁，`app.py:348`）：仅 `_agriculture_product_name` 读用，`app.py:378`。
- `_agri_name_cache`（dict，`app.py:337`）：仅 `_agriculture_product_name` 读写，`app.py:360,379`。
- `_solar_terms_cache`（dict，`app.py:942`）：仅 `solar_terms` 读写，`app.py:1003,1004,1024`。
- `_suggestions_cache`（dict，`app.py:1543`）与 `_suggestions_cache_time`（dict，`app.py:1544`）：仅 `get_agriculture_suggestions` 读写，`app.py:1573,1574,1594` 与 `app.py:1573,1595`。
- 不可变常量（无锁保护，仅读）：`_CORS_LOCAL_PATTERNS`（`app.py:54`）、`_CORS_EXTRA_ORIGINS`（`app.py:59`）、`_TEACHER_ROLES`（`app.py:112`）、`_AGRI_PRODUCT_NAME_FALLBACK`（`app.py:324`，读点 `app.py:375`）、`_AGRI_SUPPORTED_PRODUCTS`（`app.py:347`，读点 `app.py:507`）、`AGRICULTURE_KNOWLEDGE`（`app.py:588`，读点 `app.py:373`）、`CRAFTS_KNOWLEDGE`（`app.py:636`，读点 `app.py:3221,3222`）、`DIALECTS_DATA`（`app.py:3684`，读点 `app.py:3764,3772,3839`）、`_LIVE_RUBRIC`（`app.py:1916`）、`_LIVE_RUBRIC_RE`（`app.py:1927`，读点 `app.py:1993,1999,2031`）、`_LIVE_SPEED_IDEAL`（`app.py:1931`，读点 `app.py:1940,2015,2017`）、`_TRAINING_STATUS_LABELS`（`app.py:2094`，读点 `app.py:2103`）、`_CHEM_DOSE_NOTICE`（`app.py:407`）、`_CHEM_DOSE_NOTICE_BLOCK`（`app.py:411`，读点 `app.py:1392,1487`）、`_CHEM_DOSE_PATTERNS`（`app.py:416`，读点 `app.py:460`）、`_EC_PROMO_RULE`（`app.py:192`，读点 `app.py:1693,2324`）、`DIAG_SOURCE_META`（`app.py:234`，读点 `app.py:249,250`）、`RESUME_AI_SYSTEM_PROMPT`（`app.py:4462`，读点 `app.py:4581`）、`RESUME_AI_SECTIONS`（`app.py:4456`，读点 `app.py:4541,4558`）、`_BASE_DIR`（`app.py:921`，读点 `app.py:925,6397,6398,6418,6454,6455,6473,6858`）。
- AI 配置常量：`AI_API_URL`（`app.py:116`，读点 `app.py:560,1444`）、`AI_API_KEY`（`app.py:117`，读点 `app.py:258,562,1446`）、`AI_MODEL`（`app.py:118`，读点 `app.py:272,551`）、`AI_VL_MODEL`（`app.py:122`，读点 `app.py:263,3515,5893`）、`AI_CHAT_MODEL`（`app.py:131`，读点 `app.py:272`）、`AI_REASONING_EFFORT`（`app.py:138`，读点 `app.py:557,558,1440,1441`）、`AI_REASONING_TOKEN_RESERVE`（`app.py:140`，读点 `app.py:1437,1526,1587,2076,2632,3413,3421,3870,3881,4582,5858,5883`）。
- `app.py` 内不存在 `threading.Lock` 之外的模块级可变写入点；`database.py` 内无任何锁、无 `global` 语句（见 B 节）。

## B. database.py 的领域分组

### B1. 表清单（`CREATE TABLE` 位置）

- 用户与认证：`users`（`database.py:59`）、`user_sessions`（`database.py:87`）、`points`（`database.py:94`）
- 学员与教学：`students`（`database.py:109`）、`assignments`（`database.py:129`）、`assignment_submissions`（`database.py:139`）、`certificates`（`database.py:100`）、`announcements`（`database.py:120`）
- 消息与通知：`messages`（`database.py:152`）、`notifications`（`database.py:161`）、`notification_reads`（`database.py:178`）、`system_announcements`（`database.py:272`）
- 就业：`job_listings`（`database.py:214`）、`job_applications`（`database.py:186`）、`saved_jobs`（`database.py:223`）、`resumes`（`database.py:233`）、`job_intents`（`database.py:253`）
- 内容审核：`content_reviews`（`database.py:75`）
- 政策：`policies`（`database.py:197`）、`government_policies`（`database.py:371`）、`seed_meta`（`database.py:208`）
- 课程与资源：`courses`（`database.py:282`）、`course_materials`（`database.py:294`）、`models_3d`（`database.py:305`）、`carousels`（`database.py:262`）
- 社区：`comments`（`database.py:320`）、`discussions`（`database.py:331`）
- 企业采购：`procurements`（`database.py:344`）
- 农业：`farming_products`（`database.py:387`）、`farming_phenophases`（`database.py:399`）、`farming_tasks`（`database.py:412`）、`farming_subscriptions`（`database.py:439`）、`farming_reminder_log`（`database.py:448`）、`farming_seed_meta`（`database.py:459`）、`farming_sources`（`database.py:468`）
- 其他：`news_articles`（`database.py:360`，无任何函数读写，仅建表）

### B2. 函数按领域归组

**基础设施（无领域表）**

- `get_connection`（`database.py:27`）：每次调用新建连接，设 WAL / `foreign_keys=ON` / `busy_timeout=8000`（`database.py:32-34`）。被 130+ 个函数复用。
- `hash_password`（`database.py:38`）、`verify_password`（`database.py:46`，内部调 `hash_password@49`）。
- `init_db`（`database.py:52`）：建表 + 播种，内部调用 `_seed_data@545`、`_refresh_policies@548`、`_seed_farming@574`、`_ensure_demo_accounts@571`、`_seed_government_policies@565`、`_seed_carousels@569`、`_seed_case_reviews@580`、`_seed_demo_jobs@584`。内含 `ALTER TABLE job_listings`（`database.py:517-519`）与 `PRAGMA table_info(farming_tasks)` 补列逻辑（`database.py:521-527`）。

**用户与认证**

- `authenticate_user`（`database.py:1385`，读 `users@1388`，调 `verify_password@1390`）
- `create_session`（`database.py:1395`，写 `user_sessions@1401`）
- `get_session`（`database.py:1408`，读 `user_sessions@1411` + `users@1413`，跨表）
- `delete_session`（`database.py:1425`，写 `user_sessions@1428`）
- `get_user_by_id` 出现两次：`database.py:1435` 与 `database.py:2954`（同名重复定义，后者覆盖前者）
- `get_user_by_username`（`database.py:1443`）
- `update_user_profile` 出现两次：`database.py:1451` 与 `database.py:3174`（同名重复定义）
- `change_password`（`database.py:1472`，调 `hash_password@1482`、`verify_password@1479`）
- `get_points`（`database.py:1491`）、`update_points`（`database.py:1501`）
- `register_user`（`database.py:2935`，写 `users@2946`）
- `get_all_users`（`database.py:2962`）、`update_user_by_admin`（`database.py:2979`）、`count_user_relations`（`database.py:3034`）、`count_super_admins`（`database.py:3065`）、`get_admin_overview`（`database.py:3073`，读 `users@3107` + `content_reviews@3120`，跨域）、`set_user_status`（`database.py:3143`）、`delete_user_by_admin`（`database.py:3154`，写 `users@3165`、`user_sessions@3167`、`points@3168`，跨表）

**学员与教学**

- `get_students`（`database.py:1538`）、`get_student`（`database.py:1555`）、`add_student`（`database.py:1563`）、`get_linkable_student_accounts`（`database.py:1585`，读 `users@1592` + `students@1592`，跨域）、`set_student_account`（`database.py:1601`，写 `students@1624` + `users@1612`，跨域）、`update_student`（`database.py:1630`）、`delete_student`（`database.py:1662`）
- `get_certificates`（`database.py:1528`）
- `create_announcement`（`database.py:1674`）、`get_announcements`（`database.py:1683`）、`delete_announcement`（`database.py:1689`）
- `grade_submission`（`database.py:1706`，写 `assignment_submissions@1708`）
- `get_or_create_training_assignment`（`database.py:1741`，写 `assignments@1756`）、`get_or_create_live_assignment`（`database.py:1767`，转调 `get_or_create_training_assignment@1769`）
- `save_live_training`（`database.py:1772`，写 `assignment_submissions@1813`）
- `get_trainings`（`database.py:1831`，读 `assignment_submissions@1839` + `assignments@1839`）、`get_live_trainings`（`database.py:1857`，转调 `get_trainings@1859`）、`get_all_trainings`（`database.py:1862`，读 `students@1875` + `assignment_submissions@1875` + `assignments@1875`）
- `get_roster_completion`（`database.py:1899`，读 `students@1910` + `certificates@1917`，跨表）
- `get_analytics_data`（`database.py:1932`，转调 `get_roster_completion@1938`）
- `get_dashboard_stats`（`database.py:2909`，转调 `get_roster_completion@2919`）

**消息与通知**

- `send_message`（`database.py:1972`）、`get_messages`（`database.py:1986`）、`get_inbox`（`database.py:1998`，读 `students@1999` + `messages@2008` + `users@2024`，跨 3 表）、`get_unread_count`（`database.py:2046`）、`mark_messages_read`（`database.py:2056`）、`mark_all_messages_read`（`database.py:2177`）
- `create_notification`（`database.py:2068`）、`create_notification_for_all_students`（`database.py:2078`，写 `notifications@2090` + `students@2087`，跨域）、`get_notifications`（`database.py:2097`）、`get_unread_notification_count`（`database.py:2107`）、`mark_notifications_read`（`database.py:2117`）、`clear_read_notifications`（`database.py:2127`）
- `get_read_refs`（`database.py:2138`）、`mark_ref_read`（`database.py:2148`）、`mark_refs_read`（`database.py:2157`）、`clear_read_refs`（`database.py:2168`）
- `get_job_application_ids`（`database.py:2187`，读 `job_applications@2191`，就业域函数服务于通知域）、`get_active_system_announcement_ids`（`database.py:2196`）、`get_total_unread_count`（`database.py:2205`，读 `notifications@2212` + `messages@2218` + `job_applications@2228` + `notification_reads@2228` + `system_announcements@2237`，跨 5 表 3 域）
- `get_system_announcements`（`database.py:3369`）、`add_system_announcement`（`database.py:3384`）、`delete_system_announcement`（`database.py:3397`）

**就业**

- `get_job_listings`（`database.py:2251`）、`apply_for_job`（`database.py:2264`，写 `job_applications@2285` + 读 `job_listings@2276`）、`get_job_by_id`（`database.py:2291`）、`parse_salary_bounds`（`database.py:2318`）、`_salary_matches`（`database.py:2351`，调 `parse_salary_bounds@2365`）、`get_job_listings_base`（`database.py:2380`，调 `parse_salary_bounds@2399`、`_salary_matches@2403`）、`get_job_category_counts`（`database.py:2410`，调 `get_job_listings_base@2413`）、`get_job_listings_filtered`（`database.py:2419`，调 `get_job_listings_base@2428`）、`count_pending_job_listings`（`database.py:2434`）、`get_similar_jobs`（`database.py:2450`）
- `save_job`（`database.py:2465`）、`unsave_job`（`database.py:2478`）、`get_saved_jobs`（`database.py:2487`）
- `get_user_applications`（`database.py:2495`，读 `job_applications@2499` + `job_listings@2499`）、`get_application_counts`（`database.py:2520`）、`get_employment_stats`（`database.py:2531`，读 `job_applications@2534` + `saved_jobs@2535` + `job_intents@2536`，跨 3 表）
- `get_learner_profile`（`database.py:2549`，读 `certificates@2575` + `assignment_submissions@2600` + `assignments@2600` + `users@2563` + `points@2583` + `students@2590`，跨 6 表 4 域）
- `get_resume`（`database.py:2621`）、`save_resume`（`database.py:2636`，调 `get_resume@2642` 与 `get_resume@2677`）、`mark_resume_ai_used`（`database.py:2680`）
- `add_job_intent`（`database.py:2693`）、`remove_job_intent`（`database.py:2715`）、`get_job_intents`（`database.py:2726`）

**内容审核**

- `create_content_review`（`database.py:3197`）、`get_pending_reviews`（`database.py:3207`）、`approve_review`（`database.py:3221`，读 `content_reviews@3229` 并写 `courses@3238`、`job_listings@3240`、`procurements@3242`、`models_3d@3244`）、`reject_review`（`database.py:3249`，同样跨 4 表 `database.py:3259,3265,3267,3269,3271`）、`get_reviews_by_status`（`database.py:3276`）、`count_reviews_by_status`（`database.py:3307`）、`revoke_review`（`database.py:3323`，跨 4 表 `database.py:3340,3344,3346,3348,3350`）、`get_review_by_content`（`database.py:3356`）

**课程 / 模型 / 社区**

- `create_course`（`database.py:3408`，调 `create_content_review@3419`，跨域）、`get_courses`（`database.py:3423`）、`get_course`（`database.py:3439`）、`update_course`（`database.py:3447`）、`delete_course`（`database.py:3461`，写 `course_materials@3464` + `courses@3465` + `content_reviews@3466`，跨域）、`add_course_material`（`database.py:3474`）、`get_course_materials`（`database.py:3487`）、`delete_course_material`（`database.py:3496`）
- `create_model_3d`（`database.py:3508`，调 `create_content_review@3519`，跨域）、`get_models_3d`（`database.py:3523`）、`delete_model_3d`（`database.py:3539`，写 `models_3d@3543` + `content_reviews@3544`，跨域）
- `add_comment`（`database.py:3552`，写 `comments@3557` + `discussions@3563`，跨表）、`get_comments`（`database.py:3569`，读 `comments@3573` + `users@3573`，跨域）、`soft_delete_comment`（`database.py:3582`）、`create_discussion`（`database.py:3593`）、`get_discussions`（`database.py:3606`，读 `discussions@3609` + `users@3609`，跨域）、`get_discussion`（`database.py:3625`，读 `discussions@3628` + `users@3630`，跨域）、`soft_delete_discussion`（`database.py:3637`）

**政府与政策**

- `create_policy`（`database.py:3725`，调 `policy_sources_to_json@3746`、`default_policy_summary@3745`）、`get_government_policies`（`database.py:3753`，调 `_attach_policy_sources@3765`）、`get_all_government_policies`（`database.py:3768`，调 `_attach_policy_sources@3773`）、`get_policy_by_id`（`database.py:3776`，调 `_attach_policy_sources@3781`）、`update_policy`（`database.py:3784`，调 `policy_sources_to_json@3795`）、`delete_policy`（`database.py:3806`）
- `get_government_overview`（`database.py:3826`，读 `government_policies@3840`，并调 `get_case_review_stats@3857` 与 `get_success_cases@3858`，跨入案例域）
- 旧 `policies` 表残留：`get_policies`（`database.py:2899`，读 `policies@2902`，调 `_attach_policy_sources@2904`）。`app.py:3808` 注释明确标注不得降级回此函数。
- 政策辅助函数：`_policy_source_json`（`database.py:639`）、`_policies_signature`（`database.py:750`）、`_refresh_policies`（`database.py:763`，写 `policies@789` + `government_policies@798` + `seed_meta@807`，跨 3 表）、`_attach_policy_sources`（`database.py:2841`，调 `normalize_policy_category@2851`）、`policy_sources_to_json`（`database.py:2860`）、`default_policy_summary`（`database.py:2885`）、`normalize_policy_category`（`database.py:2829`）、`_POLICY_CATEGORY_ALIASES`（`database.py:2821`）
- `get_policy_notes`（`database.py:2807`，import `policies_data@2809`）

**农业（farming）**

- `get_farming_products`（`database.py:1177`）、`get_farming_product`（`database.py:1189`）、`get_farming_sources`（`database.py:1197`）、`get_farming_source_map`（`database.py:1209`，调 `get_farming_sources@1211`）、`get_farming_category_labels`（`database.py:1214`，import `farming_data@1220`）、`get_farming_phenophases`（`database.py:1226`）、`get_farming_tasks`（`database.py:1241`，读 `farming_tasks@1244` + `farming_phenophases@1244`）、`get_farming_task_by_id`（`database.py:1258`，读 2 表 `database.py:1262`）、`get_farming_subscriptions`（`database.py:1272`）、`is_farming_subscribed`（`database.py:1282`）、`set_farming_subscription`（`database.py:1291`）、`get_farming_subscribers`（`database.py:1307`）、`has_farming_reminder_sent`（`database.py:1319`）、`mark_farming_reminder_sent`（`database.py:1329`）、`clear_farming_reminder_log`（`database.py:1339`）、`get_due_farming_tasks`（`database.py:1359`，调 `get_farming_tasks@1365`）
- 播种：`_farming_seed_signature`（`database.py:1046`）、`_seed_farming`（`database.py:1083`，import `farming_data@1096`，写 `farming_sources@1114`、`farming_products@1125`、`farming_phenophases@1135`、`farming_tasks@1150`、`farming_seed_meta@1167`）

**企业采购**

- `create_procurement`（`database.py:3648`，调 `create_content_review@3663`，跨域）、`get_procurements`（`database.py:3667`，读 `procurements@3670` + `users@3670`，跨域）、`update_procurement`（`database.py:3686`）、`delete_procurement`（`database.py:3701`，写 `procurements@3704` + `content_reviews@3705`，跨域）

**案例（cases，数据源在 `cases_data.py`）**

- `get_success_cases`（`database.py:2742`，import `cases_data@2753`，读 `content_reviews@2759`）
- `get_case_review_stats`（`database.py:2766`，import `cases_data@2768`，读 `content_reviews@2775`）
- `get_case_notes`（`database.py:2798`，import `cases_data@2800`）
- `_seed_case_reviews`（`database.py:811`，import `cases_data@822`，写 `content_reviews@837`）

**播种杂项**

- `_seed_data`（`database.py:651`，写 `users@659`、`points@671`、`students@690`、`system_announcements@721`、`discussions@725`、`certificates@682`、`policies@700`、`government_policies@707`、`carousels@717`，跨 8 表，调 `hash_password` 7 次）
- `_seed_government_policies`（`database.py:731`）、`_seed_carousels`（`database.py:738`）、`_ensure_demo_accounts`（`database.py:842`，写 `users@854` + `points@856`）、`_demo_jobs_signature`（`database.py:929`）、`_create_review_with_cursor`（`database.py:939`）、`_seed_demo_jobs`（`database.py:951`，写 `job_listings@974`、`content_reviews@983`、`job_applications@1034`、`saved_jobs@1035`，跨 4 表，调 `_create_review_with_cursor@986,1028`）
- 模块级常量：`POLICIES_DATA`（`database.py:626`）、`POLICY_SOURCES`（`database.py:636`，由 `policies_data` 推导）、`POLICIES_SEED_VERSION`（`database.py:633`）、`DEMO_JOBS`（`database.py:876`）、`DEMO_JOB_ENTERPRISE_ID`（`database.py:924`）、`DEMO_JOBS_SEED_KEY`（`database.py:926`）、`TRAINING_TITLE_FMTS`（`database.py:1726`）、`LIVE_ASSIGNMENT_DIRECTION`（`database.py:1721`）、`LIVE_ASSIGNMENT_TITLE_FMT`（`database.py:1722`）、`TRAINING_DESCRIPTIONS`（`database.py:1731`）、`ENTERPRISE_JOB_CATEGORIES`（`database.py:2307`）、`RESUME_FIELDS`（`database.py:2545`）、`CASE_REVIEW_TYPE`（`database.py:2739`）、`_USER_RELATION_SPECS`（`database.py:3009`）、`_SALARY_NUM_RE`（`database.py:2314`）、`_SALARY_MIN_ABS`（`database.py:2315`）、`DB_PATH`（`database.py:24`）

### B3. database.py 内部跨领域耦合（调用点行号）

按「被调函数所属领域 != 调用方所属领域」列出：

- `get_session`（认证域，`database.py:1408`）读 `users@1413`：用户域表，属认证域必要依赖。
- `delete_user_by_admin`（用户域，`database.py:3154`）写 `user_sessions@3167`（认证域表）+ `points@3168`（积分域表）。
- `get_linkable_student_accounts`（学员域，`database.py:1585`）读 `users@1592`。
- `set_student_account`（学员域，`database.py:1601`）写 `users@1612` + `students@1624`。
- `get_roster_completion`（学员域，`database.py:1899`）读 `students@1910` + `certificates@1917`。
- `create_notification_for_all_students`（通知域，`database.py:2078`）读 `students@2087`。
- `get_inbox`（消息域，`database.py:1998`）读 `students@1999` + `users@2024`。
- `get_total_unread_count`（通知域，`database.py:2205`）聚合 `notifications@2212`、`messages@2218`、`job_applications@2228`、`notification_reads@2228`、`system_announcements@2237`，横跨消息域与就业域。
- `get_job_application_ids`（就业域实现，`database.py:2187`）被通知域的 `get_total_unread_count` 依赖（`database.py:2228` 同段）。
- `get_learner_profile`（就业域，`database.py:2549`）读 `users@2563`、`points@2583`、`students@2590`、`certificates@2575`、`assignments@2600`、`assignment_submissions@2600`，横跨 4 个域。
- `get_employment_stats`（就业域，`database.py:2531`）读 `job_applications@2534` + `saved_jobs@2535` + `job_intents@2536`，三表同为就业域，属域内聚合。
- `approve_review`（审核域，`database.py:3221`）写 `courses@3238`、`job_listings@3240`、`procurements@3242`、`models_3d@3244`：审核域反向写课程、就业、采购、模型四个域。
- `reject_review`（`database.py:3249`）同样写 `courses@3265`、`job_listings@3267`、`procurements@3269`、`models_3d@3271`。
- `revoke_review`（`database.py:3323`）同样写 `courses@3344`、`job_listings@3346`、`procurements@3348`、`models_3d@3350`。
- `get_admin_overview`（用户域，`database.py:3073`）读 `users@3107` + `content_reviews@3120`。
- `create_course`（课程域，`database.py:3408`）调 `create_content_review@3419`（审核域）。
- `delete_course`（课程域，`database.py:3461`）写 `course_materials@3464` + `content_reviews@3466`。
- `create_model_3d`（模型域，`database.py:3508`）调 `create_content_review@3519`。
- `delete_model_3d`（模型域，`database.py:3539`）写 `content_reviews@3544`。
- `create_procurement`（采购域，`database.py:3648`）调 `create_content_review@3663`。
- `delete_procurement`（采购域，`database.py:3701`）写 `content_reviews@3705`。
- `get_comments`（社区域，`database.py:3569`）读 `users@3573`；`get_discussions`（`database.py:3606`）读 `users@3609`；`get_discussion`（`database.py:3625`）读 `users@3630`。
- `add_comment`（社区域，`database.py:3552`）写 `comments@3557` + `discussions@3563`（同一事务内更新帖子的评论数，属域内耦合）。
- `get_procurements`（采购域，`database.py:3667`）读 `users@3670`。
- `get_government_overview`（政府域，`database.py:3826`）调 `get_case_review_stats@3857` 与 `get_success_cases@3858`，读案例域数据。
- `_refresh_policies`（政策域，`database.py:763`）写 `policies@789` + `government_policies@798` + `seed_meta@807`：同时维护新旧两套政策表。
- `_seed_data`（播种，`database.py:651`）横跨 `users@659`、`points@671`、`students@690`、`system_announcements@721`、`discussions@725`、`certificates@682`、`policies@700`、`government_policies@707`、`carousels@717`。
- `_seed_demo_jobs`（播种，`database.py:951`）横跨 `job_listings@974`、`content_reviews@983`、`job_applications@1034`、`saved_jobs@1035`。
- `_seed_farming`（农业播种，`database.py:1083`）import `farming_data@1096` 并写 5 张 farming 表。
- `get_farming_category_labels`（农业域，`database.py:1214`）import `farming_data@1220`。
- `get_success_cases`（案例域，`database.py:2742`）import `cases_data@2753` 并读 `content_reviews@2759`：案例内容来自模块，审核状态来自审核域表。
- `get_case_review_stats`（案例域，`database.py:2766`）读 `content_reviews@2775`。
- `get_policy_notes`（政策域，`database.py:2807`）import `policies_data@2809`。
- `get_or_create_live_assignment`（教学域，`database.py:1767`）与 `get_live_trainings`（`database.py:1857`）都是薄封装，分别转调 `get_or_create_training_assignment@1769`、`get_trainings@1859`。
- `get_dashboard_stats`（`database.py:2909`）与 `get_analytics_data`（`database.py:1932`）均转调 `get_roster_completion`（`database.py:2919`、`database.py:1938`）。

### B4. database.py 中被 app.py 之外引用的符号

全仓库（排除 `.venv`、`node_modules`）引用 `database.xxx` 的非 app.py 位置：

- `api/index.py:18` `import database`；`api/index.py:19` 调 `database.init_db()`。
- `e2e/serve.py:20` `import database`；`e2e/serve.py:22` 调 `database.init_db()`。
- `run.py:95` `import database`；`run.py:96` 调 `database.init_db()`。
- `_serve.py:9` `import database`；`_serve.py:12` 调 `database.init_db()`。
- `test_app.py` 内引用：`database.get_connection()`（`test_app.py:195,202,212,303,350,431,456,470,480,490,496,515,535,551,566,576,641`）、`database.get_job_intents`（`test_app.py:398,429`）、`database.get_job_listings_filtered`（`test_app.py:485`）、`database.init_db()`（`test_app.py:513`）、`database.create_content_review`（`test_app.py:562`）、`database.get_review_by_content`（`test_app.py:563,572`）、`database.reject_review`（`test_app.py:565`）。`test_app.py:9` 另有 `from app import app`。

## C. 导入面

### C1. `from app import` / `import app` / `from database import` / `import database`

- `api/index.py:18` `import database`
- `api/index.py:23` `from app import app`
- `app.py:20` `import database`
- `e2e/serve.py:20` `import database`
- `e2e/serve.py:24` `from app import app`
- `run.py:95` `import database`
- `run.py:98` `from app import app`
- `_serve.py:9` `import database`
- `_serve.py:14` `from app import app`
- `test_app.py:9` `from app import app`；`test_app.py:269` `import app as app_module`
- `test_app.py` 内的延迟导入：`test_app.py:164,220,270,364,455,550,618` 均为 `import database`
- 全仓库无任何 `from database import ...` 形式，一律 `import database` + 属性访问。
- `AI农技问答问题清单.md:396` 仅在文档正文提及文件名，非导入。

### C2. app.py 顶层 import 的本地模块及使用区块

- `database`（`app.py:20`）：被 21 个区块使用，是全应用唯一的持久化出口。使用区块：会话与权限助手（`app.py:86,89,366`）、农业技能API（`app.py:1059,1083,1106-1109,1201,1253,1267,1271,1274,1284,1286,1289,1324-1344`）、直播实训（`app.py:2183,2184,2221,2223`）、本土资源API（`app.py:3786,3788,3790,3797,3813,3816`）、就业对接API（`app.py:4222,4257,4264,4283,4293,4296,4302,4308,4319,4335,4338,4352,4358,4369,4382,4388,4394`）、就业能力档案（`app.py:4431,4440,4450,4556,4560,4592,4623,4643,4659,4666,4698`）、教师管理API（`app.py:4711,4719,4722,4737,4739,4777,4784,4786,4789`）、通知公告API（`app.py:5389,5402,5404,5412`）、学员个人数据API（`app.py:5426`）、消息系统API（`app.py:5462,5464,5476,5488,5490,5505,5517`）、系统通知API（`app.py:5530,5544-5549,5563,5564,5590,5602,5604,5616,5628`）、实训批改 API（`app.py:5650,5653,5655,5669`）、学情分析API（`app.py:5719`）、用户认证API（`app.py:5734,5738,5756,5767,5774`）、用户资料API（`app.py:5798,5801,5811,5819,5827,5840`）、用户注册（`app.py:5937,5940,5941`）、超级管理员 API（`app.py:5969-6254` 共 40+ 处）、政府人员 API（`app.py:6267,6281,6285,6303,6307,6316,6327`）、教师扩展 API（`app.py:6339-6471`）、企业用户 API（`app.py:6488-6643`）、公开 API（`app.py:6679-6793`）。读取的常量：`database.TRAINING_TITLE_FMTS`（`app.py:2213` 注释、`app.py:2221`）、`database.ENTERPRISE_JOB_CATEGORIES`（`app.py:4257`）。
- `pest_data`（`app.py:24`，导入 `PEST_KNOWLEDGE`、`PEST_SOURCE_MAP`、`PEST_CROP_ORDER`、`iter_pest_entries`、`get_pest_stats`）：仅在「常见病虫害速查」区块使用，唯一使用点 `app.py:3661`（`get_pest_knowledge`）。实际读取的符号是 `PEST_KNOWLEDGE.get`（`app.py:3661`）。
- `jobs_data`（`app.py:35`）：在 2 个区块使用，就业对接API `app.py:4235,4248,4258`（`get_jobs`）；就业能力档案 `app.py:4619,4667,4688`（`add_job_intent`、`get_my_jobs`）。读取符号：`CATEGORY_LIST`、`get_recruitment`、`get_recruitment_list`、`get_recruitment_notes`。
- `cases_data`：未在顶层导入，函数内延迟导入 2 处：`app.py:5971`（超级管理员 API 的 `admin_get_reviews`）、`app.py:6153`（超级管理员 API 的 `admin_approve_review`）。
- `policies_data`：未在顶层导入，仅 `database.py:624` 与 `database.py:2809` 引用。
- `farming_data`：未在顶层导入，仅 `database.py:1096`、`database.py:1220` 引用。
- `pest_image_manifest`：仅 `pest_data.py:1978` 引用，app.py 不直接用。
- 第三方/标准库顶层导入：`flask`（`app.py:8`）、`flask_cors`（`app.py:9`）、`datetime`（`app.py:10`）、`dotenv`（`app.py:11`）、`os`/`re`/`json`/`math`/`time`/`base64`/`logging`/`threading`（`app.py:12-19`）。

## D. 测试面

### D1. `test_app.py` 覆盖的 URL 前缀

- `/`（`test_app.py:22`）
- `/api/health`（`test_app.py:27`）
- `/api/resources/cases`、`/api/resources/cases/<id>`、`/api/resources/cases/9999`（`test_app.py:77,98,103,106,110`）
- `/api/resources/policies`（`test_app.py:115`）
- `/api/resources/dialects`（`test_app.py:48`）
- `/api/crafts/list`（`test_app.py:41`）
- `/api/agriculture/products`（`test_app.py:34`）
- `/api/agriculture/diagnose`（`test_app.py:680,683`）；另有 `/api/simulation/diagnose`（`test_app.py:678`，app.py 无此路由）
- `/api/employment/jobs`、`/api/employment/jobs/<id>`（`test_app.py:130,159,160,183,188,206,209,487`）
- `/api/employment/apply`（`test_app.py:191`）
- `/api/employment/intent`（`test_app.py:378,383,393,402,424`）
- `/api/employment/profile/<user>`（`test_app.py:282,284,294`）
- `/api/employment/resume/<user>`（`test_app.py:287,318,320`）、`/api/employment/resume/ai`（`test_app.py:333,343`）
- `/api/employment/my-jobs/<user>`（`test_app.py:410,420`）
- `/api/enterprise/jobs`（`test_app.py:176`）
- `/api/auth/login`（`test_app.py:169,274,368,586,600,619`）、`/api/auth/verify`（`test_app.py:612,624,636`）、`/api/auth/register` 未见直接调用
- `/api/teacher/dashboard`（`test_app.py:697`）、`/api/teacher/students`（`test_app.py:704`）
- 另有 `/api/xxx/undefined`（`test_app.py:615`，负向路径测试）
- 测试以 `unittest` 单类 `TestYueXiangApp`（`test_app.py:11`）组织，通过 `app.test_client()`（`test_app.py:17`）调用。

### D2. `e2e/specs/*.spec.js` 覆盖的 URL 前缀（按 spec 文件）

- `agriculture-subscriptions.spec.js`（7 处）：`/api/agriculture/subscriptions`、`/api/agriculture/subscribe`、`/api/agriculture/subscribe/<id>`、`/api/agriculture/products`、`/api/auth/login`
- `ai-contract.spec.js`（4 处）：`/api/agriculture/ask`、`/api/agriculture/ask/stream`、`/api/agriculture/suggestions`、`/api/agriculture/diagnose`、`/api/agriculture/pest-knowledge`、`/api/auth/login`
- `ai-live.spec.js`（4 处）：`/api/ecommerce/script`、`/api/ecommerce/live/records`、`/api/auth/login`、`/api/resources/cases`
- `discussions-comments.spec.js`（5 处）：`/api/comments`、`/api/discussions`、`/api/discussions/<id>`、`/api/auth/login`
- `government.spec.js`（6 处）：`/api/government/policies`、`/api/government/policies/<id>`、`/api/government/dashboard`、`/api/resources/policies`
- `government-publish-split.spec.js`（2 处）：`/api/government/policies`、`/api/government/policies/<id>`
- `messages.spec.js`（6 处）：`/api/messages/send`、`/api/messages/inbox`、`/api/messages/read`、`/api/messages/unread`、`/api/auth/login`
- `notifications-idor.spec.js`（9 处）：`/api/notifications`、`/api/notifications/read`、`/api/notifications/unread`、`/api/notifications/clear`、`/api/messages/unread`、`/api/auth/login`
- `ownership.spec.js`（30 处）：`/api/user/profile`、`/api/employment/profile/<user>`、`/api/employment/resume/<user>`、`/api/employment/my-jobs/<user>`、`/api/teacher/students`、`/api/teacher/dashboard`、`/api/teacher/analytics`、`/api/teacher/announcements`、`/api/teacher/courses`、`/api/teacher/trainings`、`/api/teacher/public-courses`、`/api/teacher/public-models-3d`、`/api/admin/users`、`/api/admin/dashboard`、`/api/admin/reviews`、`/api/admin/reviews/<id>`、`/api/resources/cases`、`/api/resources/cases/<id>`、`/api/auth/login`
- `portals-smoke.spec.js`（1 处）：`/api/health`
- `read-contracts.spec.js`（7 处）：`/api/resources/dialects`、`/api/resources/dialect-info`、`/api/resources/policies`、`/api/resources/cases`、`/api/resources/cases/<id>`、`/api/home/stats`、`/api/system-announcements`
- `review-gate.spec.js`（6 处）：`/api/enterprise/jobs`、`/api/admin/reviews`、`/api/admin/reviews/<id>/approve|reject|revoke`、`/api/employment/jobs`、`/api/auth/login`
- `smoke.spec.js`（2 处）：`/`、`/api/health`
- `helpers.js`：提供 `apiLogin` 等公共 helper，被上述 spec 复用
- `playwright.config.js:29` 以 `/api/health` 作 webServer 就绪探针
