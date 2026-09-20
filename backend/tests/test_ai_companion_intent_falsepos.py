import unittest

from app.ai_companion.intent import detect_business_proxy


BUSINESS_PROXY_EXAMPLES = (
    "帮我投简历",
    "替我兑换奖品",
    "代我审核这个职位",
    "帮我发消息给老师",
    "替我修改个人资料",
    "帮我删除这条内容",
)

PLAIN_QUESTIONS_WITH_AGENCY_PHRASE = (
    "帮忙讲解考试的审查环节和核心要点",
    "帮忙看看海报上的名字怎么写",
    "帮忙介绍资金支撑和付款流程",
    "帮忙解释投标和递交材料的区别",
)


class BusinessProxyFalsePositiveTests(unittest.TestCase):
    def test_business_proxy_examples_are_detected(self):
        for question in BUSINESS_PROXY_EXAMPLES:
            with self.subTest(question=question):
                self.assertTrue(detect_business_proxy(question))

    def test_plain_questions_with_agency_phrase_are_not_proxy(self):
        for question in PLAIN_QUESTIONS_WITH_AGENCY_PHRASE:
            with self.subTest(question=question):
                self.assertFalse(detect_business_proxy(question))


if __name__ == "__main__":
    unittest.main()
