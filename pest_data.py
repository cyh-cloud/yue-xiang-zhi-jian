# -*- coding: utf-8 -*-
"""常见病虫害速查 — 数据事实源

【数据性质】本模块是「常见病虫害速查」与「病虫害 AI 诊断」的**共用唯一事实源**。
  - 速查界面（/api/agriculture/pest-knowledge）读取其中的富字段；
  - 诊断的知识库降级路径读取 `common_diseases[*]` 的
    `disease / severity / symptoms / treatment / prevention` 五个字段（与历史结构兼容）。
  两条路径共用同一份条目，不再维护两套数据，避免「改了速查、诊断还停在旧内容」。

【数据来源与可核验性】
  - 药剂名录优先采信《广东省主要农作物病虫害防治药剂推荐名单（2024年修订）》
    （粤农农办〔2024〕68号，广东省农业农村厅办公室，2024-05-28）—— 本项目所在地的官方推荐名单。
  - 用量（稀释倍数 / 亩用量）、安全间隔期、每季（每造）最多使用次数，逐条取自省、市、县
    农业农村部门公开发布的《病虫情报》《防控技术指引》《科学用药指南》或农药登记数据，
    条目的 `sources` 字段登记出处 key，`chem_table` 只收录**有明确出处**的数值。
  - 凡来源未给出安全间隔期的，`chem_table` 中该字段留空并在 `safety_note` 中提示
    「以农药标签标注为准」，**不擅自补一个数字**。

【复核状态】`is_verified` 与农时日历一致：0 = 依据公开技术资料编排的参考内容（界面加「参考」标注），
  1 = 已由农技人员复核。当前全部为 0。逐条出处见项目根《常见病虫害速查数据来源.md》。

【撰写约束】面向终端农户与实训学生，只写农艺逻辑与可执行的防治要点；
  安全间隔期、每季次数等涉及食品安全的数字必须有出处；不确定的写「以农药标签为准」。
"""


# ==================== 数据来源登记表 ====================
# doc_no 只登记**已实际见到文号**的正式文件；其余统一「待核」。
PEST_SOURCES = [
    {
        'key': 'GD-PEST-2024',
        'name': '广东省主要农作物病虫害防治药剂推荐名单（2024年修订）',
        'org': '广东省农业农村厅办公室', 'doc_type': '行政通知',
        'doc_no': '粤农农办〔2024〕68号', 'date': '2024-05-28',
        'url': 'https://nyncj.gz.gov.cn/zw/tzgg/content/post_10635391.html',
    },
    {
        'key': 'GD-GZ-LYCHEE-TG',
        'name': '荔枝霜疫霉病防控技术指引',
        'org': '广州市农业农村局', 'doc_type': '防控技术指引',
        'doc_no': '待核', 'date': '',
        'url': 'https://nyncj.gz.gov.cn/attachment/8/8029/8029726/10835854.pdf',
    },
    {
        'key': 'BL-PEST-2025-8',
        'name': '2025年农作物病虫情报 第八期（荔枝病虫的发生与防治）',
        'org': '惠州市博罗县农业农村综合服务中心', 'doc_type': '病虫情报',
        'doc_no': '2025年第八期', 'date': '2025-05-14',
        'url': 'https://www.boluo.gov.cn/zwgk/zwdt/bmdt/content/post_5523942.html',
    },
    {
        'key': 'BL-PEST-2026-6',
        'name': '2026年农作物病虫情报 第六期',
        'org': '博罗县人民政府门户网站', 'doc_type': '病虫情报',
        'doc_no': '2026年第六期', 'date': '2026',
        'url': 'https://www.boluo.gov.cn/zwgk/zwdt/bmdt/content/post_5752128.html',
    },
    {
        'key': 'GX-FRUIT-LYCHEE',
        'name': '病虫情报（第8期）：抓好荔枝果期主要病虫害防控工作',
        'org': '广西壮族自治区农业农村厅', 'doc_type': '病虫情报',
        'doc_no': '第8期', 'date': '',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/gxlb/yl/t27692606.shtml',
    },
    {
        'key': 'GX-LONGAN-2025',
        'name': '龙眼果期科学管理技术要点',
        'org': '广西壮族自治区农业农村厅', 'doc_type': '技术要点',
        'doc_no': '待核', 'date': '',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/syjs/t27477205.shtml',
    },
    {
        'key': 'MM-BANANA-GUIDE',
        'name': '茂名市香蕉主要病虫害防治安全科学用药指南',
        'org': '茂名市农业农村局', 'doc_type': '科学用药指南',
        'doc_no': '待核', 'date': '',
        'url': 'http://www.maoming.gov.cn/xxgkml/mmny/zc/bmwj/content/post_1563476.html',
    },
    {
        'key': 'MM-BANANA-TG',
        'name': '茂名市香蕉质量安全生产技术指南（附录A 香蕉主要病虫害及部分登记农药）',
        'org': '茂名市农业农村局', 'doc_type': '技术指南',
        'doc_no': '待核', 'date': '',
        'url': 'http://www.maoming.gov.cn/xxgkml/mmny/gdzdgk/gzdt/content/post_1564543.html',
    },
    {
        'key': 'GX-BANANA-7M',
        'name': '7月广西重点水果病虫害绿色防控技术要点——香蕉篇',
        'org': '广西壮族自治区农业农村厅', 'doc_type': '技术要点',
        'doc_no': '待核', 'date': '',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/syjs/t22622530.shtml',
    },
    {
        'key': 'NN-CITRUS-2024',
        'name': '沃柑质量安全控制技术性指导意见（表C 常见柑橘农药安全间隔期参考表）',
        'org': '南宁市农业农村局', 'doc_type': '技术指导意见',
        'doc_no': '待核', 'date': '',
        'url': 'https://ny.nanning.gov.cn/xxgk/zwdt/bddt/t6492867.html',
    },
    {
        'key': 'JX-CITRUS-2026-14',
        'name': '吉安市病虫预报2026年第14期：切实抓好夏秋梢柑橘木虱监测和统防统治工作',
        'org': '江西省农业农村厅', 'doc_type': '病虫预报',
        'doc_no': '2026年第14期', 'date': '2026',
        'url': 'https://nync.jiangxi.gov.cn/jxsnynct/yjxx/content/content_2087436241645936640.html',
    },
    {
        'key': 'GX-CITRUS-2026-23',
        'name': '忻城县2026年病虫情报第二十三期——切实抓好秋梢期柑橘木虱等病虫害防控工作',
        'org': '广西壮族自治区农业农村厅', 'doc_type': '病虫情报',
        'doc_no': '2026年第23期', 'date': '2026',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/gxlb/lb/t28040343.shtml',
    },
    {
        'key': 'SC-NANBU-CITRUS',
        'name': '绿色食品柑桔生产主要病虫害防治推荐农药使用方案',
        'org': '四川省南部县人民政府', 'doc_type': '推荐农药使用方案',
        'doc_no': '待核', 'date': '2021-04-20',
        'url': 'https://scnanbu.gov.cn/zwgk/zdlygk/spyp_519/202104/t20210420_1164614.html',
    },
    {
        'key': 'SD-SHAODONG-2024',
        'name': '2024年邵东市农业主推技术与主推品种（水稻主要病虫草害防治常用药剂及注意事项）',
        'org': '邵东市人民政府', 'doc_type': '主推技术',
        'doc_no': '待核', 'date': '2024-11',
        'url': 'https://www.shaodong.gov.cn/shaodong/gsgg/202411/75c75827931c43889f87a41a8b31256f.shtml',
    },
    {
        'key': 'PT-LICHENG-MANUAL',
        'name': '主要农作物病虫害防治与安全用药服务手册',
        'org': '莆田市荔城区农业农村局', 'doc_type': '服务手册',
        'doc_no': '待核', 'date': '',
        'url': 'https://www.ptlc.gov.cn/bmxxgkzl/lcqnyj_27107/xxgkml/gzdt_27110/tnull_773948.htm',
    },
    {
        'key': 'MDJ-INTERVAL',
        'name': '如何科学安全使用农药（四）部分常用农药品种使用安全间隔期',
        'org': '牡丹江市农业农村局', 'doc_type': '用药指导',
        'doc_no': '待核', 'date': '2026-04',
        'url': 'https://nyncj.mdj.gov.cn/mdjsnyncj/c100584/202604/c03_1043653.shtml',
    },
    {
        'key': 'MOA-TEA-2023',
        'name': '2023年茶树主要病虫害防控技术方案',
        'org': '农业农村部 全国农业技术推广服务中心', 'doc_type': '防控技术方案',
        'doc_no': '待核', 'date': '2023-03-03',
        'url': 'https://www.moa.gov.cn/ztzl/2023cg/jszd_29356/202303/t20230306_6422312.htm',
    },
    {
        'key': 'GD-TEA-STD',
        'name': '茶树栽培与主要病虫害化学防治方法（广东省地方标准）',
        'org': '广东省市场监督管理局（省政府网站集约化平台）', 'doc_type': '地方标准',
        'doc_no': '待核', 'date': '',
        'url': 'https://yjzj.cloud.gd.gov.cn/',
    },
    {
        'key': 'YA-TEA-2025',
        'name': '2025年雅安市茶叶主要病虫害绿色防控技术方案',
        'org': '雅安市农业农村局', 'doc_type': '绿色防控技术方案',
        'doc_no': '待核', 'date': '2025-04-17',
        'url': 'https://nyncj.yaan.gov.cn/xinwen/show/4575314b418378fef7e0168d1dba1503.html',
    },
    {
        'key': 'GX-TEA-2026-7',
        'name': '金秀县2026年病虫情报第7期：当前茶园主要病虫害发生实况及防治意见',
        'org': '广西壮族自治区农业农村厅', 'doc_type': '病虫情报',
        'doc_no': '2026年第7期', 'date': '2026',
        'url': 'https://nynct.gxzf.gov.cn/xwdt/gxlb/lb/t27544312.shtml',
    },
    {
        'key': 'MOA-AQUATIC-FORECAST',
        'name': '水产养殖病害预测预报（各省月度预报汇总）',
        'org': '农业农村部 中国农业农村信息网 / 全国水产技术推广总站', 'doc_type': '病害预测预报',
        'doc_no': '待核', 'date': '',
        'url': 'https://www.agri.cn/sc/zxjc/scbch/',
    },
    {
        'key': 'GY-AQUATIC-2026-5',
        'name': '广元市水产养殖病害防控重点（2026年5月）',
        'org': '广元市农业农村局', 'doc_type': '病害防控要点',
        'doc_no': '待核', 'date': '2026-05',
        'url': 'https://nyncj.cngy.gov.cn/mshow/2245bd35e8854d699caea8eac5909d5c.html',
    },
    {
        'key': 'YC-AQUATIC-AUTUMN',
        'name': '入秋水产养殖病害防控技术要点',
        'org': '盐城水产科学研究院', 'doc_type': '病害防控技术要点',
        'doc_no': '待核', 'date': '',
        'url': 'http://ycafs.cn/end.html?id=443',
    },
    {
        'key': 'ICAMA',
        'name': '中国农药数字监督管理平台（农药登记数据查询）',
        'org': '农业农村部 农药检定所', 'doc_type': '农药登记数据库',
        'doc_no': '—', 'date': '',
        'url': 'https://www.icama.cn/',
    },
]


# ==================== 病虫害速查主数据 ====================
#
# 条目字段说明
#   id           稳定标识（前端锚点、去重、图片文件名）
#   disease      病/虫名称（诊断匹配与展示的唯一名称）
#   alias        别名 / 俗称
#   kind         'disease' 病害 | 'pest' 虫害
#   pathogen     病原或虫害学名（只在有把握时填写）
#   part         主要为害部位
#   severity     轻度 / 中度 / 重度（诊断历史字段，保留）
#   symptoms     典型症状识别要点（诊断匹配字段，保留）
#   occurrence   发生规律与流行条件
#   treatment    化学防治要点（诊断历史字段）
#   prevention   农业防治与预防措施（诊断历史字段）
#   registered   推荐/登记药剂名录
#   chem_table   有明确出处的用量表：agent / dose / interval_days / max_times
#   safety_note  用药安全提示
#   image        实拍图信息 {file, credit, source_url}，无授权图时为 None
#   sources      出处 key 列表（指向 PEST_SOURCES）
#   is_verified  0 参考 / 1 已复核
#
PEST_KNOWLEDGE = {

    # ---------------------------- 荔枝 ----------------------------
    'lychee': {
        'name': '荔枝', 'icon': '🍎', 'summary': '广东特色水果',
        'common_diseases': [
            {
                'id': 'lychee_downy_blight',
                'disease': '荔枝霜疫霉病', 'alias': '荔枝霜霉病',
                'kind': 'disease',
                'pathogen': 'Peronophythora litchii（荔枝霜疫霉，卵菌）',
                'part': '果实（多从果蒂开始）、花穗、嫩叶',
                'severity': '重度',
                'symptoms': [
                    '嫩叶受害出现褐色不规则病斑，潮湿时病部有白色霉层',
                    '花穗受害褐变腐烂，引起落花',
                    '果实多从果蒂开始出现水渍状褐色不规则病斑，迅速扩展至全果',
                    '潮湿时病部表面产生白色霜霉状物，果肉腐烂发酸并有褐色汁液流出',
                    '病果容易脱落',
                ],
                'occurrence': (
                    '病原以卵孢子和菌丝体在病叶、病果上越冬，来年春末夏初产生孢子囊借风雨传播，'
                    '形成初次侵染。果实膨大期至成熟期，遇连续阴雨、果园郁闭、通风不良时病害易暴发流行。'
                    '湿度是本病发生流行的关键因素。花穗期、幼果期及转色前是防控关键时期。'
                ),
                'treatment': [
                    '发病前或发病初期开始施药，重点保护果穗',
                    '可选用烯酰吗啉、精甲霜灵、代森锰锌、双炔酰菌胺、嘧菌酯、王铜、氧化亚铜等',
                    '果实转色期后改用氟吡菌胺、噁唑菌酮、氟噻唑吡乙酮等',
                    '同一生长季避免连续使用单一品种农药，交替使用不同作用机理的农药以延缓抗药性',
                ],
                'prevention': [
                    '采果后及时修剪，剪除交叉枝、重叠枝、病虫枝、过密枝、下垂枝，保持树冠通风透光',
                    '对郁闭树冠疏除中部1—2大枝「开天窗」，增强内膛光照',
                    '加强肥水管理，以有机肥为主、增施磷钾肥，适当控制氮肥用量，提高植株抗病力',
                    '雨后清沟排水，降低果园湿度',
                    '采后至翌年萌芽前彻底清园，病枯枝叶与病虫果穗集中深埋或销毁',
                    '雨季前地面撒施生石灰，减少土表病原初侵染源',
                    '行间生草或种植绿肥，定期刈割压青，调节园内微气候',
                ],
                'registered': ['嘧菌酯', '双炔酰菌胺', '精甲霜·锰锌', '霜脲·锰锌',
                               '唑醚·代森联', '烯酰·咪鲜胺', '氟噻唑·双炔酰', '烯酰·唑嘧菌'],
                'chem_table': [
                    {'agent': '80%代森锰锌可湿性粉剂', 'dose': '400~600倍液',
                     'interval_days': '10', 'max_times': '3'},
                    {'agent': '68%精甲霜·锰锌水分散粒剂', 'dose': '800~1000倍液',
                     'interval_days': '7', 'max_times': '4'},
                    {'agent': '250克/升嘧菌酯悬浮剂', 'dose': '1200~1600倍液',
                     'interval_days': '14', 'max_times': '3'},
                    {'agent': '23.4%双炔酰菌胺悬浮剂', 'dose': '1000~2000倍液',
                     'interval_days': '3', 'max_times': '3'},
                    {'agent': '72%甲霜·氧亚铜可湿性粉剂', 'dose': '1000~2000倍液',
                     'interval_days': '7', 'max_times': '3'},
                    {'agent': '18.7%烯酰·吡唑酯水分散粒剂', 'dose': '1000~1250倍液',
                     'interval_days': '28', 'max_times': '3'},
                ],
                'safety_note': '采收前7天停止用药；安全间隔期以所购农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'GD-GZ-LYCHEE-TG', 'BL-PEST-2025-8', 'ICAMA'],
                'is_verified': 0,
            },
            {
                'id': 'lychee_anthracnose',
                'disease': '荔枝炭疽病', 'alias': '',
                'kind': 'disease',
                'pathogen': '炭疽菌属（Colletotrichum spp.）',
                'part': '叶片、嫩梢、果实',
                'severity': '中度',
                'symptoms': [
                    '叶片出现圆形或不规则褐色斑点，边缘深褐色、中央灰白色',
                    '病斑后期生出黑色小点（分生孢子盘），常呈轮纹状排列',
                    '严重时叶片枯萎脱落，嫩梢变褐枯死',
                    '果实受害产生褐色凹陷病斑，影响商品价值',
                ],
                'occurrence': (
                    '病菌以菌丝体在病枝病叶上越冬，翌年温湿度适宜时产生分生孢子借风雨传播。'
                    '高温多雨季节、树势衰弱、偏施氮肥的果园发病较重。'
                ),
                'treatment': [
                    '剪除病枝病叶并集中烧毁，减少菌源',
                    '发病初期开始喷药，可选用苯醚甲环唑、咪鲜胺、腈菌唑、氟菌·肟菌酯等',
                    '重点喷施果实和叶片，注意轮换用药',
                ],
                'prevention': [
                    '避免偏施氮肥，增施有机肥增强树势',
                    '雨后及时排水，降低园内湿度',
                    '新梢期与幼果期喷药保护',
                    '冬季清园，剪除并处理病枝病叶',
                ],
                'registered': ['苯醚甲环唑', '咪鲜胺', '腈菌唑', '氟菌·肟菌酯', '氯氟醚·吡唑酯'],
                'chem_table': [
                    {'agent': '325克/升苯甲·嘧菌酯悬浮剂', 'dose': '1500~2000倍液',
                     'interval_days': '21', 'max_times': '3'},
                    {'agent': '10%苯醚甲环唑水分散粒剂', 'dose': '650~1000倍液',
                     'interval_days': '3', 'max_times': '3'},
                    {'agent': '25%咪鲜胺乳油', 'dose': '1000~1200倍液',
                     'interval_days': '21', 'max_times': '3'},
                    {'agent': '43%氟菌·肟菌酯悬浮剂', 'dose': '1500~2000倍液',
                     'interval_days': '14', 'max_times': '2'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；挂果期严禁使用高毒、高残留农药。',
                'image': None,
                'sources': ['GD-PEST-2024', 'BL-PEST-2025-8'],
                'is_verified': 0,
            },
            {
                'id': 'lychee_fruit_borer',
                'disease': '荔枝蒂蛀虫', 'alias': '荔枝蛀蒂虫',
                'kind': 'pest',
                'pathogen': 'Conopomorpha sinensis（荔枝蒂蛀虫）',
                'part': '果实（蛀果）、叶片（蛀食叶脉）',
                'severity': '重度',
                'symptoms': [
                    '幼虫自果蒂附近蛀入果实，果蒂内侧堆积黑色粉末状虫粪',
                    '蛀孔处果皮变褐，受害果实大量脱落',
                    '为害叶片时自叶尖蛀入叶脉，导致叶片枯死',
                    '落地果中可剥出乳白色幼虫',
                ],
                'occurrence': (
                    '在广东一年发生多代，以幼虫在荔枝、龙眼树上越冬。成虫夜间活动，'
                    '卵产于果实或嫩梢。果实膨大期至成熟期为主要为害期，卵孵化高峰后为施药适期。'
                ),
                'treatment': [
                    '抓住卵孵化高峰期至低龄幼虫期施药',
                    '可选用氯虫苯甲酰胺、高效氯氟氰菊酯、高效氯氰菊酯、除虫脲、毒死蜱等',
                    '重点喷施果穗和内膛枝干，落地果较多的果园需同时喷施地面',
                ],
                'prevention': [
                    '及时清除落地果和虫果，集中深埋或销毁，减少虫源',
                    '冬春清园，剪除枯枝落叶',
                    '成虫期可使用灯光诱杀',
                ],
                'registered': ['氯虫苯甲酰胺', '高效氯氟氰菊酯', '高效氯氰菊酯',
                               '除虫脲', '毒死蜱', '高效氯氰·虱螨脲'],
                'chem_table': [
                    {'agent': '50克/升高效氯氟氰菊酯乳油', 'dose': '2000~4000倍液',
                     'interval_days': '7', 'max_times': '2'},
                    {'agent': '4.5%高效氯氰菊酯乳油', 'dose': '65~85毫升/亩',
                     'interval_days': '14', 'max_times': '3'},
                    {'agent': '200克/升氯虫苯甲酰胺悬浮剂', 'dose': '3000~6000倍液',
                     'interval_days': '10', 'max_times': '1'},
                    {'agent': '40%除虫脲悬浮剂', 'dose': '2000~4000倍液',
                     'interval_days': '10或21', 'max_times': '3或2'},
                ],
                'safety_note': '荔枝果期易检出禁用农药（氧乐果、克百威等），严禁使用；严格遵守安全间隔期。',
                'image': None,
                'sources': ['GD-PEST-2024', 'BL-PEST-2025-8', 'GX-FRUIT-LYCHEE'],
                'is_verified': 0,
            },
            {
                'id': 'lychee_stink_bug',
                'disease': '荔枝蝽', 'alias': '荔枝蝽蟓、臭屁虫',
                'kind': 'pest',
                'pathogen': 'Tessaratoma papillosa（荔枝蝽）',
                'part': '嫩梢、花穗、幼果',
                'severity': '中度',
                'symptoms': [
                    '成若虫刺吸嫩梢、花穗和幼果的汁液',
                    '嫩梢受害后枯萎，花穗受害引起落花落果',
                    '幼果受害出现褐色斑点并大量脱落',
                    '受惊时分泌臭液，可灼伤人体皮肤',
                ],
                'occurrence': (
                    '一年发生1代，以成虫在树冠密叶层或屋檐下越冬。3—4月为产卵盛期，'
                    '若虫期是主要为害期。'
                ),
                'treatment': [
                    '若虫期施药，重点喷施花穗、嫩梢和幼果',
                    '可选用高效氯氟氰菊酯、敌百虫、溴氰菊酯、顺式氯氰菊酯等',
                    '清晨或傍晚施药效果较好',
                ],
                'prevention': [
                    '3—4月产卵盛期人工摘除卵块',
                    '每亩释放平腹小蜂卵卡50~65张进行生物防治',
                    '冬季低温期摇树震落越冬成虫并集中处理',
                ],
                'registered': ['高效氯氟氰菊酯', '敌百虫', '溴氰菊酯', '顺式氯氰菊酯', '氯氰·马拉松'],
                'chem_table': [
                    {'agent': '50克/升高效氯氟氰菊酯乳油', 'dose': '4000~8000倍液',
                     'interval_days': '7', 'max_times': '2'},
                    {'agent': '25克/升溴氰菊酯乳油', 'dose': '3000~5000倍液',
                     'interval_days': '9或28', 'max_times': '4或3'},
                    {'agent': '50克/升顺式氯氰菊酯乳油', 'dose': '2000~2500倍液',
                     'interval_days': '14', 'max_times': '3'},
                ],
                'safety_note': '部分敌百虫登记未标注安全间隔期，使用前务必以标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'BL-PEST-2025-8'],
                'is_verified': 0,
            },
            {
                'id': 'lychee_leaf_roller',
                'disease': '荔枝卷叶虫', 'alias': '荔枝卷叶蛾',
                'kind': 'pest',
                'pathogen': '卷叶蛾类（Tortricidae）',
                'part': '嫩叶、新梢',
                'severity': '轻度',
                'symptoms': [
                    '幼虫吐丝将嫩叶卷缀成苞，在其中取食叶肉',
                    '受害嫩叶残缺、卷曲',
                    '新梢受害影响抽梢质量',
                ],
                'occurrence': '新梢抽发期为害较重，与荔枝蒂蛀虫常同时发生，可在防治蒂蛀虫时兼治。',
                'treatment': [
                    '新梢期幼虫初孵时施药',
                    '可选用高氯·辛硫磷等，结合蒂蛀虫防治兼治',
                ],
                'prevention': [
                    '及时剪除虫苞并集中处理',
                    '统一放梢，摘除过早或过迟抽发的新梢，打断食物链',
                ],
                'registered': ['高氯·辛硫磷'],
                'chem_table': [
                    {'agent': '22%高氯·辛硫磷乳油', 'dose': '1500~2000倍液',
                     'interval_days': '14', 'max_times': '2'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'BL-PEST-2025-8'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 龙眼 ----------------------------
    'longan': {
        'name': '龙眼', 'icon': '🟤', 'summary': '岭南佳果',
        'common_diseases': [
            {
                'id': 'longan_witches_broom',
                'disease': '龙眼鬼帚病', 'alias': '龙眼丛枝病',
                'kind': 'disease',
                'pathogen': '植原体（Phytoplasma），由龙眼角颊木虱传播',
                'part': '新梢、花穗',
                'severity': '重度',
                'symptoms': [
                    '新梢丛生呈扫帚状，节间明显缩短',
                    '叶片狭小、卷曲、畸形，呈黄化或斑驳',
                    '花穗丛生而不结果，或结果极少',
                    '树势逐渐衰弱，病株症状逐年加重',
                ],
                'occurrence': (
                    '由龙眼角颊木虱传播。田间病株是主要侵染源，带毒苗木可造成远距离传播。'
                    '新梢抽发期是该病传播的关键时期。'
                ),
                'treatment': [
                    '目前无有效治疗药剂，以防控传毒媒介和清除病株为核心',
                    '春梢期喷药杀灭传毒木虱，压低媒介种群',
                    '发现病株立即整株挖除并销毁，树坑撒施生石灰消毒',
                ],
                'prevention': [
                    '选用无病苗木繁育，不从病区调运种苗',
                    '及时剪除病梢病穗并集中烧毁',
                    '重点防治龙眼角颊木虱等传毒昆虫',
                    '加强栽培管理，增强树势',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '本病无特效治疗药剂，切勿轻信宣称「治鬼帚病」的药剂宣传。',
                'image': None,
                'sources': ['GX-LONGAN-2025'],
                'is_verified': 0,
            },
            {
                'id': 'longan_downy_blight',
                'disease': '龙眼霜疫霉病', 'alias': '龙眼霜霉病',
                'kind': 'disease',
                'pathogen': 'Peronophythora litchii（荔枝霜疫霉）',
                'part': '果实、花穗、嫩叶',
                'severity': '重度',
                'symptoms': [
                    '果实受害出现褐色水渍状病斑，果面生褐斑并腐烂',
                    '潮湿时病部长出白色霉层',
                    '花穗受害褐变腐烂，引起落花',
                    '嫩叶受害出现褐色不规则病斑',
                ],
                'occurrence': (
                    '病原与荔枝霜疫霉病相同，发病条件亦相似。谢花后至果实成熟期遇连续阴雨'
                    '易暴发流行，是龙眼果期最主要病害之一。'
                ),
                'treatment': [
                    '谢花后及时施药，间隔7~10天喷1次，连续2~3次',
                    '可选用瑞毒霉锰锌、杀毒矾、甲霜灵等',
                    '重点保护果穗，喷湿内膛枝干',
                ],
                'prevention': [
                    '采后彻底清园，清除病果病叶并集中处理',
                    '加强果园排水，降低园内湿度',
                    '合理修剪改善通风透光',
                ],
                'registered': [],
                'chem_table': [
                    {'agent': '58%瑞毒霉锰锌可湿性粉剂', 'dose': '600倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '64%杀毒矾可湿性粉剂', 'dose': '600倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '甲霜灵', 'dose': '600倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '上述浓度出自广西壮族自治区农业农村厅技术要点，未附安全间隔期，须以农药标签为准。',
                'image': None,
                'sources': ['GX-LONGAN-2025'],
                'is_verified': 0,
            },
            {
                'id': 'longan_anthracnose',
                'disease': '龙眼炭疽病', 'alias': '',
                'kind': 'disease',
                'pathogen': '炭疽菌属（Colletotrichum spp.）',
                'part': '叶片、果实、枝条',
                'severity': '中度',
                'symptoms': [
                    '叶片出现褐色圆形或不规则病斑，中央灰白',
                    '病斑上生黑色小点，呈轮纹状排列',
                    '果实受害产生褐色凹陷病斑',
                    '枝条受害形成褐色病斑，严重时枯死',
                ],
                'occurrence': '高温多雨季节发病较重，树势衰弱、偏施氮肥的果园更易流行。',
                'treatment': [
                    '谢花后及幼果期提前用药保护',
                    '可选用苯醚甲环唑、咪鲜胺、代森锰锌等',
                ],
                'prevention': [
                    '结合修剪清除病枝病叶',
                    '平衡施肥，增强树势',
                    '雨后排水，降低园内湿度',
                ],
                'registered': [],
                'chem_table': [
                    {'agent': '30%苯醚甲环唑悬浮剂', 'dose': '3000倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GX-LONGAN-2025'],
                'is_verified': 0,
            },
            {
                'id': 'longan_stink_bug',
                'disease': '龙眼蝽蟓', 'alias': '荔枝蝽蟓',
                'kind': 'pest',
                'pathogen': 'Tessaratoma papillosa（荔枝蝽）',
                'part': '嫩梢、花穗、幼果',
                'severity': '中度',
                'symptoms': [
                    '成若虫刺吸嫩梢、花穗和幼果汁液',
                    '花穗受害引起落花，幼果受害大量脱落',
                    '受惊时分泌臭液灼伤皮肤',
                ],
                'occurrence': '与荔枝蝽同种，一年发生1代，3—4月产卵盛期，若虫期为主要为害期。',
                'treatment': [
                    '若虫期施药',
                    '可选用功夫乳油、敌杀死、敌百虫、醚菊酯、啶虫脒等',
                ],
                'prevention': [
                    '3—4月产卵盛期每亩释放平腹小蜂卵卡50~65张',
                    '人工摘除卵块',
                ],
                'registered': [],
                'chem_table': [
                    {'agent': '2.5%功夫乳油（高效氯氟氰菊酯）', 'dose': '1500倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '2.5%敌杀死乳油（溴氰菊酯）', 'dose': '1500倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '80%敌百虫可溶粉剂', 'dose': '1500倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '10%醚菊酯悬浮剂', 'dose': '2000倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '上述浓度出自广西壮族自治区农业农村厅技术要点，安全间隔期须以农药标签为准。',
                'image': None,
                'sources': ['GX-LONGAN-2025'],
                'is_verified': 0,
            },
            {
                'id': 'longan_scale_insect',
                'disease': '龙眼蚧壳虫', 'alias': '龙眼介壳虫',
                'kind': 'pest',
                'pathogen': '蚧总科（Coccoidea）多种',
                'part': '枝条、叶片、果实',
                'severity': '中度',
                'symptoms': [
                    '枝干和叶片上附着褐色或灰白色蚧壳',
                    '刺吸汁液导致树势衰弱、叶片发黄',
                    '分泌蜜露诱发煤污病，果面变黑',
                ],
                'occurrence': '一年发生多代，世代重叠，若虫期是防治关键期；果园郁闭时发生较重。',
                'treatment': [
                    '若虫孵化盛期施药，此时蚧壳尚未形成，防效最好',
                    '可选用螺虫乙酯、噻嗪酮＋毒死蜱、甲氰菊酯等',
                ],
                'prevention': [
                    '合理修剪，改善通风透光',
                    '剪除并销毁严重受害枝条',
                    '保护瓢虫等天敌',
                ],
                'registered': [],
                'chem_table': [
                    {'agent': '22.4%螺虫乙酯悬浮剂', 'dose': '4000倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '48%毒死蜱乳油', 'dose': '1000倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '20%甲氰菊酯乳油', 'dose': '1000倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '上述浓度出自广西壮族自治区农业农村厅技术要点，安全间隔期须以农药标签为准。',
                'image': None,
                'sources': ['GX-LONGAN-2025'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 香蕉 ----------------------------
    'banana': {
        'name': '香蕉', 'icon': '🍌', 'summary': '热带水果',
        'common_diseases': [
            {
                'id': 'banana_panama',
                'disease': '香蕉枯萎病', 'alias': '巴拿马病、镰刀菌枯萎病',
                'kind': 'disease',
                'pathogen': 'Fusarium oxysporum f. sp. cubense（尖孢镰刀菌古巴专化型）',
                'part': '根系、假茎（维管束）、叶片',
                'severity': '重度',
                'symptoms': [
                    '叶片从外围老叶开始自下而上逐渐黄化',
                    '假茎纵裂，剖开可见维管束呈黄褐至黑褐色',
                    '病株叶片由黄变褐枯萎倒挂，最后整株枯死',
                    '果实发育不良，一般不再抽蕾或抽蕾不结果',
                ],
                'occurrence': (
                    '病原在土壤和病株残体中可长期存活，通过带菌种苗、土壤和流水传播。'
                    '一旦田间发病，几乎无法根除，属毁灭性土传病害。'
                ),
                'treatment': [
                    '目前无有效化学药剂，不推荐用药「治疗」',
                    '立即隔离并挖除病株，病穴撒生石灰消毒并隔离',
                    '病区改种抗病品种或轮作非蕉类作物',
                ],
                'prevention': [
                    '严格检疫，选用无病组培苗',
                    '避免从病区调运种苗和带土植株',
                    '不串园作业，农具与鞋底消毒',
                    '增施有机肥、调节土壤pH，改善土壤微生物环境',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '本病无药可治，凡宣称「特效药根治巴拿马病」的均不可信，只能靠检疫、抗病品种与轮作。',
                'image': None,
                'sources': ['MM-BANANA-TG', 'GX-BANANA-7M'],
                'is_verified': 0,
            },
            {
                'id': 'banana_leaf_spot',
                'disease': '香蕉叶斑病', 'alias': '褐缘灰斑病、灰纹病、煤纹病',
                'kind': 'disease',
                'pathogen': '多种真菌（尾孢属、棒孢属等）',
                'part': '叶片',
                'severity': '中度',
                'symptoms': [
                    '叶片出现椭圆形褐色条斑',
                    '病斑中央灰白色、边缘深褐色，外围有黄色晕圈',
                    '多个病斑连片导致叶片大面积枯死',
                    '自下部老叶向上蔓延',
                ],
                'occurrence': '高温高湿、蕉园密植郁闭时发病重。抽蕾前后是防治关键期。',
                'treatment': [
                    '发病前或初见病斑时施药',
                    '可选用丙环唑、氟环唑、苯醚甲环唑、嘧菌酯、吡唑醚菌酯、代森锰锌、戊唑醇、啶氧菌酯等',
                    '轮换使用不同作用机理的药剂',
                ],
                'prevention': [
                    '及时割除病叶，清洁蕉园，保持通风透光',
                    '合理密植，控制氮肥用量',
                    '断蕾后7~10天套袋，套袋前喷施一次杀菌剂',
                ],
                'registered': ['丙环唑', '氟环唑', '苯醚甲环唑', '嘧菌酯', '吡唑醚菌酯',
                               '代森锰锌', '戊唑醇', '啶氧菌酯', '丙环·嘧菌酯'],
                'chem_table': [
                    {'agent': '25%丙环唑乳油', 'dose': '500~1000倍液',
                     'interval_days': '42', 'max_times': '2'},
                    {'agent': '12.5%氟环唑悬浮剂', 'dose': '500~1000倍液',
                     'interval_days': '35', 'max_times': '3'},
                    {'agent': '25%苯醚甲环唑乳油', 'dose': '2000~3000倍液',
                     'interval_days': '42', 'max_times': '3'},
                    {'agent': '25%嘧菌酯悬浮剂', 'dose': '1000~2000倍液',
                     'interval_days': '42', 'max_times': '3'},
                    {'agent': '430克/升代森锰锌悬浮剂', 'dose': '300~400倍液',
                     'interval_days': '7', 'max_times': '3'},
                ],
                'safety_note': '采收前14天停止使用化学农药；具体安全间隔期以农药标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MM-BANANA-GUIDE', 'MM-BANANA-TG', 'GX-BANANA-7M'],
                'is_verified': 0,
            },
            {
                'id': 'banana_black_sigatoka',
                'disease': '香蕉黑星病', 'alias': '香蕉黑斑病',
                'kind': 'disease',
                'pathogen': 'Guignardia musae（香蕉球座菌）',
                'part': '叶片、青果',
                'severity': '中度',
                'symptoms': [
                    '叶片和青果表面散生黑色小点',
                    '果实成熟时黑点周围呈星状开裂，严重降低商品价值',
                    '叶片病斑多时影响光合作用',
                ],
                'occurrence': '高温高湿、蕉园郁闭时发病较重；果实自抽蕾至成熟期均可受害。',
                'treatment': [
                    '发病初期开始施药',
                    '可选用吡唑醚菌酯、苯醚甲环唑、啶氧菌酯、腈菌唑等',
                ],
                'prevention': [
                    '及时清除病叶，保持蕉园通风',
                    '合理密植，控制施氮量',
                    '果实套袋减少侵染',
                ],
                'registered': ['吡唑醚菌酯', '苯醚甲环唑', '啶氧菌酯', '腈菌唑', '唑醚·锰锌', '氟菌·戊唑醇'],
                'chem_table': [
                    {'agent': '400克/升氟硅唑乳油', 'dose': '6000~8000倍液',
                     'interval_days': '28', 'max_times': '2'},
                    {'agent': '25%腈菌唑乳油', 'dose': '2500~3000倍液',
                     'interval_days': '20', 'max_times': '3~4'},
                    {'agent': '30%吡唑醚菌酯悬浮剂', 'dose': '1200~1600倍液',
                     'interval_days': '42', 'max_times': '2~3'},
                ],
                'safety_note': '采收前14天停止使用化学农药；具体安全间隔期以农药标签为准。',
                'image': None,
                'sources': ['MM-BANANA-GUIDE', 'MM-BANANA-TG', 'GX-BANANA-7M'],
                'is_verified': 0,
            },
            {
                'id': 'banana_thrips',
                'disease': '香蕉蓟马', 'alias': '',
                'kind': 'pest',
                'pathogen': '蓟马科（Thripidae），以花蓟马为主',
                'part': '花蕾、幼果（果皮）',
                'severity': '中度',
                'symptoms': [
                    '成若虫锉吸花器和幼果表皮汁液',
                    '幼果果皮出现黑褐色锉伤痕，呈条状或斑状',
                    '受害果面粗糙，商品价值明显下降',
                ],
                'occurrence': '现蕾期与幼果期是为害盛期，抽蕾期蓟马初发时即应施药。',
                'treatment': [
                    '现蕾期蓟马初发时施药，抽蕾期或发生始盛期补施一次',
                    '可选用高效氯氟氰菊酯、螺虫·噻虫啉、氯氟·吡虫啉等',
                ],
                'prevention': [
                    '断蕾后及时套袋，阻隔蓟马为害幼果',
                    '清除蕉园杂草，减少虫源',
                ],
                'registered': ['高效氯氟氰菊酯', '螺虫·噻虫啉', '氯氟·吡虫啉'],
                'chem_table': [
                    {'agent': '10%高效氯氟氰菊酯水乳剂', 'dose': '3000~5000倍液',
                     'interval_days': '28', 'max_times': '2'},
                    {'agent': '22%螺虫·噻虫啉悬浮剂', 'dose': '3000~5000倍液',
                     'interval_days': '28', 'max_times': '1'},
                    {'agent': '33%氯氟·吡虫啉悬浮剂', 'dose': '1000~2000倍液',
                     'interval_days': '28', 'max_times': '1'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；采收前14天停止使用化学农药。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MM-BANANA-GUIDE', 'MM-BANANA-TG'],
                'is_verified': 0,
            },
            {
                'id': 'banana_aphid',
                'disease': '香蕉蚜虫', 'alias': '香蕉交脉蚜',
                'kind': 'pest',
                'pathogen': '蚜科（Aphididae），以香蕉交脉蚜为主',
                'part': '嫩叶、心叶、花蕾',
                'severity': '轻度',
                'symptoms': [
                    '成若蚜群集在嫩叶和心叶刺吸汁液',
                    '叶片卷曲皱缩，生长受抑',
                    '分泌蜜露诱发煤污病',
                    '香蕉交脉蚜是香蕉束顶病的传播媒介',
                ],
                'occurrence': '发生初期即应防治，尤其要注意其传播束顶病的风险。',
                'treatment': [
                    '发生初期施药',
                    '可选用啶虫脒等',
                ],
                'prevention': [
                    '清除蕉园及周边杂草，减少虫源',
                    '保护瓢虫、草蛉等天敌',
                    '发现束顶病株及时挖除，防止蚜虫扩散传播',
                ],
                'registered': ['啶虫脒'],
                'chem_table': [
                    {'agent': '20%啶虫脒可溶液剂', 'dose': '4000~6000倍液',
                     'interval_days': '14', 'max_times': '2'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MM-BANANA-GUIDE'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 柑橘 ----------------------------
    'citrus': {
        'name': '柑橘', 'icon': '🍊', 'summary': '岭南水果',
        'common_diseases': [
            {
                'id': 'citrus_hlb',
                'disease': '柑橘黄龙病', 'alias': '柑橘黄梢病',
                'kind': 'disease',
                'pathogen': 'Candidatus Liberibacter asiaticus（亚洲韧皮部杆菌）',
                'part': '全株（叶片、新梢、果实、根系）',
                'severity': '重度',
                'symptoms': [
                    '叶片斑驳黄化——黄绿相间且不对称，与缺素引起的均匀黄化不同',
                    '新梢黄白、叶片变小变硬',
                    '果实畸形、着色不均，果蒂附近先转色，俗称「红鼻子果」',
                    '根系腐烂，树势逐年衰弱直至枯死',
                ],
                'occurrence': (
                    '由柑橘木虱传播，也可通过带病苗木和嫁接传播。目前无药可治，'
                    '属毁灭性病害，防控核心是「治木虱、除病株」。'
                ),
                'treatment': [
                    '无有效治疗药剂',
                    '发现病树先施药杀灭木虱，再整株挖除，防止木虱逃逸传播',
                    '清除病树按「一锯、二划、三涂、四包、五埋」五步法处理',
                ],
                'prevention': [
                    '种植无病苗木，严格检疫',
                    '统防统治柑橘木虱，抓住春、夏、秋梢新芽期',
                    '及时清除失管果园，以及九里香、黄皮等芸香科植物',
                    '连片果园统一时间、统一药剂防治',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '本病无药可治，切勿购买宣称能治黄龙病的药剂；关键是防住木虱、挖除病株。',
                'image': None,
                'sources': ['JX-CITRUS-2026-14', 'GX-CITRUS-2026-23', 'NN-CITRUS-2024'],
                'is_verified': 0,
            },
            {
                'id': 'citrus_canker',
                'disease': '柑橘溃疡病', 'alias': '',
                'kind': 'disease',
                'pathogen': 'Xanthomonas citri subsp. citri（柑橘黄单胞菌致病变种）',
                'part': '叶片、果实、枝梢',
                'severity': '中度',
                'symptoms': [
                    '叶片初现黄色油渍状小斑点',
                    '病斑扩大后呈褐色圆形，中央木栓化、隆起开裂',
                    '病斑周围有黄色晕圈，叶片两面均隆起（火山口状）',
                    '果实表面出现木栓化突起，严重影响商品价值',
                ],
                'occurrence': (
                    '细菌性病害，病菌随风雨、昆虫和农事操作传播，从伤口和气孔侵入。'
                    '台风暴雨后、夏梢期为发病高峰。'
                ),
                'treatment': [
                    '发病初期施药，连续施药2次，每隔10~15天用1次',
                    '可选用氢氧化铜、春雷霉素、噻唑锌、噻菌铜、春雷·喹啉铜等',
                    '保护性药剂与治疗性药剂轮换使用',
                ],
                'prevention': [
                    '选用抗病品种，种植无病苗木',
                    '控制氮肥用量，避免抽发大量晚夏梢',
                    '台风暴雨后及时喷药保护',
                    '剪除病叶病果并集中处理，农具消毒',
                ],
                'registered': ['氢氧化铜', '春雷霉素', '噻唑锌', '噻菌铜', '春雷·喹啉铜'],
                'chem_table': [
                    {'agent': '77%氢氧化铜可湿性粉剂', 'dose': '600~800倍液',
                     'interval_days': '15', 'max_times': ''},
                    {'agent': '20%噻唑锌悬浮剂', 'dose': '400~600倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '47%春雷·王铜可湿性粉剂', 'dose': '600倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；铜制剂在花期和幼果期慎用以防药害。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SC-NANBU-CITRUS', 'GX-CITRUS-2026-23'],
                'is_verified': 0,
            },
            {
                'id': 'citrus_anthracnose',
                'disease': '柑橘炭疽病', 'alias': '',
                'kind': 'disease',
                'pathogen': 'Colletotrichum gloeosporioides（胶孢炭疽菌）',
                'part': '叶片、枝梢、果实',
                'severity': '中度',
                'symptoms': [
                    '叶片出现叶尖或叶缘的褐色病斑，呈「V」形或不规则形',
                    '病斑上有黑色小点呈轮纹状排列',
                    '枝条受害形成褐色病斑，严重时上部枯死',
                    '果实受害产生褐色凹陷病斑，贮藏期易腐烂',
                ],
                'occurrence': (
                    '病菌在病枝病叶上越冬，高温多雨季节、树势衰弱时发病重。'
                    '春季和初夏为主要发病期。'
                ),
                'treatment': [
                    '发病初期施药',
                    '可选用咪鲜胺、代森锰锌、嘧菌酯、苯醚甲环唑、吡唑醚菌酯等',
                    '治疗兼保护，注意轮换用药',
                ],
                'prevention': [
                    '加强栽培管理，增强树势',
                    '及时剪除病枝病叶',
                    '雨后排水，降低园内湿度',
                    '采后浸果处理由专用保鲜剂承担，严禁采前喷施',
                ],
                'registered': ['咪鲜胺', '代森锰锌', '嘧菌酯', '苯醚甲环唑', '吡唑醚菌酯'],
                'chem_table': [
                    {'agent': '12.5%氟环唑悬浮剂', 'dose': '2000~3000倍液',
                     'interval_days': '14', 'max_times': ''},
                    {'agent': '250克/升嘧菌酯悬浮剂', 'dose': '1000倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '10%苯醚甲环唑水分散粒剂', 'dose': '800倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '70%甲基硫菌灵可湿性粉剂', 'dose': '800倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；咪鲜胺等保鲜药剂仅限采后浸果，严禁采前喷施。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SC-NANBU-CITRUS', 'GX-CITRUS-2026-23', 'NN-CITRUS-2024'],
                'is_verified': 0,
            },
            {
                'id': 'citrus_psyllid',
                'disease': '柑橘木虱', 'alias': '',
                'kind': 'pest',
                'pathogen': 'Diaphorina citri（柑橘木虱）',
                'part': '嫩梢、嫩芽',
                'severity': '重度',
                'symptoms': [
                    '若虫聚集在嫩梢上吸食汁液',
                    '嫩梢受害后萎缩、卷曲、畸形',
                    '分泌白色蜜露，诱发煤污病',
                    '是柑橘黄龙病的唯一田间传播媒介，防它等于防黄龙病',
                ],
                'occurrence': (
                    '年发生多代，以成虫在果园内越冬。春、夏、秋梢新芽期是防治关键期，'
                    '新梢长约0.5~1厘米时开始喷药，嫩梢生长期要喷2~3次，间隔7~10天。'
                ),
                'treatment': [
                    '新梢抽发期施药，嫩梢生长期喷2~3次，间隔7~10天',
                    '可选用螺虫乙酯、噻虫嗪、联苯菊酯、氟吡呋喃酮、吡丙醚等',
                    '连片果园统一时间、统一药剂防治，单家独户防治效果差',
                ],
                'prevention': [
                    '及时清除失管柑橘树及九里香、黄皮等芸香科植物',
                    '统一放梢，缩短嫩梢期，减少木虱食物',
                    '发现黄龙病树先杀灭木虱后砍除，防止木虱逃逸',
                    '果园周围芸香科植物要一并喷药，防止漏喷',
                ],
                'registered': ['螺虫乙酯', '噻虫嗪', '联苯菊酯', '氟吡呋喃酮', '吡丙醚'],
                'chem_table': [
                    {'agent': '吡虫啉、噻虫嗪、呋虫胺', 'dose': '',
                     'interval_days': '14~21', 'max_times': ''},
                    {'agent': '高效氯氟氰菊酯、联苯菊酯', 'dose': '',
                     'interval_days': '21~30', 'max_times': ''},
                    {'agent': '螺虫乙酯', 'dose': '',
                     'interval_days': '21~30', 'max_times': ''},
                ],
                'safety_note': '表中安全间隔期为南宁市农业农村局给出的参考区间，最终以所购农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'NN-CITRUS-2024', 'JX-CITRUS-2026-14', 'GX-CITRUS-2026-23'],
                'is_verified': 0,
            },
            {
                'id': 'citrus_red_mite',
                'disease': '柑橘红蜘蛛', 'alias': '柑橘全爪螨',
                'kind': 'pest',
                'pathogen': 'Panonychus citri（柑橘全爪螨）',
                'part': '叶片、果实表皮',
                'severity': '中度',
                'symptoms': [
                    '成螨、若螨在叶片上刺吸汁液',
                    '叶片出现密集的灰白色失绿小点，严重时全叶灰白',
                    '果实表皮受害呈灰白色，影响外观',
                    '高温干旱季节繁殖极快',
                ],
                'occurrence': '年发生多代，世代重叠。春、秋两季为发生高峰，高温干旱时暴发。',
                'treatment': [
                    '在低龄幼若螨始盛期开始用药',
                    '可选用联苯肼酯、乙唑螨腈、阿维菌素、矿物油、螺螨酯、乙螨唑等',
                    '红蜘蛛极易产生抗药性，必须轮换和混合使用不同作用机理的杀螨剂',
                ],
                'prevention': [
                    '保护捕食螨、草蛉等天敌',
                    '果园生草，改善生态环境',
                    '避免滥用广谱杀虫剂杀伤天敌',
                ],
                'registered': ['乙螨唑', '螺虫乙酯', '螺螨酯', '乙唑螨腈', '联肼·乙螨唑', '矿物油'],
                'chem_table': [
                    {'agent': '联苯肼酯、乙唑螨腈', 'dose': '',
                     'interval_days': '7~10', 'max_times': ''},
                    {'agent': '阿维菌素、阿维·乙螨唑', 'dose': '',
                     'interval_days': '14~20', 'max_times': ''},
                    {'agent': '矿物油', 'dose': '',
                     'interval_days': '15~20', 'max_times': ''},
                ],
                'safety_note': '阿维菌素见光易分解，傍晚施药效果较佳；矿物油高温时慎用，可能影响果面。',
                'image': None,
                'sources': ['GD-PEST-2024', 'NN-CITRUS-2024', 'GX-CITRUS-2026-23'],
                'is_verified': 0,
            },
            {
                'id': 'citrus_leafminer',
                'disease': '柑橘潜叶蛾', 'alias': '鬼画符',
                'kind': 'pest',
                'pathogen': 'Phyllocnistis citrella（柑橘潜叶蛾）',
                'part': '嫩叶、嫩梢',
                'severity': '中度',
                'symptoms': [
                    '幼虫潜入嫩叶表皮下取食叶肉，形成弯曲的银白色虫道',
                    '受害叶片卷曲、变形、硬化',
                    '虫道俗称「鬼画符」，是识别该虫的典型特征',
                    '受害伤口易诱发溃疡病',
                ],
                'occurrence': '夏、秋梢抽发期为主要为害期，秋梢抽发1.0厘米长时开始喷药。',
                'treatment': [
                    '秋梢抽发约1厘米时开始喷药，每隔7天喷1次，连续2~3次',
                    '可选用阿维菌素、四唑虫酰胺、高效氯氟氰菊酯、虱螨脲、虫螨腈等',
                    '选择傍晚喷药，可更多地杀死成虫和幼虫',
                ],
                'prevention': [
                    '统一放梢，摘除过早或过迟抽发的零星新梢',
                    '保护寄生蜂等天敌',
                ],
                'registered': ['阿维菌素', '四唑虫酰胺', '高效氯氟氰菊酯', '虱螨脲', '虫螨腈', '印楝素'],
                'chem_table': [
                    {'agent': '25%除虫脲悬浮剂', 'dose': '2000~4000倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '5%虱螨脲悬浮剂', 'dose': '1500~2500倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'GX-CITRUS-2026-23', 'NN-CITRUS-2024'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 水稻 ----------------------------
    'rice': {
        'name': '水稻', 'icon': '🌾', 'summary': '主要粮食作物',
        'common_diseases': [
            {
                'id': 'rice_blast',
                'disease': '水稻稻瘟病', 'alias': '稻热病、火烧瘟',
                'kind': 'disease',
                'pathogen': 'Magnaporthe oryzae（稻梨孢）',
                'part': '叶片（叶瘟）、穗颈（穗颈瘟）、节部（节瘟）',
                'severity': '重度',
                'symptoms': [
                    '叶片出现梭形（纺锤形）褐色病斑，中央灰白、边缘褐色',
                    '病斑两端常有褐色坏死线',
                    '穗颈受害变褐枯死，形成「白穗」',
                    '节部受害变黑，易折断',
                ],
                'occurrence': (
                    '病菌以菌丝和分生孢子在病稻草、病谷上越冬。多雨、寡照、高湿、'
                    '偏施氮肥时易流行。叶瘟在分蘖期、穗颈瘟在破口抽穗期为防治关键期。'
                ),
                'treatment': [
                    '防叶瘟于发病初期施药；防穗颈瘟于破口抽穗期前3~5天和齐穗期各施药1次',
                    '可选用三环唑、稻瘟灵、嘧菌酯、春雷霉素、肟菌·戊唑醇等',
                    '注意与其他作用机制不同的杀菌剂轮换使用',
                ],
                'prevention': [
                    '选用抗病品种，做好种子消毒处理',
                    '合理施氮，避免贪青晚熟',
                    '浅水勤灌、适时晒田',
                    '处理稻草，减少越冬菌源',
                ],
                'registered': ['三环唑', '稻瘟灵', '嘧菌酯', '春雷霉素', '肟菌·戊唑醇'],
                'chem_table': [
                    {'agent': '75%三环唑可湿性粉剂', 'dose': '25~30克/亩',
                     'interval_days': '21', 'max_times': '2'},
                    {'agent': '40%稻瘟灵可湿性粉剂', 'dose': '40克/亩',
                     'interval_days': '28', 'max_times': '2'},
                    {'agent': '20%稻瘟酰胺悬浮剂', 'dose': '50~67毫升/亩',
                     'interval_days': '21', 'max_times': '3'},
                    {'agent': '75%肟菌·戊唑醇水分散粒剂', 'dose': '11.25克/亩',
                     'interval_days': '21', 'max_times': '2'},
                    {'agent': '60%三环·稻瘟灵可湿性粉剂', 'dose': '60~70克/亩',
                     'interval_days': '28', 'max_times': '2'},
                ],
                'safety_note': '三环唑在水稻上安全间隔期21~28天、每季最多2次，务必遵守；具体以农药标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'SD-SHAODONG-2024', 'ICAMA'],
                'is_verified': 0,
            },
            {
                'id': 'rice_sheath_blight',
                'disease': '水稻纹枯病', 'alias': '云纹病、花脚秆',
                'kind': 'disease',
                'pathogen': 'Rhizoctonia solani（立枯丝核菌）',
                'part': '叶鞘、叶片',
                'severity': '重度',
                'symptoms': [
                    '叶鞘近水面处出现暗绿色水渍状病斑',
                    '病斑扩大成云纹状，边缘褐色、中央灰白色',
                    '病斑向上蔓延至叶片，严重时植株倒伏',
                    '潮湿时病部可见白色菌丝和褐色菌核',
                ],
                'occurrence': (
                    '病菌以菌核在土壤中越冬，高温高湿、密植、偏施氮肥的田块发病重。'
                    '水稻分蘖盛期封行时防治一次，病丛率达20%时需再次防治。'
                ),
                'treatment': [
                    '分蘖末期至孕穗抽穗期密切关注，发病初期及时防治',
                    '可选用噻呋酰胺、井冈霉素、苯甲·丙环唑、丙环·嘧菌酯、肟菌·戊唑醇等',
                    '严重田块隔10~15天再次施药',
                ],
                'prevention': [
                    '合理密植，改善通风透光',
                    '浅水勤灌、适时晒田，降低田间湿度',
                    '控制氮肥用量，增施磷钾肥',
                    '打捞菌核，减少越冬菌源',
                ],
                'registered': ['噻呋酰胺', '井冈霉素', '苯甲·丙环唑', '丙环·嘧菌酯', '肟菌·戊唑醇'],
                'chem_table': [
                    {'agent': '30%苯醚甲·丙环唑乳油', 'dose': '6.0~9.0克/亩',
                     'interval_days': '15', 'max_times': '2'},
                    {'agent': '24%噻呋酰胺悬浮剂', 'dose': '4.8克/亩',
                     'interval_days': '15', 'max_times': '2'},
                    {'agent': '43%戊唑醇悬浮剂', 'dose': '8.5毫升/亩',
                     'interval_days': '28', 'max_times': '2'},
                    {'agent': '75%肟菌·戊唑醇水分散粒剂', 'dose': '11.25克/亩',
                     'interval_days': '21', 'max_times': '2'},
                ],
                'safety_note': '具体安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024'],
                'is_verified': 0,
            },
            {
                'id': 'rice_planthopper',
                'disease': '稻飞虱', 'alias': '褐飞虱、白背飞虱',
                'kind': 'pest',
                'pathogen': '褐飞虱 Nilaparvata lugens / 白背飞虱 Sogatella furcifera',
                'part': '稻株基部（茎秆、叶鞘）',
                'severity': '重度',
                'symptoms': [
                    '成虫、若虫聚集在稻株基部刺吸汁液',
                    '叶片自下而上发黄枯死，严重时成片倒伏，俗称「冒穿」',
                    '茎秆基部可见灰褐色虫蜕',
                    '分泌蜜露诱发煤污，并可传播病毒病',
                ],
                'occurrence': (
                    '具迁飞性，随季风远距离迁入。分蘖盛期百丛虫量达500头、'
                    '穗期常规稻百丛1000头（杂交稻1500头）时达防治指标。'
                ),
                'treatment': [
                    '若虫盛孵期至低龄若虫高峰期施药，重点喷施稻株中下部',
                    '可选用三氟苯嘧啶、氟啶虫胺腈、呋虫胺、烯啶虫胺、吡蚜酮等',
                    '保持浅水层可提高药效',
                ],
                'prevention': [
                    '选用抗（耐）虫品种',
                    '清除田边杂草，减少虫源',
                    '合理密植，改善通风',
                    '保护利用蜘蛛等天敌，避免滥用广谱杀虫剂',
                ],
                'registered': ['三氟苯嘧啶', '氟啶虫胺腈', '呋虫胺', '烯啶虫胺', '毒死蜱',
                               '烯啶·吡蚜酮', '吡蚜·呋虫胺', '金龟子绿僵菌CQMa421'],
                'chem_table': [
                    {'agent': '20%及以上含量呋虫胺', 'dose': '10克/亩',
                     'interval_days': '14', 'max_times': '2'},
                    {'agent': '25%及以上含量吡蚜酮', 'dose': '6~7.5克/亩',
                     'interval_days': '14', 'max_times': '2'},
                    {'agent': '25%及以上含量噻虫嗪', 'dose': '4克/亩',
                     'interval_days': '14', 'max_times': '2'},
                    {'agent': '10%三氟苯嘧啶（褐飞虱）', 'dose': '1.6克/亩',
                     'interval_days': '14', 'max_times': '1'},
                ],
                'safety_note': '吡蚜酮在部分登记中每季最多1次、噻虫嗪为28天，须以农药标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024', 'PT-LICHENG-MANUAL'],
                'is_verified': 0,
            },
            {
                'id': 'rice_leaf_folder',
                'disease': '稻纵卷叶螟', 'alias': '刮青虫、白叶虫',
                'kind': 'pest',
                'pathogen': 'Cnaphalocrocis medinalis（稻纵卷叶螟）',
                'part': '叶片',
                'severity': '重度',
                'symptoms': [
                    '幼虫吐丝将叶片纵卷成筒状',
                    '在卷叶内取食叶肉，残留白色表皮，形成「白叶」',
                    '严重时全田一片枯白，影响光合作用与灌浆',
                ],
                'occurrence': (
                    '具迁飞性。分蘖及圆秆拔节期每百丛有50个束尖、'
                    '穗期亩平幼虫超过1万头时达防治指标。1、2龄幼虫高峰期是施药适期。'
                ),
                'treatment': [
                    '1、2龄幼虫高峰期施药',
                    '可选用乙基多杀菌素、多杀霉素、茚虫威、甲氨基阿维菌素苯甲酸盐、四唑虫酰胺、苏云金杆菌等',
                ],
                'prevention': [
                    '合理施肥，避免贪青迟熟',
                    '保护稻田天敌（赤眼蜂、蜘蛛等）',
                    '利用性诱剂监测与诱杀成虫',
                ],
                'registered': ['乙基多杀菌素', '多杀霉素', '茚虫威', '甲氨基阿维菌素苯甲酸盐',
                               '四唑虫酰胺', '苏云金杆菌'],
                'chem_table': [
                    {'agent': '20%氯虫苯甲酰胺悬浮剂', 'dose': '2克/亩',
                     'interval_days': '15', 'max_times': '2'},
                    {'agent': '1.8%阿维菌素乳油', 'dose': '30~40毫升/亩',
                     'interval_days': '7~14', 'max_times': '2'},
                    {'agent': '15%茚虫威悬浮剂', 'dose': '1.8克/亩',
                     'interval_days': '30', 'max_times': '2'},
                ],
                'safety_note': '不同来源的同一药剂安全间隔期略有差异，务必以农药标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024', 'PT-LICHENG-MANUAL', 'MDJ-INTERVAL'],
                'is_verified': 0,
            },
            {
                'id': 'rice_stem_borer',
                'disease': '水稻螟虫', 'alias': '二化螟、三化螟',
                'kind': 'pest',
                'pathogen': '二化螟 Chilo suppressalis / 三化螟 Scirpophaga incertulas',
                'part': '茎秆',
                'severity': '重度',
                'symptoms': [
                    '幼虫蛀入稻茎取食，造成枯心苗',
                    '孕穗期受害形成枯孕穗，抽穗后形成白穗',
                    '茎秆上有蛀孔和虫粪，断面可见幼虫',
                ],
                'occurrence': '分蘖期二化螟枯鞘株率达3.5%时达防治指标；蚁螟盛孵期为施药适期。',
                'treatment': [
                    '蚁螟盛孵期施药，防止幼虫蛀入茎秆',
                    '可选用甲氨基阿维菌素苯甲酸盐、乙基多杀菌素、阿维菌素、四唑虫酰胺、溴氰虫酰胺、苏云金杆菌等',
                ],
                'prevention': [
                    '冬季清除稻桩和稻草，减少越冬虫源',
                    '灌水灭蛹（春季耕沤）',
                    '利用性诱剂诱杀成虫',
                    '保护赤眼蜂等天敌',
                ],
                'registered': ['甲氨基阿维菌素苯甲酸盐', '乙基多杀菌素', '阿维菌素', '四唑虫酰胺',
                               '溴氰虫酰胺', '多杀霉素', '毒死蜱', '印楝素'],
                'chem_table': [
                    {'agent': '20%氯虫苯甲酰胺悬浮剂', 'dose': '2克/亩',
                     'interval_days': '15', 'max_times': '2'},
                    {'agent': '200克/升氯虫苯甲酰胺悬浮剂（三化螟）', 'dose': '5~10毫升/亩',
                     'interval_days': '7', 'max_times': '2'},
                    {'agent': '20%三唑磷乳油（三化螟）', 'dose': '120~150毫升/亩',
                     'interval_days': '30', 'max_times': '2'},
                ],
                'safety_note': '具体安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024', 'PT-LICHENG-MANUAL'],
                'is_verified': 0,
            },
            {
                'id': 'rice_false_smut',
                'disease': '稻曲病', 'alias': '青粉病、谷花病',
                'kind': 'disease',
                'pathogen': 'Ustilaginoidea virens（稻绿核菌）',
                'part': '穗部谷粒',
                'severity': '中度',
                'symptoms': [
                    '仅在穗部发病，谷粒被菌丝块包裹',
                    '病粒膨大呈墨绿色或黑绿色粉状孢子球',
                    '病穗空秕率增加，影响产量与品质',
                    '病粒含有毒素，人畜食用有害',
                ],
                'occurrence': (
                    '病菌以菌核在土壤中越冬。水稻破口前5~7天施药最重要，'
                    '如遇适宜发病天气，7天后需第2次施药。'
                ),
                'treatment': [
                    '水稻破口抽穗前5~7天施药，隔7~10天再施一次',
                    '可选用戊唑醇、肟菌·戊唑醇、苯甲·丙环唑、井冈·蜡芽菌等',
                ],
                'prevention': [
                    '选用抗病品种，做好种子消毒',
                    '避免偏施氮肥、迟施氮肥',
                    '及时摘除病穗并集中处理',
                ],
                'registered': ['戊唑醇', '肟菌·戊唑醇', '苯甲·丙环唑', '井冈·蜡芽菌'],
                'chem_table': [
                    {'agent': '30%苯醚甲·丙环唑乳油', 'dose': '6.0~9.0克/亩',
                     'interval_days': '15', 'max_times': '2'},
                    {'agent': '43%戊唑醇悬浮剂', 'dose': '8.5毫升/亩',
                     'interval_days': '28', 'max_times': '2'},
                ],
                'safety_note': '具体安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 茶叶 ----------------------------
    'tea': {
        'name': '茶叶', 'icon': '🍵', 'summary': '广东名茶',
        'common_diseases': [
            {
                'id': 'tea_leafhopper',
                'disease': '茶小绿叶蝉', 'alias': '假眼小绿叶蝉、浮尘子',
                'kind': 'pest',
                'pathogen': 'Empoasca onukii（茶小绿叶蝉）',
                'part': '新梢、嫩叶、芽叶',
                'severity': '重度',
                'symptoms': [
                    '新梢嫩叶出现褐色斑点',
                    '叶缘、叶尖卷曲焦枯，俗称「焦边」',
                    '芽叶生长迟缓、节间缩短',
                    '虫量高时茶园一片焦黄，产量与品质骤降',
                ],
                'occurrence': (
                    '华南茶区重点防治对象。5—6月、8—9月为若虫盛发期，'
                    '夏茶百叶虫口5~6头、秋茶超过10头时达防治指标。'
                ),
                'treatment': [
                    '适时分批勤采，带走部分卵、若虫和成虫，压低虫口基数',
                    '春茶结束修剪后每亩悬挂25张诱虫板',
                    '可选用氟啶虫酰胺、双丙环虫酯、四唑虫酰胺、噻嗪酮、噻虫嗪、虫螨腈、呋虫胺、吡蚜酮、丁醚脲、茚虫威及苦参碱、印楝素等',
                ],
                'prevention': [
                    '维护茶园周边自然植被，间作显花草本和木本植物',
                    '秋冬季在园边适度自然留草，为蜘蛛类、寄生蜂类天敌提供庇护场所',
                    '生产季节清除茶行间杂草，控制虫口基数',
                ],
                'registered': ['氟啶虫酰胺', '双丙环虫酯', '四唑虫酰胺', '噻嗪酮', '噻虫嗪',
                               '虫螨腈', '呋虫胺', '吡蚜酮', '丁醚脲', '茚虫威', '苦参碱', '印楝素'],
                'chem_table': [
                    {'agent': '50%丁醚脲悬浮剂', 'dose': '2000倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '2.5%联苯菊酯乳油', 'dose': '1500倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '茶叶安全间隔期要求严格，务必以农药标签为准；同一种药在每季作物中最多使用2次。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MOA-TEA-2023', 'GX-TEA-2026-7', 'GD-TEA-STD'],
                'is_verified': 0,
            },
            {
                'id': 'tea_anthracnose',
                'disease': '茶炭疽病', 'alias': '',
                'kind': 'disease',
                'pathogen': '炭疽菌属（Colletotrichum spp.）',
                'part': '成叶、老叶',
                'severity': '中度',
                'symptoms': [
                    '老叶出现半圆形或不规则形褐色病斑',
                    '病斑上生黑色小点，常呈轮纹状排列',
                    '病叶易脱落，树势衰退',
                    '多在5—6月、8—9月发生',
                ],
                'occurrence': '高温高湿、茶园排水不良时发病较重；5—6月、8—9月为两个发病高峰。',
                'treatment': [
                    '发病初期施药，间隔7~10天，连喷2~3次',
                    '可选用苯醚甲环唑、吡唑醚菌酯、啶氧菌酯、百菌清、代森锌、几丁聚糖等',
                ],
                'prevention': [
                    '新建茶园选用抗性健壮的种苗',
                    '平衡施肥，增强茶树抗病能力',
                    '及时剪除病枝，适时采摘',
                    '秋末用石硫合剂封园',
                ],
                'registered': ['苯醚甲环唑', '吡唑醚菌酯', '啶氧菌酯', '百菌清', '代森锌', '几丁聚糖'],
                'chem_table': [
                    {'agent': '75%百菌清可湿性粉剂', 'dose': '800倍液',
                     'interval_days': '', 'max_times': ''},
                    {'agent': '25%咪鲜胺乳油', 'dose': '1000~1500倍液',
                     'interval_days': '', 'max_times': ''},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；采茶期用药须格外谨慎。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MOA-TEA-2023', 'GX-TEA-2026-7', 'YA-TEA-2025'],
                'is_verified': 0,
            },
            {
                'id': 'tea_looper',
                'disease': '茶尺蠖', 'alias': '拱拱虫、量尺虫',
                'kind': 'pest',
                'pathogen': '灰茶尺蠖 Ectropis grisescens / 茶尺蠖 Ectropis obliqua',
                'part': '叶片',
                'severity': '中度',
                'symptoms': [
                    '幼虫取食叶片，幼龄期咬食叶肉呈网状',
                    '3龄后可食尽全叶，仅留主脉和叶柄',
                    '严重时茶园叶片被食光，树势衰弱',
                ],
                'occurrence': (
                    '防治适期宜掌握在第1、2代或5、6代的低龄幼虫期；'
                    '幼虫数超过每平方米7头时达防治指标。'
                ),
                'treatment': [
                    '低龄幼虫期施药',
                    '可选用除虫脲、高效氯氟氰菊酯、甲氰菊酯、联苯菊酯，以及苏云金杆菌、甘蓝夜蛾核型多角体病毒、茶尺蠖病毒制剂、苦参碱等',
                ],
                'prevention': [
                    '结合秋季中耕施肥，翻耕土壤，降低土中越冬虫蛹成活率',
                    '安装诱虫灯，羽化高峰期开灯诱杀成虫',
                    '成虫羽化期放置性信息素诱捕器诱杀雄虫',
                    '保护和利用茶尺蠖绒茧蜂、单白绵绒茧蜂等天敌',
                ],
                'registered': ['除虫脲', '高效氯氟氰菊酯', '甲氰菊酯', '苏云金杆菌',
                               '甘蓝夜蛾核型多角体病毒', '苦参碱'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MOA-TEA-2023', 'YA-TEA-2025', 'GD-TEA-STD'],
                'is_verified': 0,
            },
            {
                'id': 'tea_tussock_moth',
                'disease': '茶毛虫', 'alias': '茶毒蛾',
                'kind': 'pest',
                'pathogen': 'Euproctis pseudoconspersa（茶毛虫）',
                'part': '叶片',
                'severity': '中度',
                'symptoms': [
                    '幼虫群集取食叶片',
                    '体表具毒毛，接触人体皮肤引起红肿痒痛',
                    '严重时连片茶园叶片被食光',
                ],
                'occurrence': '每100米茶行有茶毛虫卵块5个时达防治指标，幼虫3龄期前为防治适期。',
                'treatment': [
                    '低龄幼虫期施药',
                    '可选用联苯菊酯、氯氰菊酯，以及苏云金杆菌、茶毛虫病毒制剂、印楝素、苦参碱等',
                ],
                'prevention': [
                    '利用幼虫群集习性人工捕杀',
                    '常发茶园安装诱虫灯，羽化高峰期开灯诱杀成虫',
                    '放置性信息素诱捕器诱捕雄虫',
                ],
                'registered': ['联苯菊酯', '氯氰菊酯', '苏云金杆菌', '印楝素', '苦参碱'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准；采茶时注意避免接触幼虫毒毛。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MOA-TEA-2023', 'YA-TEA-2025'],
                'is_verified': 0,
            },
            {
                'id': 'tea_blister_blight',
                'disease': '茶饼病', 'alias': '',
                'kind': 'disease',
                'pathogen': 'Exobasidium vexans（坏损外担菌）',
                'part': '嫩叶、新梢',
                'severity': '中度',
                'symptoms': [
                    '嫩叶正面出现淡黄色水渍状斑点',
                    '病斑背面隆起呈灰白色或粉红色饼状',
                    '病叶扭曲变形，易脱落',
                    '芽梢发病率超过35%时达防治指标',
                ],
                'occurrence': '春、秋季发病期，高湿多雾、日照少的茶园发病重。',
                'treatment': [
                    '发病初期喷施多抗霉素、苯丙烯菌酮等2~3次，喷药间隔7~10天',
                    '可选用三唑酮、苯醚甲环唑、烯唑醇、戊唑醇、氟硅唑、嘧菌酯、吡唑醚菌酯、氢氧化铜等',
                ],
                'prevention': [
                    '适时分批勤采，选择适宜时期修剪，清除枯枝，改善茶园通风透光性',
                    '平衡施肥，增强茶树抗病能力',
                    '秋末用石硫合剂封园',
                ],
                'registered': ['多抗霉素', '代森锌', '三唑酮', '苯醚甲环唑', '嘧菌酯', '吡唑醚菌酯'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-TEA-STD', 'MOA-TEA-2023', 'YA-TEA-2025'],
                'is_verified': 0,
            },
            {
                'id': 'tea_black_spiny_whitefly',
                'disease': '茶黑刺粉虱', 'alias': '',
                'kind': 'pest',
                'pathogen': 'Aleurocanthus spiniferus（黑刺粉虱）',
                'part': '叶片（背面）',
                'severity': '中度',
                'symptoms': [
                    '若虫固定在叶背刺吸汁液',
                    '分泌蜜露诱发煤污病，叶面覆盖黑色霉层',
                    '影响光合作用，芽叶生长受抑',
                ],
                'occurrence': '卵孵化盛末期、春茶后及霜降前后重点防治第1代和越冬代。',
                'treatment': [
                    '第1代幼虫孵化盛期喷施溴氰菊酯等药剂',
                    '越冬代成虫羽化始盛期使用全降解诱虫板诱杀成虫，每亩挂25块',
                    '可选用联苯菊酯、溴氰菊酯、联苯·噻虫嗪等',
                ],
                'prevention': [
                    '加强茶园管理，疏枝清园，促进通风透光',
                    '秋季在越冬虫口偏高田块用石硫合剂、矿物油封园',
                ],
                'registered': ['联苯菊酯', '溴氰菊酯', '联苯·噻虫嗪'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MOA-TEA-2023', 'GD-TEA-STD'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 蔬菜 ----------------------------
    'vegetable': {
        'name': '蔬菜', 'icon': '🥬', 'summary': '时令蔬菜',
        'common_diseases': [
            {
                'id': 'vegetable_downy_mildew',
                'disease': '蔬菜霜霉病', 'alias': '跑马干',
                'kind': 'disease',
                'pathogen': '卵菌（霜霉科，如古巴假霜霉 Pseudoperonospora cubensis）',
                'part': '叶片',
                'severity': '中度',
                'symptoms': [
                    '叶面出现多角形黄色病斑（受叶脉限制）',
                    '叶背病斑处生紫灰色或灰白色霉层',
                    '病斑扩展连片导致叶片枯黄',
                    '自下部老叶向上蔓延',
                ],
                'occurrence': '低温高湿、昼夜温差大、叶面结露时易流行；棚室栽培尤为严重。',
                'treatment': [
                    '发病前或初期用药',
                    '可选用嘧菌酯、吡唑醚菌酯、烯酰吗啉、霜霉威盐酸盐、丙森锌、氟菌·霜霉威、精甲霜·锰锌等',
                    '注意叶背均匀着药，交替用药防止抗性',
                ],
                'prevention': [
                    '合理密植改善通风',
                    '控制棚内湿度、避免叶面结露',
                    '及时摘除病叶并带出田外',
                    '雨季前预防用药',
                ],
                'registered': ['嘧菌酯', '吡唑醚菌酯', '烯酰吗啉', '霜霉威盐酸盐', '丙森锌',
                               '氟菌·霜霉威', '精甲霜·锰锌', '乙磷铝'],
                'chem_table': [
                    {'agent': '40%三乙膦酸铝可湿性粉剂', 'dose': '235~470克/亩',
                     'interval_days': '7', 'max_times': '3'},
                    {'agent': '70%丙森锌可湿性粉剂（大白菜）', 'dose': '130~160克/亩',
                     'interval_days': '21', 'max_times': '3'},
                    {'agent': '687.5克/升氟菌·霜霉威悬浮剂（大白菜）', 'dose': '60~75毫升/亩',
                     'interval_days': '5', 'max_times': '3'},
                ],
                'safety_note': '不同蔬菜的安全间隔期差异很大（5~21天），务必按所购农药在对应蔬菜上的标签标注执行。',
                'image': None,
                'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'MDJ-INTERVAL'],
                'is_verified': 0,
            },
            {
                'id': 'vegetable_diamondback_moth',
                'disease': '小菜蛾', 'alias': '吊丝虫、两头尖',
                'kind': 'pest',
                'pathogen': 'Plutella xylostella（小菜蛾）',
                'part': '叶片',
                'severity': '重度',
                'symptoms': [
                    '幼虫取食叶肉，留下透明表皮形成「开天窗」状孔洞',
                    '低龄幼虫潜叶取食，2龄后退到叶背为害',
                    '严重时叶片成网状，失去商品价值',
                    '受惊时幼虫吐丝下垂',
                ],
                'occurrence': (
                    '十字花科蔬菜最重要害虫，年发生多代、世代重叠，抗药性极强。'
                    '低龄幼虫发生期是施药适期。'
                ),
                'treatment': [
                    '低龄幼虫发生期施药',
                    '可选用茚虫威、乙基多杀菌素、甲氨基阿维菌素苯甲酸盐、虫螨腈、溴氰虫酰胺、苏云金杆菌等',
                    '必须轮换使用不同作用机理的药剂，否则极易产生抗性',
                ],
                'prevention': [
                    '清洁田园，及时清除残株落叶',
                    '合理安排茬口，避免十字花科连作',
                    '使用防虫网覆盖，阻隔成虫产卵',
                    '利用性诱剂诱杀成虫',
                ],
                'registered': ['茚虫威', '乙基多杀菌素', '甲氨基阿维菌素苯甲酸盐', '虫螨腈',
                               '溴氰虫酰胺', '溴虫氟苯双酰胺', '苏云金杆菌'],
                'chem_table': [
                    {'agent': '5%氟啶脲乳油', 'dose': '60~80毫升/亩',
                     'interval_days': '7', 'max_times': '3'},
                    {'agent': '1%甲氨基阿维菌素苯甲酸盐乳油', 'dose': '15~20毫升/亩',
                     'interval_days': '3', 'max_times': '2'},
                    {'agent': '0.3%印楝素乳油', 'dose': '60~90毫升/亩',
                     'interval_days': '5', 'max_times': '3'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准；小菜蛾抗药性强，切忌连续使用同一药剂。',
                'image': None,
                'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'MDJ-INTERVAL'],
                'is_verified': 0,
            },
            {
                'id': 'vegetable_aphid',
                'disease': '蔬菜蚜虫', 'alias': '腻虫、蜜虫',
                'kind': 'pest',
                'pathogen': '蚜科（Aphididae）多种，如桃蚜、萝卜蚜',
                'part': '嫩梢、嫩叶、叶背',
                'severity': '中度',
                'symptoms': [
                    '成若蚜群集在嫩梢嫩叶刺吸汁液',
                    '叶片卷曲皱缩，植株生长受抑',
                    '分泌蜜露诱发煤污病',
                    '可传播多种蔬菜病毒病',
                ],
                'occurrence': '春、秋季为发生高峰，高温干旱或保护地栽培时发生重。',
                'treatment': [
                    '发生初期施药，重点喷施叶片背面',
                    '可选用氟啶虫胺腈、噻虫嗪、吡蚜酮、氯氰菊酯、鱼藤酮、苦参碱等',
                    '注意保护天敌，避免滥用广谱杀虫剂',
                ],
                'prevention': [
                    '覆盖银灰地膜驱避有翅蚜',
                    '悬挂黄板诱杀',
                    '保护瓢虫、草蛉等天敌',
                    '清除田间及周边杂草',
                ],
                'registered': ['氟啶虫胺腈', '噻虫嗪', '吡蚜酮', '氯氰菊酯', '鱼藤酮', '苦参碱'],
                'chem_table': [
                    {'agent': '10%吡虫啉可湿性粉剂（甘蓝、萝卜）', 'dose': '',
                     'interval_days': '7', 'max_times': '2'},
                    {'agent': '5%啶虫脒乳油', 'dose': '',
                     'interval_days': '7~14', 'max_times': ''},
                ],
                'safety_note': '表中安全间隔期取自牡丹江市农业农村局公布的登记数据，实际以农药标签为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'MDJ-INTERVAL'],
                'is_verified': 0,
            },
            {
                'id': 'vegetable_anthracnose',
                'disease': '蔬菜炭疽病', 'alias': '',
                'kind': 'disease',
                'pathogen': '炭疽菌属（Colletotrichum spp.）',
                'part': '叶片、茎、果实',
                'severity': '中度',
                'symptoms': [
                    '叶片出现近圆形褐色病斑，中央灰白、边缘深褐',
                    '病斑上生黑色小点呈轮纹状排列',
                    '茎部受害形成凹陷褐色病斑',
                    '果实受害产生凹陷病斑，潮湿时现粉红色黏液',
                ],
                'occurrence': '高温高湿、多雨季节发病重；连作地块发病早且重。',
                'treatment': [
                    '发病前或初期用药',
                    '可选用吡唑醚菌酯、咪锰·三环唑、唑醚·代森联、吡唑·甲硫灵等',
                ],
                'prevention': [
                    '实行轮作，避免连作',
                    '及时清除病叶病果',
                    '合理密植改善通风',
                    '增施有机肥，避免偏施氮肥',
                ],
                'registered': ['吡唑醚菌酯', '咪锰·三环唑', '唑醚·代森联', '吡唑·甲硫灵'],
                'chem_table': [
                    {'agent': '250克/升吡唑醚菌酯乳油（白菜）', 'dose': '30~50毫升/亩',
                     'interval_days': '14', 'max_times': '3'},
                    {'agent': '60%唑醚·代森联水分散粒剂（大白菜）', 'dose': '40~60克/亩',
                     'interval_days': '5', 'max_times': '2'},
                ],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL'],
                'is_verified': 0,
            },
            {
                'id': 'vegetable_powdery_mildew',
                'disease': '蔬菜白粉病', 'alias': '',
                'kind': 'disease',
                'pathogen': '白粉菌（Erysiphales）',
                'part': '叶片、茎、叶柄',
                'severity': '中度',
                'symptoms': [
                    '叶面出现白色粉状霉斑，逐渐扩大连片',
                    '后期霉层变灰褐，叶片变黄枯死',
                    '植株长势衰弱，果实发育不良',
                ],
                'occurrence': '温暖干燥与高湿交替、昼夜温差大时易流行；保护地栽培发病重。',
                'treatment': [
                    '发病初期施药',
                    '可选用吡唑醚菌酯、百菌清、嘧啶核苷类抗菌素等',
                    '瓜类与茄类可选用氟硅唑、氟菌唑、氯氟醚菌唑等',
                ],
                'prevention': [
                    '合理密植，改善通风透光',
                    '控制棚内湿度，避免干湿交替剧烈',
                    '增施磷钾肥，提高抗病力',
                ],
                'registered': ['吡唑醚菌酯', '百菌清', '嘧啶核苷类抗菌素'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准。',
                'image': None,
                'sources': ['GD-PEST-2024'],
                'is_verified': 0,
            },
            {
                'id': 'vegetable_soft_rot',
                'disease': '蔬菜软腐病', 'alias': '烂菜头、水烂',
                'kind': 'disease',
                'pathogen': '欧文氏菌 / 果胶杆菌（Erwinia / Pectobacterium）',
                'part': '茎基部、叶柄、肉质根',
                'severity': '重度',
                'symptoms': [
                    '茎基部或叶柄出现水渍状病斑',
                    '组织迅速软化腐烂，具恶臭味',
                    '外叶萎蔫倒伏，轻拔即断',
                    '潮湿时病部溢出菌脓',
                ],
                'occurrence': (
                    '细菌性病害。病菌从伤口（虫伤、机械伤、中耕伤）侵入，'
                    '高温高湿、雨后积水、虫害重的田块发病重。'
                ),
                'treatment': [
                    '发病前或初期用药',
                    '可选用噻唑锌、氯溴异氰尿酸、噻菌铜、噻森铜、春雷霉素等',
                ],
                'prevention': [
                    '高垄栽培，雨后及时排水，避免田间积水',
                    '及时防治地下害虫和食叶害虫，减少伤口',
                    '操作时避免造成机械损伤',
                    '发现病株立即拔除并带出田外，病穴撒石灰',
                ],
                'registered': ['噻唑锌', '氯溴异氰尿酸', '噻菌铜', '噻森铜', '春雷霉素'],
                'chem_table': [],
                'safety_note': '安全间隔期以农药标签标注为准；软腐病为细菌性病害，需选用杀细菌药剂。',
                'image': None,
                'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL'],
                'is_verified': 0,
            },
        ],
    },

    # ---------------------------- 水产养殖 ----------------------------
    'aquatic': {
        'name': '水产养殖', 'icon': '🐟', 'summary': '鱼虾蟹贝',
        'common_diseases': [
            {
                'id': 'aquatic_bacterial_septicemia',
                'disease': '淡水鱼细菌性败血症', 'alias': '暴发性出血病、败血病',
                'kind': 'disease',
                'pathogen': '嗜水气单胞菌（Aeromonas hydrophila）、温和气单胞菌等多种细菌',
                'part': '全身（体表、鳃、肝、肾、腹腔）',
                'severity': '重度',
                'symptoms': [
                    '病鱼离群缓慢游动，反应迟钝',
                    '体表充血，鳍条基部和腹部出现红斑',
                    '眼球突出、肛门红肿',
                    '腹腔积水，肝脏充血肿大，鳃、肝、肾颜色变淡呈花斑状',
                    '短时间内大量死亡',
                ],
                'occurrence': (
                    '是造成淡水鱼损失最大的一种细菌性疾病。水温攀升、密度过大、'
                    '水质恶化（氨氮与亚硝酸盐超标）时高发，鲢、鳙、鲫最易感。'
                ),
                'treatment': [
                    '晴天全池连泼两次国标渔药消毒剂（溴氯海因、聚维酮碘或含氯消毒剂），每天一次隔天泼洒',
                    '同时拌饲投喂恩诺沙星粉或氟苯尼考粉等水产用抗菌药，连用4~6天；病情严重者适当延长',
                    '病死鱼打捞深埋，不得乱弃',
                ],
                'prevention': [
                    '放苗前彻底清塘消毒',
                    '控制放养密度，不超载养殖',
                    '日常每半月泼洒国标渔药消毒剂，降低单位水体致病菌数量',
                    '定期检测水质氨氮与亚硝酸盐，及时换水增氧',
                    '投喂优质配合饲料，定期添加维生素C增强体质',
                ],
                'registered': ['溴氯海因粉（水产用）', '聚维酮碘溶液（水产用）', '生石灰',
                               '恩诺沙星粉（水产用）', '氟苯尼考粉（水产用）', '盐酸多西环素粉（水产用）'],
                'chem_table': [],
                'safety_note': '须选用标注「水产用」的兽药，并按商品说明书用量使用；严禁使用禁用渔药。',
                'image': None,
                'sources': ['MOA-AQUATIC-FORECAST', 'GY-AQUATIC-2026-5', 'YC-AQUATIC-AUTUMN'],
                'is_verified': 0,
            },
            {
                'id': 'aquatic_wssv',
                'disease': '对虾白斑综合征', 'alias': '白斑病、WSSV',
                'kind': 'disease',
                'pathogen': '白斑综合征病毒（White Spot Syndrome Virus, WSSV）',
                'part': '全身（甲壳、鳃、肝胰腺）',
                'severity': '重度',
                'symptoms': [
                    '虾体甲壳内侧（尤其头胸甲）出现白色斑点，直径一般小于3毫米或连成片',
                    '虾体发红、空肠空胃',
                    '游塘、反应迟钝，摄食减少',
                    '短期内出现高比例死亡',
                ],
                'occurrence': (
                    '主要危害对虾、克氏原螯虾、中华绒螯蟹等甲壳类。'
                    '水温升高（夏季）、密度过高、水质剧变时高发，可经水体与摄食病虾传播。'
                ),
                'treatment': [
                    '目前无特效治疗药物，以预防和应急处置为主',
                    '发病池塘立即隔离，排换水，加强增氧',
                    '全池泼洒碘制剂消毒',
                    '病死虾及时捞出处理，防止健康虾摄食感染',
                ],
                'prevention': [
                    '选用无特定病原（SPF）虾苗，苗种检疫',
                    '养殖用水严格消毒，进水口设置过滤与消杀',
                    '虾池合理混养鱼类，摄食病虾阻断病毒传播路径',
                    '控制放养密度，避免应激；定期使用芽孢杆菌、EM菌等微生态制剂调优水质',
                    '定期检测，发病初期可投喂国标渔药抗病毒药物',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '病毒病无药可治，市售「白斑特效药」均不可信；关键在于虾苗检疫与水质管理。',
                'image': None,
                'sources': ['MOA-AQUATIC-FORECAST', 'GY-AQUATIC-2026-5', 'YC-AQUATIC-AUTUMN'],
                'is_verified': 0,
            },
            {
                'id': 'aquatic_grass_carp_hemorrhage',
                'disease': '草鱼出血病', 'alias': '草鱼红身病',
                'kind': 'disease',
                'pathogen': '草鱼呼肠孤病毒（Grass Carp Reovirus, GCRV）',
                'part': '全身（鳍、鳃盖、肌肉、肠道）',
                'severity': '重度',
                'symptoms': [
                    '主要危害草鱼及青鱼鱼种',
                    '分为红鳍红鳃盖型、红肌肉型和肠炎型',
                    '病鱼鳍基或鳃盖出血',
                    '解剖可见肌肉出血呈鲜红色、肠壁充血、肝脾充血',
                ],
                'occurrence': '水温25~30℃时易流行，主要危害鱼种阶段。',
                'treatment': [
                    '无特效药物，以预防为主',
                    '发病后保持水质稳定，先停止投喂3~7天直至死亡量下降趋稳',
                    '外用优质碘制剂泼洒；饲料中添加黄芪多糖、板蓝根、金银花等，按正常投饵量的1/3开始投喂',
                ],
                'prevention': [
                    '注射草鱼出血病疫苗（草鱼「三大病」疫苗之一）是最有效手段',
                    '加强苗种检疫，不从疫区引种',
                    '保持水质稳定，避免应激与拉网损伤',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '疫苗是防治该病最有效的手段；发病后盲目泼药、投喂抗生素反而会加重死亡。',
                'image': None,
                'sources': ['YC-AQUATIC-AUTUMN'],
                'is_verified': 0,
            },
            {
                'id': 'aquatic_enteritis',
                'disease': '淡水鱼细菌性肠炎病', 'alias': '烂肠瘟',
                'kind': 'disease',
                'pathogen': '肠型点状气单胞菌（Aeromonas punctata f. intestinalis）等',
                'part': '肠道',
                'severity': '中度',
                'symptoms': [
                    '病鱼肛门红肿突出',
                    '腹部膨大，轻压腹部有黄色黏液流出',
                    '解剖可见肠壁充血发炎、肠内充满黄色黏液',
                    '病鱼离群独游，食欲减退',
                ],
                'occurrence': '水温较高、投饵过量、饲料变质时高发，草鱼、鲤、鲫易感。',
                'treatment': [
                    '全池泼洒聚维酮碘溶液（水产用）或国标渔药含氯消毒剂',
                    '拌饲投喂大蒜素或恩诺沙星粉、复方磺胺嘧啶粉',
                ],
                'prevention': [
                    '坚持「定质、定量、定时、定位」投饵，不投喂变质饲料',
                    '控制投饵量，避免过量投喂',
                    '定期调节水质，及时清除残饵',
                ],
                'registered': ['聚维酮碘溶液（水产用）', '大蒜素', '恩诺沙星粉（水产用）',
                               '复方磺胺嘧啶粉（水产用）'],
                'chem_table': [],
                'safety_note': '须选用标注「水产用」的兽药，并按商品说明书用量使用。',
                'image': None,
                'sources': ['GY-AQUATIC-2026-5', 'MOA-AQUATIC-FORECAST'],
                'is_verified': 0,
            },
            {
                'id': 'aquatic_trichodiniasis',
                'disease': '车轮虫病', 'alias': '',
                'kind': 'disease',
                'pathogen': '车轮虫（Trichodina spp.）',
                'part': '体表、鳃部',
                'severity': '中度',
                'symptoms': [
                    '主要寄生在鱼体表和鳃部',
                    '鱼体分泌大量黏液，体表呈灰白色',
                    '病鱼呼吸困难，成群浮头',
                    '主要危害鱼苗和鱼种，可造成大量死亡',
                ],
                'occurrence': '水温20~28℃的春末夏初最易暴发，密度过大、水质不良时加重。',
                'treatment': [
                    '全池泼洒硫酸铜硫酸亚铁粉（水产用）',
                    '或饲料拌喂苦参末、雷丸槟榔散',
                ],
                'prevention': [
                    '彻底清塘消毒，杀灭底泥中的病原',
                    '控制放养密度，保持水质清新',
                    '鱼苗放养前进行浸浴消毒',
                ],
                'registered': ['硫酸铜硫酸亚铁粉（水产用）', '苦参末', '雷丸槟榔散'],
                'chem_table': [],
                'safety_note': '硫酸铜对鱼类毒性较大，须严格按用量并关注水体溶氧状况；虾蟹养殖塘慎用。',
                'image': None,
                'sources': ['GY-AQUATIC-2026-5', 'YC-AQUATIC-AUTUMN'],
                'is_verified': 0,
            },
            {
                'id': 'aquatic_ehp',
                'disease': '虾肝肠胞虫病', 'alias': 'EHP、南美白对虾生长迟缓综合症',
                'kind': 'disease',
                'pathogen': '虾肝肠胞虫（Enterocytozoon hepatopenaei, EHP）',
                'part': '肝胰腺、肠道',
                'severity': '中度',
                'symptoms': [
                    '对虾生长缓慢、个体参差不齐',
                    '摄食正常但长不大，出塘规格小',
                    '肝胰腺萎缩，呈乳白色',
                ],
                'occurrence': '经水源和生物饵料传播，主要危害南美白对虾，导致养殖效益大幅下降。',
                'treatment': [
                    '无特效治疗药物',
                    '改善养殖环境，加强检测',
                ],
                'prevention': [
                    '加强水源水中蜻蜓卵及蜻蜓幼虫的清除工作，切断外源病原传入途径',
                    '投喂生物饵料需−40℃冷冻24小时，解冻后再投喂',
                    '加强对养殖池虾肝肠胞虫的检测',
                ],
                'registered': [],
                'chem_table': [],
                'safety_note': '无特效药，重在水源与饵料环节的切源和定期检测。',
                'image': None,
                'sources': ['MOA-AQUATIC-FORECAST', 'GY-AQUATIC-2026-5'],
                'is_verified': 0,
            },
        ],
    },
}


# ==================== 实拍图清单合并 ====================
#
# 图片由实训团队拍摄后登记在项目根的 `pest_images.csv`（人填表），
# 由 `.workbuddy/_pest_img_ingest.py` 生成同目录的 `pest_image_manifest.py`，这里在导入时合并一次。
#
# 为什么不让人直接改上面 PEST_KNOWLEDGE 里的 image 字段：
#   45 条目手工改既容易漏、也容易把 id 写错，而且每补一批图就要再改一遍源码。
# 为什么清单缺失不算错误：团队还没拍时 `pest_image_manifest.py` 不存在，
#   整个速查照常工作，所有条目 image 保持 None（界面显示「暂无实拍图」）。
#
# 照片存放目录：项目根 `images/pest/`，经 app.py 末尾的静态兜底路由以 `/images/pest/<文件名>` 提供。


def _apply_image_manifest():
    """把实拍图清单合并进 PEST_KNOWLEDGE（幂等，只认 id 精确匹配）。"""
    try:
        from pest_image_manifest import PEST_IMAGES
    except ImportError:
        return
    for crop_data in PEST_KNOWLEDGE.values():
        for entry in crop_data.get('common_diseases') or []:
            img = PEST_IMAGES.get(entry.get('id'))
            if img:
                entry['image'] = img


_apply_image_manifest()


# ==================== 派生视图与查询辅助 ====================

# 展示顺序（与农时日历的产品顺序保持一致，便于前端标签页复用）
PEST_CROP_ORDER = ['lychee', 'longan', 'citrus', 'banana', 'rice', 'tea', 'vegetable', 'aquatic']

PEST_SOURCE_MAP = {s['key']: s for s in PEST_SOURCES}


def iter_pest_entries():
    """按 PEST_CROP_ORDER 顺序产出 (crop_key, crop_data, entry) 三元组。"""
    for crop in PEST_CROP_ORDER:
        crop_data = PEST_KNOWLEDGE.get(crop)
        if not crop_data:
            continue
        for entry in crop_data.get('common_diseases') or []:
            yield crop, crop_data, entry


def get_pest_stats():
    """统计条目数与覆盖情况，供界面显示「共 N 条」与自检使用。"""
    crops = 0
    entries = 0
    with_image = 0
    verified = 0
    for _, _, entry in iter_pest_entries():
        entries += 1
        if entry.get('image'):
            with_image += 1
        if entry.get('is_verified'):
            verified += 1
    for crop in PEST_CROP_ORDER:
        if PEST_KNOWLEDGE.get(crop):
            crops += 1
    return {
        'crops': crops,
        'entries': entries,
        'with_image': with_image,
        'verified': verified,
    }

