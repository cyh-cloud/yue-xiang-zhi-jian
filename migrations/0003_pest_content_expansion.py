# -*- coding: utf-8 -*-
"""0003：常见病虫害速查内容扩充（24 条，8 个作物各 3 条）。

背景：速查自 T07 起只读 pest 五张表，内容由基线库交付。当前 45 条平摊到 8 个作物，
每个作物 5~6 条，荔枝、龙眼、茶叶、水产几栏的常见对象缺口明显（例如龙眼缺蒂蛀虫、
荔枝缺瘿螨、水产缺烂鳃与寄生虫病），用户搜不到就退回问 AI。本脚本按作物补齐高频对象。

三条口径，与 db_domains/pest.py 的硬约定一致：

  1. **只增不改**。INSERT OR IGNORE 按 id 判重，已存在的行与它的来源关联一律跳过，
     运营在后台改过的内容不会被重跑覆盖。
  2. **不填没有核对过的数值**。新增条目 chem_table 一律用表默认的空数组：本轮没有
     逐条核对农药标签的用量、安全间隔期与每季最多次数，凭空写一个像样的数字违反
     速查「资料没给就留空」的口径。registered 只列登记有效成分名，不含任何数值。
  3. **无授权图不冒充**。新增条目不写 pest_images，读出来 image 就是 None，界面显示
     「暂无实拍图」，不补示意图。

is_verified 保持 0：这批内容依据公开技术资料编排，尚未经农技人员逐条复核，前端会
据此显示「尚未逐条复核」的提示。

用法：
    python migrations/0003_pest_content_expansion.py [--db 路径] [--dry-run] [--force]
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

VERSION = '0003'
NAME = 'pest_content_expansion'

# 新条目的 sort_order 从 45 起按作物顺序连排。既有 0~44 一个都不动，这样每个作物
# 新增的条目自然落在该作物原有条目之后，列表顺序与「先有的在前」一致。
_FIRST_SORT_ORDER = 45

# 写入 pest_entries 的列。chem_table 不在此列：走表默认的 '[]'，理由见模块说明第 2 条。
_COLUMNS = ('id', 'crop_id', 'disease', 'alias', 'kind', 'pathogen', 'part',
            'severity', 'symptoms', 'occurrence', 'treatment', 'prevention',
            'registered', 'safety_note', 'sort_order')

# JSON 数组列，写库前要序列化。
_JSON_COLUMNS = ('symptoms', 'treatment', 'prevention', 'registered')

ENTRIES = (
    # ---------------- 荔枝 ----------------
    {
        'id': 'lychee_erinose_mite',
        'crop': 'lychee',
        'disease': '荔枝瘿螨',
        'alias': '毛毡病、荔枝毛蜘蛛',
        'kind': 'pest',
        'pathogen': '荔枝瘿螨（Aceria litchii）',
        'part': '叶片（背面）、嫩梢、花穗、幼果',
        'severity': '中度',
        'symptoms': [
            '叶背出现黄绿色绒毛状虫瘿，形似毛毡，是本虫最典型的识别特征',
            '虫瘿初为黄白色，后转红褐至深褐色',
            '叶片向背卷曲、增厚变脆，严重时干枯脱落',
            '花穗、幼果受害后表面粗糙、畸形，落花落果增多',
        ],
        'occurrence': '年发生多代，以成螨在虫瘿内越冬。高温干旱有利其繁殖，新梢抽发期虫口密度上升，嫩叶最易受害；郁闭、偏施氮肥的果园发生重。',
        'treatment': [
            '抓住新梢抽发初期、虫瘿形成之前施药，重点喷叶背',
            '可选用阿维菌素、螺螨酯、哒螨灵、矿物油等登记药剂',
            '虫瘿已经形成后防效明显下降，此时应先剪除虫枝再补喷',
        ],
        'prevention': [
            '剪除并集中销毁带虫瘿的枝叶，减少虫源',
            '控制氮肥用量，避免抽发过多不整齐的嫩梢',
            '保护瓢虫、捕食螨等天敌，避免滥用广谱杀虫剂',
        ],
        'registered': ['阿维菌素', '螺螨酯', '哒螨灵', '矿物油'],
        'safety_note': '螨类抗性上升快，同一药剂每季不宜连续使用超过 2 次；具体用量与安全间隔期以所购农药标签为准。',
        'sources': ['BL-PEST-2025-8', 'GD-PEST-2024', 'ICAMA'],
    },
    {
        'id': 'lychee_lycaenid',
        'crop': 'lychee',
        'disease': '荔枝小灰蝶',
        'alias': '荔枝灰蝶、蛀果灰蝶',
        'kind': 'pest',
        'pathogen': '荔枝小灰蝶（Deudorix epijarbas）',
        'part': '果实（蛀果）、花穗',
        'severity': '中度',
        'symptoms': [
            '幼虫自果蒂附近或果实基部蛀入，蛀孔外常堆积虫粪',
            '被害果内部被蛀空，果蒂处变黑，轻碰即落',
            '幼果期受害造成大量落果，成熟期受害则失去商品价值',
            '花穗受害后枯萎，影响坐果',
        ],
        'occurrence': '年发生 3~4 代，以老熟幼虫在树干裂缝、翘皮下越冬。成虫产卵于果蒂附近，早熟品种开花至幼果期与幼虫发生期吻合时受害最重。',
        'treatment': [
            '在卵孵化盛期至幼虫蛀果前施药，蛀入后再防基本无效',
            '可选用氯虫苯甲酰胺、甲氨基阿维菌素苯甲酸盐、高效氯氟氰菊酯等',
            '及时摘除虫果、捡拾落果并深埋',
        ],
        'prevention': [
            '冬季刮除树干老翘皮，清除越冬幼虫',
            '果实套袋，物理阻隔产卵',
            '落果集中深埋或沤肥，不留虫源',
        ],
        'registered': ['氯虫苯甲酰胺', '甲氨基阿维菌素苯甲酸盐', '高效氯氟氰菊酯'],
        'safety_note': '开花期避免施药以保护授粉昆虫；采收前须遵守安全间隔期，具体以农药标签为准。',
        'sources': ['BL-PEST-2025-8', 'GD-PEST-2024', 'ICAMA'],
    },
    {
        'id': 'lychee_sour_rot',
        'crop': 'lychee',
        'disease': '荔枝酸腐病',
        'alias': '酸腐病、采后烂果',
        'kind': 'disease',
        'pathogen': '白地霉（Geotrichum candidum）',
        'part': '果实（多自果蒂伤口侵入）',
        'severity': '中度',
        'symptoms': [
            '多发生在近成熟期与采后贮运期，果蒂端最先变褐软腐',
            '果肉呈乳白色水渍状腐烂，汁液外流',
            '病部表面生出白色粉状霉层，散发明显酸臭味',
            '病果易招引果蝇，短期内蔓延至同箱果实',
        ],
        'occurrence': '病菌广泛存在于土壤与空气中，经果蒂伤口、虫伤与机械伤侵入。高温高湿、采后堆放过久、运输磕碰多时重发。',
        'treatment': [
            '采前防治蒂蛀虫等蛀果害虫，减少侵入伤口',
            '采后尽快预冷，挑除病果、伤果',
            '确需浸果处理时，只能选用登记用于荔枝采后处理的药剂',
        ],
        'prevention': [
            '采果时轻拿轻放，避免机械伤',
            '雨后与露水未干时不采果',
            '采后低温贮运，缩短常温堆放时间',
        ],
        'registered': [],
        'safety_note': '酸腐病以伤口侵入为主，采后温湿管理比喷药更关键；采后处理药剂须确认登记范围，不得套用其他作物用法。',
        'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL'],
    },
    # ---------------- 龙眼 ----------------
    {
        'id': 'longan_tip_borer',
        'crop': 'longan',
        'disease': '龙眼蒂蛀虫',
        'alias': '蛀果虫、果蒂虫',
        'kind': 'pest',
        'pathogen': '荔枝蒂蛀虫（Conopomorpha sinensis）',
        'part': '果实（蛀果）、嫩梢、花穗',
        'severity': '重度',
        'symptoms': [
            '幼虫自果蒂蛀入果实，果蒂内侧堆积黑色粉末状虫粪',
            '果核与果肉被蛀食，果实脱落或留树变褐',
            '嫩梢、花穗受害后枯萎，影响翌年结果母枝',
            '蛀孔细小，肉眼不易发现，常被误判为生理落果',
        ],
        'occurrence': '与荔枝蒂蛀虫为同一物种，龙眼果期是其重要寄主。年发生多代、世代重叠，果实膨大至转色期受害最重，采收前一周仍可蛀果。',
        'treatment': [
            '谢花后至果实膨大期监测成虫发生高峰，高峰后 3~5 天施药',
            '可选用氯虫苯甲酰胺、甲氨基阿维菌素苯甲酸盐、高效氯氟氰菊酯等',
            '采收前按安全间隔期停止用药，避免残留超标',
        ],
        'prevention': [
            '及时清除落果与虫果，集中深埋',
            '冬季清园，剪除枯枝、虫枝，压低越冬虫源',
            '果实套袋，阻隔成虫产卵',
        ],
        'registered': ['氯虫苯甲酰胺', '甲氨基阿维菌素苯甲酸盐', '高效氯氟氰菊酯'],
        'safety_note': '蒂蛀虫蛀入后无药可治，防治窗口只在成虫产卵至孵化期；具体用量与安全间隔期以农药标签为准。',
        'sources': ['GX-LONGAN-2025', 'GD-PEST-2024', 'ICAMA'],
    },
    {
        'id': 'longan_sooty_mold',
        'crop': 'longan',
        'disease': '龙眼煤烟病',
        'alias': '煤污病、煤病',
        'kind': 'disease',
        'pathogen': '煤炱菌（Capnodium spp.）',
        'part': '叶片（正面）、果实表面、枝条',
        'severity': '轻度',
        'symptoms': [
            '叶面、果面出现黑色煤粉状霉层，可用手抹去',
            '霉层遮盖叶面，影响光合作用，树势逐年衰弱',
            '果面被污染后外观变黑，商品性下降',
            '常与蚧壳虫、粉虱、蚜虫分泌的蜜露伴随发生',
        ],
        'occurrence': '病菌以菌丝在病部越冬，营腐生生活，依赖刺吸式害虫分泌的蜜露扩展。通风不良、虫害防治不到位的果园发病重。',
        'treatment': [
            '以治虫为主：先控制蚧壳虫、粉虱、蚜虫，切断蜜露来源',
            '虫害控制后可喷施矿物油，帮助溶解并冲刷霉层',
            '避免单独依赖杀菌剂，虫不治则霉层必然复发',
        ],
        'prevention': [
            '合理修剪，改善通风透光',
            '定期检查刺吸式害虫，虫口上升前处置',
            '雨后及时排水，降低园内湿度',
        ],
        'registered': [],
        'safety_note': '煤烟病是虫害的「副产品」，治虫优先于治病；矿物油在高温强光时段易产生药害，应避开中午施用。',
        'sources': ['GX-LONGAN-2025', 'PT-LICHENG-MANUAL'],
    },
    {
        'id': 'longan_erinose_mite',
        'crop': 'longan',
        'disease': '龙眼瘿螨',
        'alias': '龙眼毛毡病',
        'kind': 'pest',
        'pathogen': '龙眼瘿螨（Aceria dimocarpi）',
        'part': '叶片（背面）、嫩梢、花穗',
        'severity': '中度',
        'symptoms': [
            '叶背出现灰白色至黄褐色绒毛状虫瘿',
            '叶片向背卷曲、增厚变脆，严重时提早脱落',
            '花穗、嫩梢受害后畸形，影响坐果',
            '虫体极小，需借助放大镜在虫瘿绒毛间观察',
        ],
        'occurrence': '年发生多代，干旱少雨时虫口上升快。新梢期与花穗期是防治关键期，虫瘿形成后药剂难以触及虫体。',
        'treatment': [
            '新梢抽出、虫瘿形成前施药，重点喷叶背',
            '可选用阿维菌素、螺螨酯等登记药剂',
            '剪除严重受害枝叶后再补喷，单靠喷药难以压住虫口',
        ],
        'prevention': [
            '剪除虫瘿枝叶并集中销毁',
            '加强肥水管理，促梢整齐，缩短易感期',
            '保护捕食螨等天敌',
        ],
        'registered': ['阿维菌素', '螺螨酯'],
        'safety_note': '具体用量与安全间隔期以农药标签为准；同一作用机制药剂不宜连用，防止抗性。',
        'sources': ['GX-LONGAN-2025', 'GD-PEST-2024', 'ICAMA'],
    },
    # ---------------- 柑橘 ----------------
    {
        'id': 'citrus_rust_mite',
        'crop': 'citrus',
        'disease': '柑橘锈壁虱',
        'alias': '橘锈螨、锈蜘蛛、黑皮果',
        'kind': 'pest',
        'pathogen': '柑橘锈瘿螨（Phyllocoptruta oleivora）',
        'part': '果实表皮、叶片背面',
        'severity': '中度',
        'symptoms': [
            '果实表皮初现黄白色小斑，后变黑褐色粗糙「锈皮」',
            '叶片背面呈黄褐至黑褐色，失去光泽',
            '严重时大量落叶、落果，果实品质与售价下降',
            '虫体肉眼不可见，果面「黑皮」出现时已错过最佳防治期',
        ],
        'occurrence': '年发生 10 余代，高温干旱有利。7~9 月为发生高峰，果面「黑皮」多在此期形成；郁闭果园与树冠内部先发生。',
        'treatment': [
            '幼果期至果实膨大期监测，虫口上升时施药',
            '可选用阿维菌素、螺螨酯、哒螨灵、矿物油等，重点喷果面与叶背',
            '喷药须覆盖树冠内部与果实阴面，漏喷处锈斑照旧形成',
        ],
        'prevention': [
            '干旱时适度灌溉，保持园内湿度',
            '保护捕食螨，减少广谱杀虫剂使用',
            '合理修剪，改善通风透光',
        ],
        'registered': ['阿维菌素', '螺螨酯', '哒螨灵', '矿物油'],
        'safety_note': '锈壁虱防治强调「早」，果面一旦形成锈斑不可逆；具体用量与安全间隔期以农药标签为准。',
        'sources': ['NN-CITRUS-2024', 'GD-PEST-2024', 'ICAMA'],
    },
    {
        'id': 'citrus_unaspis',
        'crop': 'citrus',
        'disease': '柑橘矢尖蚧',
        'alias': '矢尖蚧、蚧壳虫',
        'kind': 'pest',
        'pathogen': '矢尖蚧（Unaspis yanonensis）',
        'part': '枝条、叶片、果实',
        'severity': '中度',
        'symptoms': [
            '枝、叶、果上附着褐色箭头状蚧壳，雌蚧壳前端尖、后端宽',
            '叶片黄化、卷曲，严重时枝条枯死',
            '果实表面出现黄绿色斑点，商品性下降',
            '蚧壳密集处常伴随煤烟病',
        ],
        'occurrence': '年发生 2~3 代，以受精雌成虫在枝干越冬。若虫盛孵期是唯一有效的防治窗口，蚧壳形成后药剂难以穿透。郁闭果园、枝叶密集处发生重。',
        'treatment': [
            '抓住各代若虫盛孵期施药，华南多在 5 月、7 月、9 月前后',
            '可选用噻嗪酮、螺虫乙酯、矿物油等登记药剂',
            '冬季可喷施矿物油封园，压低越冬虫口',
        ],
        'prevention': [
            '剪除虫枝、郁闭枝，改善通风透光',
            '苗木调运前检查，不带虫上山',
            '保护瓢虫、跳小蜂等天敌',
        ],
        'registered': ['噻嗪酮', '螺虫乙酯', '矿物油'],
        'safety_note': '噻嗪酮对蟹、虾等甲壳类敏感，靠近鱼塘的果园须防止药液流入水体；具体以农药标签为准。',
        'sources': ['NN-CITRUS-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'citrus_scab',
        'crop': 'citrus',
        'disease': '柑橘疮痂病',
        'alias': '癞头疤、疮疤病',
        'kind': 'disease',
        'pathogen': '柑橘痂圆孢（Sphaceloma fawcettii）',
        'part': '嫩叶、嫩梢、幼果',
        'severity': '中度',
        'symptoms': [
            '叶片初现蜡黄色小点，后隆起成木栓化疮痂，叶片畸形扭曲',
            '幼果表面形成褐色木栓化瘤状突起，果小、易落',
            '疮痂只发生在组织幼嫩期，叶片老熟后不再感染',
            '病斑表面粗糙，不产生霉层，借此与溃疡病区分',
        ],
        'occurrence': '病菌在病枝、病叶上越冬，靠风雨与昆虫传播。春梢期、幼果期遇低温多雨易流行；组织老熟后抗性明显增强，故防治必须抢在嫩梢期。',
        'treatment': [
            '春梢萌动期、落花后各施药 1 次，幼果期视病情补施',
            '可选用苯醚甲环唑、代森锰锌、咪鲜胺等登记药剂',
            '药剂须在组织幼嫩期到达，老熟后补喷基本无效',
        ],
        'prevention': [
            '剪除病枝病叶，集中烧毁',
            '控制春梢抽发整齐，缩短易感期',
            '合理修剪通风，降低园内湿度',
        ],
        'registered': ['苯醚甲环唑', '代森锰锌', '咪鲜胺'],
        'safety_note': '具体用量与安全间隔期以农药标签为准；幼果期用药须避开花期与高温时段。',
        'sources': ['NN-CITRUS-2024', 'SC-NANBU-CITRUS', 'ICAMA'],
    },
    # ---------------- 香蕉 ----------------
    {
        'id': 'banana_cmv',
        'crop': 'banana',
        'disease': '香蕉花叶心腐病',
        'alias': '花叶病、心腐病',
        'kind': 'disease',
        'pathogen': '黄瓜花叶病毒（CMV）香蕉株系',
        'part': '叶片、心叶（假茎内部）',
        'severity': '重度',
        'symptoms': [
            '叶片出现黄绿相间的花叶、斑驳，沿叶脉呈断续条状',
            '心叶及假茎内部变褐腐烂，有臭味',
            '植株矮化，抽蕾困难或抽出畸形花蕾',
            '苗期发病多整株枯死，成株期发病则大幅减产',
        ],
        'occurrence': '由蚜虫以非持久性方式传播，也可经带毒吸芽与刀具机械传播。苗期至成株期均可发病，高温季节症状最明显；病株与健株混种时扩散快。',
        'treatment': [
            '病毒病无特效药剂，发现病株应立即连根挖除并销毁',
            '治蚜防病：控制香蕉交脉蚜等媒介昆虫，切断传播链',
            '不要轻信市售「花叶病特效药」，避免无效投入',
        ],
        'prevention': [
            '选用无病毒组培苗，不使用来源不明的吸芽',
            '及时防治蚜虫，尤其是苗期',
            '割芽、砍病株的刀具逐株消毒，避免机械传播',
            '发现病株连根挖除深埋，并补种无病苗',
        ],
        'registered': [],
        'safety_note': '病毒病无药可治，防控核心是无毒苗、治蚜与拔除病株；任何宣称能「治愈」花叶病的药剂都不可信。',
        'sources': ['MM-BANANA-GUIDE', 'MM-BANANA-TG'],
    },
    {
        'id': 'banana_root_knot_nematode',
        'crop': 'banana',
        'disease': '香蕉根结线虫',
        'alias': '根结线虫病、根瘤线虫',
        'kind': 'pest',
        'pathogen': '南方根结线虫（Meloidogyne incognita）等',
        'part': '根系',
        'severity': '重度',
        'symptoms': [
            '根系形成大小不等的根结（瘤状肿大），剖开可见细小虫体',
            '须根减少，根尖褐变坏死，吸水吸肥能力下降',
            '地上部矮化、叶片黄化，抽蕾延迟，果指短小',
            '干旱时中午萎蔫、早晚恢复，是与枯萎病混淆的常见误判',
        ],
        'occurrence': '以二龄幼虫和卵在土壤、病根中越冬，砂质土、连作蕉园发生重。借病苗、农具与灌溉水传播，一旦传入很难彻底清除。',
        'treatment': [
            '植前进行土壤处理，压低初始虫口',
            '生长期可选用阿维菌素、噻唑膦等登记药剂灌根',
            '病株挖除时连同病根一起清出蕉园，不就地掩埋',
        ],
        'prevention': [
            '选用无病苗，新植园不与老蕉园共用农具',
            '与水稻等水生作物轮作，效果优于旱作轮作',
            '增施有机肥，培育发达根系，提高耐害能力',
            '清园时挖除病根并集中处理',
        ],
        'registered': ['阿维菌素', '噻唑膦'],
        'safety_note': '噻唑膦须按登记的作物与用量使用，不得随意加大剂量；灌根后注意个人防护，具体以农药标签为准。',
        'sources': ['MM-BANANA-GUIDE', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'banana_skipper',
        'crop': 'banana',
        'disease': '香蕉弄蝶',
        'alias': '蕉苞虫、卷叶虫',
        'kind': 'pest',
        'pathogen': '香蕉弄蝶（Erionota torus）',
        'part': '叶片',
        'severity': '中度',
        'symptoms': [
            '幼虫吐丝将叶片卷缀成筒状虫苞，藏身其中取食',
            '叶缘出现大量缺刻，严重时叶片只剩中脉',
            '虫苞悬挂叶上十分显眼，苞内可见绿色虫体与虫粪',
            '苗期与幼树叶片少，受害后生长明显受阻',
        ],
        'occurrence': '年发生 4~5 代，世代重叠。幼虫清晨与阴雨天活动最盛，晴天多伏于虫苞内。苗圃与幼龄蕉园发生重于成株园。',
        'treatment': [
            '低龄幼虫期施药，可选用苏云金杆菌、氯虫苯甲酰胺、甲氨基阿维菌素苯甲酸盐等',
            '人工摘除虫苞并踩死幼虫，小面积发生时最经济',
            '重点喷叶背与新叶，虫苞内的幼虫需药液渗透才有效',
        ],
        'prevention': [
            '冬季清理枯叶与虫苞，减少越冬虫源',
            '人工捕杀幼虫与蛹',
            '保护寄生蜂、寄生蝇等天敌',
        ],
        'registered': ['苏云金杆菌', '氯虫苯甲酰胺', '甲氨基阿维菌素苯甲酸盐'],
        'safety_note': '苏云金杆菌宜在傍晚或阴天施用，避免强光下失活；具体用量以农药标签为准。',
        'sources': ['MM-BANANA-GUIDE', 'GX-BANANA-7M', 'ICAMA'],
    },
    # ---------------- 水稻 ----------------
    {
        'id': 'rice_bacterial_blight',
        'crop': 'rice',
        'disease': '水稻白叶枯病',
        'alias': '白叶瘟、茅草瘟',
        'kind': 'disease',
        'pathogen': '稻黄单胞菌稻致病变种（Xanthomonas oryzae pv. oryzae）',
        'part': '叶片、叶鞘',
        'severity': '重度',
        'symptoms': [
            '多从叶尖、叶缘开始，出现黄绿色水渍状条斑',
            '条斑沿叶脉扩展成黄白色波浪状枯斑，边缘清晰',
            '晨露未干时病部可见蜜黄色菌脓，干后结成小胶粒',
            '病叶干枯卷曲，田块远看一片枯白，故称「茅草瘟」',
        ],
        'occurrence': '病菌在病稻草、稻种上越冬，经伤口（尤其台风暴雨造成的伤口）与叶孔侵入。台风暴雨后易暴发，偏施氮肥、深水灌溉与串灌会加速蔓延。',
        'treatment': [
            '发病初期施药，可选用噻菌铜、叶枯唑、噻唑锌等登记药剂',
            '台风暴雨过后及时排水并喷药保护，抢在发病前',
            '病田水不排入无病田，防止随水流扩散',
        ],
        'prevention': [
            '选用抗病品种，这是最经济的手段',
            '种子消毒处理，不用病稻草覆盖催芽',
            '浅水勤灌，避免深水与串灌漫灌',
            '不偏施氮肥，防止贪青披叶',
        ],
        'registered': ['噻菌铜', '叶枯唑', '噻唑锌'],
        'safety_note': '细菌性病害靠雨水与流水传播，药剂防治必须配合水管理与排灌隔离；具体用量以农药标签为准。',
        'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'rice_brown_spot',
        'crop': 'rice',
        'disease': '水稻胡麻叶斑病',
        'alias': '胡麻斑病、饥馑病',
        'kind': 'disease',
        'pathogen': '稻平脐蠕孢（Bipolaris oryzae）',
        'part': '叶片、谷粒、穗颈',
        'severity': '中度',
        'symptoms': [
            '叶片出现芝麻粒大小的褐色椭圆形病斑，中央灰褐、边缘深褐',
            '病斑外围常有黄色晕圈，密集时叶片干枯',
            '谷粒受害出现褐色斑块，米质下降',
            '穗颈受害易折断，形成瘪谷',
        ],
        'occurrence': '病菌在病稻草、病谷上越冬。土壤缺肥（尤其缺钾）、酸性土、长期深水或干旱缺水时发病重，俗称「瘦田病」，与稻瘟病的「肥田病」形成对照。',
        'treatment': [
            '发病初期施药，可选用咪鲜胺、苯醚甲环唑、代森锰锌等登记药剂',
            '补施钾肥与硅肥，提高植株抗性',
            '避免在孕穗期过量施用氮肥',
        ],
        'prevention': [
            '增施有机肥与钾肥，避免偏施氮肥',
            '酸性土适当施用石灰，改善土壤',
            '浅水勤灌，适时晒田，避免长期深水或脱水',
            '种子消毒，病稻草不还田或充分腐熟后还田',
        ],
        'registered': ['咪鲜胺', '苯醚甲环唑', '代森锰锌'],
        'safety_note': '该病多为缺素与土壤不良的「信号病」，单靠喷药效果有限，肥水管理须同步调整；具体用量以农药标签为准。',
        'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'rice_skipper',
        'crop': 'rice',
        'disease': '稻苞虫',
        'alias': '稻弄蝶、苞叶虫',
        'kind': 'pest',
        'pathogen': '直纹稻弄蝶（Parnara guttata）等',
        'part': '叶片',
        'severity': '中度',
        'symptoms': [
            '幼虫吐丝缀叶成苞，藏于苞内取食，一苞常有多头幼虫',
            '叶片被啃成缺刻，严重时稻丛只剩叶脉',
            '分蘖期至抽穗期均可受害，抽穗期幼虫可咬断穗颈',
            '虫苞多结在稻株上部，田间检查时容易发现',
        ],
        'occurrence': '年发生 3~5 代，以老熟幼虫在田边杂草、沟渠边越冬。山区、滨湖稻区发生较多，成虫昼伏夜出，有趋光性。',
        'treatment': [
            '三龄前幼虫施药，可选用苏云金杆菌、氯虫苯甲酰胺、甲氨基阿维菌素苯甲酸盐等',
            '人工摘除虫苞，小面积发生时成本最低',
            '施药时药液要能渗入虫苞，否则苞内幼虫不受影响',
        ],
        'prevention': [
            '冬春清除田边杂草与沟渠边越冬幼虫',
            '合理密植，避免田间过度郁闭',
            '保护螟蛉绒茧蜂等寄生性天敌',
        ],
        'registered': ['苏云金杆菌', '氯虫苯甲酰胺', '甲氨基阿维菌素苯甲酸盐'],
        'safety_note': '具体用量与安全间隔期以农药标签为准；稻田养鱼、养虾田块须选用对水生生物安全的药剂。',
        'sources': ['GD-PEST-2024', 'SD-SHAODONG-2024', 'ICAMA'],
    },
    # ---------------- 茶叶 ----------------
    {
        'id': 'tea_broad_mite',
        'crop': 'tea',
        'disease': '茶跗线螨',
        'alias': '茶嫩叶螨、茶半跗线螨',
        'kind': 'pest',
        'pathogen': '侧多食跗线螨（Polyphagotarsonemus latus）',
        'part': '嫩叶（背面）、嫩梢、芽尖',
        'severity': '中度',
        'symptoms': [
            '嫩叶背面呈灰褐至黄褐色，失去光泽',
            '叶缘向下卷曲，芽叶僵硬变脆，伸育停滞',
            '严重时嫩梢枯焦，状似「火烧」，直接造成减产',
            '虫体极小，多藏在叶背绒毛间，须用放大镜查看',
        ],
        'occurrence': '年发生 20 余代，高温干旱时繁殖极快。多在嫩叶背面活动，卵产于叶背绒毛间；采摘频繁、留养不足的茶园发生重。',
        'treatment': [
            '虫口上升初期施药，重点喷嫩叶背面',
            '可选用阿维菌素、联苯肼酯、矿物油等登记药剂',
            '采摘茶园须严格遵守安全间隔期，优先选用低残留品种',
        ],
        'prevention': [
            '及时分批采摘，摘除受害芽叶',
            '干旱季节适度灌溉与遮阴，降低田间温度',
            '保护捕食螨等天敌，减少广谱杀虫剂',
        ],
        'registered': ['阿维菌素', '联苯肼酯', '矿物油'],
        'safety_note': '茶叶是直接饮用作物，用药必须选用在茶树上登记的品种并严守安全间隔期；具体以农药标签为准。',
        'sources': ['MOA-TEA-2023', 'GD-TEA-STD', 'ICAMA'],
    },
    {
        'id': 'tea_grey_blight',
        'crop': 'tea',
        'disease': '茶云纹叶枯病',
        'alias': '叶枯病、云纹病',
        'kind': 'disease',
        'pathogen': '茶球腔菌（Guignardia camelliae）',
        'part': '成叶、老叶',
        'severity': '中度',
        'symptoms': [
            '老叶叶尖或叶缘出现黄绿色病斑，后扩展为半圆形或不规则形',
            '病斑具深浅相间的云纹状轮纹，中央灰白',
            '病部后期散生黑色小点（子实体）',
            '病叶易脱落，树势逐年衰弱，产量下降',
        ],
        'occurrence': '病菌在病叶上越冬，高温高湿、树势衰弱、采摘过度时发生重。梅雨期与秋雨期是两个发病高峰，台风雨后常突然加重。',
        'treatment': [
            '发病初期喷药，可选用苯醚甲环唑、吡唑醚菌酯、代森锰锌等',
            '非采摘期可结合清园施药，采摘期严格按安全间隔期安排',
            '摘除病叶并带出茶园，减少再侵染来源',
        ],
        'prevention': [
            '加强肥培管理，增强树势',
            '合理采摘，避免过度强采',
            '开沟排水，降低茶园湿度',
            '及时清除病叶，保持茶园通风',
        ],
        'registered': ['苯醚甲环唑', '吡唑醚菌酯', '代森锰锌'],
        'safety_note': '采摘期用药须严守安全间隔期，成龄茶园建议在修剪后或非采摘季进行；具体以农药标签为准。',
        'sources': ['MOA-TEA-2023', 'GD-TEA-STD', 'ICAMA'],
    },
    {
        'id': 'tea_weevil',
        'crop': 'tea',
        'disease': '茶丽纹象甲',
        'alias': '茶象甲、花鸡娘',
        'kind': 'pest',
        'pathogen': '茶丽纹象甲（Myllocerinus aurolineatus）',
        'part': '叶片（成叶）',
        'severity': '中度',
        'symptoms': [
            '成虫啃食叶片，形成不规则缺刻与孔洞',
            '严重时叶片只剩主脉，状如「网纱」',
            '被害叶边缘呈锯齿状，与毛虫啃食痕迹不同',
            '幼虫在土中取食有机质与细根，造成根系损伤',
        ],
        'occurrence': '年发生 1 代，以幼虫在土中越冬。成虫 5~7 月盛发，善爬行、不善飞翔，受惊有假死性；有机质丰富、长期不深耕的茶园发生重。',
        'treatment': [
            '成虫盛发期（5~6 月）施药，可选用苦参碱、球孢白僵菌、联苯菊酯等',
            '利用假死性，清晨人工振落捕杀，小面积茶园可行',
            '成虫出土前进行土壤处理，压低虫口基数',
        ],
        'prevention': [
            '冬季深耕翻土，破坏幼虫越冬环境',
            '清除茶园周边杂草与落叶堆',
            '保护白僵菌等病原微生物的自然控制作用',
        ],
        'registered': ['苦参碱', '球孢白僵菌', '联苯菊酯'],
        'safety_note': '球孢白僵菌避免与杀菌剂混用；采摘茶园用药须严守安全间隔期，具体以农药标签为准。',
        'sources': ['MOA-TEA-2023', 'GX-TEA-2026-7', 'ICAMA'],
    },
    # ---------------- 蔬菜 ----------------
    {
        'id': 'vegetable_whitefly',
        'crop': 'vegetable',
        'disease': '蔬菜烟粉虱',
        'alias': '小白蛾、烟粉虱、白粉虱',
        'kind': 'pest',
        'pathogen': '烟粉虱（Bemisia tabaci）',
        'part': '叶片背面',
        'severity': '重度',
        'symptoms': [
            '成若虫群集叶背刺吸汁液，叶片褪绿、黄化',
            '分泌蜜露诱发煤烟病，叶面发黑发黏',
            '成虫受惊时成群飞起如白雾，是最直观的识别特征',
            '是番茄黄化曲叶病毒等多种蔬菜病毒的传播媒介',
        ],
        'occurrence': '年发生 10 余代，世代重叠，大棚与露地均可周年发生。25~30℃ 繁殖最快，高温干旱有利；可随种苗与运输传播，一旦进入棚室很难根除。',
        'treatment': [
            '虫口初期施药，重点喷叶背，连续 2 次间隔 7 天左右',
            '可选用螺虫乙酯、呋虫胺、矿物油等登记药剂，注意轮换',
            '黄板监测与诱杀结合，掌握虫口动态再决定是否用药',
        ],
        'prevention': [
            '育苗期防虫网覆盖，切断初始虫源',
            '田间悬挂黄板诱杀成虫',
            '清除田边杂草与收获后的残株',
            '与非寄主作物轮作或间作',
        ],
        'registered': ['螺虫乙酯', '呋虫胺', '矿物油'],
        'safety_note': '烟粉虱抗药性上升快，须轮换不同作用机制药剂；花期避免使用对蜜蜂高毒的品种，具体以农药标签为准。',
        'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'vegetable_grey_mold',
        'crop': 'vegetable',
        'disease': '蔬菜灰霉病',
        'alias': '灰霉、烂花烂果',
        'kind': 'disease',
        'pathogen': '灰葡萄孢（Botrytis cinerea）',
        'part': '花、果实、叶片、茎',
        'severity': '重度',
        'symptoms': [
            '多从残花开始，花瓣变褐腐烂后向果实与茎蔓延',
            '病部表面密生灰褐色绒毛状霉层',
            '病果软腐，触之即落，果柄处最先发病',
            '茎部受害呈水渍状腐烂，绕茎一周后上部枯死',
        ],
        'occurrence': '低温高湿（15~23℃、相对湿度 90% 以上）时最易流行。大棚通风不良、连续阴雨、浇水过多时重发；病菌以菌核在土壤中越冬，存活期长。',
        'treatment': [
            '发病初期施药，可选用嘧霉胺、腐霉利、啶酰菌胺、木霉菌等',
            '不同作用机制轮换使用，灰霉病菌抗性极强',
            '棚内可用烟剂熏蒸，避免喷雾增加湿度',
        ],
        'prevention': [
            '控温控湿，晴天上午放风排湿',
            '及时摘除病花、病果、病叶并带出田外',
            '避免大水漫灌，采用滴灌或膜下灌溉',
            '地膜覆盖，减少土壤病菌飞溅到植株',
        ],
        'registered': ['嘧霉胺', '腐霉利', '啶酰菌胺', '木霉菌'],
        'safety_note': '灰霉病菌对多类杀菌剂已产生抗性，同一药剂每季使用不超过 2 次；木霉菌不可与化学杀菌剂混用。',
        'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    {
        'id': 'vegetable_fusarium_wilt',
        'crop': 'vegetable',
        'disease': '蔬菜枯萎病',
        'alias': '萎蔫病、死秧、镰刀菌枯萎病',
        'kind': 'disease',
        'pathogen': '尖孢镰刀菌（Fusarium oxysporum）',
        'part': '根系、茎基部（维管束）',
        'severity': '重度',
        'symptoms': [
            '植株白天萎蔫、早晚恢复，数日后整株枯死',
            '茎基部纵剖可见维管束变褐，是与青枯病的共同点',
            '根颈部有时溢出琥珀色胶状物',
            '叶片自下而上黄化，常从一侧枝条开始',
        ],
        'occurrence': '病菌在土壤与病残体中存活 5 年以上，经根部伤口侵入。连作、土壤黏重、积水、地温高时发病重；一旦传入，常规轮作难以根除。',
        'treatment': [
            '发病初期灌根，可选用咪鲜胺、噁霉灵、枯草芽孢杆菌等',
            '发现病株立即拔除并带出田外，病穴撒生石灰',
            '灌根须在发病初期进行，维管束变褐后基本无效',
        ],
        'prevention': [
            '与非寄主作物轮作 3 年以上，水旱轮作效果更好',
            '瓜类采用嫁接换根，抗病性显著提升',
            '高畦栽培，避免田间积水',
            '增施生物有机肥，改善土壤微生物区系',
        ],
        'registered': ['咪鲜胺', '噁霉灵', '枯草芽孢杆菌'],
        'safety_note': '枯萎病是土传病害，药剂只是辅助手段，轮作与嫁接才是根本；具体用量以农药标签为准。',
        'sources': ['GD-PEST-2024', 'PT-LICHENG-MANUAL', 'ICAMA'],
    },
    # ---------------- 水产养殖 ----------------
    {
        'id': 'aquatic_gill_rot',
        'crop': 'aquatic',
        'disease': '淡水鱼烂鳃病',
        'alias': '乌头瘟、鳃病',
        'kind': 'disease',
        'pathogen': '柱状黄杆菌（Flavobacterium columnare）',
        'part': '鳃部',
        'severity': '重度',
        'symptoms': [
            '鳃丝腐烂、边缘发白缺损，附有污泥',
            '鳃盖内表皮充血发炎，严重时中间烂穿呈「开天窗」',
            '病鱼离群独游，呼吸困难，常浮头',
            '体色变暗，尤以头部为甚，故有「乌头瘟」之称',
        ],
        'occurrence': '水温 15~30℃ 均可发生，夏季高发。水质恶化、密度过大、鳃部有寄生虫伤口时易感，草鱼、青鱼最敏感，常与肠炎、赤皮并发。',
        'treatment': [
            '全池泼洒国标渔药消毒剂（聚维酮碘、溴氯海因等）',
            '拌饲投喂氟苯尼考等水产用抗菌药，连用 4~6 天',
            '先杀虫后杀菌：鳃部有寄生虫时须先处理虫体，否则伤口持续存在',
        ],
        'prevention': [
            '定期泼洒生石灰或国标消毒剂调节水质',
            '控制放养密度，避免超载',
            '投喂优质饲料，定期添加维生素增强体质',
            '拉网、分塘操作轻缓，减少机械伤',
        ],
        'registered': ['聚维酮碘溶液（水产用）', '溴氯海因粉（水产用）', '氟苯尼考粉（水产用）', '生石灰'],
        'safety_note': '须选用标注「水产用」的兽药，严格执行休药期；严禁使用禁用渔药，具体以说明书为准。',
        'sources': ['MOA-AQUATIC-FORECAST', 'GY-AQUATIC-2026-5', 'ICAMA'],
    },
    {
        'id': 'aquatic_anchorworm',
        'crop': 'aquatic',
        'disease': '锚头鳋病',
        'alias': '锚头虫病、铁锚虫病',
        'kind': 'pest',
        'pathogen': '锚头鳋（Lernaea spp.）',
        'part': '体表（头胸部钻入肌肉）、鳃',
        'severity': '中度',
        'symptoms': [
            '鱼体表可见针状虫体，头部钻入肌肉，露出白色虫身',
            '寄生处红肿、发炎、出血，易继发细菌感染',
            '病鱼焦躁不安、跳跃、擦壁，食欲下降',
            '虫体附着处常留下深红色溃疡，影响商品外观',
        ],
        'occurrence': '水温 12~33℃ 均可繁殖，春夏之交与秋季为高峰。雌虫产卵量大，虫卵随水流传播；池塘多年不清塘、水质老化时发生重。',
        'treatment': [
            '全池泼洒水产用敌百虫或高效氯氰菊酯溶液，按说明书用量',
            '次日配合泼洒消毒剂，防止寄生伤口继发细菌感染',
            '病情严重时分塘隔离，避免全池扩散',
        ],
        'prevention': [
            '放苗前彻底清塘，杀灭水中虫卵与幼虫',
            '定期检查鱼体，发现虫体尽早处置',
            '保持水质清新，减少应激',
            '新进鱼种先检疫、暂养后再合池',
        ],
        'registered': ['敌百虫（水产用）', '高效氯氰菊酯溶液（水产用）'],
        'safety_note': '敌百虫须选用「水产用」制剂，严禁使用兽用或农用产品；鳜鱼、虾蟹等敏感品种禁用，具体以说明书为准。',
        'sources': ['MOA-AQUATIC-FORECAST', 'YC-AQUATIC-AUTUMN', 'ICAMA'],
    },
    {
        'id': 'aquatic_vibrio',
        'crop': 'aquatic',
        'disease': '对虾弧菌病',
        'alias': '副溶血弧菌病、急性肝胰腺坏死病（AHPND）',
        'kind': 'disease',
        'pathogen': '副溶血弧菌（Vibrio parahaemolyticus）等弧菌',
        'part': '肝胰腺、肠道、体表',
        'severity': '重度',
        'symptoms': [
            '病虾肝胰腺萎缩、变白或糜烂，是本病的核心病变',
            '空肠空胃，肠道发红或断节',
            '体表甲壳出现褐色斑点或溃疡，附肢发红',
            '摄食骤减，短期内出现高比例死亡，部分病虾夜间发光',
        ],
        'occurrence': '苗期投放后 20~30 天内高发（AHPND）。水温高、盐度波动、密度大、底质恶化时暴发，投喂过量与残饵堆积是主要诱因。',
        'treatment': [
            '发病后立即停料或大幅减料，先切断输入性污染',
            '全池泼洒碘制剂消毒，加强增氧',
            '确需用药时拌饲水产用抗菌药，须凭处方并遵守休药期',
            '及时捞出病死虾，避免健康虾摄食后扩散',
        ],
        'prevention': [
            '选用无特定病原（SPF）虾苗，苗种检疫',
            '彻底清塘、晒塘，杀灭底泥中的弧菌',
            '控制投喂量，避免残饵，定期改底',
            '定期使用芽孢杆菌、乳酸菌等微生态制剂调水',
            '保持盐度与水温稳定，减少应激',
        ],
        'registered': ['聚维酮碘溶液（水产用）'],
        'safety_note': '对虾用抗菌药须遵守处方与休药期规定；严禁使用氯霉素、硝基呋喃类等禁用药物，具体以说明书为准。',
        'sources': ['MOA-AQUATIC-FORECAST', 'GY-AQUATIC-2026-5', 'ICAMA'],
    },
)


def _row(entry, sort_order):
    """把一条内容摊成待插入的参数元组。JSON 列在此序列化。"""
    values = []
    for column in _COLUMNS:
        if column == 'sort_order':
            values.append(sort_order)
        elif column in _JSON_COLUMNS:
            values.append(json.dumps(entry[column], ensure_ascii=False))
        elif column == 'crop_id':
            values.append(entry['crop'])
        else:
            values.append(entry[column])
    return tuple(values)


def migrate(db_path, dry_run=False, force=False):
    """把新条目写进 pest 表。已执行过返回 None（--force 可重跑，仍不覆盖既有行）。"""
    import sqlite3

    if not os.path.isfile(db_path):
        raise SystemExit('目标库不存在：%s' % db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 表结构的唯一真相源在 db_schema，这里不另抄 DDL。
    import db_schema
    db_schema.apply_schema(cur)
    conn.commit()

    already = cur.execute(
        "SELECT version FROM schema_migrations WHERE version = ?", (VERSION,)).fetchone()
    if already and not force:
        conn.close()
        return None

    if dry_run:
        conn.close()
        return {'dry_run': True, 'entries': len(ENTRIES)}

    known_crops = {row['id'] for row in cur.execute("SELECT id FROM pest_crops").fetchall()}
    known_sources = {row['key'] for row in
                     cur.execute("SELECT key FROM pest_sources").fetchall()}

    inserted, skipped = [], []
    for offset, entry in enumerate(ENTRIES):
        if entry['crop'] not in known_crops:
            raise SystemExit('条目 %s 指向不存在的作物：%s'
                             % (entry['id'], entry['crop']))
        unknown = [key for key in entry['sources'] if key not in known_sources]
        if unknown:
            raise SystemExit('条目 %s 引用了未登记的来源：%s'
                             % (entry['id'], ', '.join(unknown)))

        cur.execute(
            "INSERT OR IGNORE INTO pest_entries (%s) VALUES (%s)"
            % (', '.join(_COLUMNS), ', '.join('?' * len(_COLUMNS))),
            _row(entry, _FIRST_SORT_ORDER + offset))
        if cur.rowcount == 0:
            # 行已存在：来源关联也不碰，运营可能已经改过。
            skipped.append(entry['id'])
            continue
        for order, key in enumerate(entry['sources']):
            cur.execute(
                "INSERT OR IGNORE INTO pest_entry_sources "
                "(entry_id, source_key, sort_order) VALUES (?, ?, ?)",
                (entry['id'], key, order))
        inserted.append(entry['id'])

    log = {'version': VERSION, 'name': NAME,
           'inserted': inserted, 'skipped': skipped}
    cur.execute(
        """INSERT INTO schema_migrations (version, name, applied_at, extra)
           VALUES (?, ?, datetime('now','localtime'), ?)
           ON CONFLICT(version) DO UPDATE SET
               name=excluded.name, applied_at=excluded.applied_at, extra=excluded.extra""",
        (VERSION, NAME, json.dumps(log, ensure_ascii=False)))
    conn.commit()
    conn.close()
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='病虫害速查内容扩充：新增 24 条条目（只增不改）。')
    parser.add_argument('--db', default=None, help='目标库路径，默认走 db_connection.DB_PATH')
    parser.add_argument('--dry-run', action='store_true', help='只报告，不写库')
    parser.add_argument('--force', action='store_true',
                        help='忽略已执行标记重跑；已存在的条目仍不会被覆盖')
    args = parser.parse_args(argv)

    from db_connection import DB_PATH
    db_path = args.db or DB_PATH

    log = migrate(db_path, dry_run=args.dry_run, force=args.force)
    if log is None:
        print('版本 %s 已执行过，跳过（--force 可重跑）。' % VERSION)
        return 0
    if log.get('dry_run'):
        print('dry-run：将写入 %d 条新条目，目标库 %s，未写入。'
              % (log['entries'], db_path))
        return 0
    print('迁移 %s（%s）完成，目标库 %s' % (VERSION, NAME, db_path))
    print('  新增 %d 条，跳过已存在 %d 条' % (len(log['inserted']), len(log['skipped'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
