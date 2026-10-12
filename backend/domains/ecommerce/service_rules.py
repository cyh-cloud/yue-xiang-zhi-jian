# -*- coding: utf-8 -*-
"""客服对练的规则部分：回复评分、情绪信号、动态兜底与动态提示。

从 app.py 迁出（后端按领域拆分 T12），逐字未改。四个函数只服务
`/api/ecommerce/customer-service` 及其两个辅助接口，没有第二个消费方，
所以单独成模块、不摊在路由文件里（路由文件有 600 行上限）。

两条口径在整份模块里一致：

- 评分只评**学员（客服）自己的回复**，对象不能错；
- 兜底与提示都不虚构优惠、物流时效、赔付承诺与认证检测数据。
  客服对练教的是「怎么说话」，不是「编一个能促单的谎言」。
"""

import random


def _sentiment_from_score(total):
    """体验优化⑥（2026-10-06）：把本轮学员回复质量映射为客户情绪信号。

    纯规则、无随机，供前端「客户情绪温度条」展示。返回 0-100 的满意度 + 文案标签。
    """
    if total >= 85:
        return {'level': 90, 'label': u'满意'}
    if total >= 70:
        return {'level': 72, 'label': u'较满意'}
    if total >= 55:
        return {'level': 52, 'label': u'一般'}
    return {'level': 32, 'label': u'不满'}


def analyze_service_reply(customer_msg, ai_reply, scenario, history, difficulty=u'进阶'):
    """分析客服（用户）的回复质量。

    customer_msg = 学员（客服）这一句回复；history = 前端传来的对话历史
    （其中 role='assistant' 是 AI 客户、role='user' 是学员客服，均不含当前句）。
    据此额外判定「答非所问」：取客户上一句，看学员回复是否回应了它。
    """
    last_user_msg = customer_msg

    scores = {
        'politeness': 50,   # 礼貌度
        'professional': 50, # 专业度
        'solving': 50,      # 解决问题能力
        'empathy': 50,      # 同理心
    }
    tips = []

    # 礼貌度检测
    polite_words = [u'亲', u'您好', u'感谢', u'抱歉', u'不好意思', u'请', u'麻烦', u'感谢您']
    polite_count = sum(1 for w in polite_words if w in last_user_msg)
    scores['politeness'] = min(95, 50 + polite_count * 12)
    if polite_count == 0:
        tips.append(u'开头用"亲"或"您好"会更亲切')

    # 专业度检测
    pro_words = [u'产地', u'品种', u'甜度', u'规格', u'发货', u'冷链', u'检测', u'新鲜', u'当季', u'直发']
    pro_count = sum(1 for w in pro_words if w in last_user_msg)
    scores['professional'] = min(95, 45 + pro_count * 10)
    if pro_count < 2:
        tips.append(u'加入产品专业信息（产地、品种、规格）更有说服力')

    # 解决问题能力
    solving_words = [u'可以', u'没问题', u'帮您', u'给您', u'安排', u'处理', u'解决方案', u'补偿', u'退款', u'换货']
    solving_count = sum(1 for w in solving_words if w in last_user_msg)
    scores['solving'] = min(95, 40 + solving_count * 12)
    if solving_count < 2 and scenario in [u'售后处理', u'投诉应对']:
        tips.append(u'明确告诉客户解决方案，如"帮您补发""给您退款"')

    # 同理心检测
    empathy_words = [u'理解', u'抱歉', u'不好意思', u'确实', u'换做我', u'体谅', u'心情', u'感受']
    empathy_count = sum(1 for w in empathy_words if w in last_user_msg)
    scores['empathy'] = min(95, 40 + empathy_count * 15)
    if empathy_count == 0 and scenario in [u'投诉应对', u'售后处理']:
        tips.append(u'先表达理解和歉意，再解决问题效果更好')

    # ===== P1-2（2026-10-06 走查）：答非所问判定 =====
    # 取客户上一句（history 里最后一条 assistant = AI 客户），若学员回复与它
    # 毫无关联（既没回应关键词、也没给解决方案），则视为「答非所问」，整体降分。
    # 反之，正面回应了客户关注点，是「解决力」的核心体现，应给 solving 加分。
    if isinstance(history, list):
        last_customer = ''
        for h in reversed(history):
            if isinstance(h, dict) and h.get('role') == 'assistant':
                last_customer = str(h.get('content', '') or '')
                break
        if last_customer:
            # 客户上一句的「关注点」关键词（价格/品质/发货/售后/议价/推荐）
            concern_words = {
                'price': [u'钱', u'价格', u'贵', u'便宜', u'优惠', u'折', u'包邮', u'多少'],
                'quality': [u'新鲜', u'甜', u'好吃', u'品质', u'质量', u'口感', u'坏', u'破'],
                'delivery': [u'发货', u'几天', u'到货', u'快递', u'物流', u'到'],
                'aftersale': [u'退货', u'退款', u'换货', u'补偿', u'处理', u'投诉', u'差评'],
                'recommend': [u'推荐', u'哪个', u'选', u'适合', u'什么'],
            }
            concern = None
            for key, words in concern_words.items():
                if any(w in last_customer for w in words):
                    concern = key
                    break
            # 学员回复里「回应了客户关注点」的迹象
            respond_words = {
                'price': [u'价', u'元', u'优惠', u'折', u'包邮', u'划算', u'活动', u'送'],
                'quality': [u'新鲜', u'甜', u'品质', u'产地', u'品种', u'检测', u'冷链', u'口感'],
                'delivery': [u'发货', u'天', u'顺丰', u'快递', u'物流', u'到货', u'加急'],
                'aftersale': [u'退款', u'退货', u'换货', u'补发', u'补偿', u'处理', u'安排', u'帮您', u'解决'],
                'recommend': [u'推荐', u'这款', u'适合', u'送', u'礼盒', u'建议', u'可以'],
            }
            if concern and concern in respond_words:
                responded = any(w in last_user_msg for w in respond_words[concern])
                if not responded:
                    # 答非所问：整体每项都打折，并给明确提示
                    for k in scores:
                        scores[k] = max(35, int(scores[k] * 0.6))
                    tips.insert(0, u'客户在问「%s」相关，你的回复没有正面回应' % concern)
                else:
                    # 正面回应客户关注点 = 解决力的核心，给 solving 加分；
                    # 同时「回应」本身就是专业 + 共情的体现，小幅提升这两维，
                    # 避免「正确报了价格」的学员因专业/同理基线分而显得不及格。
                    scores['solving'] = min(95, scores['solving'] + 20)
                    scores['professional'] = min(95, scores['professional'] + 10)
                    scores['empathy'] = min(95, scores['empathy'] + 8)
                    if scenario in [u'售后处理', u'投诉应对']:
                        scores['solving'] = min(95, scores['solving'] + 10)

    # 长度合理性
    if len(last_user_msg) < 10:
        tips.append(u'回复太短，客户可能觉得敷衍')
    elif len(last_user_msg) > 200:
        tips.append(u'回复太长，客户可能没耐心看完')

    total = round(sum(scores.values()) / 4)

    # ===== P3-8（2026-10-06）：难度加权 =====
    # 挑战难度下，简单/敷衍的回复应被压分，否则难度对评分零作用。
    if difficulty == u'挑战':
        if len(last_user_msg) < 10:
            total = max(20, total - 12)
            tips.append(u'挑战难度下回复过于简单，客户会被"糊弄"激怒')
        elif total >= 80:
            # 挑战难度拿高分的门槛更高，轻微回压体现区分度
            total = total - 3

    # 通用建议
    if not tips:
        if total >= 85:
            tips.append(u'回复很棒！继续保持')
        elif total >= 70:
            tips.append(u'整体不错，可以再多一些情感表达')
        else:
            tips.append(u'多站在客户角度思考，理解他们的真实需求')

    return {
        'total': total,
        'details': scores,
        'tips': tips[:3]
    }


def generate_dynamic_fallback(scenario, product, personality, history, last_reply):
    """根据对话上下文动态生成客户回复（不依赖AI）"""

    # 统计对话轮数
    rounds = len([h for h in history if h.get('role') == 'user'])

    # 分析客服回复的关键词
    has_apology = any(w in last_reply for w in [u'抱歉', u'不好意思', u'对不起', 'sorry'])
    has_solution = any(w in last_reply for w in [u'补发', u'退款', u'换货', u'处理', u'解决', u'补偿'])
    has_data = any(w in last_reply for w in [u'甜度', u'产地', u'品种', u'规格', u'检测', u'冷链'])
    has_price = any(w in last_reply for w in [u'优惠', u'打折', u'便宜', u'减', u'送'])
    has_greeting = any(w in last_reply for w in [u'亲', u'您好', u'欢迎'])

    if scenario == u'售前咨询':
        if rounds <= 1:
            options = [
                u"这个{product}到底新不新鲜啊？能发个实拍看看吗？",
                u"你们的{product}多少钱一斤？比别家贵不？",
                u"{product}是哪里产的？当季的吗？",
                u"我想买点{product}，发货快吗？几天能到？"
            ]
        elif has_data:
            options = [
                u"听起来还不错，有没有买家秀看看？",
                u"那和其他家比你们有什么优势？",
                u"可以先买少一点试试吗？",
                u"礼盒装多少钱？送人合适吗？"
            ]
        elif has_price:
            options = [
                u"这个价格能再便宜点不？",
                u"买多几箱有优惠吗？",
                u"行吧，那我先下一单试试",
                u"有没有满减活动？"
            ]
        else:
            options = [
                u"嗯...我再看看吧",
                u"你说的这些我不太懂，能简单点说吗？",
                u"那你们售后怎么样？坏了怎么办？",
                u"行，我考虑一下"
            ]

    elif scenario == u'售后处理':
        if has_apology and has_solution:
            options = [
                u"那行吧，你帮我处理一下",
                u"补发的话多久能到？",
                u"退款多久能到账？",
                u"这次就算了，下次注意点"
            ]
        elif has_apology:
            options = [
                u"光道歉有什么用，倒是给个解决方案啊",
                u"我都等了好几天了，怎么处理？",
                u"那你说怎么办吧"
            ]
        else:
            options = [
                u"我收到的{product}有几个坏的，你们怎么处理？",
                u"你们客服怎么回事？半天不处理",
                u"我要退货，怎么操作？",
                u"包装都破了，东西都压坏了"
            ]

    elif scenario == u'投诉应对':
        if rounds >= 4:
            options = [
                u"行吧，这次就这样吧",
                u"那你赶紧处理吧，我等着",
                u"补偿就算了，下次别这样了",
                u"我再信你们一次"
            ]
        elif has_apology:
            options = [
                u"道歉有什么用？我要实际的解决方案！",
                u"你们每次都这样说，有啥用？",
                u"那你说怎么补偿吧"
            ]
        else:
            options = [
                u"你们这是什么服务态度！太差了！",
                u"我要投诉你们！太坑了！",
                u"再也不买了，什么玩意儿！",
                u"找你们领导来！"
            ]

    elif scenario == u'议价谈判':
        if has_price:
            options = [
                u"还是有点贵，再便宜点呗",
                u"行吧，那你送点赠品",
                u"那我先买一箱试试",
                u"下次再来买能给老客户价不？"
            ]
        else:
            options = [
                u"能便宜点吗？别家比你们便宜啊",
                u"买两箱给个优惠价呗",
                u"零头去掉行不行？",
                u"送点赠品呗，我介绍朋友也来买"
            ]

    else:  # 产品推荐
        if rounds <= 1:
            options = [
                u"你们有什么好吃的推荐？",
                u"第一次来，哪个比较好？",
                u"送人买什么合适？",
                u"当季有什么新鲜的？"
            ]
        else:
            options = [
                u"这个口感怎么样？甜不甜？",
                u"那就要这个吧，怎么下单？",
                u"有没有礼盒装的？",
                u"行，我再看看其他的"
            ]

    # 按产品名回填占位
    options = [o.format(product=product) if '{product}' in o else o for o in options]

    # 根据性格调整
    if personality == u'急躁型':
        options = [o + u'！快点回复' if random.random() > 0.5 else o for o in options]
    elif personality == u'挑剔型':
        if random.random() > 0.5:
            options.append(u'你确定没问题吧？我可不好糊弄')

    return random.choice(options)


def generate_dynamic_hint(scenario, product, personality, last_msg, history):
    """根据对话上下文动态生成回复建议（不虚构优惠/物流/赔付承诺）"""

    rounds = len([h for h in history if h.get('role') == 'user'])

    ask_price = any(w in last_msg for w in [u'多少钱', u'价格', u'贵', u'便宜', u'优惠'])
    ask_quality = any(w in last_msg for w in [u'新鲜', u'甜', u'好吃', u'品质', u'质量'])
    ask_delivery = any(w in last_msg for w in [u'发货', u'几天', u'到货', u'快递', u'物流'])
    ask_refund = any(w in last_msg for w in [u'退货', u'退款', u'换货', u'坏了', u'破损'])
    is_angry = any(w in last_msg for w in [u'差评', u'投诉', u'骗子', u'垃圾', u'太差'])
    is_hesitating = any(w in last_msg for w in [u'考虑', u'想想', u'再看看', u'犹豫'])

    if scenario == u'售前咨询':
        if ask_price:
            return {
                'analysis': u'客户在关注价格',
                'strategy': u'讲价值+按实际活动谈优惠',
                'templates': [
                    u'我们的%s是产地直发，品质和性价比都不错，您可以先了解下规格' % product,
                    u'具体优惠以本店当前活动为准，您可以先看看商品详情页',
                    u'您大概想买多少？量大我帮您看看有没有合适的方案'
                ],
                'tips': [u'先讲价值再谈价格', u'优惠以店铺实际活动为准，不要随口承诺']
            }
        elif ask_quality:
            return {
                'analysis': u'客户在担心品质',
                'strategy': u'用真实信息建立信任',
                'templates': [
                    u'%s的甜度和新鲜度都不错，具体以您收到的实物为准' % product,
                    u'我们有相关的检测/实拍资料，稍后可以发您参考',
                    u'很多老客户都回购，您可以看看真实评价'
                ],
                'tips': [u'用真实信息说话', u'有检测报告/实拍图就主动展示']
            }
        elif ask_delivery:
            return {
                'analysis': u'客户关心物流时效',
                'strategy': u'给明确预期但不虚构时效',
                'templates': [
                    u'发货和物流时效以实际下单后为准，您可以关注物流信息',
                    u'我们会尽快安排发出，具体到达时间视物流情况',
                    u'您在哪个城市？我帮您估一下大致时效'
                ],
                'tips': [u'给明确预期但不虚构时效', u'物流以实际情况为准']
            }
        elif is_hesitating:
            return {
                'analysis': u'客户在犹豫中',
                'strategy': u'用真实卖点促单',
                'templates': [
                    u'%s当季吃口感最好，错过要等明年了' % product,
                    u'您可以先少拿一点试试，觉得好再回购',
                    u'有不清楚的随时问我，我帮您参谋'
                ],
                'tips': [u'用真实卖点促单', u'不要编造限时/限量优惠']
            }
        else:
            return {
                'analysis': u'客户在了解产品',
                'strategy': u'主动引导+了解需求',
                'templates': [
                    u'亲，您是自己吃还是送人呢？我帮您推荐',
                    u'我们的%s当季新鲜，很多客户都回购' % product,
                    u'您有什么顾虑可以告诉我，我帮您解答'
                ],
                'tips': [u'主动问客户需求', u'用提问引导对话']
            }

    elif scenario == u'售后处理':
        if ask_refund:
            return {
                'analysis': u'客户要退换货',
                'strategy': u'快速处理+减少损失',
                'templates': [
                    u'亲，非常抱歉给您带来不便，马上帮您处理',
                    u'您看是补发还是退款呢？我这边都可以',
                    u'方便拍个照片给我看看吗？我好给您处理'
                ],
                'tips': [u'先道歉再处理', u'给客户选择权']
            }
        elif rounds <= 2:
            return {
                'analysis': u'客户刚开始反馈问题',
                'strategy': u'耐心倾听+了解详情',
                'templates': [
                    u'亲，非常抱歉给您带来不好的体验',
                    u'方便说下具体情况吗？我帮您核实',
                    u'您放心，问题我们一定会跟进处理'
                ],
                'tips': [u'先倾听再处理', u'不要急着辩解']
            }
        else:
            return {
                'analysis': u'客户等待解决方案',
                'strategy': u'给出具体可执行的方案',
                'templates': [
                    u'我这边马上帮您登记处理，您看补发方便吗？',
                    u'给您退款可以吗？具体按本店售后流程办',
                    u'这次真的很抱歉，后续我们一定改进'
                ],
                'tips': [u'方案要具体可执行', u'补偿按店铺实际政策，不口头承诺额外好处']
            }

    elif scenario == u'投诉应对':
        if is_angry:
            return {
                'analysis': u'客户情绪很激动',
                'strategy': u'先安抚情绪再处理',
                'templates': [
                    u'亲，真的很抱歉，您的心情我完全理解',
                    u'这种情况确实不应该发生，我马上帮您处理',
                    u'您先消消气，我一定给您一个明确答复'
                ],
                'tips': [u'不要反驳', u'让客户先发泄']
            }
        elif rounds >= 4:
            return {
                'analysis': u'客户情绪已缓和',
                'strategy': u'提出合规补偿方案',
                'templates': [
                    u'给您申请一下本店当前的补偿方案可以吗？',
                    u'这次我们按规则为您处理退款',
                    u'后续您来都是按会员权益对待'
                ],
                'tips': [u'补偿要有诚意且合规', u'优惠/补偿以店铺实际政策为准']
            }
        else:
            return {
                'analysis': u'客户在表达不满',
                'strategy': u'真诚道歉+表达重视',
                'templates': [
                    u'亲，真的很抱歉给您带来这么差的体验',
                    u'您反馈的问题我们非常重视',
                    u'我马上帮您处理，您看怎么处理比较合适？'
                ],
                'tips': [u'态度要诚恳', u'不要推卸责任']
            }

    elif scenario == u'议价谈判':
        if rounds >= 3:
            return {
                'analysis': u'客户多次议价',
                'strategy': u'守价格底线+讲价值',
                'templates': [
                    u'亲，%s这个价已经很有诚意了' % product,
                    u'您可以看看我们的品质，值这个价',
                    u'您先拿一点试试，满意再回头'
                ],
                'tips': [u'守住价格底线', u'用价值代替降价']
            }
        elif ask_price:
            return {
                'analysis': u'客户想要优惠',
                'strategy': u'强调价值+按实际活动优惠',
                'templates': [
                    u'亲，%s品质对得起这个价' % product,
                    u'具体优惠以本店当前活动为准，您可以先看看',
                    u'您想买多少？我帮您看下合适的方案'
                ],
                'tips': [u'先说价值再说优惠', u'不虚构折扣']
            }
        else:
            return {
                'analysis': u'客户在比较价格',
                'strategy': u'突出差异化优势',
                'templates': [
                    u'我们的和别家不一样的，您看这个品相',
                    u'我们是产地直发，少中间环节',
                    u'品质有保证，您可以先少拿点试'
                ],
                'tips': [u'强调品质差异', u'不编造绝对化承诺']
            }

    else:  # 产品推荐
        if rounds <= 1:
            return {
                'analysis': u'客户需要推荐',
                'strategy': u'问需求再推荐',
                'templates': [
                    u'请问您是自己吃还是送人呢？',
                    u'您喜欢甜一点的还是清淡一点的？',
                    u'现在当季的%s最好吃，推荐您试试' % product
                ],
                'tips': [u'先了解需求', u'不要盲目推荐']
            }
        else:
            return {
                'analysis': u'客户在考虑选择',
                'strategy': u'精准推荐+打消顾虑',
                'templates': [
                    u'这款是最受欢迎的%s，回头客很多' % product,
                    u'送人的话推荐礼盒装，包装更有面子',
                    u'您要几斤的？我帮您推荐合适的规格'
                ],
                'tips': [u'推荐1-2款就行', u'说明推荐理由']
            }


__all__ = [
    '_sentiment_from_score', 'analyze_service_reply',
    'generate_dynamic_fallback', 'generate_dynamic_hint',
]
