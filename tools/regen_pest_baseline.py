# -*- coding: utf-8 -*-
"""T12 一次性工具：把 tests/baseline_pest_switch.json 的速查部分按新形状重算一遍。

新形状只多了 total（筛选后总条数）与 limit/offset 两个请求参数，其余字段与
排序都不动。这里只重算速查那六个变体；诊断降级那条**不碰**，它比对的是切换前的
知识库结论，与本次改动无关，改它等于把一条不相关的契约悄悄换掉。

用法（在仓库根跑）：
    python tools/regen_pest_baseline.py
"""

import hashlib
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO_ROOT, 'backend')
sys.path.insert(0, BACKEND)

BASELINE = os.path.join(REPO_ROOT, 'tests', 'baseline_pest_switch.json')

# 与 tests/test_pest_read_db_snapshot.py 的 KNOWLEDGE_VARIANTS 保持同一批请求。
KNOWLEDGE_VARIANTS = (
    ('/api/agriculture/pest-knowledge', {}),
    ('/api/agriculture/pest-knowledge', {'crop': 'lychee'}),
    ('/api/agriculture/pest-knowledge', {'kind': 'pest'}),
    ('/api/agriculture/pest-knowledge', {'q': u'炭疽'}),
    ('/api/agriculture/pest-knowledge', {'crop': 'no-such-crop'}),
    ('/api/agriculture/pest-knowledge', {'kind': 'virus'}),
)


def _strip_pagination(body):
    u"""与 tests/test_pest_read_db_snapshot.py 的同名函数保持一致。"""
    stripped = dict(body)
    stripped.pop('total', None)
    if 'crops' in stripped:
        stripped['crops'] = [
            {k: v for k, v in crop.items() if k != 'count'} for crop in stripped['crops']
        ]
    return stripped


def _key(path, args):
    if not args:
        return path
    query = '&'.join('%s=%s' % item for item in sorted(args.items()))
    return '%s?%s' % (path, query)


def main():
    from app import app
    client = app.test_client()

    with open(BASELINE, encoding='utf-8') as handle:
        baseline = json.load(handle)

    for path, args in KNOWLEDGE_VARIANTS:
        response = client.get(path, query_string=args)
        body = json.loads(response.data.decode('utf-8'))
        canonical = json.dumps(_strip_pagination(body), ensure_ascii=False,
                               sort_keys=True).encode('utf-8')
        baseline[_key(path, args)] = {
            'status': response.status_code,
            'bytes': len(response.data),
            'sha256': hashlib.sha256(response.data).hexdigest(),
            'sha256_ex_total': hashlib.sha256(canonical).hexdigest(),
        }

    with open(BASELINE, 'w', encoding='utf-8') as handle:
        json.dump(baseline, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(u'已重算 %d 个速查变体（诊断降级那条未动）' % len(KNOWLEDGE_VARIANTS))


if __name__ == '__main__':
    main()
