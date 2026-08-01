#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
粤乡智匠 - 基于AI实训系统的农村本土人才赋能平台
Flask后端应用
"""

from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from datetime import datetime
from dotenv import load_dotenv
import os
import json
import logging
import database

# 加载环境变量（优先 .env 文件）
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化Flask应用
app = Flask(__name__)
CORS(app)

# 应用配置
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', os.urandom(24).hex()),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    JSON_AS_ASCII=False
)

# AI服务配置
AI_API_URL = os.getenv('AI_API_URL', 'https://api.siliconflow.cn/v1/chat/completions')
AI_API_KEY = os.getenv('AI_API_KEY', '')
AI_MODEL = os.getenv('AI_MODEL', 'Qwen/Qwen3-32B')

# 农业知识库
AGRICULTURE_KNOWLEDGE = {
    "lychee": {
        "name": "荔枝",
        "seasons": {
            "spring": {
                "tasks": ["促花肥施用", "病虫害预防", "修剪整形"],
                "tips": "春季是荔枝开花关键期，注意防治霜疫霉病"
            },
            "summer": {
                "tasks": ["果实采收", "采后修剪", "恢复肥施用"],
                "tips": "及时采收成熟果实，采后及时补充营养"
            },
            "autumn": {
                "tasks": ["秋梢管理", "病虫害防治", "水分管理"],
                "tips": "培养健壮秋梢，为来年结果打基础"
            },
            "winter": {
                "tasks": ["冬季清园", "树干涂白", "深翻改土"],
                "tips": "做好防寒措施，减少越冬病虫源"
            }
        },
        "diseases": [
            {"name": "霜疫霉病", "symptoms": "果实表面出现褐色病斑", "treatment": "喷施甲霜灵·锰锌"},
            {"name": "炭疽病", "symptoms": "叶片出现圆形病斑", "treatment": "喷施咪鲜胺"},
            {"name": "蒂蛀虫", "symptoms": "果实被蛀食", "treatment": "喷施高效氯氰菊酯"}
        ]
    },
    "longan": {
        "name": "龙眼",
        "seasons": {
            "spring": {"tasks": ["促花肥", "疏花"], "tips": "控制花量，提高坐果率"},
            "summer": {"tasks": ["壮果肥", "水分管理"], "tips": "保持土壤湿润"},
            "autumn": {"tasks": ["采收", "采后管理"], "tips": "适时采收"},
            "winter": {"tasks": ["冬季修剪", "清园"], "tips": "做好防寒"}
        }
    },
    "aquatic": {
        "name": "水产养殖",
        "basics": [
            "水质管理是关键",
            "合理投喂饲料",
            "定期消毒防病",
            "保持溶氧充足"
        ]
    }
}

# 手工艺知识
CRAFTS_KNOWLEDGE = {
    "embroidery": {
        "name": "广绣",
        "origin": "广州",
        "history": "国家级非物质文化遗产，起源于唐代，与苏绣、湘绣、蜀绣并称中国四大名绣。广绣以构图饱满、色彩艳丽、针法多变著称，尤以金银线绣最为独特。",
        "steps": [
            {
                "title": "准备工具与材料",
                "desc": "准备绣架、绣针（12号-7号）、真丝绣线（建议从12色基础色开始）、丝绸绣布（19姆米素绉缎）、剪刀、水消笔、复写纸。",
                "tips": "初学者建议选白色或浅色绣布，便于看清针脚；绣线不要剪太长，50cm左右为宜，过长容易打结。"
            },
            {
                "title": "图案设计与转印",
                "desc": "在纸上绘制或打印图案，用复写纸转印到绣布上。也可用水消笔直接在绣布上绘制。初学者建议从简单的花卉、水果图案开始。",
                "tips": "转印时力度要轻，避免划伤绣布；水消笔画错可用湿布擦掉重画。"
            },
            {
                "title": "上绷与固定",
                "desc": "将绣布平整地固定在绣绷上，调整松紧度。绣布要绷紧但不能变形，以手指轻弹有弹性为宜。",
                "tips": "每隔10分钟检查一次绷紧度，绣制过程中绣布可能会松弛。"
            },
            {
                "title": "基础针法练习",
                "desc": "掌握直针（最基础，用于轮廓）、扭针（用于花瓣叶片）、长短针（用于渐变色彩）、打籽针（用于花蕊点缀）。每种针法先在废布上练习20分钟。",
                "tips": "针距保持均匀，一般2-3mm；起针收针都要在背面打结，正面不能露线头。"
            },
            {
                "title": "配色与绣制",
                "desc": "根据图案选择绣线颜色，广绣讲究'花无正色'，常用渐变色表现立体感。从深色到浅色逐层绣制，先绣主体再绣背景。",
                "tips": "配色时准备色卡对比；同一区域用3-5个渐变色会更自然；丝线有正反面，光泽面朝外。"
            },
            {
                "title": "收尾与装裱",
                "desc": "绣完后剪去多余线头，从绣绷上取下，用蒸汽熨斗低温熨平背面。然后选择合适的画框或屏风进行装裱。",
                "tips": "熨烫时绣面朝下，垫一块薄布；装裱前确保绣品完全干燥，避免发霉。"
            }
        ],
        "materials": [
            {"name": "实木绣绷（30cm）", "price": "35-80元", "where": "淘宝搜'广绣绣绷'，选榉木材质", "note": "初学者选30cm圆形即可"},
            {"name": "广绣专用针套装", "price": "15-35元", "where": "搜'广绣针12支装'，选不锈钢材质", "note": "包含12号-7号各2支"},
            {"name": "真丝绣线（12色）", "price": "45-120元", "where": "搜'蚕丝绣线12色'，选150D粗细", "note": "每色8米，够绣一幅小作品"},
            {"name": "19姆米素绉缎", "price": "25-60元/米", "where": "搜'真丝绣布'或'素绉缎'", "note": "白色最百搭，建议买0.5米"},
            {"name": "水消笔+复写纸", "price": "10-20元", "where": "文具店或淘宝均有", "note": "水消笔选蓝色，更易看清"}
        ]
    },
    "woodcarving": {
        "name": "潮汕木雕",
        "origin": "潮汕",
        "history": "国家级非物质文化遗产，始于唐代，盛于明清。以多层镂通雕刻技法闻名，作品玲珑剔透、层次分明，常用于建筑装饰、家具和祭祀器具。潮汕金漆木雕与东阳木雕、黄杨木雕、龙眼木雕并称中国四大木雕。",
        "steps": [
            {
                "title": "选材与备料",
                "desc": "常用木材有樟木（防虫）、椴木（易雕刻）、红木（高档作品）。选材要求木纹细腻、无裂纹、无虫蛀。原木需自然干燥3-6个月，含水率控制在12%以下。",
                "tips": "初学者建议用椴木练习，价格便宜且质地均匀；樟木有特殊气味，需在通风处操作。"
            },
            {
                "title": "画样与放稿",
                "desc": "在纸上绘制1:1图稿，传统题材有花鸟鱼虫、戏曲人物、祥瑞图案。用复写纸将图稿转印到木料上，或用铅笔直接绘制。",
                "tips": "图稿线条要清晰，标注好哪些部分需要镂空、哪些保留；初学者避免选择过于复杂的图案。"
            },
            {
                "title": "开粗坯",
                "desc": "用大号平刀和圆刀去除多余木料，雕刻出大体轮廓。先从最高层开始，逐层向下推进。注意留出精雕余量，一般多留1-2mm。",
                "tips": "刀具要保持锋利，钝刀容易崩木；用力要均匀，顺着木纹方向雕刻；大块废料可用木槌敲击刀背去除。"
            },
            {
                "title": "精雕细刻",
                "desc": "用小号雕刻刀精修细节，如羽毛纹理、花瓣脉络、人物五官。多层镂通作品需要逐层打通，注意层与层之间的连接强度。",
                "tips": "精雕时坐姿要正，手肘撑在桌面上保持稳定；镂空部分从中间向两边雕，避免边缘崩裂。"
            },
            {
                "title": "打磨与修光",
                "desc": "用砂纸从180目逐级打磨到600目，使表面光滑。凹陷处可用砂纸卷成小棒打磨。最后用棉布擦拭干净。",
                "tips": "打磨方向要顺着木纹；每次换更细砂纸前要清除上一级的木屑；600目以上可用木蜡油抛光。"
            },
            {
                "title": "上漆与装饰",
                "desc": "传统潮汕木雕常用金漆装饰：先涂生漆底漆，干燥后贴金箔或涂金粉。也可选择清漆保持原木色，或用木蜡油保养。",
                "tips": "生漆会引起过敏，操作时必须戴手套和口罩；金箔很薄，操作时不能有风。"
            }
        ],
        "materials": [
            {"name": "椴木方料（20×10×5cm）", "price": "20-40元", "where": "搜'椴木方料'或木雕材料店", "note": "初学者练习用，选无裂纹的"},
            {"name": "木雕刀具套装（12件）", "price": "80-200元", "where": "搜'木雕刀套装'，选SK5钢材质", "note": "含平刀、圆刀、三角刀等"},
            {"name": "木槌", "price": "15-30元", "where": "五金店或淘宝", "note": "选黄杨木或榉木材质"},
            {"name": "砂纸套装（180-600目）", "price": "10-25元", "where": "五金店", "note": "每样买2-3张"},
            {"name": "木蜡油/清漆", "price": "25-50元", "where": "搜'硬质木蜡油'", "note": "用于成品保养和装饰"}
        ]
    },
    "ceramics": {
        "name": "石湾陶艺",
        "origin": "佛山石湾",
        "history": "国家级非物质文化遗产，始于新石器时代，盛于明清。石湾公仔以'胎骨朴拙、釉色斑斓、造型生动'著称，尤以人物陶塑最为出名，被誉为'石湾公仔甲天下'。",
        "steps": [
            {
                "title": "揉泥排气",
                "desc": "将陶泥反复揉压，排出内部气泡。采用菊花揉或螺旋揉法，揉至泥料柔软均匀、切面无气孔为止。每次揉泥至少15分钟。",
                "tips": "泥中有气泡烧制时会炸裂；揉泥时如果太干可适量喷水，太湿可晾干一会儿。"
            },
            {
                "title": "拉坯成型",
                "desc": "将揉好的泥放在拉坯机中心，双手沾水后从中间开孔，慢慢向上提拉塑形。初学者先练习拉圆柱体，再尝试碗、杯等器型。",
                "tips": "拉坯时身体重心要稳，双手力度均匀；转速先快后慢；失败了重新揉泥再来，不要灰心。"
            },
            {
                "title": "修坯利底",
                "desc": "待坯体半干（皮革硬度）时，用修坯刀修整外形和底部。修出圈足，使底部平整。壁厚控制在3-5mm为宜。",
                "tips": "修坯时坯体要固定好，可用泥条粘在转盘上；太干修不动，太湿会变形。"
            },
            {
                "title": "装饰雕刻",
                "desc": "在坯体上进行刻花、贴花、镂空等装饰。石湾陶艺特色是'贴塑'技法——用泥片捏出花叶、人物等部件贴在坯体上。",
                "tips": "贴花时接触面要划毛并涂泥浆，否则烧制时会脱落；细节工具可用牙签、旧毛笔代替。"
            },
            {
                "title": "干燥与素烧",
                "desc": "坯体需自然干燥7-10天，完全干透后入窑素烧。素烧温度约800°C，升温要缓慢（每小时50°C），防止开裂。",
                "tips": "干燥时避免阳光直射和风吹，可用塑料薄膜半遮盖；底部也要干透才能入窑。"
            },
            {
                "title": "上釉与釉烧",
                "desc": "素烧后的坯体浸釉或刷釉，石湾特色是使用低温颜色釉（如翠毛蓝、石榴红）。釉烧温度约1100-1200°C。",
                "tips": "釉层厚度要均匀，底部要刮掉釉料防止粘连；可先试烧小样看颜色效果。"
            }
        ],
        "materials": [
            {"name": "陶泥（10斤）", "price": "20-40元", "where": "搜'石湾陶泥'或'高温陶泥'", "note": "选适合当地窑温的泥料"},
            {"name": "拉坯机", "price": "300-800元", "where": "搜'小型拉坯机'", "note": "初学者买40cm直径即可"},
            {"name": "修坯刀套装", "price": "25-50元", "where": "搜'陶艺修坯刀'", "note": "含各种形状刀头"},
            {"name": "陶艺工具10件套", "price": "30-60元", "where": "搜'陶艺工具套装'", "note": "含刮刀、海绵、转盘等"},
            {"name": "石湾颜色釉（5色）", "price": "60-150元", "where": "搜'石湾陶釉'或佛山陶艺店", "note": "翠毛蓝、石榴红是经典色"},
            {"name": "电窑（小型）", "price": "1500-3000元", "where": "搜'小型电窑1200度'", "note": "没有窑可找当地陶艺工作室代烧"}
        ]
    },
    "lacquer": {
        "name": "阳江漆器",
        "origin": "阳江",
        "history": "广东省级非物质文化遗产，始于明末清初，以阳江漆器厂为代表。阳江漆器以皮胎漆器闻名，工艺精湛，色彩绚丽，曾是广东重要的出口工艺品。",
        "steps": [
            {
                "title": "制作胎体",
                "desc": "传统阳江漆器用牛皮制胎（皮胎），也可用木胎或布胎。木胎需选用质地细腻的木材，打磨光滑后涂生漆封底。",
                "tips": "皮胎制作难度高，初学者建议从木胎开始；木胎表面要彻底打磨光滑，否则影响漆面效果。"
            },
            {
                "title": "批灰与打磨",
                "desc": "在胎体上批涂生漆与瓦灰调和的漆灰，填补缝隙和不平处。干燥后打磨平整，一般需要批灰2-3遍。",
                "tips": "每遍批灰要薄而均匀，厚了容易开裂；打磨后要用布擦干净再批下一遍。"
            },
            {
                "title": "髹底漆",
                "desc": "涂刷生漆作为底漆，每遍薄涂，自然阴干（需在温度25°C、湿度80%的环境下）。底漆一般涂3-5遍，每遍干燥后需水磨。",
                "tips": "生漆干燥需要高湿度，可在房间放加湿器；生漆会引起皮肤过敏，必须戴手套操作。"
            },
            {
                "title": "装饰工艺",
                "desc": "阳江漆器装饰技法有：描金（用金粉描绘图案）、螺钿（镶嵌贝壳片）、推光（反复抛光至镜面效果）、彩绘（用矿物颜料作画）。",
                "tips": "描金时金粉要用桐油调和；螺钿片要提前裁剪好形状；彩绘颜料要与漆兼容。"
            },
            {
                "title": "上面漆与推光",
                "desc": "最后一道面漆要特别精细，涂完后在特定条件下干燥7天以上。然后用细砂纸水磨，再用抛光粉反复推光至镜面效果。",
                "tips": "推光是体力活，需要耐心；用棉花蘸瓦灰和人头油反复擦拭，越推越亮。"
            },
            {
                "title": "完成与保养",
                "desc": "成品完成后避免阳光直射和高温环境。日常保养用柔软干布擦拭，避免接触化学溶剂。传统漆器越用越有光泽。",
                "tips": "漆器怕干燥，长期不用可涂薄薄一层核桃油保养；避免与硬物碰撞。"
            }
        ],
        "materials": [
            {"name": "生漆（500g）", "price": "100-200元", "where": "搜'天然生漆'或陕西/湖北漆农", "note": "初学者买小包装即可"},
            {"name": "瓦灰/漆灰", "price": "15-30元", "where": "搜'漆艺瓦灰'", "note": "用于批灰找平"},
            {"name": "木胎/皮胎", "price": "50-200元", "where": "搜'漆器木胎'或定制", "note": "初学者选简单器型"},
            {"name": "砂纸（800-2000目）", "price": "15-30元", "where": "五金店或淘宝", "note": "水磨砂纸，多买几张"},
            {"name": "描金笔+金粉", "price": "40-80元", "where": "搜'漆艺描金工具'", "note": "金粉选24K铜金粉即可"},
            {"name": "防过敏手套+口罩", "price": "20-40元", "where": "药店或劳保店", "note": "生漆过敏很严重，必须防护"}
        ]
    }
}


# ==================== 静态文件 ====================

# 项目根目录（适配 Vercel Serverless 环境）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    return send_from_directory(_BASE_DIR, 'index.html')


# ==================== 农业技能API ====================

@app.route('/api/agriculture/products', methods=['GET'])
def get_products():
    products = [
        {"id": "lychee", "name": "荔枝", "icon": "apple-alt", "desc": "广东特色水果"},
        {"id": "longan", "name": "龙眼", "icon": "circle", "desc": "岭南佳果"},
        {"id": "aquatic", "name": "水产养殖", "icon": "fish", "desc": "鱼虾蟹贝"},
        {"id": "rice", "name": "水稻", "icon": "seedling", "desc": "主要粮食作物"},
        {"id": "tea", "name": "茶叶", "icon": "mug-hot", "desc": "广东名茶"},
        {"id": "vegetable", "name": "蔬菜", "icon": "carrot", "desc": "时令蔬菜"}
    ]
    return jsonify({"success": True, "products": products})


@app.route('/api/agriculture/calendar/<product_id>', methods=['GET'])
def get_farming_calendar(product_id):
    if product_id in AGRICULTURE_KNOWLEDGE:
        return jsonify({"success": True, "data": AGRICULTURE_KNOWLEDGE[product_id]})
    return jsonify({"success": False, "message": "未找到该农产品信息"})


@app.route('/api/agriculture/ask', methods=['POST'])
def ask_agriculture():
    data = request.get_json()
    question = data.get('question', '')
    product = data.get('product', '')
    history = data.get('history', [])
    if not question:
        return jsonify({"success": False, "message": "请输入问题"})

    product_name = AGRICULTURE_KNOWLEDGE.get(product, {}).get('name', '广东特色农产品')
    system_prompt = (
        f"你是粤乡智匠平台的专业农业技术专家，专注于{product_name}领域。"
        f"回答要求：1)简洁实用，分点列出；2)结合广东本地气候和种植条件；"
        f"3)涉及农药时注明安全用量；4)适当用通俗易懂的语言。"
        f"回答控制在300字以内。"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-5:]:
        messages.append({"role": "user", "content": h.get("question", "")})
        messages.append({"role": "assistant", "content": h.get("answer", "")})
    messages.append({"role": "user", "content": question})

    try:
        import requests as req
        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": AI_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 800
        }
        resp = req.post(AI_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        answer = resp.json()['choices'][0]['message']['content']

        # 生成追问建议
        suggestions = _generate_suggestions(product, question, answer)

        return jsonify({"success": True, "answer": answer, "suggestions": suggestions})
    except Exception as e:
        logger.error(f"AI问答失败: {e}")
        # 降级：用AI生成通用建议（不带上下文）
        try:
            fallback = call_ai_service(
                system_prompt="你是农业技术专家。用户的问题无法获取回答，请用一句话建议用户咨询当地农技站或参考官方渠道，并给出一个通用的农业小贴士。",
                user_message=question
            )
            return jsonify({"success": True, "answer": fallback, "suggestions": []})
        except Exception:
            return jsonify({"success": True, "answer": "抱歉，AI服务暂时不可用。建议咨询当地农技站或拨打12316三农服务热线获取帮助。", "suggestions": []})


@app.route('/api/agriculture/ask/stream', methods=['POST'])
def ask_agriculture_stream():
    """SSE 流式 AI 问答"""
    data = request.get_json()
    question = data.get('question', '')
    product = data.get('product', '')
    history = data.get('history', [])
    if not question:
        return jsonify({"success": False, "message": "请输入问题"})

    product_name = AGRICULTURE_KNOWLEDGE.get(product, {}).get('name', '广东特色农产品')
    system_prompt = (
        f"你是粤乡智匠平台的专业农业技术专家，专注于{product_name}领域。"
        f"回答要求：1)简洁实用，分点列出；2)结合广东本地气候和种植条件；"
        f"3)涉及农药时注明安全用量；4)适当用通俗易懂的语言。"
        f"回答控制在300字以内。"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-5:]:
        messages.append({"role": "user", "content": h.get("question", "")})
        messages.append({"role": "assistant", "content": h.get("answer", "")})
    messages.append({"role": "user", "content": question})

    import requests as req

    def generate():
        try:
            headers = {
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": AI_MODEL,
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 800,
                "stream": True
            }
            resp = req.post(AI_API_URL, headers=headers, json=payload, stream=True, timeout=60)
            resp.raise_for_status()

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        yield 'event: done\ndata: [DONE]\n\n'
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk['choices'][0].get('delta', {})
                        content = delta.get('content', '')
                        if content:
                            yield f'data: {json.dumps({"content": content}, ensure_ascii=False)}\n\n'
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            resp.close()
        except Exception as e:
            logger.error(f"SSE问答失败: {e}")
            yield f'event: error\ndata: {json.dumps({"error": str(e)}, ensure_ascii=False)}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


def _generate_suggestions(product, question, answer):
    """基于当前问答生成3个追问建议"""
    product_name = AGRICULTURE_KNOWLEDGE.get(product, {}).get('name', '农业')
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。根据用户的问题和AI回答，生成3个相关的追问建议。只输出3个问题，每行一个，不要编号，不要其他内容。每个问题控制在20字以内。",
            user_message=f"用户问：{question}\nAI答：{answer[:200]}",
            max_tokens=150,
            temperature=0.6
        )
        suggestions = [s.strip().lstrip('0123456789.、 ') for s in result.strip().split('\n') if s.strip()]
        return suggestions[:3]
    except Exception:
        return []


# 建议问题缓存
_suggestions_cache = {}
_suggestions_cache_time = {}
SUGGESTIONS_CACHE_TTL = 300  # 5分钟


@app.route('/api/agriculture/suggestions', methods=['GET'])
def get_agriculture_suggestions():
    """获取指定农产品的常见问题建议"""
    product = request.args.get('product', 'lychee')
    import time
    now = time.time()

    # 检查缓存
    if product in _suggestions_cache and now - _suggestions_cache_time.get(product, 0) < SUGGESTIONS_CACHE_TTL:
        return jsonify({"success": True, "suggestions": _suggestions_cache[product]})

    product_name = AGRICULTURE_KNOWLEDGE.get(product, {}).get('name', '广东特色农产品')
    try:
        result = call_ai_service(
            system_prompt=f"你是{product_name}种植专家。生成4个农民最常问的实用问题，每行一个，不要编号，不要其他内容。每个问题控制在15-25字。要覆盖不同方面（种植、病虫害、施肥、采收等）。",
            user_message=f"请为{product_name}生成4个常见问题",
            max_tokens=200,
            temperature=0.7
        )
        suggestions = [s.strip().lstrip('0123456789.、 ') for s in result.strip().split('\n') if s.strip()][:4]
        _suggestions_cache[product] = suggestions
        _suggestions_cache_time[product] = now
        return jsonify({"success": True, "suggestions": suggestions})
    except Exception as e:
        logger.error(f"生成建议问题失败: {e}")
        fallback = {
            "lychee": ["荔枝花期如何管理？", "如何防治荔枝霜疫霉病？", "荔枝采后怎样恢复树势？", "荔枝膨大期施什么肥？"],
            "longan": ["龙眼如何疏花疏果？", "龙眼鬼帚病怎么防治？", "龙眼冬季管理要点？", "龙眼什么时候采收最好？"],
            "aquatic": ["鱼塘水质如何调节？", "虾塘增氧机怎么开？", "鱼病预防有哪些方法？", "养殖密度多少合适？"],
            "rice": ["水稻纹枯病怎么防治？", "水稻什么时候晒田好？", "稻飞虱用什么药？", "水稻收割最佳时期？"],
            "tea": ["茶园如何进行冬管？", "茶叶虫害绿色防控？", "春茶采摘标准是什么？", "茶树修剪技术要点？"],
            "vegetable": ["蔬菜大棚如何控温？", "叶菜类常见病害防治？", "有机蔬菜怎么施肥？", "蔬菜轮作有什么好处？"]
        }
        return jsonify({"success": True, "suggestions": fallback.get(product, fallback["lychee"])})


# ==================== 电商运营API ====================

@app.route('/api/ecommerce/script', methods=['POST'])
def generate_script():
    data = request.get_json()
    product = data.get('product', '荔枝')
    style = data.get('style', '热情')
    style_prompts = {
        '热情': {
            'desc': '热情洋溢、极具感染力的带货风格',
            'techniques': [
                '开场用"家人们""宝子们"等亲昵称呼拉近距离',
                '用感叹句和反问句制造情绪高潮，如"这也太香了吧！""你们说值不值？"',
                '重复强调核心卖点至少3次，形成记忆锚点',
                '制造紧迫感：限时、限量、直播间专属价',
                '穿插互动指令："想要的扣1""觉得值的点个赞"',
                '用价格对比制造超值感：原价→划线价→直播间价'
            ]
        },
        '专业': {
            'desc': '专业可信、知识型带货风格',
            'techniques': [
                '开场介绍产品产地、品种、种植/养殖方式等专业背景',
                '用具体数据说话：甜度、含水量、营养成分、检测指标',
                '对比同类产品突出差异化优势',
                '引用权威认证：绿色食品、有机认证、地理标志',
                '讲解挑选技巧和食用方法，提供附加价值',
                '语调沉稳但不失热情，像专家在分享而非推销'
            ]
        },
        '故事': {
            'desc': '故事型、情感共鸣带货风格',
            'techniques': [
                '以种植者/产地的真实故事开篇，塑造人物形象',
                '描述产品的生长环境、气候、水土等自然条件',
                '讲述从田间到餐桌的旅程，强调匠心和坚持',
                '融入岭南文化元素和乡土情怀',
                '用五感描写让消费者"看到""闻到""尝到"',
                '结尾升华：支持乡村振兴、助力农户增收'
            ]
        },
        '高级': {
            'desc': '高级感、品质生活带货风格',
            'techniques': [
                '用品质生活的角度切入，不直接叫卖',
                '营造场景感：夏日冰镇荔枝配白葡萄酒、秋日茶席',
                '强调稀缺性和产区限定，制造高端感',
                '用文艺化的语言描述产品，如"岭南夏日的第一口甜"',
                '引用美食家、品鉴师的评价增加背书',
                '控制节奏，留白有度，不急不躁地展示品质'
            ]
        }
    }
    style_config = style_prompts.get(style, style_prompts['热情'])
    techniques_text = '\n'.join(f'- {t}' for t in style_config['techniques'])
    try:
        ai_script = call_ai_service(
            system_prompt=f"""你是一位顶级直播带货话术专家，擅长为广东特色农产品撰写高转化率的直播脚本。

【风格】{style_config['desc']}

【话术技巧】
{techniques_text}

【结构要求】
1. 开场钩子（1-2句）：3秒内抓住注意力
2. 产品亮点（2-3句）：核心卖点+数据支撑
3. 信任背书（1-2句）：产地/认证/口碑
4. 促单话术（1-2句）：价格锚点+紧迫感
5. 互动引导（1句）：引导点赞/下单

【输出要求】
- 总共8-12句，每句一行
- 口语化，有节奏感，适合朗读
- 用【】标注关键卖点和价格
- 穿插互动指令（括号标注，如：(引导点赞)）""",
            user_message=f"为广东{product}撰写直播带货话术，要突出岭南特色和产品优势"
        )
        return jsonify({"success": True, "script": ai_script})
    except Exception as e:
        logger.error(f"话术生成失败: {e}")
        fallback_scripts = {
            '热情': f"""家人们！今天给你们带来广东最正宗的{product}！
(互动) 想要的扣1，让我看看有多少人识货！
你们看这个品相，【颗颗饱满】，色泽鲜亮，这可不是随便哪里都能找到的！
原价128，今天直播间专属价——只要【79元】！没听错，79！
(引导) 觉得值的给我点个赞，点到500我再送一份赠品！
最后30单，拍完就恢复原价，手慢无！""",

            '专业': f"""各位朋友好，今天给大家带来的是广东{product}。
这个品种产自岭南核心产区，年均气温22°C，日照充足，土壤富含矿物质。
我们每一批都经过【农残检测、甜度筛选】，检测报告大家可以看屏幕。
和市面上的普通产品相比，我们的优势在于：果径大15%、甜度高3度、保鲜期多5天。
今天直播间特惠，【买二送一】，性价比非常高的。""",

            '故事': f"""在广东的一个小村子里，有位老师傅种了30年{product}。
他常说："好东西急不得，要等天时、靠地利、更要用心。"
(停顿) 每年这个时候，他凌晨4点就下地，只为赶在日出前采摘最新鲜的一批。
从枝头到你手里，不超过48小时——这就是我们对品质的承诺。
今天把这份来自岭南的匠心之味带给大家，【尝过的都说好】。
(引导) 想尝尝这份用心的，点下方链接下单吧。""",

            '高级': f"""岭南夏日，最令人期待的，莫过于这口来自广东的{product}。
它生长在北回归线以南的沃土，吸饱了亚热带的阳光和雨露。
【果肉如玉，汁水丰盈】，入口即化的细腻口感，是大自然最好的馈赠。
古人云"日啖荔枝三百颗"，而今这份岭南风物，只需一键下单便可抵达你的餐桌。
今日限量供应，【精品礼盒装】，自用送礼皆宜。
品味不将就，生活要讲究。"""
        }
        return jsonify({"success": True, "script": fallback_scripts.get(style, fallback_scripts['热情'])})


@app.route('/api/ecommerce/feedback', methods=['POST'])
def get_live_feedback():
    """AI评分直播表现"""
    data = request.get_json()
    script_text = data.get('script', '')
    import re, random

    def analyze_script(text):
        """基于规则分析话术内容，生成差异化分数"""
        # 统计各类特征
        exclamation = len(re.findall(r'[！!]{1,}', text))
        question = len(re.findall(r'[？?]{1,}', text))
        interaction_words = len(re.findall(r'扣\d|点[个一]赞|觉得值|想要的|有没有|是不是|对不对|家人们|宝子们', text))
        pause_marks = len(re.findall(r'停顿|稍等|等一下|\.\.\.|\…', text))
        data_marks = len(re.findall(r'\d+[%°度]|【[^】]+】|\d+[元斤箱份]', text))
        emotion_words = len(re.findall(r'太[香好吃棒]|绝了|真的|必须|一定要|超级|特别|非常', text))
        price_words = len(re.findall(r'原价|划线价|专属价|只要|仅需|优惠|折扣|限量|最后|手慢无', text))

        # 基础分 + 特征加权
        speed = 68 + min(pause_marks * 6, 20) + min(exclamation * 2, 10) - (0 if len(text) > 100 else 5)
        emotion = 65 + min(emotion_words * 5, 20) + min(exclamation * 3, 15) + min(question * 2, 10)
        interaction = 60 + min(interaction_words * 8, 30) + min(question * 3, 10)
        selling = 66 + min(data_marks * 5, 20) + min(price_words * 4, 16)

        # 加少量随机波动
        speed = max(50, min(98, speed + random.randint(-3, 3)))
        emotion = max(50, min(98, emotion + random.randint(-3, 3)))
        interaction = max(50, min(98, interaction + random.randint(-3, 3)))
        selling = max(50, min(98, selling + random.randint(-3, 3)))

        return speed, emotion, interaction, selling

    def generate_suggestions(speed, emotion, interaction, selling, text):
        """基于分数和内容生成针对性建议"""
        suggestions = []
        has_interaction = bool(re.search(r'扣\d|点[个一]赞|觉得值', text))
        has_pause = bool(re.search(r'停顿|\.\.\.', text))
        has_data = bool(re.search(r'\d+[元斤箱度%]', text))
        has_price = bool(re.search(r'原价|只要|专属价', text))
        has_emotion = bool(re.search(r'家人们|宝子们|太[香好吃]', text))

        if interaction < 75 and not has_interaction:
            suggestions.append('加入互动指令，如"想要的扣1""觉得值的点个赞"')
        if speed < 72 and not has_pause:
            suggestions.append('适当加入停顿，制造悬念感，如"(停顿3秒)"')
        if selling < 75 and not has_data:
            suggestions.append('用具体数据支撑卖点，如甜度、重量、检测指标')
        if emotion < 72 and not has_emotion:
            suggestions.append('增加情绪词和感叹句，如"这也太香了吧！"')
        if not has_price:
            suggestions.append('加入价格锚点，如"原价128，今天只要79"')
        if selling >= 75 and interaction >= 75:
            suggestions.append('整体不错，可以尝试讲故事增加情感共鸣')

        # 补充通用建议到至少3条
        general = [
            '开场3秒内抛出核心卖点抓住注意力',
            '用"最后XX单"制造紧迫感促进下单',
            '加入用户好评或复购数据增强信任',
            '结尾引导关注直播间获取更多优惠',
            '用对比法突出产品差异化优势'
        ]
        random.shuffle(general)
        while len(suggestions) < 3 and general:
            suggestions.append(general.pop())

        return suggestions[:3]

    try:
        result = call_ai_service(
            system_prompt="""你是直播话术评分专家。分析以下直播带货话术，给出四个维度的评分和改进建议。

请先分析话术中的具体特征（互动词数量、感叹句数量、数据支撑等），然后给出评分。

评分维度（每项0-100整数，四个分数必须不同）：
- speed_score：语速节奏（看停顿标记、句子长短变化、节奏感）
- emotion_score：情绪感染力（看感叹句、情绪词、反问句）
- interaction_score：互动技巧（看"扣1""点赞""家人们"等互动词数量）
- selling_score：卖点提炼（看数据支撑、价格锚点、【】标注）

输出格式（严格JSON，不要其他文字）：
{"speed_score":数字,"emotion_score":数字,"interaction_score":数字,"selling_score":数字,"summary":"20字总评","suggestions":["针对性建议1","建议2","建议3"]}""",
            user_message=f"请评分：\n{script_text}"
        )
        try:
            json_match = re.search(r'\{.*?\}', result, re.DOTALL)
            feedback = json.loads(json_match.group()) if json_match else json.loads(result)
        except (json.JSONDecodeError, AttributeError, TypeError):
            feedback = {}

        # 用规则分析作为基础
        s, e, i, se = analyze_script(script_text)

        # 如果AI返回了有效分数且有差异，优先用AI的；否则用规则分析
        ai_scores = [feedback.get('speed_score'), feedback.get('emotion_score'),
                     feedback.get('interaction_score'), feedback.get('selling_score')]
        ai_valid = all(isinstance(x, (int, float)) and 40 <= x <= 100 for x in ai_scores)
        ai_diff = len(set(ai_scores)) >= 3  # 至少3个不同才算有效

        if ai_valid and ai_diff:
            final_speed, final_emotion, final_interaction, final_selling = [int(x) for x in ai_scores]
            final_suggestions = feedback.get('suggestions', []) if feedback.get('suggestions') else generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', '整体表现不错')
        else:
            final_speed, final_emotion, final_interaction, final_selling = s, e, i, se
            final_suggestions = generate_suggestions(s, e, i, se, script_text)
            final_summary = feedback.get('summary', '') or '整体表现不错，有提升空间'

        scores = [final_speed, final_emotion, final_interaction, final_selling]
        return jsonify({"success": True, "feedback": {
            "speed_score": scores[0],
            "emotion_score": scores[1],
            "interaction_score": scores[2],
            "selling_score": scores[3],
            "overall_score": round(sum(scores) / 4),
            "summary": final_summary,
            "suggestions": final_suggestions[:3]
        }})
    except Exception as e:
        logger.error(f"AI评分失败: {e}")
        s, e, i, se = analyze_script(script_text)
        suggestions = generate_suggestions(s, e, i, se, script_text)
        return jsonify({"success": True, "feedback": {
            "speed_score": s, "emotion_score": e, "interaction_score": i, "selling_score": se,
            "overall_score": round((s + e + i + se) / 4),
            "summary": "基于规则分析的评分结果",
            "suggestions": suggestions
        }})


@app.route('/api/ecommerce/copywriting', methods=['POST'])
def generate_copywriting():
    """AI生成商品文案 - 支持多种格式"""
    data = request.get_json()
    product = data.get('product', '荔枝')
    fmt = data.get('format', '详情页')
    audience = data.get('audience', '')
    selling_points = data.get('selling_points', '')
    tone = data.get('tone', '')

    format_prompts = {
        '详情页': {
            'desc': '电商商品详情页文案',
            'structure': '包含：吸引眼球的主标题（10字内）→ 副标题（一句话卖点）→ 5-8个核心卖点（每个配小标题+1-2句描述）→ 使用场景（2-3个）→ 品质承诺 → 促单话术',
            'style': '专业可信，层次分明，卖点突出，适合长图文排版'
        },
        '主图文案': {
            'desc': '电商主图/轮播图上的短文案',
            'structure': '生成5条独立的主图文案，每条8-15字，要求：第1条突出核心卖点，第2条突出价格优势，第3条突出产地/品质，第4条突出促销活动，第5条突出情感/场景',
            'style': '简洁有力，一击即中，适合小空间展示'
        },
        '朋友圈': {
            'desc': '微信朋友圈推广文案',
            'structure': '包含：生活化开场（1句）→ 产品体验描述（2-3句，用五感描写）→ 信任背书（1句）→ 互动引导（1句）→ 适当emoji，总长度150字内',
            'style': '真实自然，像朋友分享而非广告，有生活气息'
        },
        '小红书': {
            'desc': '小红书种草笔记',
            'structure': '包含：吸睛标题（带emoji，15字内）→ 开头hook（1句，制造好奇）→ 产品体验（3-4句，真实感受）→ 使用tips（2-3条）→ 总结推荐 → 标签推荐（5-8个）',
            'style': '种草感强，真实分享，有闺蜜推荐的感觉，多用emoji和口语化表达'
        },
        '短视频脚本': {
            'desc': '15-30秒短视频带货脚本',
            'structure': '按时间轴输出：【0-3秒】开场hook（制造悬念/反差）→ 【3-8秒】展示产品（描述外观/特点）→ 【8-15秒】核心卖点+使用场景 → 【15-20秒】价格促单 → 【20-25秒】行动指令',
            'style': '节奏紧凑，口语化，适合朗读，每句标注时间点'
        }
    }

    config = format_prompts.get(fmt, format_prompts['详情页'])
    extra = []
    if audience:
        extra.append(f"目标人群：{audience}")
    if selling_points:
        extra.append(f"必须包含的卖点：{selling_points}")
    if tone:
        extra.append(f"语调要求：{tone}")
    extra_text = '\n'.join(extra) if extra else ''

    try:
        result = call_ai_service(
            system_prompt=f"""你是顶级电商文案专家，擅长为广东特色农产品撰写高转化率文案。

【文案类型】{config['desc']}
【输出结构】{config['structure']}
【风格要求】{config['style']}

【通用要求】
- 语言生动有画面感，避免空洞的"品质保证"类套话
- 善用数据、对比、场景、情感等说服技巧
- 突出广东/岭南地域特色和产品差异化优势
- 输出格式清晰，用markdown排版""",
            user_message=f"请为「{product}」撰写{fmt}文案。\n{extra_text}"
        )
        return jsonify({"success": True, "copywriting": result, "format": fmt})
    except Exception as e:
        logger.error(f"文案生成失败: {e}")
        fallback = generate_fallback_copywriting(product, fmt)
        return jsonify({"success": True, "copywriting": fallback, "format": fmt})


def generate_fallback_copywriting(product, fmt):
    """生成fallback文案"""
    if fmt == '详情页':
        return f"""## {product} · 岭南鲜味直达

### 一口入夏，满嘴甘甜

**核心卖点**
- **产地直供** — 来自广东核心产区，北纬23°黄金种植带
- **严选品质** — 每一颗都经过人工筛选，果径≥28mm
- **新鲜直达** — 采摘后48小时内发货，冷链保鲜
- **安心保障** — 通过农残检测，附检测报告

**适用场景**
- 夏日冰镇鲜食，消暑解渴
- 送礼佳品，精美礼盒装
- 家庭分享，亲子时光

**品质承诺**
不新鲜包退，坏果包赔，让您买的放心，吃的安心。

> 限时特惠，前100名下单送定制冰袋"""

    elif fmt == '主图文案':
        return f"""**主图文案（5条）**

1. **岭南直供·{product}** — 核心卖点
2. **到手价仅¥69** — 价格优势
3. **48h产地直发** — 品质保障
4. **限时买二送一** — 促销活动
5. **一口入夏的甜蜜** — 情感场景"""

    elif fmt == '朋友圈':
        return f"""今天收到了从广东寄来的{product}，打开箱子那一刻，整个房间都是清甜的果香🌿

颗颗饱满，皮薄肉厚，一口咬下去汁水四溢，甜度刚刚好，是那种自然的清甜，不是齁甜。

产地直发的，比超市新鲜太多了，家里老人小孩都爱吃。

想尝鲜的朋友扣1，我发链接给你们～"""

    elif fmt == '小红书':
        return f"""🌿广东人的夏天，从这口{product}开始！

姐妹们！！这个{product}真的绝了😭 从广东产地直发的，打开箱子那股清香直接梦回岭南～

✨真实体验：
• 颗颗饱满，皮超薄，轻轻一剥就开
• 肉厚核小，一口下去全是汁水
• 甜度刚好，是那种清甜不腻的感觉
• 比超市买的新鲜太多太多了！

💡小tips：
1. 收到后放冰箱冷藏2小时口感更佳
2. 送人的话选礼盒装，很有面子
3. 现在买还有限时优惠，赶紧冲！

#广东美食 #时令水果 #夏日限定 #吃货日记 #好物分享"""

    else:
        return f"""**短视频脚本（25秒）**

**【0-3秒】开场hook**
"广东人夏天最馋的水果，你猜是什么？"

**【3-8秒】产品展示**
（镜头给到{product}特写）
"看这个品相，颗颗饱满，色泽鲜亮，从广东产地直发的。"

**【8-15秒】核心卖点**
（剥开展示果肉）
"皮薄肉厚，一口下去汁水四溢，甜度刚刚好。"

**【15-20秒】价格促单**
"原价128，今天直播间只要69，还包邮！"

**【20-25秒】行动指令**
"想要的赶紧点下方链接，手慢无！" """


@app.route('/api/ecommerce/store-design', methods=['POST'])
def get_store_design():
    """AI店铺装修指导 - 多模块、多平台"""
    data = request.get_json()
    store_type = data.get('store_type', '农产品')
    platform = data.get('platform', '淘宝')
    style = data.get('style', '清新自然')
    module = data.get('module', '首页布局')
    product = data.get('product', '')
    needs = data.get('needs', '')

    module_prompts = {
        '首页布局': {
            'desc': '店铺首页整体布局规划',
            'output': '''请按以下结构输出首页布局指导：

## 首屏（Banner区）
- 轮播图数量、尺寸建议
- 主推产品/活动海报设计要点
- 文案风格和字体建议

## 导航区
- 分类导航的逻辑和排列
- 图标/文字导航的选择建议

## 核心展示区
- 爆款产品展示模块设计
- 产品卡片的布局（图片/标题/价格/销量）

## 信任区
- 资质展示、好评截图、物流保障

## 底部区
- 店铺故事、联系方式、售后承诺

每个模块给出具体的尺寸、配色、排版建议。'''
        },
        '色彩方案': {
            'desc': '店铺整体色彩搭配方案',
            'output': '''请按以下结构输出色彩方案：

## 主色调
- 推荐色值（HEX）和使用场景
- 色彩心理分析

## 辅助色
- 2-3个辅助色及色值
- 搭配比例建议

## 强调色
- 按钮、价格、促销标签用色

## 背景色
- 页面背景、模块背景、卡片背景

## 实际应用
- Banner配色示例
- 产品卡片配色示例
- 按钮和文字配色示例

给出具体的HEX色值，可直接使用。'''
        },
        '详情页设计': {
            'desc': '商品详情页设计指导',
            'output': '''请按以下结构输出详情页设计指导：

## 页面结构（从上到下）
1. 商品主图区（轮播、视频位）
2. 价格与促销区
3. 规格选择区
4. 卖点亮点区（图文结合）
5. 产品参数区
6. 场景展示区
7. 细节特写区
8. 品质保障区
9. 用户评价区
10. 关联推荐区

每个区域的设计要点、排版建议、注意事项。'''
        },
        '主图设计': {
            'desc': '产品主图/白底图设计',
            'output': '''请按以下结构输出主图设计指导：

## 主图规范
- 各平台尺寸要求
- 白底图/场景图/透明底的区别

## 5张主图策略
- 第1张：白底产品图
- 第2张：场景使用图
- 第3张：卖点特写图
- 第4张：规格对比图
- 第5张：促销/赠品图

## 设计技巧
- 构图法则（三分法、对角线）
- 光影处理
- 背景选择
- 文字叠加技巧

## 避坑指南
- 常见违规点
- 审核不通过的原因'''
        },
        '分类导航': {
            'desc': '店铺分类导航设计',
            'output': '''请按以下结构输出分类导航设计：

## 导航逻辑
- 按品类/场景/人群/价格的分类方式
- 推荐的分类层级（不超过3级）

## 视觉设计
- 图标+文字 vs 纯文字导航
- 图标风格建议（线性/面性/手绘）
- 选中态和默认态设计

## 推荐分类
根据店铺类型推荐具体的分类名称和排列顺序

## 交互细节
- 悬停效果
- 移动端适配
- 快速跳转'''
        }
    }

    config = module_prompts.get(module, module_prompts['首页布局'])
    extra_info = f"店铺类型：{store_type}\n电商平台：{platform}\n视觉风格：{style}"
    if product:
        extra_info += f"\n主营产品：{product}"
    if needs:
        extra_info += f"\n具体需求：{needs}"

    try:
        result = call_ai_service(
            system_prompt=f"""你是资深电商视觉设计专家，擅长店铺装修和视觉营销。

【指导模块】{config['desc']}
【输出要求】{config['output']}

【通用要求】
- 给出具体的数值（尺寸、色值、字号），可直接执行
- 考虑平台特性（{platform}的规则和用户习惯）
- 配色要符合「{style}」风格
- 农产品店铺要体现新鲜、健康、产地特色
- 用markdown格式输出，层次清晰""",
            user_message=extra_info
        )
        return jsonify({"success": True, "design": result, "module": module})
    except Exception as e:
        logger.error(f"装修指导失败: {e}")
        fallback = generate_fallback_store_design(store_type, platform, style, module)
        return jsonify({"success": True, "design": fallback, "module": module})


def generate_fallback_store_design(store_type, platform, style, module):
    """生成fallback装修指导"""
    style_colors = {
        '清新自然': {'primary': '#2ECC71', 'secondary': '#A8E6CF', 'accent': '#FF6B6B', 'bg': '#F8FFF8'},
        '高端大气': {'primary': '#1A1A2E', 'secondary': '#C9A96E', 'accent': '#E8D5B7', 'bg': '#FAFAFA'},
        '年轻活泼': {'primary': '#FF6B9D', 'secondary': '#C44569', 'accent': '#F8B500', 'bg': '#FFF5F5'},
        '传统国风': {'primary': '#8B0000', 'secondary': '#D4A574', 'accent': '#FFD700', 'bg': '#FFF8F0'}
    }
    colors = style_colors.get(style, style_colors['清新自然'])

    if module == '色彩方案':
        return f"""## {style}风格 · 色彩方案

### 主色调
- **{colors['primary']}** — 用于标题、导航栏、重点按钮
- 色彩心理：传达品牌核心气质

### 辅助色
- **{colors['secondary']}** — 模块背景、标签底色
- **{colors['accent']}** — 价格标注、促销标签、行动按钮

### 背景色
- 页面背景：**{colors['bg']}**
- 模块背景：**#FFFFFF**
- 卡片背景：**#FFFFFF**（带轻微阴影）

### 文字色
- 标题文字：**#333333**
- 正文文字：**#666666**
- 辅助文字：**#999999**

### 配色比例
- 主色占60%（背景、大色块）
- 辅助色占30%（模块、卡片）
- 强调色占10%（按钮、价格、标签）

### 实际应用示例
- Banner背景：{colors['primary']}渐变到{colors['secondary']}
- 价格文字：{colors['accent']}加粗
- 立即购买按钮：{colors['accent']}背景+白色文字"""

    elif module == '主图设计':
        return f"""## 产品主图设计指导

### 尺寸规范
- {platform}主图：800×800px（1:1正方形）
- 白底图：800×800px，纯白背景#FFFFFF
- 详情页长图：750×不限（宽度固定）

### 5张主图策略
1. **白底产品图** — 正面45°角，展示产品全貌
2. **场景图** — 产品在真实使用场景中（果园、餐桌）
3. **卖点特写** — 放大展示果肉、细节、品质
4. **规格对比** — 与参照物对比展示大小
5. **促销信息** — 赠品、优惠、礼盒展示

### 构图技巧
- 产品占画面60-70%
- 留白区域放文字信息
- 光线从左上方45°照射
- 背景虚化突出主体

### 避坑指南
- ❌ 不能有牛皮癣（过多文字覆盖）
- ❌ 不能有其他平台水印
- ❌ 不能虚假宣传
- ✅ 可以有品牌logo（左上角，不超过1/4）"""

    elif module == '详情页设计':
        return f"""## 商品详情页设计指导

### 页面结构（从上到下）

**1. 商品主图区**
- 5-8张轮播图 + 1个短视频
- 第一张必须是白底图

**2. 价格促销区**
- 原价（划线）→ 现价（红色大字）
- 优惠券领取入口
- 满减/赠品信息

**3. 卖点亮点区**
- 3-4个核心卖点，图文结合
- 每个卖点：图标 + 标题 + 1句话描述
- 建议用对比图（vs普通产品）

**4. 产品参数区**
- 产地、品种、规格、保质期、储存方式
- 表格形式展示

**5. 场景展示区**
- 2-3个使用场景图
- 配场景文案

**6. 品质保障区**
- 检测报告、资质证书
- 物流保障、售后承诺

### 设计要点
- 图片宽度：750px
- 每张图高度：300-500px
- 文字不超过图片面积的20%
- 配色与店铺主色调一致"""

    elif module == '分类导航':
        return f"""## 分类导航设计指导

### 导航逻辑
建议按以下维度分类（选1-2种组合）：
- **按品类**：鲜果、干货、礼盒、零食
- **按场景**：自用、送礼、团购、批发
- **按人群**：家庭装、尝鲜装、送礼装

### 推荐分类（{store_type}）
1. 🔥 爆款推荐
2. 🍎 当季鲜果
3. 🎁 精选礼盒
4. 🏷️ 特惠专区
5. 📦 家庭囤货
6. 🌿 新品尝鲜

### 视觉设计
- 图标风格：线性图标，2px描边
- 图标大小：48×48px
- 文字：14px，中等字重
- 间距：上下16px，左右12px

### 交互效果
- 默认态：灰色图标 + 灰色文字
- 选中态：主色图标 + 主色文字 + 底部色条
- 悬停态：背景变为浅灰色"""

    else:  # 首页布局
        return f"""## {store_type}首页布局指导

### 首屏（Banner区）
- 尺寸：750×350px（{platform}标准）
- 内容：当季主打产品 + 促销活动
- 轮播数量：3-5张
- 文案：大标题12-16字，副标题8-12字

### 导航区
- 分类数量：5-8个
- 排列：横向滑动或2行网格
- 图标+文字形式

### 核心展示区
- 爆款单品：大图展示，1-2个
- 热销排行：3-4个产品卡片
- 新品推荐：2-3个产品卡片

### 信任区
- 资质证书：横排展示2-3个
- 好评截图：精选3-5条
- 物流保障：图标+文字说明

### 配色建议
- 主色：{colors['primary']}
- 辅助色：{colors['secondary']}
- 强调色：{colors['accent']}
- 背景：{colors['bg']}"""


@app.route('/api/ecommerce/customer-service', methods=['POST'])
def simulate_customer_service():
    """AI客服模拟 - 多场景、多性格、实时评分"""
    data = request.get_json()
    message = data.get('message', '')
    history = data.get('history', [])
    scenario = data.get('scenario', '售前咨询')
    difficulty = data.get('difficulty', '进阶')
    personality = data.get('personality', '友善型')
    product = data.get('product', '荔枝')

    # 场景配置
    scenario_config = {
        '售前咨询': {
            'desc': '客户询问产品信息、价格、发货等',
            'customer_prompts': [
                '我想买{product}，新鲜吗？', '你们的{product}多少钱？', '{product}甜不甜？',
                '发货快吗？几天能到？', '有没有礼盒装？', '可以试吃吗？',
                '你们的{product}和别家有什么区别？', '产地是哪里的？'
            ]
        },
        '售后处理': {
            'desc': '客户收到货后反馈问题',
            'customer_prompts': [
                '我收到的{product}有几个坏的', '收到的和图片不一样啊',
                '物流太慢了，等了好久', '口感没有描述的那么好',
                '我要退货，怎么操作？', '包装破了，{product}都压坏了',
                '发错货了，我订的不是这个', '怎么和上次买的不一样？'
            ]
        },
        '投诉应对': {
            'desc': '客户情绪激动，需要安抚和解决',
            'customer_prompts': [
                '你们这是什么质量！太差了！', '我要投诉你们！太坑了！',
                '再也不买了，骗子！', '我要给差评！退款！',
                '等了一个星期还没到，什么意思？', '客服在吗？怎么一直不回复？',
                '你们是不是卖假货？', '我要找平台介入！'
            ]
        },
        '议价谈判': {
            'desc': '客户要求优惠、降价、赠品',
            'customer_prompts': [
                '能便宜点吗？', '买多几箱有优惠吗？', '别家比你们便宜啊',
                '送点赠品呗', '老客户了，给个优惠价', '零头去掉行不行？',
                '下次还买能打折吗？', '我介绍朋友来买，能便宜不？'
            ]
        },
        '产品推荐': {
            'desc': '客户不确定买什么，需要推荐',
            'customer_prompts': [
                '你们有什么好吃的推荐？', '送人买什么比较好？',
                '第一次买，选哪个品种？', '家里老人吃什么合适？',
                '哪个性价比最高？', '有没有适合煲汤的？',
                '当季有什么新鲜的？', '我想买点特产，有推荐吗？'
            ]
        }
    }

    # 客户性格配置
    personality_config = {
        '友善型': '语气友好、有耐心、好说话，容易被说服',
        '急躁型': '语气急躁、没耐心、喜欢催促，需要快速回应',
        '犹豫型': '犹豫不决、反复比较、需要更多说服和信心',
        '挑剔型': '要求高、爱挑毛病、注重细节、不好糊弄'
    }

    sc = scenario_config.get(scenario, scenario_config['售前咨询'])
    pc = personality_config.get(personality, personality_config['友善型'])

    # 难度调整
    diff_prompt = {
        '新手': '客户问题简单直接，容易回答，不太会追问',
        '进阶': '客户会追问细节、比较竞品，需要专业回答',
        '挑战': '客户很挑剔、会质疑回答、要求证据、不好对付'
    }

    system_prompt = f"""【重要】你必须只扮演客户角色，绝对不能扮演客服！

你的身份：一个想买{product}的网购客户。
性格：{pc}
场景：{scenario}（{sc['desc']}）
难度：{diff_prompt.get(difficulty, diff_prompt['进阶'])}

【你只能说客户该说的话】
- 提出问题、表达顾虑、追问细节
- 对客服的回答表示满意或不满
- 提出新的要求或疑虑
- 绝对不能说"亲""您好""帮您处理"等客服用语

【对话节奏】
- 客服回答好 → 表示认可，可以追问或说"那行，我下单了"
- 客服回答差 → 追问、质疑、表达不满
- 客服没解决问题 → 继续追问，不要轻易放过

【回复要求】
- 不超过60字
- 口语化，像真人在聊天
- 不要输出括号里的动作描述
- 不要输出任何解释，只输出客户说的话"""

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-8:]:
            messages.append({"role": h.get('role', 'user'), "content": h.get('content', '')})
        messages.append({"role": "user", "content": message})

        import requests as req
        headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": AI_MODEL, "messages": messages, "temperature": 0.7, "max_tokens": 200}
        resp = req.post(AI_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        reply = resp.json()['choices'][0]['message']['content'].strip()

        # 分析客服表现
        score = analyze_service_reply(message, reply, scenario, history)

        return jsonify({"success": True, "reply": reply, "score": score})
    except Exception as e:
        logger.error(f"客服模拟失败: {e}")
        # 根据对话历史和客服回复动态生成fallback
        reply = generate_dynamic_fallback(scenario, product, personality, history, message)
        score = analyze_service_reply(message, reply, scenario, history)
        return jsonify({"success": True, "reply": reply, "score": score})


def generate_dynamic_fallback(scenario, product, personality, history, last_reply):
    """根据对话上下文动态生成客户回复（不依赖AI）"""
    import random

    # 统计对话轮数
    rounds = len([h for h in history if h.get('role') == 'user'])

    # 分析客服回复的关键词
    has_apology = any(w in last_reply for w in ['抱歉', '不好意思', '对不起', 'sorry'])
    has_solution = any(w in last_reply for w in ['补发', '退款', '换货', '处理', '解决', '补偿'])
    has_data = any(w in last_reply for w in ['甜度', '产地', '品种', '规格', '检测', '冷链'])
    has_price = any(w in last_reply for w in ['优惠', '打折', '便宜', '减', '送'])
    has_greeting = any(w in last_reply for w in ['亲', '您好', '欢迎'])

    if scenario == '售前咨询':
        if rounds <= 1:
            options = [
                f"这个{product}到底新不新鲜啊？能发个实拍看看吗？",
                f"你们的{product}多少钱一斤？比别家贵不？",
                f"{product}是哪里产的？当季的吗？",
                f"我想买点{product}，发货快吗？几天能到？"
            ]
        elif has_data:
            options = [
                "听起来还不错，有没有买家秀看看？",
                "那和其他家比你们有什么优势？",
                "可以先买少一点试试吗？",
                "礼盒装多少钱？送人合适吗？"
            ]
        elif has_price:
            options = [
                "这个价格能再便宜点不？",
                "买多几箱有优惠吗？",
                "行吧，那我先下一单试试",
                "有没有满减活动？"
            ]
        else:
            options = [
                "嗯...我再看看吧",
                "你说的这些我不太懂，能简单点说吗？",
                "那你们售后怎么样？坏了怎么办？",
                "行，我考虑一下"
            ]

    elif scenario == '售后处理':
        if has_apology and has_solution:
            options = [
                "那行吧，你帮我处理一下",
                "补发的话多久能到？",
                "退款多久能到账？",
                "这次就算了，下次注意点"
            ]
        elif has_apology:
            options = [
                "光道歉有什么用，倒是给个解决方案啊",
                "我都等了好几天了，怎么处理？",
                "那你说怎么办吧"
            ]
        else:
            options = [
                f"我收到的{product}有几个坏的，你们怎么处理？",
                "你们客服怎么回事？半天不处理",
                "我要退货，怎么操作？",
                "包装都破了，东西都压坏了"
            ]

    elif scenario == '投诉应对':
        if rounds >= 4:
            options = [
                "行吧，这次就这样吧",
                "那你赶紧处理吧，我等着",
                "补偿就算了，下次别这样了",
                "我再信你们一次"
            ]
        elif has_apology:
            options = [
                "道歉有什么用？我要实际的解决方案！",
                "你们每次都这样说，有啥用？",
                "那你说怎么补偿吧"
            ]
        else:
            options = [
                "你们这是什么服务态度！太差了！",
                "我要投诉你们！太坑了！",
                "再也不买了，什么玩意儿！",
                "找你们领导来！"
            ]

    elif scenario == '议价谈判':
        if has_price:
            options = [
                "还是有点贵，再便宜点呗",
                "行吧，那你送点赠品",
                "那我先买一箱试试",
                "下次再来买能给老客户价不？"
            ]
        else:
            options = [
                "能便宜点吗？别家比你们便宜啊",
                "买两箱给个优惠价呗",
                "零头去掉行不行？",
                "送点赠品呗，我介绍朋友也来买"
            ]

    else:  # 产品推荐
        if rounds <= 1:
            options = [
                "你们有什么好吃的推荐？",
                "第一次来，哪个比较好？",
                "送人买什么合适？",
                "当季有什么新鲜的？"
            ]
        else:
            options = [
                "这个口感怎么样？甜不甜？",
                "那就要这个吧，怎么下单？",
                "有没有礼盒装的？",
                "行，我再看看其他的"
            ]

    # 根据性格调整
    if personality == '急躁型':
        options = [o + '！快点回复' if random.random() > 0.5 else o for o in options]
    elif personality == '挑剔型':
        if random.random() > 0.5:
            options.append('你确定没问题吧？我可不好糊弄')

    return random.choice(options)


def analyze_service_reply(customer_msg, ai_reply, scenario, history):
    """分析客服（用户）的回复质量"""
    # customer_msg 就是客服（用户）当前发送的消息
    last_user_msg = customer_msg

    scores = {
        'politeness': 50,   # 礼貌度
        'professional': 50, # 专业度
        'solving': 50,      # 解决问题能力
        'empathy': 50,      # 同理心
    }
    tips = []

    # 礼貌度检测
    polite_words = ['亲', '您好', '感谢', '抱歉', '不好意思', '请', '麻烦', '感谢您']
    polite_count = sum(1 for w in polite_words if w in last_user_msg)
    scores['politeness'] = min(95, 50 + polite_count * 12)
    if polite_count == 0:
        tips.append('开头用"亲"或"您好"会更亲切')

    # 专业度检测
    pro_words = ['产地', '品种', '甜度', '规格', '发货', '冷链', '检测', '新鲜', '当季', '直发']
    pro_count = sum(1 for w in pro_words if w in last_user_msg)
    scores['professional'] = min(95, 45 + pro_count * 10)
    if pro_count < 2:
        tips.append('加入产品专业信息（产地、品种、规格）更有说服力')

    # 解决问题能力
    solving_words = ['可以', '没问题', '帮您', '给您', '安排', '处理', '解决方案', '补偿', '退款', '换货']
    solving_count = sum(1 for w in solving_words if w in last_user_msg)
    scores['solving'] = min(95, 40 + solving_count * 12)
    if solving_count < 2 and scenario in ['售后处理', '投诉应对']:
        tips.append('明确告诉客户解决方案，如"帮您补发""给您退款"')

    # 同理心检测
    empathy_words = ['理解', '抱歉', '不好意思', '确实', '换做我', '体谅', '心情', '感受']
    empathy_count = sum(1 for w in empathy_words if w in last_user_msg)
    scores['empathy'] = min(95, 40 + empathy_count * 15)
    if empathy_count == 0 and scenario in ['投诉应对', '售后处理']:
        tips.append('先表达理解和歉意，再解决问题效果更好')

    # 长度合理性
    if len(last_user_msg) < 10:
        tips.append('回复太短，客户可能觉得敷衍')
    elif len(last_user_msg) > 200:
        tips.append('回复太长，客户可能没耐心看完')

    total = round(sum(scores.values()) / 4)

    # 通用建议
    if not tips:
        if total >= 85:
            tips.append('回复很棒！继续保持')
        elif total >= 70:
            tips.append('整体不错，可以再多一些情感表达')
        else:
            tips.append('多站在客户角度思考，理解他们的真实需求')

    return {
        'total': total,
        'details': scores,
        'tips': tips[:2]
    }


@app.route('/api/ecommerce/customer-service/next', methods=['POST'])
def get_next_customer_msg():
    """AI生成下一句客户消息（用于主动引导对话）"""
    data = request.get_json()
    scenario = data.get('scenario', '售前咨询')
    personality = data.get('personality', '友善型')
    product = data.get('product', '荔枝')
    history = data.get('history', [])

    sc_map = {
        '售前咨询': f'询问{product}的品质、价格、发货等信息',
        '售后处理': f'反馈收到的{product}有问题，要求处理',
        '投诉应对': f'对{product}或服务不满意，情绪激动',
        '议价谈判': f'想买{product}但要求优惠',
        '产品推荐': f'想买{product}但不确定选什么'
    }

    try:
        result = call_ai_service(
            system_prompt=f"""你是一个电商客户，性格：{personality}。
场景：{scenario}，{sc_map.get(scenario, '')}。
请生成一句自然的客户开场白或追问，不超过50字，口语化。
只输出客户说的话，不要其他内容。""",
            user_message="请生成一句客户消息"
        )
        return jsonify({"success": True, "message": result.strip()})
    except:
        fallback = {
            '售前咨询': f'你好，这个{product}怎么卖？',
            '售后处理': f'我收到的{product}有问题，怎么办？',
            '投诉应对': '你们客服呢？怎么半天不回复？',
            '议价谈判': '能便宜点不？',
            '产品推荐': '有什么推荐的吗？'
        }
        return jsonify({"success": True, "message": fallback.get(scenario, '你好')})


@app.route('/api/ecommerce/customer-service/hint', methods=['POST'])
def get_service_hint():
    """根据当前对话动态生成回复建议"""
    data = request.get_json()
    scenario = data.get('scenario', '售前咨询')
    personality = data.get('personality', '友善型')
    product = data.get('product', '荔枝')
    history = data.get('history', [])
    last_customer_msg = data.get('last_customer_msg', '')

    # 获取最近的对话上下文
    recent = history[-4:] if len(history) > 4 else history
    context = '\n'.join(
        f"{'客户' if h.get('role') == 'assistant' else '客服'}：{h.get('content', '')}"
        for h in recent
    )

    try:
        result = call_ai_service(
            system_prompt=f"""你是客服培训专家。根据当前对话情况，给出具体的回复建议。

【场景】{scenario}，客户性格：{personality}，产品：{product}

【输出格式】严格JSON，不要其他文字：
{{
    "analysis": "客户当前的真实需求/情绪（15字内）",
    "strategy": "推荐的回复策略（15字内）",
    "templates": ["建议回复1（可直接复制使用）", "建议回复2", "建议回复3"],
    "tips": ["注意事项1", "注意事项2"]
}}

【要求】
- 建议回复要口语化、自然、不超过50字
- 根据客户性格调整语气（急躁的要快速回应，犹豫的要给信心）
- 根据对话阶段调整策略（初期多了解需求，中期解决问题，后期促单）""",
            user_message=f"最近对话：\n{context}\n\n客户最新消息：{last_customer_msg}\n\n请给出回复建议。"
        )
        import re, json
        json_match = re.search(r'\{.*?\}', result, re.DOTALL)
        hint = json.loads(json_match.group()) if json_match else {}
        return jsonify({"success": True, "hint": hint})
    except:
        # 根据对话上下文动态生成建议
        hint = generate_dynamic_hint(scenario, product, personality, last_customer_msg, history)
        return jsonify({"success": True, "hint": hint})


def generate_dynamic_hint(scenario, product, personality, last_msg, history):
    """根据对话上下文动态生成回复建议"""
    import random

    rounds = len([h for h in history if h.get('role') == 'user'])

    # 分析客户消息的关键词
    ask_price = any(w in last_msg for w in ['多少钱', '价格', '贵', '便宜', '优惠'])
    ask_quality = any(w in last_msg for w in ['新鲜', '甜', '好吃', '品质', '质量'])
    ask_delivery = any(w in last_msg for w in ['发货', '几天', '到货', '快递', '物流'])
    ask_refund = any(w in last_msg for w in ['退货', '退款', '换货', '坏了', '破损'])
    is_angry = any(w in last_msg for w in ['差评', '投诉', '骗子', '垃圾', '太差'])
    is_hesitating = any(w in last_msg for w in ['考虑', '想想', '再看看', '犹豫'])

    if scenario == '售前咨询':
        if ask_price:
            return {
                'analysis': '客户在关注价格',
                'strategy': '强调性价比+给优惠',
                'templates': [
                    f'亲，我们的{product}是产地直发，性价比很高的',
                    '现在有满减活动，买两箱更划算哦',
                    '这个价格包含顺丰包邮，很值了'
                ],
                'tips': ['不要直接报最低价', '先强调价值再说价格']
            }
        elif ask_quality:
            return {
                'analysis': '客户在担心品质',
                'strategy': '用数据和证据打消顾虑',
                'templates': [
                    f'我们的{product}甜度达到18度以上，每批都检测的',
                    '给您看下我们的检测报告和实拍图',
                    '很多老客户都回购的，您可以看看评价'
                ],
                'tips': ['用具体数据说话', '提供证据增加信任']
            }
        elif ask_delivery:
            return {
                'analysis': '客户关心物流时效',
                'strategy': '明确告知时效+保障',
                'templates': [
                    '今天下单明天就能发货，顺丰2-3天到',
                    '我们用冷链运输，保证新鲜到家',
                    '省内次日达，省外2-3天，很快的'
                ],
                'tips': ['给出明确的时间', '强调物流保障']
            }
        elif is_hesitating:
            return {
                'analysis': '客户在犹豫中',
                'strategy': '制造紧迫感+给信心',
                'templates': [
                    f'现在{product}正是最好吃的时候，错过要等明年了',
                    '今天下单还有限时优惠哦',
                    '不满意可以退货退款，您没有风险的'
                ],
                'tips': ['用限时限量促单', '打消售后顾虑']
            }
        else:
            templates = [
                f'亲，您是自己吃还是送人呢？我帮您推荐',
                f'我们的{product}是当季新鲜的，很多客户都回购',
                '您有什么顾虑可以告诉我，我帮您解答'
            ]
            return {
                'analysis': '客户在了解产品',
                'strategy': '主动引导+了解需求',
                'templates': templates,
                'tips': ['主动问客户需求', '用提问引导对话']
            }

    elif scenario == '售后处理':
        if ask_refund:
            return {
                'analysis': '客户要退换货',
                'strategy': '快速处理+减少损失',
                'templates': [
                    '亲，非常抱歉给您带来不便，马上帮您处理',
                    '您看是补发还是退款呢？我这边都可以',
                    '方便拍个照片给我看看吗？我好给您处理'
                ],
                'tips': ['先道歉再处理', '给客户选择权']
            }
        elif rounds <= 2:
            return {
                'analysis': '客户刚开始反馈问题',
                'strategy': '耐心倾听+了解详情',
                'templates': [
                    '亲，非常抱歉给您带来不好的体验',
                    '方便告诉我具体是什么情况吗？',
                    '您放心，我们一定会给您处理好的'
                ],
                'tips': ['不要急着辩解', '先让客户说完']
            }
        else:
            return {
                'analysis': '客户等待解决方案',
                'strategy': '给出明确方案+补偿',
                'templates': [
                    '我这边马上帮您安排补发，您看可以吗？',
                    '给您退款+送一张20元优惠券，您看行吗？',
                    '这次真的很抱歉，下次一定注意'
                ],
                'tips': ['方案要具体可执行', '适当给些补偿']
            }

    elif scenario == '投诉应对':
        if is_angry:
            return {
                'analysis': '客户情绪很激动',
                'strategy': '先安抚情绪再处理',
                'templates': [
                    '亲，真的很抱歉，您的心情我完全理解',
                    '这种情况确实不应该发生，我马上帮您处理',
                    '您先消消气，我一定给您一个满意的答复'
                ],
                'tips': ['不要反驳', '让客户先发泄']
            }
        elif rounds >= 4:
            return {
                'analysis': '客户情绪已缓和',
                'strategy': '提出补偿方案',
                'templates': [
                    '给您申请一张50元无门槛优惠券可以吗？',
                    '这次我们全额退款，东西您留着',
                    '以后您来我们店都是VIP价格'
                ],
                'tips': ['补偿要有诚意', '让客户感受到重视']
            }
        else:
            return {
                'analysis': '客户在表达不满',
                'strategy': '真诚道歉+表达重视',
                'templates': [
                    '亲，真的很抱歉给您带来这么差的体验',
                    '您反馈的问题我们非常重视',
                    '我马上帮您处理，您看怎么补偿比较合适？'
                ],
                'tips': ['态度要诚恳', '不要推卸责任']
            }

    elif scenario == '议价谈判':
        if rounds >= 3:
            return {
                'analysis': '客户多次议价',
                'strategy': '给底线优惠促单',
                'templates': [
                    '亲，这真的是最低价了，我给您申请个赠品吧',
                    '行，给您打个9折，这是最大优惠了',
                    '送您一包试吃装，满意下次再来'
                ],
                'tips': ['守住底线', '用赠品代替降价']
            }
        elif ask_price:
            return {
                'analysis': '客户想要优惠',
                'strategy': '强调价值+阶梯优惠',
                'templates': [
                    f'亲，我们的{product}品质对得起这个价的',
                    '买两箱可以给您打9折哦',
                    '现在下单送试吃装，不满意包退'
                ],
                'tips': ['先说价值再说优惠', '给阶梯优惠']
            }
        else:
            return {
                'analysis': '客户在比较价格',
                'strategy': '突出差异化优势',
                'templates': [
                    '我们的和别家不一样的，您看这个品相',
                    '我们是产地直发，没有中间商赚差价',
                    '品质保证的，不满意随时退'
                ],
                'tips': ['强调品质差异', '不要打价格战']
            }

    else:  # 产品推荐
        if rounds <= 1:
            return {
                'analysis': '客户需要推荐',
                'strategy': '问需求再推荐',
                'templates': [
                    '请问您是自己吃还是送人呢？',
                    '您喜欢甜一点的还是清淡一点的？',
                    f'现在当季的{product}最好吃，推荐您试试'
                ],
                'tips': ['先了解需求', '不要盲目推荐']
            }
        else:
            return {
                'analysis': '客户在考虑选择',
                'strategy': '精准推荐+打消顾虑',
                'templates': [
                    f'这款是最受欢迎的{product}，回头客很多',
                    '送人的话推荐礼盒装，包装很有面子',
                    '您要几斤的？我帮您推荐合适的规格'
                ],
                'tips': ['推荐1-2款就行', '说明推荐理由']
            }


# ==================== 手工技能API ====================

@app.route('/api/crafts/list', methods=['GET'])
def get_crafts_list():
    crafts = [
        {"id": "embroidery", "name": "广绣", "level": "入门级", "origin": "广州"},
        {"id": "woodcarving", "name": "潮汕木雕", "level": "进阶级", "origin": "潮汕"},
        {"id": "ceramics", "name": "石湾陶艺", "level": "中级", "origin": "佛山"},
        {"id": "lacquer", "name": "阳江漆器", "level": "高级", "origin": "阳江"}
    ]
    return jsonify({"success": True, "crafts": crafts})


@app.route('/api/crafts/<craft_id>', methods=['GET'])
def get_craft_detail(craft_id):
    if craft_id in CRAFTS_KNOWLEDGE:
        return jsonify({"success": True, "data": CRAFTS_KNOWLEDGE[craft_id]})
    return jsonify({"success": False, "message": "未找到该手工艺信息"})


# ==================== 虚拟实训API ====================

# 病虫害知识库
PEST_KNOWLEDGE = {
    "lychee": {
        "name": "荔枝", "icon": "🍎",
        "common_diseases": [
            {"disease": "荔枝霜疫霉病", "confidence": 0.92, "severity": "中度",
             "symptoms": ["果实表面出现褐色不规则病斑", "湿度大时病斑表面长出白色霉层", "病果容易脱落", "果肉变褐发酸"],
             "treatment": ["及时清除病果落果并深埋", "加强果园排水降低湿度", "喷施甲霜灵·锰锌可湿性粉剂600倍液", "采收前20天停止用药"],
             "prevention": ["冬季清园减少病源", "合理修剪改善通风透光", "增施有机肥增强树势", "雨季前喷药预防"]},
            {"disease": "荔枝炭疽病", "confidence": 0.85, "severity": "轻度",
             "symptoms": ["叶片出现圆形或不规则褐色斑点", "斑点边缘深褐色中央灰白色", "严重时叶片枯萎脱落", "嫩梢变褐枯死"],
             "treatment": ["剪除病枝病叶集中烧毁", "喷施咪鲜胺乳油1000倍液", "加强肥水管理恢复树势"],
             "prevention": ["避免偏施氮肥", "雨后及时排水", "新梢期喷药保护"]}
        ]
    },
    "longan": {
        "name": "龙眼", "icon": "🟤",
        "common_diseases": [
            {"disease": "龙眼鬼帚病", "confidence": 0.88, "severity": "重度",
             "symptoms": ["新梢丛生呈扫帚状", "叶片狭小卷曲畸形", "花穗丛生不结果", "树势逐渐衰弱"],
             "treatment": ["及时剪除病梢病枝", "加强肥水管理", "喷施抗病毒药剂"],
             "prevention": ["选用无病苗木", "防治传毒昆虫", "加强果园管理"]},
            {"disease": "龙眼叶斑病", "confidence": 0.82, "severity": "轻度",
             "symptoms": ["叶片出现褐色小圆点", "逐渐扩大为不规则大斑", "后期病斑中央灰色", "严重时早期落叶"],
             "treatment": ["清除落叶减少病源", "喷施代森锰锌800倍液"],
             "prevention": ["保持果园清洁", "合理密植通风"]}
        ]
    },
    "banana": {
        "name": "香蕉", "icon": "🍌",
        "common_diseases": [
            {"disease": "香蕉枯萎病(巴拿马病)", "confidence": 0.90, "severity": "重度",
             "symptoms": ["叶片从外围向内逐渐变黄", "假茎纵裂维管束变褐", "整株枯死", "果实发育不良"],
             "treatment": ["立即隔离病株", "病穴用石灰消毒", "改种抗病品种"],
             "prevention": ["严格检疫种苗", "轮作换茬", "增施有机肥"]},
            {"disease": "香蕉叶斑病", "confidence": 0.86, "severity": "中度",
             "symptoms": ["叶片出现椭圆形褐色条斑", "病斑中央灰白色边缘深褐色", "多个病斑连片导致叶片枯死"],
             "treatment": ["剪除严重病叶", "喷施丙环唑乳油1000倍液", "交替用药防止抗性"],
             "prevention": ["合理密植", "清除田间病残体", "雨季前预防喷药"]}
        ]
    },
    "citrus": {
        "name": "柑橘", "icon": "🍊",
        "common_diseases": [
            {"disease": "柑橘黄龙病", "confidence": 0.91, "severity": "重度",
             "symptoms": ["叶片斑驳黄化", "新梢黄白", "果实畸形着色不均", "根系腐烂"],
             "treatment": ["立即挖除病株销毁", "防治柑橘木虱", "健壮苗木补种"],
             "prevention": ["种植无病苗木", "及时防治木虱", "加强栽培管理"]},
            {"disease": "柑橘溃疡病", "confidence": 0.84, "severity": "中度",
             "symptoms": ["叶片出现黄色油渍状小斑点", "扩大后呈褐色圆形溃疡", "果实表面出现木栓化突起"],
             "treatment": ["剪除病叶病果", "喷施氢氧化铜800倍液", "夏梢期重点防治"],
             "prevention": ["选用抗病品种", "控制氮肥用量", "雨后及时喷药"]}
        ]
    }
}

# 直播场景库
LIVE_SCENARIOS = [
    {"id": "opening", "name": "开场白", "icon": "🎬", "desc": "练习如何在30秒内抓住观众注意力",
     "prompts": ["请用一句话欢迎观众并介绍今天的产品", "设计一个引起好奇心的开场", "用一个故事开头吸引观众"],
     "tips": ["前5秒决定观众去留", "要有悬念或利益点", "声音要有感染力"]},
    {"id": "product_intro", "name": "产品介绍", "icon": "📦", "desc": "练习有逻辑地介绍产品卖点",
     "prompts": ["介绍这个产品的3个核心卖点", "用对比法突出产品优势", "讲述产品的产地故事"],
     "tips": ["FAB法则：特点→优势→利益", "用具体数字说话", "配合实物展示"]},
    {"id": "interaction", "name": "互动引导", "icon": "💬", "desc": "练习与观众互动提升参与感",
     "prompts": ["设计一个引导观众扣1的问题", "用选择题引导观众互动", "感谢观众并引导关注"],
     "tips": ["每3分钟一次互动", "点名感谢活跃观众", "用问题引导下单"]},
    {"id": "closing", "name": "促单话术", "icon": "🔥", "desc": "练习在关键时刻推动下单",
     "prompts": ["用限时限量制造紧迫感", "用从众心理促单", "给出下单的理由和步骤"],
     "tips": ["强调稀缺性", "降低决策门槛", "给出明确的下单指引"]},
    {"id": "objection", "name": "异议处理", "icon": "🛡️", "desc": "练习应对观众的质疑和异议",
     "prompts": ["观众说太贵了怎么回应", "观众质疑品质怎么回答", "观众说要考虑一下怎么引导"],
     "tips": ["先认同再引导", "用事实和数据说话", "不要和观众争论"]}
]

# 手工AR指导步骤
CRAFT_AR_GUIDES = {
    "embroidery": {
        "name": "广绣", "icon": "🧵",
        "steps": [
            {"step": 1, "title": "穿针引线", "desc": "选择合适的绣针，将丝线穿过针眼，线长不超过手臂长度",
             "action": "右手持针，左手捏线，对准针眼穿入", "check": "线头露出针眼2-3厘米",
             "common_mistakes": ["线太长容易打结", "线头分叉导致穿不进去"]},
            {"step": 2, "title": "起针定位", "desc": "从绣布背面起针，针脚落在图案轮廓线上",
             "action": "针从背面刺入，正面拉出，起针点在图案边缘", "check": "针脚均匀，间距约2毫米",
             "common_mistakes": ["起针位置偏差大", "针脚间距不均匀"]},
            {"step": 3, "title": "基础针法-直针", "desc": "直线绣是最基础的针法，用于勾勒轮廓",
             "action": "针从A点入B点出，形成直线", "check": "线条流畅无弯曲",
             "common_mistakes": ["用力不均导致线条歪斜", "针脚太长不美观"]},
            {"step": 4, "title": "填充针法-长短针", "desc": "长短针交替使用，用于填充花瓣等大面积区域",
             "action": "第一针长，第二针短，交替排列", "check": "颜色过渡自然，无明显空隙",
             "common_mistakes": ["针脚方向混乱", "颜色分层不自然"]},
            {"step": 5, "title": "收针打结", "desc": "绣完一段后在背面打结固定",
             "action": "针从背面穿过一个小针脚，绕两圈拉紧", "check": "结牢固不松脱，背面整洁",
             "common_mistakes": ["结太松容易散开", "线头留太长"]}
        ]
    },
    "woodcarving": {
        "name": "木雕", "icon": "🪵",
        "steps": [
            {"step": 1, "title": "选材备料", "desc": "选择纹理细腻、无裂纹的木材，樟木或檀木为佳",
             "action": "观察木材纹理，标记可用区域", "check": "木材含水量适中，无虫蛀",
             "common_mistakes": ["选了有暗裂的木材", "木材太湿容易变形"]},
            {"step": 2, "title": "画线描图", "desc": "在木材表面用铅笔描绘图案轮廓",
             "action": "用铅笔轻描图案，注意留出加工余量", "check": "线条清晰，比例协调",
             "common_mistakes": ["画得太深难以修改", "未考虑木纹方向"]},
            {"step": 3, "title": "粗坯定型", "desc": "用大号平刀去除多余木材，确定大体形状",
             "action": "刀口朝外，顺着木纹方向推削", "check": "轮廓基本成型，留有精修余量",
             "common_mistakes": ["逆纹雕刻导致劈裂", "一次去料太多无法补救"]},
            {"step": 4, "title": "精雕细刻", "desc": "用圆刀、三角刀雕刻细节纹理",
             "action": "换小号刻刀，逐步雕刻细节", "check": "纹理清晰，层次分明",
             "common_mistakes": ["用力过猛损伤细节", "刀具不够锋利导致毛边"]},
            {"step": 5, "title": "打磨抛光", "desc": "从粗砂纸到细砂纸逐级打磨",
             "action": "先用240目，再用400目，最后用800目", "check": "表面光滑无毛刺",
             "common_mistakes": ["跳级打磨留划痕", "忘记清理粉尘"]}
        ]
    },
    "ceramics": {
        "name": "陶瓷", "icon": "🏺",
        "steps": [
            {"step": 1, "title": "揉泥排气", "desc": "反复揉捏陶泥排出气泡，使泥质均匀",
             "action": "双手用力向前推压，反复折叠", "check": "切开无气泡，断面均匀",
             "common_mistakes": ["揉泥不充分有气泡", "泥太干容易开裂"]},
            {"step": 2, "title": "拉坯定型", "desc": "在转盘上将泥拉成所需的器型",
             "action": "双手沾水，从中心向外拉起", "check": "壁厚均匀，形状对称",
             "common_mistakes": ["转速不稳导致变形", "壁厚不均容易塌"]},
            {"step": 3, "title": "修坯整形", "desc": "坯体半干后用刮刀修整外形",
             "action": "用刮刀轻刮表面，修正不平整处", "check": "表面平滑，线条流畅",
             "common_mistakes": ["修得太薄", "坯体太湿被刮变形"]},
            {"step": 4, "title": "装饰刻画", "desc": "在坯体上刻画图案或贴花装饰",
             "action": "用竹签或刻刀在坯体上刻画", "check": "图案清晰，深浅一致",
             "common_mistakes": ["刻得太深穿透坯体", "图案比例失调"]},
            {"step": 5, "title": "上釉烧制", "desc": "均匀施釉后入窑烧制",
             "action": "浸釉或刷釉，厚度约1毫米", "check": "釉面均匀无气泡",
             "common_mistakes": ["釉层太厚流淌", "烧制温度不当导致开裂"]}
        ]
    }
}


@app.route('/api/simulation/diagnose', methods=['POST'])
def diagnose_pest():
    """AI病虫害诊断 — 支持多种作物和自定义症状"""
    data = request.get_json()
    crop = data.get('crop', 'lychee')
    user_symptoms = data.get('symptoms', '')

    # 根据用户描述匹配知识库
    crop_data = PEST_KNOWLEDGE.get(crop, PEST_KNOWLEDGE['lychee'])
    matched = crop_data['common_diseases'][0]  # 默认第一个

    # 如果用户描述了症状，尝试匹配
    if user_symptoms:
        user_lower = user_symptoms.lower()
        for d in crop_data['common_diseases']:
            score = sum(1 for s in d['symptoms'] if any(kw in user_lower for kw in s[:2]))
            if score > 0:
                matched = d
                break

    # 尝试调用AI获得更精准诊断
    try:
        symptom_text = user_symptoms if user_symptoms else '叶片发黄、有斑点'
        result = call_ai_service(
            system_prompt=f"""你是植物病虫害诊断专家，擅长诊断{crop_data['name']}的病虫害。
根据用户描述的症状给出诊断结果。返回JSON格式：
{{
    "disease": "病名",
    "confidence": 0.0-1.0之间的置信度,
    "severity": "轻度/中度/重度",
    "symptoms": ["症状1", "症状2", "症状3"],
    "treatment": ["治疗方案1", "治疗方案2", "治疗方案3"],
    "prevention": ["预防措施1", "预防措施2", "预防措施3"],
    "timing": "最佳防治时期",
    "note": "注意事项"
}}
只返回JSON，不要其他文字。""",
            user_message=f"作物：{crop_data['name']}\n症状描述：{symptom_text}"
        )
        try:
            # 清理可能的markdown包裹
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            diagnosis = json.loads(clean)
            diagnosis['crop'] = crop_data['name']
            diagnosis['crop_icon'] = crop_data['icon']
            return jsonify({"success": True, "diagnosis": diagnosis})
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.error(f"AI诊断失败: {e}")

    # 降级使用知识库
    diagnosis = {
        "disease": matched['disease'],
        "confidence": matched['confidence'],
        "severity": matched['severity'],
        "symptoms": matched['symptoms'],
        "treatment": matched['treatment'],
        "prevention": matched['prevention'],
        "timing": "发病初期为最佳防治期",
        "note": "建议结合当地农技站指导进行防治",
        "crop": crop_data['name'],
        "crop_icon": crop_data['icon']
    }
    return jsonify({"success": True, "diagnosis": diagnosis})


@app.route('/api/simulation/crops', methods=['GET'])
def get_sim_crops():
    """获取支持的作物列表"""
    crops = [{"id": k, "name": v['name'], "icon": v['icon']} for k, v in PEST_KNOWLEDGE.items()]
    return jsonify({"success": True, "crops": crops})


@app.route('/api/simulation/scenarios', methods=['GET'])
def get_live_scenarios():
    """获取直播训练场景列表"""
    return jsonify({"success": True, "scenarios": LIVE_SCENARIOS})


@app.route('/api/simulation/live-score', methods=['POST'])
def score_live_performance():
    """AI评分实训表现 — 支持按场景评分"""
    data = request.get_json()
    script_text = data.get('script', '')
    scenario = data.get('scenario', 'opening')
    duration = data.get('duration', 0)

    if not script_text.strip():
        return jsonify({"success": False, "message": "请先输入直播话术"})

    # 基于规则的评分（主逻辑，不依赖AI）
    def rule_based_score(text, scen):
        scores = {}
        text_len = len(text)

        # 语速流畅度：基于文本长度和结构
        sentences = [s.strip() for s in text.replace('！', '。').replace('？', '。').split('。') if s.strip()]
        avg_len = sum(len(s) for s in sentences) / max(len(sentences), 1)
        scores['speed'] = min(95, max(50, 80 - abs(avg_len - 15) * 2))

        # 清晰度：基于标点和分段
        has_structure = any(kw in text for kw in ['第一', '首先', '其次', '最后', '1.', '2.', '①', '②'])
        scores['clarity'] = 88 if has_structure else (75 if len(sentences) >= 3 else 62)

        # 互动性：检测互动词
        interaction_words = ['扣', '评论', '点赞', '关注', '分享', '告诉我', '你们', '大家', '宝宝们', '亲们']
        interaction_count = sum(1 for w in interaction_words if w in text)
        scores['engagement'] = min(95, max(45, 55 + interaction_count * 10))

        # 产品知识：检测专业词
        product_words = ['品质', '产地', '新鲜', '口感', '营养', '种植', '采摘', '甜度', '价格', '优惠', '限时', '秒杀']
        product_count = sum(1 for w in product_words if w in text)
        scores['product_knowledge'] = min(95, max(50, 55 + product_count * 8))

        # 场景匹配度
        scenario_keywords = {
            'opening': ['欢迎', '今天', '给大家', '看到', '来了'],
            'product_intro': ['卖点', '特点', '优势', '品质', '产地', '新鲜'],
            'interaction': ['扣', '评论', '告诉我', '觉得', '选择', '投票'],
            'closing': ['下单', '购买', '链接', '秒杀', '最后', '抓紧', '限量'],
            'objection': ['理解', '确实', '但是', '其实', '放心', '保证', '质量']
        }
        scen_kw = scenario_keywords.get(scenario, scenario_keywords['opening'])
        scen_match = sum(1 for kw in scen_kw if kw in text)
        scores['scenario_match'] = min(95, max(40, 50 + scen_match * 12))

        # 综合得分
        scores['overall'] = round(sum(scores.values()) / len(scores))

        # 生成反馈
        feedback_parts = []
        if scores['engagement'] < 70:
            feedback_parts.append('互动性不足，多用问句引导观众')
        if scores['product_knowledge'] < 70:
            feedback_parts.append('产品介绍可以更具体，加入数据')
        if scores['clarity'] < 70:
            feedback_parts.append('建议分点阐述，逻辑更清晰')
        if not feedback_parts:
            feedback_parts.append('表现不错！继续保持互动节奏')

        return scores, '；'.join(feedback_parts)

    scores, feedback = rule_based_score(script_text, scenario)

    # 尝试用AI增强评分
    try:
        result = call_ai_service(
            system_prompt=f"""你是直播实训评分专家。请对学员的直播话术进行评价。
训练场景：{next((s['name'] for s in LIVE_SCENARIOS if s['id'] == scenario), '开场白')}
返回JSON格式：
{{
    "speed": 0-100分,
    "clarity": 0-100分,
    "engagement": 0-100分,
    "product_knowledge": 0-100分,
    "scenario_match": 0-100分,
    "overall": 0-100分,
    "feedback": "具体评价和改进建议，2-3句话",
    "highlights": ["亮点1", "亮点2"],
    "improvements": ["改进1", "改进2"]
}}
只返回JSON。""",
            user_message=f"学员话术：\n{script_text}"
        )
        try:
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            ai_scores = json.loads(clean)
            # AI评分成功，使用AI结果
            return jsonify({"success": True, "score": ai_scores})
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.error(f"AI评分失败: {e}")

    # 降级使用规则评分
    return jsonify({"success": True, "score": {
        **scores,
        "feedback": feedback,
        "highlights": [k for k, v in scores.items() if v >= 80 and k != 'overall'],
        "improvements": [k for k, v in scores.items() if v < 70 and k != 'overall']
    }})


@app.route('/api/simulation/craft-ar', methods=['POST'])
def get_craft_ar_guide():
    """获取手工AR指导步骤"""
    data = request.get_json()
    craft = data.get('craft', 'embroidery')
    step = data.get('step', 1)

    guide = CRAFT_AR_GUIDES.get(craft, CRAFT_AR_GUIDES['embroidery'])
    step_data = next((s for s in guide['steps'] if s['step'] == step), guide['steps'][0])

    # 尝试用AI生成更详细的指导
    try:
        result = call_ai_service(
            system_prompt=f"""你是{guide['name']}技艺传承大师。请对以下步骤给出详细指导。
返回JSON格式：
{{
    "step": {step},
    "title": "步骤标题",
    "detailed_desc": "详细的步骤描述，100字左右",
    "action": "具体操作动作",
    "check": "完成标准",
    "common_mistakes": ["常见错误1", "常见错误2"],
    "pro_tips": ["专业技巧1", "专业技巧2"],
    "estimated_time": "预计耗时"
}}
只返回JSON。""",
            user_message=f"请指导{guide['name']}的第{step}步：{step_data['title']}"
        )
        try:
            clean = result.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            ai_guide = json.loads(clean)
            return jsonify({"success": True, "guide": ai_guide, "craft": guide['name'], "total_steps": len(guide['steps'])})
        except json.JSONDecodeError:
            pass
    except Exception as e:
        logger.error(f"AI指导失败: {e}")

    # 降级使用知识库
    return jsonify({"success": True, "guide": {
        "step": step_data['step'],
        "title": step_data['title'],
        "detailed_desc": step_data['desc'],
        "action": step_data['action'],
        "check": step_data['check'],
        "common_mistakes": step_data['common_mistakes'],
        "pro_tips": ["多练习是关键", "注意手法的稳定性"],
        "estimated_time": "约5-10分钟"
    }, "craft": guide['name'], "total_steps": len(guide['steps'])})


# ==================== 本土资源API ====================

# 方言知识库
DIALECTS_DATA = {
    "cantonese": {
        "id": "cantonese", "name": "粤语", "region": "广州话", "emoji": "🗣️",
        "areas": "广州、佛山、深圳、东莞、中山、珠海、江门",
        "speakers": "约7000万使用者",
        "greeting": "你好！食咗饭未？",
        "greeting_meaning": "你好！吃饭了吗？",
        "features": ["九声六调", "保留古汉语词汇", "大量外来语借词"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "nei5 hou2"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 ze6"},
            {"dialect": "几多钱？", "mandarin": "多少钱？", "pinyin": "gei2 do1 cin2"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "hou2 sik6"},
            {"dialect": "唔该", "mandarin": "麻烦/请", "pinyin": "m4 goi1"},
            {"dialect": "点解？", "mandarin": "为什么？", "pinyin": "dim2 gaai2"},
            {"dialect": "边度", "mandarin": "哪里", "pinyin": "bin1 dou6"},
            {"dialect": "靓", "mandarin": "漂亮/好", "pinyin": "leng3"}
        ],
        "quick_questions": [
            "荔枝点样施肥最好？",
            "龙眼几时可以摘？",
            "香蕉点样防虫？",
            "柑橘落叶点处理？"
        ]
    },
    "hakka": {
        "id": "hakka", "name": "客家话", "region": "梅州话", "emoji": "🏔️",
        "areas": "梅州、惠州、河源、韶关、深圳(部分)",
        "speakers": "约4500万使用者",
        "greeting": "你好！食咗饭无？",
        "greeting_meaning": "你好！吃饭了吗？",
        "features": ["六声调", "保留入声", "古汉语活化石"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "ngi2 hau3"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 cia5"},
            {"dialect": "几多钱？", "mandarin": "多少钱？", "pinyin": "gi1 do1 qian2"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "hau3 siid6"},
            {"dialect": "对唔住", "mandarin": "对不起", "pinyin": "dui4 m4 cu5"},
            {"dialect": "做麻个？", "mandarin": "做什么？", "pinyin": "zo4 ma2 ge4"},
            {"dialect": "奈里", "mandarin": "哪里", "pinyin": "nai4 li1"},
            {"dialect": "靓", "mandarin": "漂亮", "pinyin": "liang4"}
        ],
        "quick_questions": [
            "荔枝样般施肥做得好？",
            "龙眼几时可以摘？",
            "香蕉样般防虫？",
            "柑橘落叶样般处理？"
        ]
    },
    "teochew": {
        "id": "teochew", "name": "潮汕话", "region": "汕头话", "emoji": "🌊",
        "areas": "汕头、潮州、揭阳、汕尾",
        "speakers": "约1500万使用者",
        "greeting": "你好！食未？",
        "greeting_meaning": "你好！吃了吗？",
        "features": ["八声调", "保留古汉语入声", "文白异读丰富"],
        "phrases": [
            {"dialect": "你好", "mandarin": "你好", "pinyin": "le2 ho2"},
            {"dialect": "多谢", "mandarin": "谢谢", "pinyin": "do1 sia7"},
            {"dialect": "若挤？", "mandarin": "多少钱？", "pinyin": "rioh8 zoi6"},
            {"dialect": "好食", "mandarin": "好吃", "pinyin": "ho2 ziah8"},
            {"dialect": "对唔住", "mandarin": "对不起", "pinyin": "dui3 m6 zu6"},
            {"dialect": "做呢？", "mandarin": "为什么？", "pinyin": "zo3 ni1"},
            {"dialect": "地块", "mandarin": "哪里", "pinyin": "de7 kau3"},
            {"dialect": "雅", "mandarin": "漂亮", "pinyin": "ngia2"}
        ],
        "quick_questions": [
            "荔枝怎生施肥正好？",
            "龙眼时阵好摘？",
            "香蕉怎生防虫？",
            "柑橘落叶怎生处理？"
        ]
    }
}


@app.route('/api/resources/dialects', methods=['GET'])
def get_dialects():
    dialects = [{"id": v["id"], "name": v["name"], "region": v["region"],
                 "emoji": v["emoji"], "areas": v["areas"], "speakers": v["speakers"]}
                for v in DIALECTS_DATA.values()]
    return jsonify({"success": True, "dialects": dialects})


@app.route('/api/resources/dialect-info', methods=['GET'])
def get_dialect_info():
    """获取方言详细信息（问候、短语、快捷问题）"""
    dialect_id = request.args.get('dialect', 'cantonese')
    d = DIALECTS_DATA.get(dialect_id, DIALECTS_DATA['cantonese'])
    return jsonify({"success": True, "info": {
        "id": d["id"], "name": d["name"], "region": d["region"],
        "emoji": d["emoji"], "areas": d["areas"], "speakers": d["speakers"],
        "greeting": d["greeting"], "greeting_meaning": d["greeting_meaning"],
        "features": d["features"], "phrases": d["phrases"],
        "quick_questions": d["quick_questions"]
    }})


@app.route('/api/resources/cases', methods=['GET'])
def get_success_cases():
    cases = database.get_success_cases()
    return jsonify({"success": True, "cases": cases})


@app.route('/api/resources/cases/<int:case_id>', methods=['GET'])
def get_success_case(case_id):
    cases = database.get_success_cases()
    case = next((c for c in cases if c['id'] == case_id), None)
    if case:
        return jsonify({"success": True, "case": case})
    return jsonify({"success": False, "message": "案例不存在"}), 404


@app.route('/api/resources/policies', methods=['GET'])
def get_policies():
    policies = database.get_policies()
    return jsonify({"success": True, "policies": policies})


@app.route('/api/resources/voice', methods=['POST'])
def process_voice():
    """处理语音/文字输入 — 支持对话历史"""
    data = request.get_json()
    text = data.get('text', '')
    dialect = data.get('dialect', 'cantonese')
    history = data.get('history', [])  # 最近对话历史

    if not text:
        return jsonify({"success": False, "message": "未收到内容"})

    d = DIALECTS_DATA.get(dialect, DIALECTS_DATA['cantonese'])
    dialect_name = d['name']
    areas = d['areas']

    # 构建对话历史
    messages = [{
        "role": "system",
        "content": f"""你是粤乡智匠平台的AI农业助手，精通{dialect_name}（{areas}地区）。
用户用{dialect_name}方言提问，你也必须用{dialect_name}方言回答！
要求：
1. 全程用{dialect_name}方言回答，不要用普通话
2. 语气亲切自然，像老乡之间聊天
3. 回答简洁实用，200字以内
4. 涉及病虫害给出具体防治方案
5. 结合广东本地气候和种植习惯
6. 如果不确定某个方言词怎么写，就用普通话混搭，但整体风格必须是{dialect_name}"""
    }]
    # 加入历史对话（最多5轮）
    for h in history[-5:]:
        if h.get('user'):
            messages.append({"role": "user", "content": h['user']})
        if h.get('bot'):
            messages.append({"role": "assistant", "content": h['bot']})
    messages.append({"role": "user", "content": text})

    try:
        import requests as req
        headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
        payload = {"model": AI_MODEL, "messages": messages, "temperature": 0.4, "max_tokens": 500}
        resp = req.post(AI_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        answer = result['choices'][0]['message']['content']

        # 生成追问建议
        suggestions = []
        try:
            sug_resp = call_ai_service(
                system_prompt="根据用户的问题和你的回答，生成3个相关的追问建议。返回JSON数组格式，如：[\"问题1\",\"问题2\",\"问题3\"]。只返回JSON。",
                user_message=f"用户问题：{text}\n回答：{answer}",
                temperature=0.5, max_tokens=200
            )
            clean = sug_resp.strip()
            if clean.startswith('```'):
                clean = clean.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            suggestions = json.loads(clean)[:3]
        except:
            # 根据用户问题生成动态追问建议
            sug_map = {
                "施肥": ["有机肥和化肥怎么搭配？", "叶面肥什么时候喷？", "施肥后要浇水吗？"],
                "病": ["怎么区分真菌和细菌病害？", "打药要注意什么？", "有没有不用药的方法？"],
                "虫": ["黄板蓝板怎么选？", "什么虫害最常见？", "天敌怎么保护？"],
                "种植": ["第一年怎么管理？", "什么时候种最好？", "要挖多大的坑？"],
                "修剪": ["什么时候修剪最好？", "大枝小枝怎么分？", "修剪后怎么护理？"],
                "直播": ["开场怎么吸引人？", "产品怎么展示？", "怎么引导下单？"],
                "电商": ["图片怎么拍好看？", "标题怎么写？", "怎么处理售后？"]
            }
            suggestions = None
            for kw, sugs in sug_map.items():
                if kw in text:
                    suggestions = sugs
                    break
            if not suggestions:
                suggestions = [f"{text}有什么技巧？", "需要注意什么问题？", "有没有成功案例？"]

        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions
        }})
    except Exception as e:
        logger.error(f"语音处理失败: {e}")
        answer, suggestions = generate_dynamic_voice_answer(text, dialect)
        return jsonify({"success": True, "result": {
            "text": text, "dialect": dialect, "dialect_name": dialect_name,
            "answer": answer, "suggestions": suggestions
        }})


def generate_dynamic_voice_answer(text, dialect):
    """根据用户问题动态生成方言回答，不依赖AI"""
    import random
    text_lower = text.lower()

    # 方言版回答模板
    dialect_templates = {
        "cantonese": {
            "施肥": {
                "answer": "广东施肥要睇季节嘅：冬天施基肥，用腐熟嘅有机肥，每棵大树施20-30斤；开花前（2-3月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大约1:0.5:1。施完肥要覆土浇水，唔好烧根。{extra}",
                "extras": [
                    "叶面喷0.3%磷酸二氢钾效果都几好。",
                    "有机肥同化肥夹埋用效果最好。",
                    "落雨后施肥吸收更好，但暴雨前就唔好施。"
                ],
                "suggestions": ["用咩有机肥最好？", "施肥量点控制？", "叶面肥点喷？"]
            },
            "病": {
                "answer": "防病最紧要预防为主。先做好冬季清园，清走病枝落叶集中烧咗；再加强果园管理，剪好枝保持通风透光；发病初期快啲喷药，用多菌灵、甲基托布津都得，每隔7-10日喷一次，连喷2-3次。{extra}",
                "extras": [
                    "雨季系病害高发期，要提前预防。",
                    "唔同病害用药唔同，最好先确认系咩病。",
                    "生物菌肥都可以增强抗病能力。"
                ],
                "suggestions": ["点判断系咩病害？", "有冇生物防治方法？", "雨季点预防？"]
            },
            "虫": {
                "answer": "治虫要综合嚟搞：物理方法可以挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治要保护天敌好似瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。最紧要早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效嘅方法。",
                    "蚜虫可以用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，啱绿色种植。"
                ],
                "suggestions": ["黄板点挂效果好？", "安全间隔期系几耐？", "有边啲生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都得。种嘅时候要注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；仲要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗好紧要，要拣冇病嘅壮苗。",
                    "种之前要深翻泥土施足基肥。",
                    "可以去当地农技站问下啱种嘅品种。"
                ],
                "suggestions": ["咩品种最好？", "种植密度点定？", "基肥点施？"]
            },
            "修剪": {
                "answer": "剪枝系果树管理好重要嘅一环。冬天大剪，剪走病虫枝、交叉枝、下垂枝；夏天搞摘心抹芽，控制营养生长。剪完要及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀要消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "剪嘅量唔好超过总量嘅三分之一。"
                ],
                "suggestions": ["冬剪同夏剪有咩区别？", "伤口愈合剂点配？", "幼树点整形？"]
            },
            "浇水": {
                "answer": "浇水要睇季节同生长阶段。春天发芽期保持泥土湿润；夏天高温朝晚浇水，唔好中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果仲好啲。",
                    "泥面发白就要浇水啦。",
                    "铺啲禾秆可以减少水分蒸发。"
                ],
                "suggestions": ["滴灌点装？", "点判断缺水？", "铺咩材料好？"]
            },
            "直播": {
                "answer": "做农产品直播要注意几点：首先要熟识产品，讲得出产地、口感、种植过程；其次要有感染力，用真实嘅场景打动观众；第三要善于互动，及时回复评论引导下单；最后要保证物流同售后。{extra}",
                "extras": [
                    "喺果园现场直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术点设计？", "点涨粉？", "物流点拣？"]
            },
            "电商": {
                "answer": "做农村电商首先要拣好产品，搵差异化卖点；其次要影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都得；仲要做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系而家最有效嘅方式。",
                    "包装要兼顾保护同靓观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["边个平台啱新手？", "点影好产品图？", "包装点设计？"]
            }
        },
        "hakka": {
            "施肥": {
                "answer": "广东施肥要看季节嘅：冬天施基肥，用沤熟嘅有机肥，每棵大树施二十到三十斤；开花前（二三月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大概一比零点五比一。施完肥要覆土浇水，莫烧根。{extra}",
                "extras": [
                    "叶面喷零点三嘅磷酸二氢钾效果都做得。",
                    "有机肥同化肥搭起来用效果最好。",
                    "落水后施肥吸收更好，但大水前就莫施。"
                ],
                "suggestions": ["用么嘢有机肥最好？", "施肥量样般控制？", "叶面肥样般喷？"]
            },
            "病": {
                "answer": "防病最紧要预防为主。先做好冬季清园，清走病枝落叶集中烧咗；再加强果园管理，修好枝保持通风透光；发病初期快滴喷药，用多菌灵、甲基托布津都做得，隔七八日喷一次，连喷两三回。{extra}",
                "extras": [
                    "雨季系病害多发期，要提前预防。",
                    "唔同病害用药唔同，最好先确认系么嘢病。",
                    "生物菌肥都可以增强抗病能力。"
                ],
                "suggestions": ["样般判断系么嘢病害？", "有冇生物防治方法？", "雨季样般预防？"]
            },
            "虫": {
                "answer": "治虫要综合来做：物理方法可以挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治要保护天敌像瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。最紧要早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效嘅方法。",
                    "蚜虫可以用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，做得绿色种植。"
                ],
                "suggestions": ["黄板样般挂效果好？", "安全间隔期系几久？", "有哪滴生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都做得。种嘅时节要注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；还要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗好紧要，要拣冇病嘅壮苗。",
                    "种之前要深翻泥巴施足基肥。",
                    "可以去当地农技站问下适合种嘅品种。"
                ],
                "suggestions": ["么嘢品种最好？", "种植密度样般定？", "基肥样般施？"]
            },
            "修剪": {
                "answer": "修枝系果树管理好紧要嘅一环。冬天大修，剪走病虫枝、交叉枝、下垂枝；夏天做摘心抹芽，控制营养生长。修完要及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀要消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "修嘅量莫超过总量嘅三分之一。"
                ],
                "suggestions": ["冬修同夏修有么嘢区别？", "伤口愈合剂样般配？", "幼树样般整形？"]
            },
            "浇水": {
                "answer": "浇水要看季节同生长阶段。春天发芽期保持泥巴湿润；夏天高温朝晚浇水，莫中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果还更好。",
                    "泥面发白就要浇水了。",
                    "铺滴禾秆可以减少水分蒸发。"
                ],
                "suggestions": ["滴灌样般装？", "样般判断缺水？", "铺么嘢材料好？"]
            },
            "直播": {
                "answer": "做农产品直播要注意几滴：首先要识得产品，讲得出产地、口感、种植过程；其次要有感染力，用真实嘅场景打动观众；第三要善于互动，及时回复评论引导下单；最后要保证物流同售后。{extra}",
                "extras": [
                    "在果园现场直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术样般设计？", "样般涨粉？", "物流样般拣？"]
            },
            "电商": {
                "answer": "做农村电商首先要拣好产品，寻差异化卖点；其次要影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都做得；还要做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系如今最有效嘅方式。",
                    "包装要兼顾保护同靓观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["哪只平台适合新手？", "样般影好产品图？", "包装样般设计？"]
            }
        },
        "teochew": {
            "施肥": {
                "answer": "广东施肥着看季节个：冬天施底肥，用沤熟个有机肥，每丛大树施二十到三十斤；开花前（二三月）追磷钾肥，帮手促花；幼果期补复合肥，氮磷钾大概一比零点五比一。施了肥着覆土浇水，勿烧根。{extra}",
                "extras": [
                    "叶面喷零点三个磷酸二氢钾效果都做得。",
                    "有机肥同化肥配起来用效果正好。",
                    "落雨后施肥吸收更好，但大雨前就勿施。"
                ],
                "suggestions": ["用什物有机肥最好？", "施肥量怎生控制？", "叶面肥怎生喷？"]
            },
            "病": {
                "answer": "防病上紧预防为主。先做好冬季清园，清走病枝落叶集中烧掉；再加强果园管理，修好枝保持通风透光；发病初期猛个喷药，用多菌灵、甲基托布津都做得，隔七八日喷一次，连喷两三回。{extra}",
                "extras": [
                    "雨季系病害多发期，着提前预防。",
                    "唔同病害用药唔同，上好先确认系什物病。",
                    "生物菌肥都可能增强抗病能力。"
                ],
                "suggestions": ["怎生判断系什物病害？", "有无生物防治方法？", "雨季怎生预防？"]
            },
            "虫": {
                "answer": "治虫着综合来做：物理方法可能挂黄板诱杀蚜虫、蓟马，用灯诱杀蛾类；生物防治着保护天敌像瓢虫、草蛉；化学防治拣低毒药，注意安全间隔期。上紧早发现早处理，定期巡查果园。{extra}",
                "extras": [
                    "挂黄板系简单又有效个方法。",
                    "蚜虫可能用吡虫啉，螨类用阿维菌素。",
                    "生物农药更安全，做得绿色种植。"
                ],
                "suggestions": ["黄板怎生挂效果好？", "安全间隔期系偌久？", "有什物生物农药？"]
            },
            "种植": {
                "answer": "广东天气暖湿，种荔枝、龙眼、香蕉、柑橘都做得。种个时节着注意拣好品种，因地制宜；合理密植，保证通风透光；做好水肥管理，旱季灌水雨季排水；还要注意病虫害防治。{extra}",
                "extras": [
                    "拣苗上紧要，着拣无病个壮苗。",
                    "种之前着深翻涂土施足底肥。",
                    "可能去当地农技站问下适合种个品种。"
                ],
                "suggestions": ["什物品种最好？", "种植密度怎生定？", "底肥怎生施？"]
            },
            "修剪": {
                "answer": "修枝系果树管理上紧要个一环。冬天大修，剪走病虫枝、交叉枝、下垂枝；夏天做摘心抹芽，控制营养生长。修了着及时涂伤口愈合剂，防止病菌感染。{extra}",
                "extras": [
                    "剪刀着消毒，避免传播病害。",
                    "幼树以整形为主，结果树以调节为主。",
                    "修个量勿超过总量个三分之一。"
                ],
                "suggestions": ["冬修同夏修有什物区别？", "伤口愈合剂怎生配？", "幼树怎生整形？"]
            },
            "浇水": {
                "answer": "浇水着看季节同生长阶段。春天发芽期保持涂土湿润；夏天高温朝晚浇水，勿中午浇伤根；秋天果实膨大期需水量大；冬天控水促花。雨季着要及时排水防涝。{extra}",
                "extras": [
                    "滴灌比漫灌更省水，效果还更好。",
                    "涂面发白就着浇水了。",
                    "铺滴稻草可能减少水分蒸发。"
                ],
                "suggestions": ["滴灌怎生装？", "怎生判断缺水？", "铺什物材料好？"]
            },
            "直播": {
                "answer": "做农产品直播着注意几滴：上先着识得产品，讲得出产地、口感、种植过程；其次着有感染力，用真实个场景打动观众；第三着善于互动，及时回复评论引导下单；上后着保证物流同售后。{extra}",
                "extras": [
                    "在现场果园直播效果更加好。",
                    "讲故事比硬推产品更加有效。",
                    "固定时间直播培养观众习惯。"
                ],
                "suggestions": ["直播话术怎生设计？", "怎生涨粉？", "物流怎生拣？"]
            },
            "电商": {
                "answer": "做农村电商上先着拣好产品，寻差异化卖点；其次着影好相拍好视频，真实展示产品；然后拣好平台，淘宝、拼多多、抖音都做得；还着做好包装同物流，保证产品完好送到。{extra}",
                "extras": [
                    "短视频引流系现今上有效个方式。",
                    "包装着兼顾保护同雅观。",
                    "售后服务决定复购率。"
                ],
                "suggestions": ["什物平台适合新手？", "怎生影好产品图？", "包装怎生设计？"]
            }
        }
    }

    # 获取该方言的模板，没有则用粤语
    templates = dialect_templates.get(dialect, dialect_templates["cantonese"])

    # 匹配主题
    matched_topic = None
    for keyword, topic in templates.items():
        if keyword in text_lower:
            matched_topic = topic
            break

    if matched_topic:
        extra = random.choice(matched_topic["extras"])
        answer = matched_topic["answer"].format(extra=extra)
        suggestions = matched_topic["suggestions"]
    else:
        # 通用回答（方言版）
        general = {
            "cantonese": [
                "呢个问题问得好！广东做农业要注意因地制宜，睇下当地气候同土壤条件。建议多啲同周围有经验嘅农户倾下，都可以去当地农技站攞专业指导。",
                "种嘢要讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都好紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业要有耐性，都要多学新技术。而家有好多农业技术培训同线上课程，可以多参加。有咩具体问题随时问我。"
            ],
            "hakka": [
                "这个问题问得做得！广东做农业要注意因地制宜，看下当地气候同土壤条件。建议多滴同周围有经验嘅农户聊下，都可以去当地农技站拿专业指导。",
                "种嘢要讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都好紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业要有耐性，都要多学新技术。今下有好多农业技术培训同线上课程，可以多参加。有么嘢具体问题随时问我。"
            ],
            "teochew": [
                "这个问题问得好！广东做农业着因地制宜，看下当地气候同涂土条件。建议多滴同周围有经验个农户聊下，都可能去当地农技站拿专业指导。",
                "种嘢着讲究科学管理，由拣种、施肥、浇水到病虫害防治，每个环节都上紧要。建议做好记录，总结经验，慢慢提高种植技术。",
                "做农业着有耐性，都要多学新技术。现今有好多农业技术培训同线上课程，可能多参加。有什物具体问题随时问我。"
            ]
        }
        answers = general.get(dialect, general["cantonese"])
        answer = random.choice(answers)
        suggestions = ["样般提高产量？", "有么嘢新技术？", "样般申请农业补贴？"]

    return answer, suggestions


# ==================== 就业对接API ====================

@app.route('/api/employment/jobs', methods=['GET'])
def get_jobs():
    keyword = request.args.get('keyword', '')
    location = request.args.get('location', '')
    salary_range = request.args.get('salary', '')
    category = request.args.get('category', '')
    jobs = database.get_job_listings_filtered(keyword, location, salary_range, category)
    return jsonify({"success": True, "jobs": jobs})


@app.route('/api/employment/jobs/<int:job_id>', methods=['GET'])
def get_job_detail(job_id):
    job = database.get_job_by_id(job_id)
    if not job:
        return jsonify({"success": False, "message": "职位不存在"}), 404
    return jsonify({"success": True, "job": job})


@app.route('/api/employment/jobs/<int:job_id>/similar', methods=['GET'])
def get_similar_jobs(job_id):
    job = database.get_job_by_id(job_id)
    if not job:
        return jsonify({"success": True, "jobs": []})
    similar = database.get_similar_jobs(job_id, job.get('category', ''), 3)
    return jsonify({"success": True, "jobs": similar})


@app.route('/api/employment/certificates/<user_id>', methods=['GET'])
def get_certificates(user_id):
    certs = database.get_certificates(user_id)
    return jsonify({"success": True, "certificates": certs})


@app.route('/api/employment/points/<user_id>', methods=['GET'])
def get_points(user_id):
    pts = database.get_points(user_id)
    return jsonify({"success": True, "points": pts['balance'], "history": pts['history']})


@app.route('/api/employment/exchange', methods=['POST'])
def exchange_points():
    data = request.get_json()
    user_id = data.get('user_id')
    item = data.get('item', '商品')
    cost = data.get('cost', 0)

    new_balance = database.update_points(user_id, -cost, f"兑换{item}")
    if new_balance == -1:
        return jsonify({"success": False, "message": "积分不足"})
    return jsonify({"success": True, "message": f"成功兑换：{item}", "remaining_points": new_balance})


@app.route('/api/employment/apply', methods=['POST'])
def apply_job():
    """申请职位"""
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')

    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})

    success = database.apply_for_job(user_id, job_id)
    if success:
        # 申请成功加积分
        database.update_points(user_id, 20, "申请职位奖励")
        return jsonify({"success": True, "message": "申请成功！已获得20积分奖励"})
    return jsonify({"success": False, "message": "您已申请过该职位"})


@app.route('/api/employment/applications/<user_id>', methods=['GET'])
def get_user_applications(user_id):
    status_filter = request.args.get('status', '')
    apps = database.get_user_applications(user_id, status_filter)
    return jsonify({"success": True, "applications": apps})


@app.route('/api/employment/applications/<user_id>/counts', methods=['GET'])
def get_application_counts(user_id):
    counts = database.get_application_counts(user_id)
    return jsonify({"success": True, "counts": counts})


@app.route('/api/employment/save', methods=['POST'])
def save_job():
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')
    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    success = database.save_job(user_id, job_id)
    if success:
        return jsonify({"success": True, "message": "收藏成功"})
    return jsonify({"success": False, "message": "已收藏过该职位"})


@app.route('/api/employment/save', methods=['DELETE'])
def unsave_job():
    data = request.get_json()
    user_id = data.get('user_id')
    job_id = data.get('job_id')
    if not user_id or not job_id:
        return jsonify({"success": False, "message": "参数不完整"})
    database.unsave_job(user_id, job_id)
    return jsonify({"success": True, "message": "已取消收藏"})


@app.route('/api/employment/saved/<user_id>', methods=['GET'])
def get_saved_jobs(user_id):
    saved_ids = database.get_saved_jobs(user_id)
    return jsonify({"success": True, "saved_ids": saved_ids})


@app.route('/api/employment/stats/<user_id>', methods=['GET'])
def get_employment_stats(user_id):
    stats = database.get_employment_stats(user_id)
    return jsonify({"success": True, "stats": stats})


# ==================== 教师管理API ====================

@app.route('/api/teacher/dashboard', methods=['GET'])
def get_teacher_dashboard():
    stats = database.get_dashboard_stats()
    return jsonify({"success": True, "dashboard": {"stats": stats, "recent_activities": [
        {"type": "student_join", "student": "张小明", "time": "2小时前"},
        {"type": "certificate_earned", "student": "李小红", "time": "4小时前"}
    ]}})


@app.route('/api/teacher/students', methods=['GET'])
def get_students():
    search = request.args.get('search', None)
    students = database.get_students(search)
    return jsonify({"success": True, "students": students})


@app.route('/api/teacher/students/<student_id>', methods=['GET'])
def get_student_detail(student_id):
    """获取学员详情"""
    student = database.get_student(student_id)
    if student:
        return jsonify({"success": True, "student": student})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/students/add', methods=['POST'])
def add_student():
    """添加学员"""
    data = request.get_json()
    name = data.get('name', '')
    class_name = data.get('class_name', '')
    direction = data.get('direction', '')

    if not name:
        return jsonify({"success": False, "message": "请输入学员姓名"})

    sid = database.add_student(name, class_name, direction)
    return jsonify({"success": True, "message": f"添加成功，学员编号：{sid}", "student_id": sid})


@app.route('/api/teacher/students/<student_id>', methods=['PUT'])
def update_student(student_id):
    """编辑学员"""
    data = request.get_json()
    result = database.update_student(
        student_id,
        name=data.get('name'),
        class_name=data.get('class_name'),
        direction=data.get('direction'),
        progress=data.get('progress'),
        status=data.get('status')
    )
    if result:
        return jsonify({"success": True, "message": "更新成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/students/<student_id>', methods=['DELETE'])
def delete_student(student_id):
    """删除学员"""
    result = database.delete_student(student_id)
    if result:
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到学员"})


@app.route('/api/teacher/reports/generate', methods=['POST'])
def generate_report():
    """AI生成教学报告 — 接受自然语言prompt，灵活生成"""
    data = request.get_json()
    user_prompt = data.get('prompt', '').strip()
    if not user_prompt:
        return jsonify({"success": False, "message": "请输入分析需求"}), 400

    try:
        students = database.get_students()
        if not students:
            return jsonify({"success": True, "report": {
                "title": "AI 教学报告",
                "generated_at": datetime.now().isoformat(),
                "content": "## 暂无数据\n\n当前没有学员数据，请先添加学员后再生成报告。"
            }})

        # 全量数据采集
        total = len(students)
        avg_progress = sum(s['progress'] for s in students) / total

        directions = {}
        for s in students:
            d = s.get('direction', '未分类')
            directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
            directions[d]['count'] += 1
            directions[d]['progresses'].append(s['progress'])
            directions[d]['students'].append(s['name'])

        # 进度分段
        brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
        for s in students:
            p = s['progress']
            if p < 25: brackets['0-25%'] += 1
            elif p < 50: brackets['25-50%'] += 1
            elif p < 75: brackets['50-75%'] += 1
            else: brackets['75-100%'] += 1

        at_risk = [s for s in students if s['progress'] < 30]
        excellent = [s for s in students if s['progress'] >= 80]
        completed = [s for s in students if s['progress'] >= 100]

        # 组装数据上下文
        dir_lines = []
        for d, info in directions.items():
            avg = sum(info['progresses']) / info['count']
            hi = max(info['progresses'])
            lo = min(info['progresses'])
            names = '、'.join(info['students'])
            dir_lines.append(f"- {d}：{info['count']}人，平均进度{avg:.1f}%，最高{hi}%，最低{lo}%，学员：{names}")

        student_lines = []
        for s in students:
            status = '已完成' if s['progress'] >= 100 else '学习中' if s['progress'] > 0 else '未开始'
            student_lines.append(f"- {s['name']}（{s.get('class_name','未分班')}）方向={s['direction']} 进度={s['progress']}% 状态={status}")

        risk_lines = [f"- {s['name']}：进度{s['progress']}%，方向{s['direction']}" for s in at_risk]
        good_lines = [f"- {s['name']}：进度{s['progress']}%，方向{s['direction']}" for s in excellent]

        data_context = f"""学员总数：{total}
平均进度：{avg_progress:.1f}%
方向数量：{len(directions)}
已完成学员：{len(completed)}人
风险学员（进度<30%）：{len(at_risk)}人
优秀学员（进度>=80%）：{len(excellent)}人

进度分布：
{chr(10).join(f'{k}: {v}人' for k, v in brackets.items())}

各方向详情：
{chr(10).join(dir_lines)}

全部学员：
{chr(10).join(student_lines)}

风险学员名单：
{chr(10).join(risk_lines) if risk_lines else '无'}

优秀学员名单：
{chr(10).join(good_lines) if good_lines else '无'}"""

        result = call_ai_service(
            system_prompt=(
                "你是一位资深教学数据分析师。用户会给你一份学员数据和一个具体的分析问题。"
                "你必须紧紧围绕用户的问题来生成报告，不要生成与问题无关的内容。\n"
                "要求：\n"
                "1）报告标题和所有小节都要围绕用户的问题展开\n"
                "2）引用具体数据和学员姓名，不要泛泛而谈\n"
                "3）建议要具体可执行，不要空话套话\n"
                "4）不同问题生成完全不同的报告结构和内容，禁止千篇一律"
            ),
            user_message=f"## 用户的问题\n{user_prompt}\n\n## 学员数据\n{data_context}\n\n请围绕上述问题生成报告。"
        )

        # 构建概览数据
        overview = {
            "total": total,
            "avg_progress": round(avg_progress, 1),
            "direction_count": len(directions),
            "completed_count": len(completed),
            "risk_count": len(at_risk),
            "excellent_count": len(excellent),
            "brackets": brackets,
            "directions": [
                {"name": d, "count": info['count'],
                 "avg_progress": round(sum(info['progresses'])/info['count'], 1),
                 "students": info['students']}
                for d, info in directions.items()
            ],
            "at_risk": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in at_risk],
            "excellent": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in excellent]
        }

        # 根据 prompt 分析报告主题，决定概览侧重点
        p = user_prompt.lower()
        if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
            overview['focus'] = 'risk'
            overview['title'] = '风险预警概览'
            overview['highlight_stats'] = ['risk_count', 'total', 'avg_progress']
        elif any(k in p for k in ['方向', '对比', '比较', '哪个', '排名', '对比分析']):
            overview['focus'] = 'direction'
            overview['title'] = '方向对比概览'
            overview['highlight_stats'] = ['direction_count', 'total', 'avg_progress']
        elif any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
            overview['focus'] = 'progress'
            overview['title'] = '进度分析概览'
            overview['highlight_stats'] = ['avg_progress', 'completed_count', 'total']
        elif any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
            overview['focus'] = 'excellent'
            overview['title'] = '优秀学员概览'
            overview['highlight_stats'] = ['excellent_count', 'completed_count', 'total']
        elif any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
            overview['focus'] = 'trend'
            overview['title'] = '趋势预测概览'
            overview['highlight_stats'] = ['avg_progress', 'completed_count', 'risk_count']
        elif any(k in p for k in ['效果', '评估', '教学', '质量']):
            overview['focus'] = 'performance'
            overview['title'] = '教学效果概览'
            overview['highlight_stats'] = ['completed_count', 'avg_progress', 'excellent_count']
        else:
            overview['focus'] = 'general'
            overview['title'] = '班级总览'
            overview['highlight_stats'] = ['total', 'avg_progress', 'direction_count']

        return jsonify({"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": result,
            "overview": overview
        }})

    except Exception as e:
        logger.error(f"报告生成失败: {e}")
        # 兜底报告
        try:
            students = database.get_students()
            fallback = _build_fallback_report(students, user_prompt)
            overview = _build_fallback_overview(students, user_prompt)
        except Exception:
            fallback = "## 生成失败\n\nAI 服务暂时不可用，请稍后重试。"
            overview = None
        resp = {"success": True, "report": {
            "title": "AI 教学报告",
            "generated_at": datetime.now().isoformat(),
            "content": fallback
        }}
        if overview:
            resp["report"]["overview"] = overview
        return jsonify(resp)


def _build_fallback_overview(students, prompt):
    """兜底报告的概览数据"""
    if not students:
        return None
    total = len(students)
    avg_progress = sum(s['progress'] for s in students) / total
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, {'count': 0, 'progresses': [], 'students': []})
        directions[d]['count'] += 1
        directions[d]['progresses'].append(s['progress'])
        directions[d]['students'].append(s['name'])
    at_risk = [s for s in students if s['progress'] < 30]
    excellent = [s for s in students if s['progress'] >= 80]
    completed = [s for s in students if s['progress'] >= 100]
    brackets = {'0-25%': 0, '25-50%': 0, '50-75%': 0, '75-100%': 0}
    for s in students:
        p = s['progress']
        if p < 25: brackets['0-25%'] += 1
        elif p < 50: brackets['25-50%'] += 1
        elif p < 75: brackets['50-75%'] += 1
        else: brackets['75-100%'] += 1

    overview = {
        "total": total, "avg_progress": round(avg_progress, 1),
        "direction_count": len(directions), "completed_count": len(completed),
        "risk_count": len(at_risk), "excellent_count": len(excellent),
        "brackets": brackets,
        "directions": [{"name": d, "count": info['count'],
                        "avg_progress": round(sum(info['progresses'])/info['count'], 1),
                        "students": info['students']} for d, info in directions.items()],
        "at_risk": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in at_risk],
        "excellent": [{"name": s['name'], "progress": s['progress'], "direction": s['direction']} for s in excellent]
    }

    p = prompt.lower()
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        overview['focus'] = 'risk'; overview['title'] = '风险预警概览'
        overview['highlight_stats'] = ['risk_count', 'total', 'avg_progress']
    elif any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        overview['focus'] = 'direction'; overview['title'] = '方向对比概览'
        overview['highlight_stats'] = ['direction_count', 'total', 'avg_progress']
    elif any(k in p for k in ['进度', '滞后', '完成', '速度']):
        overview['focus'] = 'progress'; overview['title'] = '进度分析概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'total']
    elif any(k in p for k in ['优秀', '突出', '表扬', '领先']):
        overview['focus'] = 'excellent'; overview['title'] = '优秀学员概览'
        overview['highlight_stats'] = ['excellent_count', 'completed_count', 'total']
    elif any(k in p for k in ['预测', '趋势', '未来', '计划']):
        overview['focus'] = 'trend'; overview['title'] = '趋势预测概览'
        overview['highlight_stats'] = ['avg_progress', 'completed_count', 'risk_count']
    elif any(k in p for k in ['效果', '评估', '教学', '质量']):
        overview['focus'] = 'performance'; overview['title'] = '教学效果概览'
        overview['highlight_stats'] = ['completed_count', 'avg_progress', 'excellent_count']
    else:
        overview['focus'] = 'general'; overview['title'] = '班级总览'
        overview['highlight_stats'] = ['total', 'avg_progress', 'direction_count']
    return overview


def _build_fallback_report(students, prompt):
    """AI不可用时根据prompt生成不同的兜底报告"""
    if not students:
        return "## 暂无数据\n\n当前没有学员数据，请先添加学员。"

    total = len(students)
    avg_progress = sum(s['progress'] for s in students) / total
    directions = {}
    for s in students:
        d = s.get('direction', '未分类')
        directions.setdefault(d, []).append(s)

    at_risk = sorted([s for s in students if s['progress'] < 30], key=lambda x: x['progress'])
    excellent = sorted([s for s in students if s['progress'] >= 80], key=lambda x: -x['progress'])
    completed = [s for s in students if s['progress'] >= 100]
    mid_risk = [s for s in students if 30 <= s['progress'] < 50]

    p = prompt.lower()

    # 风险主题
    if any(k in p for k in ['风险', '预警', '掉队', '落后', '关注', '帮扶', '干预']):
        lines = [
            "## 一、风险概况",
            f"当前共 **{total}** 名学员，其中 **{len(at_risk)}** 人进度低于30%，处于高风险状态。",
            f"另有 **{len(mid_risk)}** 人进度在30%-50%之间，需要持续关注。", ""
        ]
        if at_risk:
            lines.append("## 二、高风险学员详情")
            for s in at_risk:
                lines.append(f"- **{s['name']}**（{s['direction']}）：进度仅 **{s['progress']}%**，建议优先介入")
            lines.append("")
        if mid_risk:
            lines.append("## 三、中等风险学员")
            for s in mid_risk:
                lines.append(f"- {s['name']}（{s['direction']}）：进度 {s['progress']}%，有下滑风险")
            lines.append("")
        lines.append("## 四、分级干预方案")
        lines.append(f"1. **高风险（<30%）**：一对一约谈，了解学习障碍，制定个性化追赶计划")
        lines.append(f"2. **中等风险（30-50%）**：安排学习伙伴，每周检查进度")
        lines.append(f"3. **预防措施**：建立进度预警机制，低于40%自动提醒")
        return "\n".join(lines)

    # 方向对比主题
    if any(k in p for k in ['方向', '对比', '比较', '哪个', '排名']):
        dir_stats = []
        for d, sts in directions.items():
            avg = sum(s['progress'] for s in sts) / len(sts)
            hi = max(s['progress'] for s in sts)
            lo = min(s['progress'] for s in sts)
            dir_stats.append((d, len(sts), avg, hi, lo, sts))
        dir_stats.sort(key=lambda x: -x[2])

        lines = [
            "## 一、方向排名",
            f"共 **{len(dir_stats)}** 个方向，按平均进度排名如下：", ""
        ]
        for i, (d, cnt, avg, hi, lo, _) in enumerate(dir_stats):
            medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else f'{i+1}.'
            lines.append(f"{medal} **{d}**：{cnt}人，平均进度 {avg:.1f}%（最高{hi}%，最低{lo}%）")
        lines.append("")

        if len(dir_stats) >= 2:
            best = dir_stats[0]
            worst = dir_stats[-1]
            lines.append("## 二、差距分析")
            lines.append(f"- 最优方向 **{best[0]}** 平均进度 {best[2]:.1f}%，最弱方向 **{worst[0]}** 平均进度 {worst[2]:.1f}%")
            lines.append(f"- 差距 **{best[2]-worst[2]:.1f}** 个百分点")
            lines.append("")

        lines.append("## 三、资源调配建议")
        lines.append(f"1. 对进度较低的方向增加教学资源和辅导频次")
        lines.append(f"2. 让优秀方向的学员分享学习经验")
        lines.append(f"3. 分析各方向教学方法差异，推广最佳实践")
        return "\n".join(lines)

    # 进度主题
    if any(k in p for k in ['进度', '滞后', '完成', '速度', '加快']):
        brackets = {'0-25%': [], '25-50%': [], '50-75%': [], '75-100%': []}
        for s in students:
            if s['progress'] < 25: brackets['0-25%'].append(s)
            elif s['progress'] < 50: brackets['25-50%'].append(s)
            elif s['progress'] < 75: brackets['50-75%'].append(s)
            else: brackets['75-100%'].append(s)

        lines = [
            "## 一、进度分布",
            f"全班平均进度 **{avg_progress:.1f}%**，各阶段分布如下：", ""
        ]
        for k, sts in brackets.items():
            pct = len(sts)/total*100 if total else 0
            names = '、'.join(s['name'] for s in sts[:5])
            extra = f'（{names}）' if names else ''
            lines.append(f"- **{k}**：{len(sts)}人，占 {pct:.0f}% {extra}")
        lines.append("")

        if brackets['0-25%']:
            lines.append("## 二、进度滞后学员")
            for s in brackets['0-25%']:
                lines.append(f"- {s['name']}（{s['direction']}）：{s['progress']}%，需要加速")
            lines.append("")

        lines.append("## 三、提速建议")
        lines.append(f"1. 为进度<25%的学员制定每周学习目标")
        lines.append(f"2. 进度>75%的学员可作为小组长带动后进")
        lines.append(f"3. 增加实操练习，减少纯理论学习时间")
        return "\n".join(lines)

    # 优秀主题
    if any(k in p for k in ['优秀', '突出', '表扬', '先进', '领先']):
        lines = [
            "## 一、优秀学员概况",
            f"当前共 **{len(excellent)}** 名学员进度达到80%以上，占比 **{len(excellent)/total*100:.1f}%**。", ""
        ]
        if excellent:
            lines.append("## 二、优秀学员名单")
            for s in excellent:
                pct = s['progress']
                status = '已完成' if pct >= 100 else f'{pct}%'
                lines.append(f"- **{s['name']}**（{s['direction']}）：{status}")
            lines.append("")

        lines.append("## 三、优秀学员特征分析")
        for d, sts in directions.items():
            d_excellent = [s for s in sts if s['progress'] >= 80]
            if d_excellent:
                lines.append(f"- **{d}**：{len(d_excellent)}/{len(sts)} 人优秀，比例 {len(d_excellent)/len(sts)*100:.0f}%")
        lines.append("")

        lines.append("## 四、激励建议")
        lines.append(f"1. 对已完成学员颁发结业证书或优秀学员称号")
        lines.append(f"2. 安排优秀学员担任学习助教，辅导后进学员")
        lines.append(f"3. 为优秀学员提供进阶课程或实践项目机会")
        return "\n".join(lines)

    # 预测/趋势主题
    if any(k in p for k in ['预测', '趋势', '未来', '下月', '计划']):
        completion_rate = len(completed)/total*100 if total else 0
        risk_rate = len(at_risk)/total*100 if total else 0
        lines = [
            "## 一、当前状态",
            f"- 完成率：**{completion_rate:.1f}%**（{len(completed)}/{total}人）",
            f"- 风险率：**{risk_rate:.1f}%**（{len(at_risk)}人进度<30%）",
            f"- 平均进度：**{avg_progress:.1f}%**", ""
        ]
        lines.append("## 二、趋势预测")
        if avg_progress >= 60:
            lines.append(f"- 整体趋势向好，预计多数学员可在2-3个月内完成学习")
        elif avg_progress >= 40:
            lines.append(f"- 整体进度中等，预计需要3-4个月完成，需加强辅导力度")
        else:
            lines.append(f"- 整体进度偏慢，需要调整教学计划并加大辅导投入")
        lines.append("")
        lines.append("## 三、下阶段计划建议")
        lines.append(f"1. 对{len(at_risk)}名风险学员制定专项提升计划")
        lines.append(f"2. 每周跟踪进度，及时调整教学节奏")
        lines.append(f"3. 组织阶段性测评，检验学习效果")
        return "\n".join(lines)

    # 教学效果主题
    if any(k in p for k in ['效果', '评估', '教学', '质量']):
        lines = [
            "## 一、教学完成情况",
            f"共 **{total}** 名学员，已完成 **{len(completed)}** 人，平均进度 **{avg_progress:.1f}%**。", ""
        ]
        lines.append("## 二、各方向教学效果")
        for d, sts in directions.items():
            avg = sum(s['progress'] for s in sts) / len(sts)
            done = len([s for s in sts if s['progress'] >= 100])
            level = '优秀' if avg >= 70 else '良好' if avg >= 50 else '需加强'
            lines.append(f"- **{d}**：{len(sts)}人，平均 {avg:.1f}%，已完成{done}人，评价：{level}")
        lines.append("")
        lines.append("## 三、改进建议")
        for d, sts in directions.items():
            avg = sum(s['progress'] for s in sts) / len(sts)
            if avg < 50:
                lines.append(f"1. **{d}**方向进度偏低，建议增加辅导频次和实操练习")
        lines.append(f"2. 建立学员互评机制，促进同伴学习")
        lines.append(f"3. 定期收集学员反馈，优化教学内容")
        return "\n".join(lines)

    # 默认：通用报告
    lines = [
        "## 一、总体概况",
        f"- 共 **{total}** 名学员，平均学习进度 **{avg_progress:.1f}%**",
        f"- 涵盖 **{len(directions)}** 个方向",
        ""
    ]
    lines.append("## 二、各方向情况")
    for d, sts in directions.items():
        avg = sum(s['progress'] for s in sts) / len(sts)
        names = '、'.join(s['name'] for s in sts)
        lines.append(f"- **{d}**：{len(sts)}人，平均进度 {avg:.1f}%，学员：{names}")
    lines.append("")
    if at_risk:
        lines.append(f"## 三、风险预警（{len(at_risk)}人）")
        for s in at_risk:
            lines.append(f"- {s['name']}（{s['direction']}）：进度仅 {s['progress']}%")
        lines.append("")
    if excellent:
        lines.append(f"## 四、优秀学员（{len(excellent)}人）")
        for s in excellent:
            lines.append(f"- {s['name']}（{s['direction']}）：进度 {s['progress']}%")
        lines.append("")
    lines.append("## 五、建议")
    if at_risk:
        lines.append(f"1. 对 {len(at_risk)} 名风险学员进行一对一辅导，了解学习障碍")
    lines.append(f"2. 对已完成学员安排进阶内容或实践项目")
    lines.append(f"3. 组织方向间交流活动，促进经验分享")
    return "\n".join(lines)


# ==================== 通知公告API ====================

@app.route('/api/teacher/announcements', methods=['GET'])
def get_announcements():
    announcements = database.get_announcements()
    return jsonify({"success": True, "announcements": announcements})

@app.route('/api/teacher/announcements', methods=['POST'])
def create_announcement():
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '')
    category = data.get('category', '通知')
    pinned = 1 if data.get('pinned') else 0
    if not title or not content:
        return jsonify({"success": False, "message": "请填写标题和内容"})
    aid = database.create_announcement(title, content, category, pinned)
    # 自动给所有学员发通知
    database.create_notification_for_all_students(
        'announcement', f'新{category}', title, 'announcement', aid
    )
    return jsonify({"success": True, "message": "发布成功", "id": aid})

@app.route('/api/teacher/announcements/<int:ann_id>', methods=['DELETE'])
def delete_announcement(ann_id):
    if database.delete_announcement(ann_id):
        return jsonify({"success": True, "message": "删除成功"})
    return jsonify({"success": False, "message": "未找到通知"})


# ==================== 学员个人数据API ====================

@app.route('/api/student/submissions', methods=['GET'])
def get_my_submissions():
    """获取当前学员的作业提交记录"""
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"})
    submissions = database.get_student_submissions(user_id)
    return jsonify({"success": True, "submissions": submissions})


@app.route('/api/student/attendance', methods=['GET'])
def get_my_attendance():
    """获取当前学员的考勤记录"""
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"})
    records = database.get_student_attendance_history(user_id)
    return jsonify({"success": True, "records": records})


@app.route('/api/student/announcements', methods=['GET'])
def get_my_announcements():
    """获取通知公告列表（学员可见）"""
    announcements = database.get_announcements(limit=30)
    return jsonify({"success": True, "announcements": announcements})


# ==================== 消息系统API ====================

@app.route('/api/messages/send', methods=['POST'])
def send_message():
    data = request.get_json()
    sender_id = data.get('sender_id', '')
    receiver_id = data.get('receiver_id', '')
    content = data.get('content', '').strip()
    if not sender_id or not receiver_id or not content:
        return jsonify({"success": False, "message": "参数不完整"})
    database.send_message(sender_id, receiver_id, content)
    return jsonify({"success": True, "message": "发送成功"})


@app.route('/api/messages/inbox', methods=['GET'])
def get_inbox():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"})
    inbox = database.get_inbox(user_id)
    return jsonify({"success": True, "inbox": inbox})


@app.route('/api/messages/conversation/<other_id>', methods=['GET'])
def get_conversation(other_id):
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"})
    messages = database.get_messages(user_id, other_id)
    # 标记对方发来的消息为已读
    database.mark_messages_read(other_id, user_id)
    return jsonify({"success": True, "messages": messages})


@app.route('/api/messages/read', methods=['POST'])
def mark_messages_read():
    data = request.get_json()
    sender_id = data.get('sender_id', '')
    receiver_id = data.get('receiver_id', '')
    database.mark_messages_read(sender_id, receiver_id)
    return jsonify({"success": True})


@app.route('/api/messages/unread', methods=['GET'])
def get_unread_count():
    user_id = request.args.get('user_id', '')
    count = database.get_unread_count(user_id)
    return jsonify({"success": True, "count": count})


# ==================== 系统通知API ====================

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return jsonify({"success": False, "message": "缺少用户ID"})
    notifications = database.get_notifications(user_id)
    return jsonify({"success": True, "notifications": notifications})


@app.route('/api/notifications/read', methods=['POST'])
def mark_notifications_read():
    data = request.get_json()
    user_id = data.get('user_id', '')
    database.mark_notifications_read(user_id)
    return jsonify({"success": True})


@app.route('/api/notifications/clear', methods=['DELETE'])
def clear_read_notifications():
    user_id = request.args.get('user_id', '')
    database.clear_read_notifications(user_id)
    return jsonify({"success": True})


@app.route('/api/notifications/unread', methods=['GET'])
def get_unread_notification_count():
    user_id = request.args.get('user_id', '')
    count = database.get_unread_notification_count(user_id)
    return jsonify({"success": True, "count": count})


# ==================== 作业管理API ====================

@app.route('/api/teacher/assignments', methods=['GET'])
def get_assignments():
    assignments = database.get_assignments()
    return jsonify({"success": True, "assignments": assignments})

@app.route('/api/teacher/assignments', methods=['POST'])
def create_assignment():
    data = request.get_json()
    title = data.get('title', '')
    if not title:
        return jsonify({"success": False, "message": "请填写作业标题"})
    aid = database.create_assignment(
        title=title,
        description=data.get('description', ''),
        direction=data.get('direction', ''),
        deadline=data.get('deadline', ''),
        total_score=data.get('total_score', 100)
    )
    # 自动通知
    direction = data.get('direction', '')
    if direction:
        all_students = database.get_students()
        for s in all_students:
            if s.get('direction') == direction:
                database.create_notification(s['id'], 'assignment', f'新作业：{title}', f'方向：{direction}', 'assignment', aid)
    else:
        database.create_notification_for_all_students('assignment', f'新作业：{title}', '全部方向', 'assignment', aid)
    return jsonify({"success": True, "message": "发布成功", "id": aid})

@app.route('/api/teacher/assignments/<int:assignment_id>', methods=['GET'])
def get_assignment_detail(assignment_id):
    assignment = database.get_assignment(assignment_id)
    if assignment:
        return jsonify({"success": True, "assignment": assignment})
    return jsonify({"success": False, "message": "未找到作业"})

@app.route('/api/teacher/assignments/grade', methods=['POST'])
def grade_submission():
    data = request.get_json()
    submission_id = data.get('submission_id')
    score = data.get('score')
    feedback = data.get('feedback', '')
    if submission_id is None or score is None:
        return jsonify({"success": False, "message": "请填写批改信息"})
    # 获取提交信息以发送通知
    conn = database.get_connection()
    sub = conn.execute("SELECT student_id, assignment_id FROM assignment_submissions WHERE id = ?", (submission_id,)).fetchone()
    conn.close()
    if database.grade_submission(submission_id, score, feedback):
        if sub:
            database.create_notification(sub['student_id'], 'grade', '作业已批改', f'得分：{score}', 'assignment', sub['assignment_id'])
        return jsonify({"success": True, "message": "批改成功"})
    return jsonify({"success": False, "message": "批改失败"})

@app.route('/api/teacher/submissions/<student_id>', methods=['GET'])
def get_student_submissions(student_id):
    submissions = database.get_student_submissions(student_id)
    return jsonify({"success": True, "submissions": submissions})


# ==================== 签到考勤API ====================

@app.route('/api/teacher/attendance', methods=['GET'])
def get_attendances():
    attendances = database.get_attendances()
    return jsonify({"success": True, "attendances": attendances})

@app.route('/api/teacher/attendance', methods=['POST'])
def create_attendance():
    data = request.get_json() or {}
    title = data.get('title', '日常签到')
    aid = database.create_attendance(title)
    database.create_notification_for_all_students('attendance', f'签到通知：{title}', '请尽快签到', 'attendance', aid)
    return jsonify({"success": True, "message": "签到已发起", "id": aid})

@app.route('/api/teacher/attendance/close', methods=['POST'])
def close_attendance():
    data = request.get_json()
    att_id = data.get('id')
    if not att_id:
        return jsonify({"success": False, "message": "缺少签到ID"})
    database.close_attendance(att_id)
    return jsonify({"success": True, "message": "签到已结束"})

@app.route('/api/teacher/attendance/<int:att_id>', methods=['GET'])
def get_attendance_detail(att_id):
    records = database.get_attendance_records(att_id)
    return jsonify({"success": True, "records": records})


# ==================== 学情分析API ====================

@app.route('/api/teacher/analytics', methods=['GET'])
def get_analytics():
    data = database.get_analytics_data()
    return jsonify({"success": True, "analytics": data})


# ==================== 用户认证API ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"success": False, "message": "请输入用户名和密码"}), 400

    user = database.authenticate_user(username, password)
    if user:
        session_id = database.create_session(username)
        return jsonify({
            "success": True,
            "session_id": session_id,
            "user": {"id": user['username'], "name": user['name'], "role": user['role'], "email": user.get('email', '')}
        })

    return jsonify({"success": False, "message": "用户名或密码错误"}), 401


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    data = request.get_json()
    session_id = data.get('session_id')
    if session_id:
        database.delete_session(session_id)
    return jsonify({"success": True, "message": "已退出登录"})


@app.route('/api/auth/verify', methods=['POST'])
def verify_session():
    data = request.get_json()
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({"success": False, "message": "未提供session"}), 401

    session = database.get_session(session_id)
    if session:
        return jsonify({"success": True, "user": session})
    return jsonify({"success": False, "message": "会话无效"}), 401


# ==================== 用户资料API ====================

@app.route('/api/user/profile', methods=['GET'])
def get_user_profile():
    """获取当前用户完整资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    user = database.get_user_by_id(session['user_id'])
    if not user:
        return jsonify({"success": False, "message": "用户不存在"})
    return jsonify({"success": True, "user": user})


@app.route('/api/user/profile', methods=['PUT'])
def update_profile():
    """更新用户资料"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    if not name:
        return jsonify({"success": False, "message": "姓名不能为空"})
    database.update_user_profile(session['user_id'], name=name, email=email)
    return jsonify({"success": True, "message": "资料更新成功"})


@app.route('/api/user/password', methods=['PUT'])
def change_password():
    """修改密码"""
    session_id = request.headers.get('X-Session-Id', '')
    session = database.get_session(session_id)
    if not session:
        return jsonify({"success": False, "message": "未登录"}), 401
    data = request.get_json()
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    confirm_password = data.get('confirm_password', '')
    if not old_password or not new_password:
        return jsonify({"success": False, "message": "请填写完整"})
    if new_password != confirm_password:
        return jsonify({"success": False, "message": "两次输入的新密码不一致"})
    if len(new_password) < 6:
        return jsonify({"success": False, "message": "新密码至少6位"})
    success, msg = database.change_password(session['user_id'], old_password, new_password)
    return jsonify({"success": success, "message": msg})


# ==================== 健康检查 ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "success": True, "healthy": True,
        "service": "粤乡智匠API",
        "timestamp": datetime.now().isoformat()
    })


# ==================== AI服务调用 ====================

def call_ai_service(system_prompt, user_message, temperature=0.3, max_tokens=1000):
    import requests
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    response = requests.post(AI_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    result = response.json()
    return result['choices'][0]['message']['content']


# ==================== 静态文件兜底（必须放最后） ====================

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(_BASE_DIR, filename)


# ==================== 启动 ====================

if __name__ == '__main__':
    database.init_db()
    print("🌾 启动粤乡智匠服务...")
    print("=" * 50)
    print("🌱 粤乡智匠 - AI驱动的农村人才赋能平台")
    print(f"📊 服务地址: http://localhost:5000")
    print(f"📚 健康检查: http://localhost:5000/api/health")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
