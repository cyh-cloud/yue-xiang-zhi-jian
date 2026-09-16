from __future__ import annotations


LIVE_SCRIPT_STYLES = (
    "enthusiastic",
    "professional",
    "humorous",
)

SIMULATION_SCENES = {
    "opening": {
        "label": "开场白",
        "segments": [
            {"key": "greeting", "label": "问候"},
            {"key": "hook", "label": "引题"},
            {"key": "audience_call", "label": "聚人"},
        ],
    },
    "product_intro": {
        "label": "产品介绍",
        "segments": [
            {"key": "core_value", "label": "核心卖点"},
            {"key": "use_case", "label": "使用场景"},
            {"key": "proof", "label": "信任证明"},
        ],
    },
    "interaction": {
        "label": "互动引导",
        "segments": [
            {"key": "question", "label": "提问"},
            {"key": "poll", "label": "投票"},
            {"key": "response_prompt", "label": "回应引导"},
        ],
    },
    "closing": {
        "label": "促单话术",
        "segments": [
            {"key": "offer", "label": "利益点"},
            {"key": "urgency", "label": "紧迫感"},
            {"key": "call_to_action", "label": "行动指令"},
        ],
    },
    "objection": {
        "label": "异议处理",
        "segments": [
            {"key": "acknowledge", "label": "承接异议"},
            {"key": "clarify", "label": "澄清问题"},
            {"key": "evidence", "label": "证据回应"},
            {"key": "close", "label": "再次促单"},
        ],
    },
}

COPY_DEFECT_CATEGORIES = (
    "missing_key_information",
    "unclear_value",
    "unsupported_claim",
    "missing_interaction",
    "missing_action",
)

STORE_PLATFORMS = (
    "taobao",
    "pinduoduo",
    "douyin_shop",
)

CUSTOMER_SCENARIOS = {
    "product_info": {
        "label": "商品信息咨询",
        "criteria": ["product_need_identified", "accurate_info_and_next_step"],
    },
    "price_promo": {
        "label": "价格优惠咨询",
        "criteria": ["promotion_rule_explained", "eligibility_verified"],
    },
    "shipping": {
        "label": "物流时效咨询",
        "criteria": ["order_context_identified", "delivery_and_next_step"],
    },
    "after_sales": {
        "label": "售后退换咨询",
        "criteria": ["issue_identified", "policy_and_process_explained"],
    },
    "complaint": {
        "label": "投诉与情绪安抚",
        "criteria": ["emotion_acknowledged", "resolution_or_escalation"],
    },
}
