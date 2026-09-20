AI_COMPANION_ROLES = ("student", "teacher", "enterprise", "government")
ADMIN_ROLES = ("super_admin", "admin")
INTENTS = ("platform_usage", "learning_question", "out_of_scope")
DIALECTS = {"yue": "粤语", "hak": "客家话", "nan": "潮汕话"}

AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
KNOWLEDGE_UNAVAILABLE_MESSAGE = "暂无法回答，请稍后再试"
ASR_FAILURE_MESSAGE = "未能识别，请重说或改用文字"
REFUSAL_MESSAGE = "AI 学伴不代办业务操作，请使用对应功能入口或联系管理员。"

MAX_QUESTION_LENGTH = 2000
MAX_CONVERSATIONS = 100
MAX_MESSAGES_PER_CONVERSATION = 200
CONVERSATION_RETENTION_DAYS = 180
