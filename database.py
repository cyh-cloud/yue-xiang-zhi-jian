#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - SQLite数据库层
"""

import sqlite3
import hashlib
import uuid
import time
import json
import os
from datetime import datetime

# Vercel 环境使用 /tmp（可写但非持久），本地环境使用 data/ 目录
if os.environ.get('VERCEL') or os.environ.get('VERCEL_ENV'):
    DB_DIR = '/tmp'
else:
    DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'yuexiang.db')


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def hash_password(password, salt=None):
    """哈希密码"""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(stored, password):
    """验证密码"""
    salt, hashed = stored.split('$', 1)
    return hash_password(password, salt) == stored


def init_db():
    """初始化数据库：建表 + 填充种子数据"""
    conn = get_connection()
    cursor = conn.cursor()

    # 建表
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            bio TEXT DEFAULT '',
            company_name TEXT DEFAULT '',
            region TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS content_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type TEXT NOT NULL,
            content_id INTEGER NOT NULL,
            submitter_id TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            review_comment TEXT DEFAULT '',
            reviewed_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            login_time REAL NOT NULL,
            expires_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS points (
            user_id TEXT PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            history TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'locked',
            progress INTEGER DEFAULT 0,
            date TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT NOT NULL,
            class_name TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            progress INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT '通知',
            pinned INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            direction TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            total_score INTEGER DEFAULT 100,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            content TEXT DEFAULT '',
            score INTEGER DEFAULT NULL,
            feedback TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            submitted_at TEXT DEFAULT (datetime('now','localtime')),
            graded_at TEXT DEFAULT NULL,
            UNIQUE(assignment_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS attendances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '日常签到',
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            closed_at TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            check_status TEXT DEFAULT 'present',
            checked_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(attendance_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            receiver_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            type TEXT DEFAULT 'system',
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            link_type TEXT DEFAULT '',
            link_id INTEGER DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS job_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            applied_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS success_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            stats TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            date TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS job_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            salary TEXT DEFAULT '',
            requirements TEXT DEFAULT '[]',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS saved_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            job_id INTEGER NOT NULL,
            saved_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(user_id, job_id)
        );

        CREATE TABLE IF NOT EXISTS carousels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_url TEXT NOT NULL,
            link_url TEXT DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS system_announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT '',
            teacher_id TEXT NOT NULL,
            cover_url TEXT DEFAULT '',
            review_status TEXT DEFAULT 'pending',
            is_published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            material_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS models_3d (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            craft_type TEXT DEFAULT '',
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            thumbnail_url TEXT DEFAULT '',
            teacher_id TEXT NOT NULL,
            review_status TEXT DEFAULT 'pending',
            is_published INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            content TEXT NOT NULL,
            is_deleted INTEGER DEFAULT 0,
            deleted_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS discussions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            user_id TEXT NOT NULL,
            is_pinned INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            view_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS procurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            specification TEXT DEFAULT '',
            quantity TEXT DEFAULT '',
            price_range TEXT DEFAULT '',
            delivery_location TEXT DEFAULT '',
            deadline TEXT DEFAULT '',
            contact_info TEXT DEFAULT '',
            description TEXT DEFAULT '',
            enterprise_id TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            review_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS news_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'news',
            author_id TEXT NOT NULL,
            is_published INTEGER DEFAULT 1,
            view_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS government_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            author_id TEXT NOT NULL,
            is_published INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
    ''')

    # 扩展 users 表结构（兼容已有数据库）
    user_cols = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
    user_new_cols = {
        'phone': "TEXT DEFAULT ''",
        'avatar_url': "TEXT DEFAULT ''",
        'bio': "TEXT DEFAULT ''",
        'company_name': "TEXT DEFAULT ''",
        'region': "TEXT DEFAULT ''",
        'status': "TEXT DEFAULT 'active'",
    }
    for col, typedef in user_new_cols.items():
        if col not in user_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col} {typedef}")

    # 扩展 job_listings 表结构
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(job_listings)").fetchall()}
    job_new_cols = {
        'location': "TEXT DEFAULT ''",
        'category': "TEXT DEFAULT ''",
        'job_type': "TEXT DEFAULT '全职'",
        'education': "TEXT DEFAULT ''",
        'experience': "TEXT DEFAULT ''",
        'company_size': "TEXT DEFAULT ''",
        'industry': "TEXT DEFAULT ''",
        'company_logo': "TEXT DEFAULT ''",
        'posted_at': "TEXT DEFAULT ''",
        'enterprise_id': "TEXT DEFAULT ''",
        'review_status': "TEXT DEFAULT 'approved'",
    }
    for col, typedef in job_new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE job_listings ADD COLUMN {col} {typedef}")

    # 检查是否已有种子数据
    count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        _seed_data(cursor)
    else:
        # 已有数据时，刷新政策内容（保证政策详情是最新的）
        _refresh_policies(cursor)
        # 如果岗位数少于10条，补充新岗位数据
        job_count = cursor.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
        if job_count < len(JOBS_DATA):
            _seed_jobs(cursor)
        # 如果政府政策表为空，填充初始数据
        gp_count = cursor.execute("SELECT COUNT(*) FROM government_policies").fetchone()[0]
        if gp_count == 0:
            _seed_government_policies(cursor)
        # 如果轮播图为空，填充默认数据
        car_count = cursor.execute("SELECT COUNT(*) FROM carousels").fetchone()[0]
        if car_count == 0:
            _seed_carousels(cursor)
        # 如果缺少新角色演示账户，补充创建
        _ensure_demo_accounts(cursor)

    conn.commit()
    conn.close()


# 政策数据常量，供 _seed_data 和 _refresh_policies 共用
POLICIES_DATA = [
    ("农业补贴申请指南", """【政策概述】
2026年广东省农业补贴政策涵盖耕地地力保护补贴、农机购置补贴、种粮大户补贴、农业保险补贴等多项内容，旨在保障粮食安全、促进农业现代化、增加农民收入。广东省财政全年安排农业补贴资金超过50亿元，惠及全省800多万农户。

【补贴项目明细】
一、耕地地力保护补贴
• 补贴对象：拥有耕地承包权的种地农民
• 补贴标准：每亩不低于100元，珠三角地区每亩120-150元
• 发放时间：每年6月30日前一次性发放到户
• 特别说明：抛荒一年以上的取消补贴资格

二、农机购置补贴
• 补贴范围：拖拉机、收割机、插秧机、植保无人机等15大类42个小类
• 补贴标准：一般机具按售价30%补贴，单机最高5万元
• 植保无人机：按售价40%补贴，单机最高1.6万元
• 申请上限：个人年度补贴额不超过20万元，合作社不超过80万元
• 购买渠道：必须在省农机购置补贴系统中的经销商处购买

三、种粮大户补贴
• 补贴条件：种植水稻30亩以上（含30亩）
• 补贴标准：每亩补贴150元，早稻和晚稻分别计算
• 叠加补贴：可同时享受耕地地力保护补贴
• 申报时间：早稻4月底前，晚稻8月底前

四、农业保险补贴
• 水稻保险：保费每亩30元，财政补贴80%，农户自缴6元
• 荔枝保险：保费每亩60元，财政补贴70%，农户自缴18元
• 能繁母猪：保费每头100元，财政补贴80%
• 理赔标准：因自然灾害、病虫害等造成的损失，按实际损失赔付

五、其他专项补贴
• 粮食烘干设施建设补贴：设备投资额的50%，最高50万元
• 冷链物流设施建设补贴：投资额的30%，最高100万元
• 高标准农田建设补贴：每亩补助1500-2000元

【申请条件】
1. 具有广东省农村户籍或在当地从事农业生产经营满1年以上
2. 拥有合法的土地承包经营权证、流转合同或土地入股协议
3. 按照规定进行农业生产经营活动，不撂荒耕地
4. 无骗取套取农业补贴资金的违法违规记录
5. 同一地块不得重复申领同类补贴

【申请流程】
1. 农户向村委会提交《农业补贴申请表》及相关材料
2. 村委会汇总公示7天，无异议后上报乡镇
3. 乡镇农业服务中心初审、实地核查
4. 县级农业农村局审核、抽查
5. 财政部门复核后拨付资金
6. 补贴资金通过"一卡通"直接发放到户

【所需材料清单】
• 本人身份证原件及复印件（正反面）
• 户口簿原件及复印件
• 土地承包经营权证或土地流转合同
• 本人银行卡或存折复印件（需为本人名下）
• 种植面积申报表（村委会领取）
• 农机购置发票及合格证（申请农机补贴时提供）
• 农业保险保单复印件（申请保险补贴时提供）

【办理时限】
• 一般补贴：受理后30个工作日内完成审核
• 农机补贴：购买后60日内提交申请
• 保险理赔：报案后15个工作日内完成定损

【常见问题解答】
问：流转的土地能申请补贴吗？
答：可以，需提供规范的土地流转合同，且流转期限在3年以上。
问：补贴资金什么时候到账？
答：一般在审核通过后30个工作日内发放到银行卡。
问：在外务工的农民能申请吗？
答：可以，只要拥有耕地承包权且未撂荒即可申请耕地地力保护补贴。

【咨询渠道】
• 广东省农业农村厅：020-37288100
• 全国三农服务热线：12316
• 粤省事小程序：搜索"农业补贴"在线查询""", "补贴", "2026-06-01"),
    ("农村电商扶持政策", """【政策概述】
广东省大力推进"互联网+农业"发展，对从事农产品电商的个人和企业提供创业补贴、培训补贴、物流补贴等多项扶持政策。目标到2026年底，全省农村网络零售额突破3000亿元，培育100个电商示范村。

【扶持项目明细】
一、创业启动补贴
• 补贴对象：首次从事农产品电商创业的个人或团队
• 补贴条件：在主流平台开设店铺并正常经营满6个月
• 补贴标准：一次性创业补贴10000元
• 额外奖励：年销售额达50万元，额外奖励5000元
• 申请时限：店铺开业后6-12个月内申请

二、电商培训补贴
• 培训内容：店铺运营、直播带货、短视频拍摄、摄影美工、客服管理
• 培训时长：初级班5天、进阶班10天、高级班15天
• 补贴标准：培训费用全免，由政府全额补贴
• 生活补助：参加培训期间每天补助50元生活费
• 证书补贴：取得电商相关职业技能证书，奖励500-1000元

三、物流仓储补贴
• 快递补贴：农产品上行快递费用补贴30%，每户每年最高5000元
• 冷链补贴：建设冷库设施投资额的30%补贴，最高50万元
• 仓储补贴：入驻电商产业园，首年租金减免50%
• 包装补贴：农产品包装设计费用补贴50%，最高3000元

四、平台入驻补贴
• 淘宝/天猫：入驻保证金补贴50%，最高1万元
• 拼多多：入驻费用补贴50%
• 抖音电商：开通小店技术费补贴
• 京东：入驻技术服务费补贴50%

五、品牌建设补贴
• 商标注册：农产品商标注册费用全额补贴
• 品牌设计：品牌VI设计费用补贴50%，最高5000元
• 直播基地：建设村级直播基地补贴投资额的30%，最高20万元

【扶持对象】
1. 返乡创业大学生（毕业5年内）
2. 农村致富带头人和新型职业农民
3. 农民专业合作社和家庭农场
4. 农业产业化龙头企业
5. 农村青年创业者（18-45周岁）
6. 脱贫户和边缘易致贫户（优先扶持）

【申请流程】
1. 到当地商务局或人社局领取申请表
2. 提交创业计划书和身份证明材料
3. 参加政府组织的免费电商培训（5-15天）
4. 在主流电商平台开设店铺并上架农产品
5. 正常经营满6个月后提交补贴申请
6. 主管部门审核、实地核查
7. 公示无异议后拨付补贴资金

【所需材料】
• 个人身份证、户口簿复印件
• 营业执照复印件（个体工商户）
• 电商平台店铺截图和后台数据
• 银行账户信息
• 创业计划书
• 培训合格证书
• 农产品来源证明（收购合同或自产证明）

【成功案例】
案例一：梅州某村电商转型
梅州丰顺县某村通过电商培训，30户农户开设网店销售客家特产，年销售额突破500万元，户均增收3万元。其中村民张某从零起步，现月销售额超过10万元。

案例二：茂名荔枝直播带货
茂名高州市某荔枝合作社组建直播团队，通过抖音直播销售荔枝，旺季日销5000斤，带动周边50户果农增收。

案例三：潮州手工艺人数字化传承
潮州某手工艺人通过短视频展示非遗技艺，粉丝超过50万，通过电商销售手工艺品月入2万+。

【主要电商平台入驻指南】
• 淘宝店铺：注册支付宝→实名认证→开设店铺→缴纳保证金（1000元起）
• 拼多多店铺：下载拼多多商家版→注册→上传资质→缴纳保证金（2000元起）
• 抖音小店：注册抖音账号→开通小店→上传资质→缴纳保证金（5000元起）

【咨询渠道】
• 广东省商务厅：020-38819900
• 广东省农村电商协会：020-87654321
• 各地级市商务局电商科""", "电商", "2026-05-15"),
    ("非遗传承人认定办法", """【政策概述】
非物质文化遗产代表性传承人是非遗保护传承的核心力量。广东省目前共有国家级非遗传承人132名、省级传承人729名。对认定的传承人给予传习补助、展示平台、培训机会和荣誉激励等多方面支持。

【非遗项目类别】
一、传统技艺类
• 广绣：广州刺绣，以金银线绣著称
• 广州牙雕：象牙雕刻技艺
• 石湾陶塑：佛山石湾公仔制作技艺
• 潮州木雕：潮汕地区金漆木雕
• 阳江风筝：阳江传统风筝制作技艺
• 端砚制作：肇庆端砚雕刻技艺

二、传统美术类
• 广东剪纸：佛山剪纸、潮阳剪纸
• 粤绣：潮绣、广绣
• 潮州大吴泥塑

三、传统戏剧类
• 粤剧：广东最大的地方戏曲剧种
• 潮剧：潮汕地区传统戏曲
• 雷剧：雷州半岛传统戏曲
• 客家山歌剧

四、传统音乐舞蹈类
• 广东音乐：丝竹乐种
• 潮州音乐：潮汕传统音乐
• 英歌舞：潮汕地区传统舞蹈

【认定条件】
1. 长期从事该项非遗传承实践，连续传承时间不少于10年
2. 熟练掌握所传承项目的技艺，在同领域内具有代表性和影响力
3. 积极开展传承活动，已培养后继人才不少于3人
4. 居住在广东省境内，身体健康能正常开展传承活动
5. 遵纪守法，无违法犯罪记录

【支持措施】
一、经费支持
• 国家级传承人：每年传习补助20000元
• 省级传承人：每年传习补助10000元
• 市级传承人：每年传习补助5000元（各地市标准略有差异）
• 传习所建设补贴：最高10万元

二、展示平台
• 优先推荐参加国内外非遗展览和交流活动
• 在省非遗展示馆设专区展示传承人作品
• 支持传承人开设个人作品展
• 协助传承人参加文博会、旅博会等展会

三、培训研修
• 免费参加文化部、省文化厅组织的非遗传承人群研修研习
• 资助传承人到高等院校进修学习
• 提供技艺交流和合作创作机会

四、宣传推广
• 通过省级媒体平台宣传传承人及其技艺
• 制作传承人口述纪录片
• 在省非遗官网和公众号展示传承人信息
• 协助传承人开设社交媒体账号

五、其他优惠
• 传承人子女就读相关专业可优先录取
• 传承人可优先申请文化产业发展专项资金
• 享受公共文化设施免费使用权益

【申报材料】
1. 《广东省非物质文化遗产代表性传承人申报表》（一式三份）
2. 申请人身份证、户口簿复印件
3. 掌握技艺的证明材料：作品照片（不少于10张）、获奖证书、媒体报道等
4. 传承谱系说明：师承关系、学习经历
5. 授徒传艺情况说明：徒弟名单、传习活动记录
6. 当地文化和旅游部门的推荐意见
7. 项目保护单位的推荐意见
8. 其他有助于说明申请人代表性的材料

【认定流程】
1. 个人申请或单位推荐（每年3-4月）
2. 县级文化和旅游部门初审、实地考察（30个工作日）
3. 市级文化和旅游部门复审、组织专家评议（20个工作日）
4. 省级专家评审委员会评审、投票表决（15个工作日）
5. 社会公示（20个工作日），接受公众监督
6. 省文化和旅游厅审批、正式公布认定结果
7. 颁发传承人证书和传习补助

【传承人义务】
1. 制定并执行传承计划，每年开展传习活动不少于4次
2. 培养后继人才，每人每年带徒不少于2人
3. 参加非遗展示、宣传和交流活动
4. 配合文化和旅游部门做好非遗记录和档案建设
5. 接受年度考核评估

【年度考核标准】
• 优秀：传习活动6次以上，带徒3人以上，有创新成果
• 合格：传习活动4次以上，带徒2人以上
• 不合格：未完成传习任务，将被约谈整改，连续两年不合格取消资格

【咨询渠道】
• 广东省文化和旅游厅：020-37803300
• 广东省非物质文化遗产保护中心：020-87650813
• 各地级市文化和旅游局非遗科""", "非遗", "2026-05-01"),
    ("农业技术培训补贴", """【政策概述】
广东省实施高素质农民培育计划，2026年计划培训新型职业农民10万人次，对参加农业技术培训的农民给予全额免费培训、生活补助、交通补贴等支持。培训涵盖种植技术、养殖技术、电商技能、农机操作、经营管理五大板块。

【培训课程详情】
一、种植技术类
• 岭南水果栽培：荔枝、龙眼、香蕉、柑橘、菠萝等品种选择、水肥管理、整形修剪、花果管理
• 蔬菜种植：叶菜、瓜果、根茎类蔬菜的设施栽培和露地栽培技术
• 水稻种植：优质稻品种选择、育秧技术、田间管理、病虫害防治
• 茶叶种植：茶树栽培、茶园管理、茶叶采摘技术
• 中药材种植：广藿香、巴戟天、何首乌等南药种植技术

二、养殖技术类
• 水产养殖：对虾、鲈鱼、生鱼、加州鲈等品种养殖技术
• 畜禽养殖：生猪、家禽养殖管理和疫病防控
• 蜜蜂养殖：中蜂活框饲养技术、蜂蜜采收加工

三、电商直播类
• 电商基础：淘宝、拼多多、抖音小店开店运营全流程
• 直播带货：直播话术、互动技巧、促单方法
• 短视频制作：拍摄技巧、剪辑软件使用、内容策划
• 摄影美工：产品拍摄、图片处理、详情页设计
• 客服管理：售前咨询、售后处理、客户维护

四、农机操作类
• 无人机植保：大疆T40/T50操作培训、航线规划、飞防施药
• 智能农机：无人驾驶拖拉机、自动插秧机操作
• 农机维修：常用农机日常维护和简单故障排除
• 农机安全：农机安全操作规范和事故预防

五、经营管理类
• 合作社管理：合作社组建、运营、财务管理
• 家庭农场：家庭农场认定、经营策略、品牌建设
• 农产品营销：市场分析、定价策略、渠道拓展
• 农业品牌：品牌定位、包装设计、品牌推广

【补贴标准明细】
• 培训费用：全额免费，由政府财政承担
• 生活补助：培训期间每天50元，按实际天数发放
• 交通补贴：按实际费用报销，市内最高50元/天，跨市最高200元/次
• 住宿补贴：跨市培训提供免费住宿
• 证书奖励：取得农业类职业技能证书奖励500元，高级证书奖励1000元
• 创业扶持：培训后创业的优先提供贷款贴息支持

【培训安排】
• 培训时长：初级班7天、中级班10天、高级班15天
• 培训地点：各地级市农业培训中心、农业院校实训基地
• 培训方式：理论授课（40%）+ 实操练习（40%）+ 现场观摩（20%）
• 培训规模：每期30-50人小班教学
• 培训频次：每月至少开设2期，全年滚动开班

【报名条件】
1. 年龄16-60周岁，身体健康
2. 广东省户籍或在粤从事农业生产经营
3. 有意愿从事农业生产经营或已在从事农业
4. 脱贫户、返乡大学生、退伍军人优先录取

【报名方式】
1. 现场报名：到当地农业农村局或乡镇农业服务中心填写报名表
2. 线上报名：下载"粤农通"APP，搜索"农民培训"在线报名
3. 电话报名：拨打12316三农服务热线
4. 微信报名：关注"广东农业农村"公众号，点击"培训报名"

【报名材料】
• 本人身份证复印件
• 近期一寸照片2张
• 学历证书复印件（如有）
• 从事农业的证明材料（如有）

【培训机构名录】
• 广东省农业科学院培训中心
• 华南农业大学继续教育学院
• 仲恺农业工程学院培训中心
• 各地级市农业学校
• 各县级农业广播电视学校

【考核认证】
• 培训结束参加结业考试，合格者颁发培训结业证书
• 可自愿报名参加职业技能等级认定
• 获得证书者享受证书奖励补贴

【咨询渠道】
• 广东省农业农村厅科教处：020-37288230
• 全国三农服务热线：12316
• "粤农通"APP在线客服""", "培训", "2026-04-20"),
    ("农产品质量安全认证", """【政策概述】
广东省鼓励农产品生产经营主体开展绿色食品、有机农产品、地理标志农产品认证（简称"两品一标"），提升农产品附加值和市场竞争力。2026年全省有效期内"两品一标"产品超过3000个，位居全国前列。

【认证类型详解】
一、绿色食品认证
• 定义：产自优良生态环境，按照绿色食品标准生产，实行全程质量控制
• 分类：A级绿色食品（限量使用限定化学合成物质）和AA级绿色食品（不使用化学合成物质）
• 标志有效期：3年
• 适用产品：蔬菜、水果、粮食、畜禽、水产、茶叶等
• 产品要求：产地环境符合NY/T391标准，生产过程符合NY/T392标准

二、有机农产品认证
• 定义：按照有机农业标准生产，不使用化学合成的农药、化肥、生长调节剂
• 标志有效期：1年（需每年重新认证）
• 适用产品：蔬菜、水果、粮食、茶叶、中药材等
• 转换期：一年生作物24个月，多年生作物36个月
• 产品要求：产地环境未受污染，3年内未使用禁用物质

三、地理标志农产品登记
• 定义：产自特定地域，所具有的质量、声誉本质上取决于该产地的自然因素和人文因素
• 标志有效期：长期有效
• 适用产品：具有地域特色的农产品
• 广东主要地标产品：增城荔枝、从化荔枝、高州香蕉、德庆贡柑、英德红茶等

【奖补政策明细】
• 绿色食品认证：每个产品奖补30000元
• 有机农产品认证：每个产品奖补50000元
• 地理标志登记：每个产品奖补100000元
• 续展认证：绿色食品续展每个奖补10000元
• 产品检测费：首次认证检测费用全额补贴
• 标志使用费：首年标志使用费全额补贴

【认证流程详解】
一、绿色食品认证流程
1. 申请人向省绿色食品发展中心提交申请
2. 省中心对材料进行文审（5个工作日）
3. 检查员现场检查（产地环境、生产过程、质量控制）
4. 产品抽样送检（指定检测机构）
5. 中国绿色食品发展中心评审
6. 颁发绿色食品证书
7. 全程约需3-6个月

二、有机农产品认证流程
1. 申请人向认证机构提交申请
2. 认证机构审核申请材料
3. 检查员现场检查（至少1次/年）
4. 产品抽样检测（400+项农残检测）
5. 认证决定
6. 颁发有机产品证书
7. 全程约需6-12个月

三、地理标志登记流程
1. 县级以上人民政府农业主管部门提出申请
2. 省级农业主管部门初审
3. 农业农村部农产品质量安全中心审查
4. 专家评审
5. 公示（60天）
6. 登记发证

【申请条件】
一、基本条件
1. 具有合法的生产经营资质（营业执照）
2. 产品符合相关标准要求
3. 建立完善的质量管理制度和追溯体系
4. 有稳定的生产基地和加工场所

二、绿色食品专项条件
• 产地环境符合绿色食品产地环境质量标准
• 生产过程符合绿色食品生产操作规程
• 产品质量符合绿色食品产品标准
• 包装贮运符合绿色食品包装贮运标准

三、有机产品专项条件
• 产地环境未受污染
• 转换期内不使用化学合成物质
• 建立完整的有机生产管理体系
• 有内部检查员

【所需申请材料】
• 认证申请书
• 营业执照复印件
• 产品执行标准
• 生产操作规程
• 质量管理制度
• 产地环境检测报告
• 产品检测报告
• 生产基地位置图和地块图
• 包装标签设计样张

【认证后管理】
• 绿色食品：每年至少1次年度检查，3年到期续展
• 有机产品：每年1次跟踪检查，1年到期重新认证
• 地理标志：定期抽检产品质量
• 不合格处理：暂停或撤销标志使用权

【市场价值提升】
• 绿色食品：价格比普通产品高20-50%
• 有机产品：价格比普通产品高50-200%
• 地理标志：品牌溢价30-100%
• 电商优势：认证产品在各大平台有流量扶持

【广东特色认证产品】
• 增城荔枝（地理标志）：挂绿、桂味、糯米糍
• 从化荔枝（地理标志）：井岗红糯、流溪桂味
• 高州香蕉（地理标志）：品质优良、口感香甜
• 德庆贡柑（地理标志）：果色金黄、清甜蜜味
• 英德红茶（地理标志）：英红九号、高香型红茶
• 新会陈皮（地理标志）：三年以上陈化

【咨询渠道】
• 中国绿色食品发展中心广州办公室：020-84229060
• 广东省农产品质量安全中心：020-37288456
• 各地级市农业农村局质监科
• 中国绿色食品网：www.greenfood.org.cn""", "认证", "2026-04-01")
]

# 岗位数据常量，供 _seed_data 和 _seed_jobs 共用
JOBS_DATA = [
    ("荔枝种植技术员", "茂名高州农业合作社", "5000-8000元/月", '["荔枝种植证书","2年以上经验"]',
     "负责荔枝种植技术指导和病虫害防治，指导农户科学施肥、修剪整形、花果管理。要求熟悉岭南水果栽培技术，有荔枝种植经验优先。",
     "茂名", "农业技术", "全职", "中专", "2年以上", "50-200人", "农业", "2026-06-18"),
    ("电商直播运营", "广州鲜果汇电商有限公司", "6000-10000元/月", '["电商运营师证书","直播经验优先"]',
     "负责农产品直播带货和短视频内容运营，策划直播活动，撰写直播话术，分析直播数据。有抖音/快手直播经验优先。",
     "广州", "电商运营", "全职", "大专", "1年以上", "20-50人", "电子商务", "2026-06-17"),
    ("农产品质检员", "深圳绿源食品有限公司", "5500-7500元/月", '["食品检验相关证书","大专以上学历"]',
     "负责农产品质量检测、抽样检验、出具检测报告，协助建立质量追溯体系。食品科学、农学相关专业优先。",
     "深圳", "农业技术", "全职", "大专", "不限", "100-500人", "食品加工", "2026-06-15"),
    ("广绣工艺师", "佛山顺德非遗工作室", "4500-8000元/月", '["手工技能证书","3年以上经验"]',
     "从事广绣作品的设计与绣制，参与非遗传承活动，指导学员基础针法。要求熟练掌握直针、扭针、长短针等广绣针法。",
     "佛山", "手工工艺", "全职", "不限", "3年以上", "10人以下", "文化创意", "2026-06-14"),
    ("乡村旅游导游", "梅州客天下旅游公司", "4000-6000元/月", '["导游证优先","普通话流利"]',
     "负责乡村旅游线路讲解、游客接待、活动策划组织。了解客家文化，会客家话优先，有导游经验者优先。",
     "梅州", "乡村旅游", "全职", "中专", "不限", "50-200人", "旅游服务", "2026-06-13"),
    ("农产品物流专员", "湛江湛农物流有限公司", "5000-7000元/月", '["物流管理经验","有驾照优先"]',
     "负责农产品仓储管理、物流调度、冷链运输协调，确保果蔬新鲜送达。有冷链物流经验优先。",
     "湛江", "物流仓储", "全职", "不限", "1年以上", "50-200人", "物流运输", "2026-06-12"),
    ("短视频内容编辑", "汕头潮创传媒有限公司", "6000-9000元/月", '["短视频运营经验","熟悉剪辑软件"]',
     "负责农产品和乡村文化短视频的选题策划、脚本撰写、拍摄指导和后期剪辑。熟悉抖音、快手平台规则优先。",
     "汕头", "电商运营", "全职", "大专", "1年以上", "20-50人", "传媒广告", "2026-06-10"),
    ("农业技术推广员", "惠州农业科学研究院", "5500-8500元/月", '["农学相关专业","本科以上学历"]',
     "负责农业新技术的试验示范和推广应用，组织农民培训，编写技术资料。农学、植保、园艺相关专业，有基层工作经验优先。",
     "惠州", "农业技术", "全职", "本科", "2年以上", "100-500人", "科研机构", "2026-06-08"),
    ("茶艺师", "潮州凤凰茶业有限公司", "4000-6500元/月", '["茶艺师证优先","形象气质佳"]',
     "负责茶叶品鉴、茶艺表演、客户接待和茶叶销售。了解潮汕功夫茶文化，有茶艺师资格证优先。",
     "潮州", "手工工艺", "全职", "不限", "不限", "50-200人", "农业", "2026-06-06"),
    ("水产养殖技术员", "阳江海纳水产有限公司", "5000-7500元/月", '["水产养殖经验","中专以上学历"]',
     "负责水产养殖场日常管理，包括水质监测、饲料投喂、病害防治、设备维护。有对虾或鱼类养殖经验优先。",
     "阳江", "农业技术", "全职", "中专", "1年以上", "50-200人", "水产养殖", "2026-06-05"),
    # === 以下为新增 20 条 ===
    ("龙眼种植管理员", "茂名信宜果业公司", "4500-7000元/月", '["农业种植经验","吃苦耐劳"]',
     "负责龙眼果园日常管理，包括水肥管理、病虫害防治、采收组织。有龙眼或荔枝种植经验优先，提供住宿。",
     "茂名", "农业技术", "全职", "中专", "1年以上", "20-50人", "农业", "2026-06-18"),
    ("直播带货主播", "广州花城电商基地", "8000-15000元/月", '["直播经验","形象气质佳"]',
     "负责农产品直播间带货，与观众互动，促成订单转化。要求口齿伶俐，有直播经验，能接受排班制度。",
     "广州", "电商运营", "全职", "大专", "1年以上", "50-200人", "电子商务", "2026-06-17"),
    ("水产饲料销售", "珠海海大饲料有限公司", "6000-12000元/月", '["销售经验","有驾照"]',
     "负责水产饲料产品的市场开拓和客户维护，完成销售目标。有水产养殖或饲料销售经验优先，底薪+提成。",
     "珠海", "农业技术", "全职", "大专", "2年以上", "100-500人", "饲料加工", "2026-06-17"),
    ("潮汕木雕师傅", "汕头金漆木雕工艺厂", "5000-9000元/月", '["木雕经验3年以上","手工技能证书"]',
     "从事潮汕传统金漆木雕的设计与制作，参与建筑装饰和工艺品雕刻。要求有扎实的木雕基本功，能独立完成作品。",
     "汕头", "手工工艺", "全职", "不限", "3年以上", "10-50人", "文化创意", "2026-06-16"),
    ("农业无人机飞手", "梅州丰顺农业科技公司", "5500-8000元/月", '["无人机驾照","植保经验"]',
     "操作植保无人机进行农药喷洒、施肥作业，负责航线规划和设备维护。有大疆T40/T50操作经验优先。",
     "梅州", "农业技术", "全职", "中专", "1年以上", "10-50人", "农业科技", "2026-06-16"),
    ("电商客服主管", "东莞优品电商有限公司", "5000-7500元/月", '["客服管理经验","熟悉电商平台"]',
     "负责客服团队管理，制定服务规范，处理疑难客诉，分析客服数据。有淘宝/拼多多客服管理经验优先。",
     "东莞", "电商运营", "全职", "大专", "2年以上", "50-200人", "电子商务", "2026-06-15"),
    ("乡村旅游策划", "肇庆星湖旅游发展公司", "5000-8000元/月", '["旅游策划经验","创意能力"]',
     "负责乡村旅游线路策划、活动方案设计、民宿运营指导。有文旅项目策划经验优先，了解肇庆本地文化。",
     "肇庆", "乡村旅游", "全职", "大专", "2年以上", "50-200人", "旅游服务", "2026-06-14"),
    ("食品加工技术员", "江门新会陈皮食品公司", "4500-6500元/月", '["食品加工经验","健康证"]',
     "负责陈皮食品的加工生产，包括原料处理、加工操作、质量监控。有食品加工经验优先，提供岗前培训。",
     "江门", "农业技术", "全职", "中专", "不限", "100-500人", "食品加工", "2026-06-14"),
    ("水产养殖技术顾问", "中山万通水产有限公司", "7000-10000元/月", '["水产养殖5年以上","技术指导能力"]',
     "为合作养殖户提供技术指导，解决养殖过程中的水质、病害问题。要求有丰富的水产养殖实战经验，能独立排查问题。",
     "中山", "农业技术", "全职", "大专", "5年以上", "50-200人", "水产养殖", "2026-06-13"),
    ("农产品电商运营", "韶关丹霞农产品公司", "5000-8000元/月", '["电商运营经验","熟悉抖音小店"]',
     "负责公司农产品在抖音、淘宝等平台的店铺运营，包括产品上架、活动策划、数据分析。有农产品电商经验优先。",
     "韶关", "电商运营", "全职", "大专", "1年以上", "10-50人", "电子商务", "2026-06-13"),
    ("石湾陶艺学徒", "佛山石湾陶艺研究所", "3500-5000元/月", '["对手工艺术有兴趣","能吃苦"]',
     "跟随陶艺大师学习石湾陶塑技艺，从揉泥、拉坯到上釉、烧制全流程学习。提供免费培训，表现优秀可转正。",
     "佛山", "手工工艺", "全职", "不限", "不限", "10-50人", "文化创意", "2026-06-12"),
    ("冷链物流司机", "茂名顺丰冷运有限公司", "6000-9000元/月", '["B2驾照","冷链运输经验"]',
     "负责冷链车辆驾驶，将生鲜农产品从产地运输至分拨中心。要求有B2驾照，熟悉广东省内路线，能接受夜班。",
     "茂名", "物流仓储", "全职", "不限", "2年以上", "100-500人", "物流运输", "2026-06-12"),
    ("民宿管家", "惠州龙门南昆山民宿", "4000-6000元/月", '["服务行业经验","会做饭优先"]',
     "负责民宿日常运营管理，包括客房管理、客人接待、餐饮服务、活动安排。有酒店或民宿管理经验优先，包吃住。",
     "惠州", "乡村旅游", "全职", "中专", "1年以上", "10人以下", "旅游服务", "2026-06-11"),
    ("农业会计", "湛江国兴农业发展公司", "4500-6500元/月", '["会计证","农业企业经验"]',
     "负责公司财务核算、税务申报、成本分析、财务报表编制。有农业企业会计经验优先，熟悉农业补贴核算。",
     "湛江", "农业技术", "全职", "大专", "2年以上", "50-200人", "农业", "2026-06-11"),
    ("短视频拍摄", "潮州潮文化传播有限公司", "5000-8000元/月", '["摄影摄像经验","会PR/FCP"]',
     "负责潮州非遗文化、美食、风景类短视频的拍摄和后期制作。要求有审美能力，能独立完成拍摄任务。",
     "潮州", "电商运营", "全职", "大专", "1年以上", "10-50人", "传媒广告", "2026-06-10"),
    ("龙眼干加工技师", "揭阳惠来龙眼加工厂", "4500-6500元/月", '["食品加工经验","了解烘干技术"]',
     "负责龙眼干的加工生产，包括原料筛选、烘干操作、品质分级、包装入库。有食品加工或烘干设备操作经验优先。",
     "揭阳", "农业技术", "全职", "中专", "不限", "50-200人", "食品加工", "2026-06-09"),
    ("园林绿化养护员", "东莞绿美园林有限公司", "4000-5500元/月", '["绿化养护经验","会使用园林机械"]',
     "负责城市绿化带、公园的苗木养护、修剪整形、病虫害防治、浇灌施肥。有园林绿化工作经验优先。",
     "东莞", "农业技术", "全职", "不限", "1年以上", "100-500人", "园林绿化", "2026-06-09"),
    ("电商美工设计", "广州谷雨电商有限公司", "5500-8000元/月", '["PS/AI熟练","电商设计经验"]',
     "负责农产品详情页设计、主图制作、活动海报设计、店铺装修。要求熟练使用Photoshop和Illustrator，有电商设计作品集。",
     "广州", "电商运营", "全职", "大专", "1年以上", "20-50人", "电子商务", "2026-06-08"),
    ("有机蔬菜种植员", "云浮新兴有机农场", "4000-6000元/月", '["有机种植经验","了解有机标准"]',
     "负责有机蔬菜的种植管理，包括育苗、定植、田间管理、采收。要求了解有机农业标准，不使用化学农药和化肥。",
     "云浮", "农业技术", "全职", "中专", "2年以上", "10-50人", "农业", "2026-06-07"),
    ("客家娘酒酿造师", "梅州客家娘酒酿造公司", "4500-7000元/月", '["酿造经验","了解传统工艺"]',
     "负责客家娘酒的传统酿造工艺操作，包括浸米、蒸饭、发酵、压榨、陈酿。有酿酒经验优先，可提供学徒培训。",
     "梅州", "手工工艺", "全职", "不限", "不限", "20-50人", "食品加工", "2026-06-06"),
]


def _seed_data(cursor):
    """填充种子数据"""
    # 用户
    admin_pw = hash_password('admin123')
    gov_pw = hash_password('123456')
    enterprise_pw = hash_password('123456')
    teacher_pw = hash_password('123456')
    student_pw = hash_password('123456')
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('admin_demo', admin_pw, '系统管理员', 'super_admin'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                   ('gov_demo', gov_pw, '王主任', 'government', '广东省农业农村厅'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role, company_name, region) VALUES (?, ?, ?, ?, ?, ?)",
                   ('enterprise_demo', enterprise_pw, '陈经理', 'enterprise', '广州鲜果汇电商有限公司', '广州'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('teacher_demo', teacher_pw, '张老师', 'teacher'))
    cursor.execute("INSERT INTO users (username, password_hash, name, role) VALUES (?, ?, ?, ?)",
                   ('student_demo', student_pw, '李同学', 'student'))

    # 积分
    cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                   ('student_demo', 1250, json.dumps([
                       {"action": "完成课程", "points": 50, "date": "2024-06-10"},
                       {"action": "通过考试", "points": 100, "date": "2024-06-08"}
                   ])))
    for uid in ('admin_demo', 'gov_demo', 'enterprise_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                       (uid, 0, '[]'))

    # 证书
    for uid in ('student_demo', 'teacher_demo'):
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress, date) VALUES (?, ?, ?, ?, ?)",
                       (uid, '荔枝种植技术员', 'earned', 100, '2024-05-20'))
        cursor.execute("INSERT INTO certificates (user_id, name, status, progress) VALUES (?, ?, ?, ?)",
                       (uid, '电商运营师', 'in_progress', 75))
        cursor.execute("INSERT INTO certificates (user_id, name, status) VALUES (?, ?, ?)",
                       (uid, '广绣工艺师', 'locked'))

    # 学员
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU001', 'student_demo', '张小明', '2024春季班', '荔枝种植', 85, 'active'))
    cursor.execute("INSERT INTO students (id, user_id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ('STU002', '', '李小红', '2024春季班', '电商运营', 62, 'active'))

    # 成功案例
    cases = [
        ("梅州某村电商转型之路", "梅州", "从传统农业到年销售额500万的电商村", '{"farmers":30,"income_growth":"300%"}'),
        ("潮州手工艺人数字化传承", "潮州", "非遗技艺通过短视频平台焕发新生", '{"fans":"50万+","income":"月入2万+"}'),
        ("韶关有机农场品牌打造", "韶关", "从无名小农场到区域知名品牌", '{"certification":"有机认证","channel":"线上线下结合"}')
    ]
    for title, loc, desc, stats in cases:
        cursor.execute("INSERT INTO success_cases (title, location, description, stats) VALUES (?, ?, ?, ?)",
                       (title, loc, desc, stats))

    # 政策（使用共用常量）
    for title, content, cat, date in POLICIES_DATA:
        cursor.execute("INSERT INTO policies (title, content, category, date) VALUES (?, ?, ?, ?)",
                       (title, content, cat, date))

    # 岗位（使用共用常量）
    for title, company, salary, reqs, desc, loc, cat, jtype, edu, exp, csize, industry, posted in JOBS_DATA:
        cursor.execute("INSERT INTO job_listings (title, company, salary, requirements, description, location, category, job_type, education, experience, company_size, industry, posted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (title, company, salary, reqs, desc, loc, cat, jtype, edu, exp, csize, industry, posted))

    # 政府政策（存到 government_policies 表）
    for title, content, cat, date in POLICIES_DATA:
        cursor.execute("INSERT INTO government_policies (title, content, category, author_id) VALUES (?, ?, ?, ?)",
                       (title, content, cat, 'gov_demo'))

    # 轮播图种子数据
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))

    # 系统公告种子数据
    cursor.execute("INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
                   ('欢迎使用粤乡智匠平台', '粤乡智匠是基于AI实训系统的农村本土人才赋能平台，致力于为广东乡村振兴培养实用型人才。', 1, 'admin_demo'))

    # 讨论区种子数据
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('荔枝种植经验交流', '各位种植荔枝的老乡，今年荔枝花期管理有什么心得？欢迎分享！', 'agriculture', 'student_demo'))
    cursor.execute("INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
                   ('电商直播新手问答', '刚开始做直播带货，想请教各位前辈有什么注意事项？', 'ecommerce', 'student_demo'))


def _seed_government_policies(cursor):
    """已有数据库时，补充政府政策数据"""
    for title, content, cat, date in POLICIES_DATA:
        cursor.execute("INSERT INTO government_policies (title, content, category, author_id) VALUES (?, ?, ?, ?)",
                       (title, content, cat, 'gov_demo'))


def _seed_carousels(cursor):
    """已有数据库时，补充默认轮播图"""
    carousels = [
        ("粤乡智匠正式上线", "https://placehold.co/1200x400/10b981/white?text=粤乡智匠", "", 0),
        ("乡村振兴政策解读", "https://placehold.co/1200x400/00b4d8/white?text=政策解读", "/resources", 1),
        ("非遗技艺传承计划", "https://placehold.co/1200x400/8b5cf6/white?text=非遗传承", "/crafts", 2),
    ]
    for title, img, link, sort in carousels:
        cursor.execute("INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
                       (title, img, link, sort))


def _refresh_policies(cursor):
    """刷新政策内容（已有数据时更新政策详情）"""
    # 更新旧 policies 表
    rows = cursor.execute("SELECT title, length(content) FROM policies").fetchall()
    need_refresh = any(r[1] < 200 for r in rows) if rows else True
    if not need_refresh:
        return
    cursor.execute("DELETE FROM policies")
    for title, content, cat, date in POLICIES_DATA:
        cursor.execute("INSERT INTO policies (title, content, category, date) VALUES (?, ?, ?, ?)",
                       (title, content, cat, date))
    # 同时更新 government_policies 表（如果为空）
    gp_count = cursor.execute("SELECT COUNT(*) FROM government_policies").fetchone()[0]
    if gp_count == 0:
        for title, content, cat, date in POLICIES_DATA:
            cursor.execute("INSERT INTO government_policies (title, content, category, author_id) VALUES (?, ?, ?, ?)",
                           (title, content, cat, 'gov_demo'))


def _ensure_demo_accounts(cursor):
    """已有数据库时，补充缺少的新角色演示账户"""
    demo_accounts = [
        ('admin_demo', 'admin123', '系统管理员', 'super_admin', ''),
        ('gov_demo', '123456', '王主任', 'government', '广东省农业农村厅'),
        ('enterprise_demo', '123456', '陈经理', 'enterprise', '广州'),
    ]
    for username, password, name, role, region in demo_accounts:
        existing = cursor.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not existing:
            pw_hash = hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash, name, role, region) VALUES (?, ?, ?, ?, ?)",
                (username, pw_hash, name, role, region))
            cursor.execute("INSERT INTO points (user_id, balance, history) VALUES (?, 0, '[]')", (username,))


def _refresh_policies_OLD():
    pass


def _seed_jobs(cursor):
    """补充岗位种子数据（已有用户但岗位不足时调用）"""
    # 清除旧数据后重新插入
    cursor.execute("DELETE FROM job_listings")
    cursor.execute("DELETE FROM job_applications")
    cursor.execute("DELETE FROM saved_jobs")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='job_listings'")
    for title, company, salary, reqs, desc, loc, cat, jtype, edu, exp, csize, industry, posted in JOBS_DATA:
        cursor.execute("INSERT INTO job_listings (title, company, salary, requirements, description, location, category, job_type, education, experience, company_size, industry, posted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (title, company, salary, reqs, desc, loc, cat, jtype, edu, exp, csize, industry, posted))


# ==================== 认证 ====================

def authenticate_user(username, password):
    """验证用户登录"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and verify_password(user['password_hash'], password):
        return dict(user)
    return None


def create_session(user_id):
    """创建会话"""
    session_id = str(uuid.uuid4())
    now = time.time()
    expires = now + 86400  # 24小时
    conn = get_connection()
    conn.execute("INSERT INTO user_sessions (session_id, user_id, login_time, expires_at) VALUES (?, ?, ?, ?)",
                 (session_id, user_id, now, expires))
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id):
    """获取会话"""
    conn = get_connection()
    session = conn.execute("SELECT * FROM user_sessions WHERE session_id = ?", (session_id,)).fetchone()
    if session and time.time() < session['expires_at']:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (session['user_id'],)).fetchone()
        conn.close()
        if user:
            return {
                'user_id': user['username'],
                'name': user['name'],
                'role': user['role']
            }
    conn.close()
    return None


def delete_session(session_id):
    """删除会话"""
    conn = get_connection()
    conn.execute("DELETE FROM user_sessions WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()


# ==================== 用户资料 ====================

def get_user_by_id(user_id):
    """根据用户ID获取完整用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT id, username, name, role, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username):
    """根据用户名获取用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT id, username, name, role, email, created_at FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_profile(user_id, name=None, email=None):
    """更新用户资料（姓名、邮箱）"""
    conn = get_connection()
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if email is not None:
        updates.append("email = ?")
        params.append(email)
    if not updates:
        conn.close()
        return False
    params.append(user_id)
    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    conn.close()
    return True


def change_password(user_id, old_password, new_password):
    """修改密码，需验证旧密码"""
    conn = get_connection()
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return False, "用户不存在"
    if not verify_password(row['password_hash'], old_password):
        conn.close()
        return False, "旧密码错误"
    new_hash = hash_password(new_password)
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    conn.close()
    return True, "密码修改成功"


# ==================== 积分 ====================

def get_points(user_id):
    """获取积分"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM points WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return {'balance': row['balance'], 'history': json.loads(row['history'])}
    return {'balance': 0, 'history': []}


def update_points(user_id, delta, action="操作"):
    """更新积分"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM points WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        conn.execute("INSERT INTO points (user_id, balance, history) VALUES (?, ?, ?)",
                     (user_id, max(0, delta), json.dumps([{"action": action, "points": delta, "date": datetime.now().strftime('%Y-%m-%d')}])))
        conn.commit()
        conn.close()
        return max(0, delta)

    new_balance = row['balance'] + delta
    if new_balance < 0:
        conn.close()
        return -1  # 余额不足

    history = json.loads(row['history'])
    history.append({"action": action, "points": delta, "date": datetime.now().strftime('%Y-%m-%d')})
    conn.execute("UPDATE points SET balance = ?, history = ? WHERE user_id = ?",
                 (new_balance, json.dumps(history), user_id))
    conn.commit()
    conn.close()
    return new_balance


# ==================== 证书 ====================

def get_certificates(user_id):
    """获取用户证书"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM certificates WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 学员 ====================

def get_students(search=None):
    """获取学员列表"""
    conn = get_connection()
    if search:
        rows = conn.execute("SELECT * FROM students WHERE name LIKE ? OR id LIKE ? OR direction LIKE ?",
                            (f'%{search}%', f'%{search}%', f'%{search}%')).fetchall()
    else:
        rows = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student(student_id):
    """获取单个学员"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_student(name, class_name, direction):
    """添加学员"""
    conn = get_connection()
    # 生成ID
    last = conn.execute("SELECT id FROM students ORDER BY id DESC LIMIT 1").fetchone()
    if last:
        num = int(last['id'].replace('STU', '')) + 1
    else:
        num = 1
    sid = f"STU{num:03d}"
    conn.execute("INSERT INTO students (id, name, class_name, direction, progress, status) VALUES (?, ?, ?, ?, ?, ?)",
                 (sid, name, class_name, direction, 0, 'active'))
    conn.commit()
    conn.close()
    return sid


def update_student(student_id, name=None, class_name=None, direction=None, progress=None, status=None):
    """编辑学员信息"""
    conn = get_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return False
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if class_name is not None:
        updates.append("class_name = ?")
        params.append(class_name)
    if direction is not None:
        updates.append("direction = ?")
        params.append(direction)
    if progress is not None:
        updates.append("progress = ?")
        params.append(int(progress))
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if updates:
        params.append(student_id)
        conn.execute(f"UPDATE students SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()
    return True


def delete_student(student_id):
    """删除学员"""
    conn = get_connection()
    result = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


# ==================== 通知公告 ====================

def create_announcement(title, content, category='通知', pinned=0):
    conn = get_connection()
    cursor = conn.execute("INSERT INTO announcements (title, content, category, pinned) VALUES (?, ?, ?, ?)",
                          (title, content, category, pinned))
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid

def get_announcements(limit=50):
    conn = get_connection()
    rows = conn.execute("SELECT * FROM announcements ORDER BY pinned DESC, created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_announcement(ann_id):
    conn = get_connection()
    result = conn.execute("DELETE FROM announcements WHERE id = ?", (ann_id,))
    conn.commit()
    deleted = result.rowcount > 0
    conn.close()
    return deleted


# ==================== 作业管理 ====================

def create_assignment(title, description='', direction='', deadline='', total_score=100):
    conn = get_connection()
    cursor = conn.execute("INSERT INTO assignments (title, description, direction, deadline, total_score) VALUES (?, ?, ?, ?, ?)",
                          (title, description, direction, deadline, total_score))
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid

def get_assignments():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM assignments ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        # 统计提交数
        d['submission_count'] = conn.execute if False else 0
        result.append(d)
    # 需要重新连接来统计
    conn2 = get_connection()
    for a in result:
        a['submission_count'] = conn2.execute(
            "SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ?", (a['id'],)
        ).fetchone()[0]
        a['graded_count'] = conn2.execute(
            "SELECT COUNT(*) FROM assignment_submissions WHERE assignment_id = ? AND status = 'graded'", (a['id'],)
        ).fetchone()[0]
    conn2.close()
    return result

def get_assignment(assignment_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
    if not row:
        conn.close()
        return None
    a = dict(row)
    a['submissions'] = [dict(r) for r in conn.execute(
        "SELECT s.*, st.name as student_name FROM assignment_submissions s LEFT JOIN students st ON s.student_id = st.id WHERE s.assignment_id = ? ORDER BY s.submitted_at DESC",
        (assignment_id,)
    ).fetchall()]
    conn.close()
    return a

def submit_assignment(assignment_id, student_id, content=''):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO assignment_submissions (assignment_id, student_id, content, status) VALUES (?, ?, ?, 'submitted')",
                     (assignment_id, student_id, content))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def grade_submission(submission_id, score, feedback=''):
    conn = get_connection()
    conn.execute("UPDATE assignment_submissions SET score = ?, feedback = ?, status = 'graded', graded_at = datetime('now','localtime') WHERE id = ?",
                 (score, feedback, submission_id))
    conn.commit()
    updated = conn.execute("SELECT changes()").fetchone()[0] > 0
    conn.close()
    return updated

def get_student_submissions(student_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.*, a.title as assignment_title, a.total_score FROM assignment_submissions s LEFT JOIN assignments a ON s.assignment_id = a.id WHERE s.student_id = ? ORDER BY s.submitted_at DESC",
        (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 签到考勤 ====================

def create_attendance(title='日常签到'):
    conn = get_connection()
    cursor = conn.execute("INSERT INTO attendances (title, status) VALUES (?, 'open')", (title,))
    conn.commit()
    aid = cursor.lastrowid
    conn.close()
    return aid

def close_attendance(att_id):
    conn = get_connection()
    conn.execute("UPDATE attendances SET status = 'closed', closed_at = datetime('now','localtime') WHERE id = ?", (att_id,))
    conn.commit()
    conn.close()

def get_attendances():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM attendances ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['total_checked'] = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE attendance_id = ?", (d['id'],)
        ).fetchone()[0]
        d['present_count'] = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE attendance_id = ? AND check_status = 'present'", (d['id'],)
        ).fetchone()[0]
        d['late_count'] = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE attendance_id = ? AND check_status = 'late'", (d['id'],)
        ).fetchone()[0]
        result.append(d)
    conn.close()
    return result

def check_in(attendance_id, student_id, check_status='present'):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO attendance_records (attendance_id, student_id, check_status) VALUES (?, ?, ?)",
                     (attendance_id, student_id, check_status))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def get_attendance_records(attendance_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT ar.*, s.name as student_name FROM attendance_records ar LEFT JOIN students s ON ar.student_id = s.id WHERE ar.attendance_id = ? ORDER BY ar.checked_at",
        (attendance_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_attendance_history(student_id):
    """获取某个学员的所有签到记录"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT a.id as attendance_id, a.title, a.created_at as session_time,
                  ar.check_status, ar.checked_at
           FROM attendances a
           LEFT JOIN attendance_records ar ON a.id = ar.attendance_id AND ar.student_id = ?
           ORDER BY a.created_at DESC""",
        (student_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 学情分析 ====================

def get_analytics_data():
    conn = get_connection()
    # 进度分布
    ranges = [(0, 20, '0-20%'), (21, 40, '21-40%'), (41, 60, '41-60%'), (61, 80, '61-80%'), (81, 100, '81-100%')]
    progress_dist = []
    for low, high, label in ranges:
        count = conn.execute("SELECT COUNT(*) FROM students WHERE progress >= ? AND progress <= ?", (low, high)).fetchone()[0]
        progress_dist.append({'label': label, 'count': count})
    # 方向分布
    rows = conn.execute("SELECT direction, COUNT(*) as count FROM students GROUP BY direction").fetchall()
    direction_dist = [dict(r) for r in rows]
    # 各方向平均进度
    rows2 = conn.execute("SELECT direction, AVG(progress) as avg_progress FROM students GROUP BY direction").fetchall()
    direction_progress = [{'direction': r['direction'], 'avg_progress': round(r['avg_progress'], 1)} for r in rows2]
    conn.close()
    return {
        'progress_distribution': progress_dist,
        'direction_distribution': direction_dist,
        'direction_progress': direction_progress
    }


# ==================== 消息系统 ====================

def send_message(sender_id, receiver_id, content):
    conn = get_connection()
    conn.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)",
        (sender_id, receiver_id, content)
    )
    conn.commit()
    conn.close()


def get_messages(user1_id, user2_id, limit=50):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM messages
           WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
           ORDER BY created_at DESC LIMIT ?""",
        (user1_id, user2_id, user2_id, user1_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_inbox(user_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT m.*, s.name as sender_name FROM messages m
           LEFT JOIN students s ON m.sender_id = s.id
           WHERE m.id IN (
               SELECT MAX(id) FROM messages
               WHERE sender_id = ? OR receiver_id = ?
               GROUP BY CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END
           )
           ORDER BY m.created_at DESC""",
        (user_id, user_id, user_id)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        other_id = d['receiver_id'] if d['sender_id'] == user_id else d['sender_id']
        other_name = d.get('sender_name', other_id) if d['sender_id'] != user_id else other_id
        # 如果对方不是学生，尝试用ID作为名称
        if other_name == other_id:
            conn2 = get_connection()
            row2 = conn2.execute("SELECT name FROM students WHERE id = ?", (other_id,)).fetchone()
            conn2.close()
            if row2:
                other_name = row2['name']
        d['other_id'] = other_id
        d['other_name'] = other_name
        d['is_mine'] = d['sender_id'] == user_id
        result.append(d)
    return result


def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def mark_messages_read(sender_id, receiver_id):
    conn = get_connection()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE sender_id = ? AND receiver_id = ? AND is_read = 0",
        (sender_id, receiver_id)
    )
    conn.commit()
    conn.close()


# ==================== 系统通知 ====================

def create_notification(user_id, ntype, title, content='', link_type='', link_id=None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, ntype, title, content, link_type, link_id)
    )
    conn.commit()
    conn.close()


def create_notification_for_all_students(ntype, title, content='', link_type='', link_id=None):
    conn = get_connection()
    students = conn.execute("SELECT id FROM students").fetchall()
    for s in students:
        conn.execute(
            "INSERT INTO notifications (user_id, type, title, content, link_type, link_id) VALUES (?, ?, ?, ?, ?, ?)",
            (s['id'], ntype, title, content, link_type, link_id)
        )
    conn.commit()
    conn.close()


def get_notifications(user_id, limit=20):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notification_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,)
    )
    conn.commit()
    conn.close()


def clear_read_notifications(user_id):
    conn = get_connection()
    conn.execute(
        "DELETE FROM notifications WHERE user_id = ? AND is_read = 1",
        (user_id,)
    )
    conn.commit()
    conn.close()


# ==================== 就业 ====================

def get_job_listings():
    """获取岗位列表"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM job_listings").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def apply_for_job(user_id, job_id):
    """申请职位"""
    conn = get_connection()
    existing = conn.execute("SELECT * FROM job_applications WHERE user_id = ? AND job_id = ?",
                            (user_id, job_id)).fetchone()
    if existing:
        conn.close()
        return False  # 已申请
    conn.execute("INSERT INTO job_applications (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
    conn.commit()
    conn.close()
    return True


def get_job_by_id(job_id):
    """获取单条职位详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d['requirements'] = json.loads(d['requirements'])
    return d


def get_job_listings_filtered(keyword=None, location=None, salary_range=None, category=None):
    """按条件筛选职位"""
    conn = get_connection()
    query = "SELECT * FROM job_listings WHERE 1=1"
    params = []
    if keyword:
        query += " AND (title LIKE ? OR company LIKE ? OR description LIKE ?)"
        params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
    if location:
        query += " AND location = ?"
        params.append(location)
    if category:
        query += " AND category = ?"
        params.append(category)
    if salary_range:
        if salary_range == '12000+':
            query += " AND salary LIKE '%1%'"
        else:
            parts = salary_range.split('-')
            if len(parts) == 2:
                query += " AND salary LIKE ?"
                params.append(f'%{parts[0]}%')
    query += " ORDER BY posted_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def get_similar_jobs(job_id, category, limit=3):
    """获取同分类相似职位"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM job_listings WHERE category = ? AND id != ? LIMIT ?",
                        (category, job_id, limit)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['requirements'] = json.loads(d['requirements'])
        result.append(d)
    return result


def save_job(user_id, job_id):
    """收藏职位"""
    conn = get_connection()
    try:
        conn.execute("INSERT INTO saved_jobs (user_id, job_id) VALUES (?, ?)", (user_id, job_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


def unsave_job(user_id, job_id):
    """取消收藏"""
    conn = get_connection()
    conn.execute("DELETE FROM saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    conn.commit()
    conn.close()
    return True


def get_saved_jobs(user_id):
    """获取用户收藏的职位ID列表"""
    conn = get_connection()
    rows = conn.execute("SELECT job_id FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return [r['job_id'] for r in rows]


def get_user_applications(user_id, status_filter=None):
    """获取用户投递记录（含职位详情）"""
    conn = get_connection()
    if status_filter and status_filter != 'all':
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ? AND ja.status = ?
            ORDER BY ja.applied_at DESC
        """, (user_id, status_filter)).fetchall()
    else:
        rows = conn.execute("""
            SELECT ja.id, ja.user_id, ja.job_id, ja.status, ja.applied_at,
                   jl.title, jl.company, jl.salary, jl.location, jl.category
            FROM job_applications ja
            JOIN job_listings jl ON ja.job_id = jl.id
            WHERE ja.user_id = ?
            ORDER BY ja.applied_at DESC
        """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_application_counts(user_id):
    """获取各状态投递计数"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'pending'", (user_id,)).fetchone()[0]
    approved = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'approved'", (user_id,)).fetchone()[0]
    rejected = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ? AND status = 'rejected'", (user_id,)).fetchone()[0]
    conn.close()
    return {'total': total, 'pending': pending, 'approved': approved, 'rejected': rejected}


def get_employment_stats(user_id):
    """获取就业模块快捷统计"""
    conn = get_connection()
    applied = conn.execute("SELECT COUNT(*) FROM job_applications WHERE user_id = ?", (user_id,)).fetchone()[0]
    saved = conn.execute("SELECT COUNT(*) FROM saved_jobs WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    return {'applied': applied, 'saved': saved, 'messages': 0}


# ==================== 资源 ====================

def get_success_cases():
    """获取成功案例"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM success_cases").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['stats'] = json.loads(d['stats'])
        result.append(d)
    return result


def get_policies():
    """获取政策"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM policies").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ==================== 教师仪表板 ====================

def get_dashboard_stats():
    """获取教师仪表板统计"""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    earned = conn.execute("SELECT COUNT(*) FROM certificates WHERE status = 'earned'").fetchone()[0]
    total_certs = conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
    avg_progress = conn.execute("SELECT AVG(progress) FROM students").fetchone()[0] or 0
    conn.close()

    completion_rate = int((earned / total_certs * 100)) if total_certs > 0 else 0
    return {
        "total_students": total,
        "certificates_earned": earned,
        "completion_rate": completion_rate,
        "avg_score": int(avg_progress)
    }

# ==================== 用户注册和管理 ====================

def register_user(username, password, name, role='student', email='', phone='',
                  company_name='', region=''):
    """注册新用户"""
    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        conn.close()
        return None, "用户名已存在"
    pw_hash = hash_password(password)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, name, role, email, phone, company_name, region) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (username, pw_hash, name, role, email, phone, company_name, region))
    conn.commit()
    conn.close()
    return username, "注册成功"


def get_user_by_id(user_id):
    """根据用户名获取用户信息"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_all_users(search=None, role=None):
    """获取所有用户列表（管理员视角）"""
    conn = get_connection()
    query = "SELECT * FROM users WHERE 1=1"
    params = []
    if search:
        query += " AND (username LIKE ? OR name LIKE ?)"
        params.extend([f'%{search}%', f'%{search}%'])
    if role:
        query += " AND role = ?"
        params.append(role)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_by_admin(user_id, name=None, role=None, status=None, phone=None, email=None):
    """管理员编辑用户"""
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False
    updates = []
    params = []
    if name is not None:
        updates.append("name = ?"); params.append(name)
    if role is not None:
        updates.append("role = ?"); params.append(role)
    if status is not None:
        updates.append("status = ?"); params.append(status)
    if phone is not None:
        updates.append("phone = ?"); params.append(phone)
    if email is not None:
        updates.append("email = ?"); params.append(email)
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", params)
        conn.commit()
    conn.close()
    return True


def delete_user_by_admin(user_id):
    """管理员删除用户"""
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE username = ?", (user_id,))
    conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM points WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True


def update_user_profile(user_id, name=None, email=None, phone=None, avatar_url=None,
                        bio=None, company_name=None, region=None):
    """更新用户个人资料（扩展版）"""
    conn = get_connection()
    updates = []
    params = []
    if name is not None: updates.append("name = ?"); params.append(name)
    if email is not None: updates.append("email = ?"); params.append(email)
    if phone is not None: updates.append("phone = ?"); params.append(phone)
    if avatar_url is not None: updates.append("avatar_url = ?"); params.append(avatar_url)
    if bio is not None: updates.append("bio = ?"); params.append(bio)
    if company_name is not None: updates.append("company_name = ?"); params.append(company_name)
    if region is not None: updates.append("region = ?"); params.append(region)
    if updates:
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE username = ?", params)
        conn.commit()
    conn.close()
    return True


# ==================== 内容审核 ====================

def create_content_review(content_type, content_id, submitter_id):
    """创建内容审核记录"""
    conn = get_connection()
    conn.execute(
        "INSERT INTO content_reviews (content_type, content_id, submitter_id) VALUES (?, ?, ?)",
        (content_type, content_id, submitter_id))
    conn.commit()
    conn.close()


def get_pending_reviews(content_type=None):
    """获取待审核列表"""
    conn = get_connection()
    if content_type:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status = 'pending' AND content_type = ? ORDER BY created_at DESC",
            (content_type,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM content_reviews WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def approve_review(review_id, reviewer_id):
    """审核通过"""
    conn = get_connection()
    conn.execute(
        "UPDATE content_reviews SET status='approved', reviewed_by=?, reviewed_at=datetime('now','localtime') WHERE id=?",
        (reviewer_id, review_id))
    review = conn.execute("SELECT * FROM content_reviews WHERE id=?", (review_id,)).fetchone()
    if review:
        ct, cid = review['content_type'], review['content_id']
        if ct == 'course':
            conn.execute("UPDATE courses SET review_status='approved', is_published=1 WHERE id=?", (cid,))
        elif ct == 'job':
            conn.execute("UPDATE job_listings SET review_status='approved' WHERE id=?", (cid,))
        elif ct == 'procurement':
            conn.execute("UPDATE procurements SET review_status='approved' WHERE id=?", (cid,))
        elif ct == 'model_3d':
            conn.execute("UPDATE models_3d SET review_status='approved', is_published=1 WHERE id=?", (cid,))
    conn.commit()
    conn.close()


def reject_review(review_id, reviewer_id, comment=''):
    """审核拒绝"""
    conn = get_connection()
    conn.execute(
        "UPDATE content_reviews SET status='rejected', reviewed_by=?, review_comment=?, reviewed_at=datetime('now','localtime') WHERE id=?",
        (reviewer_id, comment, review_id))
    conn.commit()
    conn.close()


def get_review_by_content(content_type, content_id):
    """获取内容的审核记录"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM content_reviews WHERE content_type=? AND content_id=? ORDER BY id DESC LIMIT 1",
        (content_type, content_id)).fetchone()
    conn.close()
    return dict(row) if row else None


# ==================== 轮播图 ====================

def get_carousels(active_only=True):
    """获取轮播图列表"""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM carousels WHERE is_active=1 ORDER BY sort_order").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM carousels ORDER BY sort_order").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_carousel(title, image_url, link_url='', sort_order=0):
    """添加轮播图"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO carousels (title, image_url, link_url, sort_order) VALUES (?, ?, ?, ?)",
        (title, image_url, link_url, sort_order))
    conn.commit()
    car_id = cursor.lastrowid
    conn.close()
    return car_id


def update_carousel(car_id, **kwargs):
    """更新轮播图"""
    conn = get_connection()
    allowed = {'title', 'image_url', 'link_url', 'sort_order', 'is_active'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [car_id]
        conn.execute(f"UPDATE carousels SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_carousel(car_id):
    """删除轮播图"""
    conn = get_connection()
    conn.execute("DELETE FROM carousels WHERE id=?", (car_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 系统公告 ====================

def get_system_announcements(active_only=True):
    """获取系统公告"""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM system_announcements WHERE is_active=1 ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM system_announcements ORDER BY is_pinned DESC, created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_system_announcement(title, content, is_pinned=0, created_by=''):
    """新增系统公告"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO system_announcements (title, content, is_pinned, created_by) VALUES (?, ?, ?, ?)",
        (title, content, is_pinned, created_by))
    conn.commit()
    ann_id = cursor.lastrowid
    conn.close()
    return ann_id


def delete_system_announcement(ann_id):
    """删除系统公告（软删除）"""
    conn = get_connection()
    conn.execute("UPDATE system_announcements SET is_active=0 WHERE id=?", (ann_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程 ====================

def create_course(title, description, category, teacher_id, cover_url=''):
    """教师创建课程"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO courses (title, description, category, teacher_id, cover_url) VALUES (?, ?, ?, ?, ?)",
        (title, description, category, teacher_id, cover_url))
    conn.commit()
    course_id = cursor.lastrowid
    conn.close()
    # 创建审核记录
    create_content_review('course', course_id, teacher_id)
    return course_id


def get_courses(teacher_id=None, published_only=True):
    """获取课程列表"""
    conn = get_connection()
    query = "SELECT * FROM courses WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_course(course_id):
    """获取单个课程"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_course(course_id, **kwargs):
    """更新课程"""
    conn = get_connection()
    allowed = {'title', 'description', 'category', 'cover_url'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [course_id]
        conn.execute(f"UPDATE courses SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_course(course_id):
    """删除课程及关联素材"""
    conn = get_connection()
    conn.execute("DELETE FROM course_materials WHERE course_id = ?", (course_id,))
    conn.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='course' AND content_id=?", (course_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 课程素材 ====================

def add_course_material(course_id, material_type, file_name, file_path, file_size=0):
    """添加课程素材"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO course_materials (course_id, material_type, file_name, file_path, file_size) VALUES (?, ?, ?, ?, ?)",
        (course_id, material_type, file_name, file_path, file_size))
    conn.commit()
    mat_id = cursor.lastrowid
    conn.close()
    return mat_id


def get_course_materials(course_id):
    """获取课程素材列表"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM course_materials WHERE course_id = ? ORDER BY sort_order", (course_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_course_material(mat_id):
    """删除课程素材"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM course_materials WHERE id = ?", (mat_id,)).fetchone()
    conn.execute("DELETE FROM course_materials WHERE id = ?", (mat_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 3D 模型 ====================

def create_model_3d(title, description, craft_type, file_path, file_name, file_size, teacher_id, thumbnail_url=''):
    """上传3D模型"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO models_3d (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, description, craft_type, file_path, file_name, file_size, thumbnail_url, teacher_id))
    conn.commit()
    model_id = cursor.lastrowid
    conn.close()
    create_content_review('model_3d', model_id, teacher_id)
    return model_id


def get_models_3d(teacher_id=None, published_only=True):
    """获取3D模型列表"""
    conn = get_connection()
    query = "SELECT * FROM models_3d WHERE 1=1"
    params = []
    if teacher_id:
        query += " AND teacher_id = ?"
        params.append(teacher_id)
    if published_only:
        query += " AND is_published = 1"
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_model_3d(model_id):
    """删除3D模型"""
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM models_3d WHERE id = ?", (model_id,)).fetchone()
    conn.execute("DELETE FROM models_3d WHERE id = ?", (model_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='model_3d' AND content_id=?", (model_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


# ==================== 评论 ====================

def add_comment(target_type, target_id, user_id, content):
    """添加评论"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (target_type, target_id, user_id, content) VALUES (?, ?, ?, ?)",
        (target_type, target_id, user_id, content))
    conn.commit()
    comment_id = cursor.lastrowid
    # 更新讨论区评论计数
    if target_type == 'discussion':
        conn.execute("UPDATE discussions SET comment_count = comment_count + 1 WHERE id = ?", (target_id,))
        conn.commit()
    conn.close()
    return comment_id


def get_comments(target_type, target_id):
    """获取评论列表"""
    conn = get_connection()
    rows = conn.execute(
        """SELECT c.*, u.name as user_name, u.avatar_url
           FROM comments c LEFT JOIN users u ON c.user_id = u.username
           WHERE c.target_type = ? AND c.target_id = ? AND c.is_deleted = 0
           ORDER BY c.created_at ASC""",
        (target_type, target_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def soft_delete_comment(comment_id, deleted_by=''):
    """软删除评论"""
    conn = get_connection()
    conn.execute("UPDATE comments SET is_deleted=1, deleted_by=? WHERE id=?", (deleted_by, comment_id))
    conn.commit()
    conn.close()
    return True


# ==================== 讨论区 ====================

def create_discussion(title, content, category, user_id):
    """创建讨论帖"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO discussions (title, content, category, user_id) VALUES (?, ?, ?, ?)",
        (title, content, category, user_id))
    conn.commit()
    disc_id = cursor.lastrowid
    conn.close()
    return disc_id


def get_discussions(category=None, page=1, page_size=20):
    """获取讨论区列表（分页）"""
    conn = get_connection()
    query = "SELECT d.*, u.name as user_name FROM discussions d LEFT JOIN users u ON d.user_id = u.username WHERE d.is_deleted = 0"
    params = []
    if category:
        query += " AND d.category = ?"
        params.append(category)
    query += " ORDER BY d.is_pinned DESC, d.created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM discussions WHERE is_deleted = 0" +
        (f" AND category = ?" if category else ""),
        (category,) if category else ()).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_discussion(disc_id):
    """获取讨论详情"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET view_count = view_count + 1 WHERE id = ?", (disc_id,))
    row = conn.execute(
        "SELECT d.*, u.name as user_name FROM discussions d LEFT JOIN users u ON d.user_id = u.username WHERE d.id = ?",
        (disc_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


def soft_delete_discussion(disc_id):
    """软删除讨论帖"""
    conn = get_connection()
    conn.execute("UPDATE discussions SET is_deleted = 1 WHERE id = ?", (disc_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 农产品求购 ====================

def create_procurement(product_name, enterprise_id, specification='', quantity='',
                       price_range='', delivery_location='', deadline='',
                       contact_info='', description=''):
    """企业发布求购"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO procurements (product_name, specification, quantity, price_range, "
        "delivery_location, deadline, contact_info, description, enterprise_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (product_name, specification, quantity, price_range, delivery_location,
         deadline, contact_info, description, enterprise_id))
    conn.commit()
    proc_id = cursor.lastrowid
    conn.close()
    create_content_review('procurement', proc_id, enterprise_id)
    return proc_id


def get_procurements(enterprise_id=None, status=None, published_only=True):
    """获取求购列表"""
    conn = get_connection()
    query = "SELECT p.*, u.company_name, u.region as enterprise_region FROM procurements p LEFT JOIN users u ON p.enterprise_id = u.username WHERE 1=1"
    params = []
    if enterprise_id:
        query += " AND p.enterprise_id = ?"
        params.append(enterprise_id)
    if status:
        query += " AND p.status = ?"
        params.append(status)
    if published_only:
        query += " AND p.review_status = 'approved'"
    query += " ORDER BY p.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_procurement(proc_id, **kwargs):
    """更新求购"""
    conn = get_connection()
    allowed = {'product_name', 'specification', 'quantity', 'price_range',
               'delivery_location', 'deadline', 'contact_info', 'description', 'status'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [proc_id]
        conn.execute(f"UPDATE procurements SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_procurement(proc_id):
    """删除求购"""
    conn = get_connection()
    conn.execute("DELETE FROM procurements WHERE id = ?", (proc_id,))
    conn.execute("DELETE FROM content_reviews WHERE content_type='procurement' AND content_id=?", (proc_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 新闻资讯 ====================

def create_news(title, content, author_id, category='news'):
    """发布新闻"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO news_articles (title, content, category, author_id) VALUES (?, ?, ?, ?)",
        (title, content, category, author_id))
    conn.commit()
    news_id = cursor.lastrowid
    conn.close()
    return news_id


def get_news(category=None, page=1, page_size=20):
    """获取新闻列表"""
    conn = get_connection()
    query = "SELECT n.*, u.name as author_name FROM news_articles n LEFT JOIN users u ON n.author_id = u.username WHERE n.is_published = 1"
    params = []
    if category:
        query += " AND n.category = ?"
        params.append(category)
    query += " ORDER BY n.created_at DESC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM news_articles WHERE is_published = 1" +
        (f" AND category = ?" if category else ""),
        (category,) if category else ()).fetchone()[0]
    conn.close()
    return [dict(r) for r in rows], total


def get_news_by_id(news_id):
    """获取新闻详情"""
    conn = get_connection()
    conn.execute("UPDATE news_articles SET view_count = view_count + 1 WHERE id = ?", (news_id,))
    row = conn.execute(
        "SELECT n.*, u.name as author_name FROM news_articles n LEFT JOIN users u ON n.author_id = u.username WHERE n.id = ?",
        (news_id,)).fetchone()
    conn.commit()
    conn.close()
    return dict(row) if row else None


def update_news(news_id, **kwargs):
    """更新新闻"""
    conn = get_connection()
    allowed = {'title', 'content', 'category', 'is_published'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [news_id]
        conn.execute(f"UPDATE news_articles SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_news(news_id):
    """删除新闻"""
    conn = get_connection()
    conn.execute("DELETE FROM news_articles WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 政府政策 ====================

def create_policy(title, content, category, author_id):
    """发布政策"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO government_policies (title, content, category, author_id) VALUES (?, ?, ?, ?)",
        (title, content, category, author_id))
    conn.commit()
    policy_id = cursor.lastrowid
    conn.close()
    return policy_id


def get_government_policies(category=None):
    """获取政府政策列表"""
    conn = get_connection()
    query = "SELECT * FROM government_policies WHERE is_published = 1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_government_policies():
    """获取所有政府政策（含未发布，政府端使用）"""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM government_policies ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_policy_by_id(policy_id):
    """获取政策详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM government_policies WHERE id = ?", (policy_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_policy(policy_id, **kwargs):
    """更新政策"""
    conn = get_connection()
    allowed = {'title', 'content', 'category', 'is_published'}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if updates:
        updates['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        set_clause = ', '.join(f"{k}=?" for k in updates)
        params = list(updates.values()) + [policy_id]
        conn.execute(f"UPDATE government_policies SET {set_clause} WHERE id=?", params)
        conn.commit()
    conn.close()
    return True


def delete_policy(policy_id):
    """删除政策"""
    conn = get_connection()
    conn.execute("DELETE FROM government_policies WHERE id = ?", (policy_id,))
    conn.commit()
    conn.close()
    return True


# ==================== 数据大屏 ====================

def get_dashboard_overview():
    """政府数据大屏 - 总览统计"""
    conn = get_connection()
    # 各类用户数
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    student_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    teacher_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0]
    enterprise_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='enterprise'").fetchone()[0]

    # 培训数据
    total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    avg_progress = conn.execute("SELECT AVG(progress) FROM students").fetchone()[0] or 0
    completed = conn.execute("SELECT COUNT(*) FROM students WHERE progress >= 100").fetchone()[0]

    # 就业数据
    total_jobs = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
    total_applications = conn.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0]
    approved_apps = conn.execute("SELECT COUNT(*) FROM job_applications WHERE status='approved'").fetchone()[0]

    # 内容数据
    total_courses = conn.execute("SELECT COUNT(*) FROM courses WHERE is_published=1").fetchone()[0]
    total_policies = conn.execute("SELECT COUNT(*) FROM government_policies WHERE is_published=1").fetchone()[0]
    total_news = conn.execute("SELECT COUNT(*) FROM news_articles WHERE is_published=1").fetchone()[0]
    total_procurements = conn.execute("SELECT COUNT(*) FROM procurements WHERE status='active' AND review_status='approved'").fetchone()[0]

    # 证书数据
    total_certs = conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0]
    earned_certs = conn.execute("SELECT COUNT(*) FROM certificates WHERE status='earned'").fetchone()[0]

    # 讨论区热度
    total_discussions = conn.execute("SELECT COUNT(*) FROM discussions WHERE is_deleted=0").fetchone()[0]
    total_comments = conn.execute("SELECT COUNT(*) FROM comments WHERE is_deleted=0").fetchone()[0]

    conn.close()

    return {
        "users": {
            "total": total_users,
            "students": student_count,
            "teachers": teacher_count,
            "enterprises": enterprise_count
        },
        "training": {
            "total_students": total_students,
            "avg_progress": round(avg_progress, 1),
            "completed": completed,
            "completion_rate": round(completed / total_students * 100, 1) if total_students > 0 else 0
        },
        "employment": {
            "total_jobs": total_jobs,
            "total_applications": total_applications,
            "match_rate": round(approved_apps / total_applications * 100, 1) if total_applications > 0 else 0
        },
        "content": {
            "courses": total_courses,
            "policies": total_policies,
            "news": total_news,
            "procurements": total_procurements
        },
        "certificates": {
            "total": total_certs,
            "earned": earned_certs,
            "earn_rate": round(earned_certs / total_certs * 100, 1) if total_certs > 0 else 0
        },
        "community": {
            "discussions": total_discussions,
            "comments": total_comments
        }
    }


def get_dashboard_region_stats():
    """各地区数据统计"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT region, COUNT(*) as count FROM users WHERE region != '' GROUP BY region ORDER BY count DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_dashboard_direction_stats():
    """各培训方向统计"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT direction, COUNT(*) as count, AVG(progress) as avg_progress FROM students GROUP BY direction"
    ).fetchall()
    conn.close()
    return [{"direction": r['direction'] or '未分类', "count": r['count'],
             "avg_progress": round(r['avg_progress'] or 0, 1)} for r in rows]
