# -*- coding: utf-8 -*-
"""并发骨架自身的回归测试：worker 抛异常必须变成返回的 errors，而不是永久挂死。

这条用例针对的是「测试代码把整个测试进程挂住」这一类缺陷。它不能用普通的
直接调用来写：真出问题时调用不会返回，断言根本没机会执行。所以这里把调用
放进一个看门线程，超时未返回就判失败。
"""

import os
import sys
import threading
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.concurrency import run_concurrently


class RunConcurrentlyTest(unittest.TestCase):
    def _call_with_watchdog(self, seconds, func):
        """在后台线程里调 func，返回 (是否按时结束, 返回箱)。"""
        box = {}

        def runner():
            box['value'] = func()

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join(seconds)
        return (not thread.is_alive()), box

    def test_a_raising_call_is_reported_instead_of_killing_its_thread(self):
        """worker 抛异常 -> 收进 errors、全部线程正常收工、整体按时返回。"""
        def boom(index, attempt):
            if (index, attempt) == (2, 1):
                raise RuntimeError('injected: 学号生成失败')
            return (index, attempt)

        finished, box = self._call_with_watchdog(
            20, lambda: run_concurrently(4, 3, boom, timeout=5))
        self.assertTrue(finished, '并发骨架没有按时返回：worker 抛异常又把用例挂住了')

        results, errors, alive = box['value']
        self.assertEqual(alive, [], '有 worker 线程没能收工')
        self.assertEqual(len(results), 4 * 3 - 1, '正常轮次的结果应当全部收到')
        self.assertEqual(len(errors), 1, '抛出的异常必须被收进 errors')
        self.assertIn('RuntimeError', errors[0][2])

    def test_every_worker_runs_every_round_when_nothing_raises(self):
        results, errors, alive = run_concurrently(
            5, 3, lambda index, attempt: (index, attempt), timeout=5)
        self.assertEqual(errors, [])
        self.assertEqual(alive, [])
        self.assertEqual(len(results), 5 * 3)


if __name__ == '__main__':
    unittest.main()
