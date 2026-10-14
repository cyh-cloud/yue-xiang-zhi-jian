import json
import subprocess
import sys

REPO = 'cyh-cloud/yue-xiang-zhi-jian'

# ticket number -> database id
dbid = {3: 5800898318, 4: 5800898637, 5: 5800899013, 6: 5800899262,
        7: 5800899538, 8: 5800899791, 9: 5800900051, 10: 5800900312,
        11: 5800900647, 12: 5800900931, 13: 5800901192, 14: 5800901424,
        15: 5800901704, 16: 5800902003, 17: 5800902277, 18: 5800902536,
        19: 5800902816, 20: 5800903084}
PARENT_DBID = 5800814327

# blocker -> list of tickets blocked by it
edges = {
    3: [5],
    4: [5, 6],
    5: [9],
    6: [7],
    7: [8, 10],
    8: [11],
    9: [10],
    10: [11],
    11: [12],
    12: [13],
    13: [14],
    14: [15],
    15: [16],
    16: [17],
    17: [18],
    18: [19],
    6 + 2: [20],
}


def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding='utf-8')


failures = []

for blocker, blocked_list in edges.items():
    for blocked in blocked_list:
        r = run(['gh', 'api', '--method', 'POST',
                 'repos/%s/issues/%d/dependencies/blocked_by' % (REPO, blocked),
                 '-F', 'issue_id=%d' % dbid[blocker]])
        ok = r.returncode == 0
        print('blocker #%d -> #%d : %s' % (blocker, blocked, 'ok' if ok else 'FAIL ' + r.stderr.strip()))
        if not ok:
            failures.append((blocker, blocked))

for child in range(3, 21):
    r = run(['gh', 'api', '--method', 'POST',
             'repos/%s/issues/%d/sub_issues' % (REPO, PARENT_DBID),
             '-F', 'sub_issue_id=%d' % dbid[child]])
    ok = r.returncode == 0
    if not ok:
        failures.append(('parent', child))
        print('sub-issue #%d -> #2 : FAIL %s' % (child, r.stderr.strip()))

if failures:
    print('FAILURES:', failures)
    sys.exit(1)
print('all edges and sub-issue links set')
