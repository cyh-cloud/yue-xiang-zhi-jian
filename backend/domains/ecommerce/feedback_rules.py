# -*- coding: utf-8 -*-
"""话术评分规则：基于关键词与标点的纯规则分析，无随机数、无 AI 依赖。

从 app.py 迁出（后端按领域拆分 T12），逐字未改。它只服务
`/api/ecommerce/feedback`，没有第二个消费方，所以单独成模块、不摊在路由文件里
（路由文件有 600 行上限，见 spec 的验收门槛）。

EC2 的口径在这里落地：四个维度都不叠加随机扰动。测评必须可复现 ——
学员无法凭一个每次都在跳的分数判断自己有没有进步，教师也无法用它打分。
"""

import re


def analyze_script(text):
    """基于规则分析话术内容，生成差异化分数"""
    # 统计各类特征
    exclamation = len(re.findall(r'[！!]{1,}', text))
    question = len(re.findall(r'[？?]{1,}', text))
    interaction_words = len(re.findall(r'扣\d|扣[一1]|觉得值|想买要|想不想|是不是|好不好|要不要|家人们|宝宝们|姐妹们|朋友们|大家看', text))
    pause_marks = len(re.findall(r'停顿|缓一缓|等一下|\.\.\.|……', text))
    data_marks = len(re.findall(r'\d+[%％度]|【[^】]+】|\d+[元斤箱颗个盒]', text))
    emotion_words = len(re.findall(r'太[香好吃甜]|绝了|爆款|必买|一定要|赶紧|快来|错过|疯了|爱了|好吃', text))
    price_words = len(re.findall(r'原价|划线价|专属价|只要|到手价|特价|便宜|优惠|立减|折扣', text))

    # 基础分 + 特征权重
    speed = 68 + min(pause_marks * 6, 20) + min(exclamation * 2, 10) - (0 if len(text) > 100 else 5)
    emotion = 65 + min(emotion_words * 5, 20) + min(exclamation * 3, 15) + min(question * 2, 10)
    interaction = 60 + min(interaction_words * 8, 30) + min(question * 3, 10)
    selling = 66 + min(data_marks * 5, 20) + min(price_words * 4, 16)

    # EC2：这里原先每个维度都叠加 random.randint(-3, 3) 随机扰动，
    # 导致同一份话术每次得分都不同（实测 80/81/78）。测评必须是可复现的 ——
    # 学员无法凭一个每次都在跳的分数判断自己有没有进步，教师也无法用它打分。
    # 现已全部去掉随机数：同样的输入必然得到同样的输出。
    return (max(50, min(98, speed)), max(50, min(98, emotion)),
            max(50, min(98, interaction)), max(50, min(98, selling)))


def generate_suggestions(speed, emotion, interaction, selling, text):
    """基于分数和内容生成针对性建议"""
    suggestions = []
    has_interaction = bool(re.search(r'扣\d|点[个一]赞|觉得值', text))
    has_pause = bool(re.search(r'停顿|\.\.\.', text))
    has_data = bool(re.search(r'\d+[元斤箱度%]', text))
    has_price = bool(re.search(r'原价|只要|专属价', text))
    has_emotion = bool(re.search(r'家人们|宝子们|太[香好吃]', text))

    if interaction < 75 and not has_interaction:
        suggestions.append(u'加入互动指令，如"想要的扣1""觉得值的点个赞"')
    if speed < 72 and not has_pause:
        suggestions.append(u'适当加入停顿，制造悬念感，如"(停顿3秒)"')
    if selling < 75 and not has_data:
        suggestions.append(u'需要补充的真实数据（规格、检测指标等）用【待填写】标注，不要编数字')
    if emotion < 72 and not has_emotion:
        suggestions.append(u'增加情绪词和感叹句，如"这也太香了吧！"')
    if not has_price:
        suggestions.append(u'加入价格信息；价格必须填真实值，不要虚构原价或划线价')
    if selling >= 75 and interaction >= 75:
        suggestions.append(u'整体不错，可以尝试讲故事增加情感共鸣')

    # 补充通用建议到至少3条。EC2：去掉 random.shuffle —— 建议列表同样必须可复现。
    general = [
        u'开场3秒内抛出核心卖点抓住注意力',
        u'用真实的库存或时限表达紧迫感，不要虚构销量',
        u'补充可核实的信任信息（产地、检测报告编号）',
        u'结尾引导关注直播间获取更多优惠',
        u'用对比法突出产品差异化优势'
    ]
    for g in general:
        if len(suggestions) >= 3:
            break
        suggestions.append(g)

    return suggestions[:3]


__all__ = ['analyze_script', 'generate_suggestions']
