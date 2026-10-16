# -*- coding: utf-8 -*-
"""并发用例的公共骨架：把「线程里抛异常」变成一条失败的断言，而不是永久挂死。

背景（一次真实事故）：一条用例用 `threading.Barrier(8)` 让 8 个线程同步起跑，
跑完 `thread.join()` 就直接断言。只要有一个 worker 在其请求里抛了异常，
那个线程会静悄悄死掉，其余 7 个在下一轮 `barrier.wait()` 上永远等不到第 8 个，
主线程的 `join()` 也一样永久等待 —— 整条用例不返回，整个测试进程也再不返回
（表现为「全量测试跑到一半卡死，没有任何输出」）。

所以并发用例一律走这里：超时的 barrier、超时的 join、异常被收进 errors。
三个返回值的用途：results 是正常结果，errors 是「本会让线程死掉」的异常，
alive 是超时后仍然活着的线程名（非空即说明同步骨架本身有洞）。
"""

import threading


def run_concurrently(worker_count, rounds, call, timeout=30.0):
    """在 worker_count 个线程里各跑 rounds 轮 call(index, attempt)。

    call 抛出的任何异常都被收进 errors 并继续下一轮，绝不任其把线程杀掉：
    线程悄悄死掉正是上面那个永久挂死的成因。
    """
    barrier = threading.Barrier(worker_count, timeout=timeout)
    results = []
    errors = []
    lock = threading.Lock()

    def worker(index):
        for attempt in range(rounds):
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                # 有 worker 没能到达（或者整体已经超时）：记一笔然后收工，
                # 不能让本线程在这里无限等下去。
                with lock:
                    errors.append((index, attempt, '同步超时：未能让全部 worker 同时起跑'))
                return
            try:
                value = call(index, attempt)
            except Exception as exc:  # noqa: BLE001 - 必须收下，漏出去就是线程死亡
                with lock:
                    errors.append((index, attempt, '%s: %s' % (type(exc).__name__, exc)))
                continue
            with lock:
                results.append(value)

    threads = [threading.Thread(target=worker, args=(i,), name='worker-%d' % i)
               for i in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout)

    alive = [thread.name for thread in threads if thread.is_alive()]
    return results, errors, alive
