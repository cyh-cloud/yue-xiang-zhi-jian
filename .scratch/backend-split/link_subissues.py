import json
import subprocess
import sys

REPO = 'cyh-cloud/yue-xiang-zhi-jian'
PARENT = 5800814327
CHILDREN = [5800898318, 5800898637, 5800899013, 5800899262, 5800899538,
            5800899791, 5800900051, 5800900312, 5800900647, 5800900931,
            5800901192, 5800901424, 5800901704, 5800902003, 5800902277,
            5800902536, 5800902816, 5800903084]

query = '''
mutation($issueId: ID!, $subIssueId: ID!) {
  addSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId}) {
    subIssue { number }
  }
}
'''

failures = []
for child in CHILDREN:
    r = subprocess.run(['gh', 'api', 'graphql', '-f', 'query=' + query,
                        '-F', 'issueId=%s' % PARENT, '-F', 'subIssueId=%s' % child],
                       capture_output=True, text=True, encoding='utf-8')
    ok = r.returncode == 0
    if ok:
        try:
            num = json.loads(r.stdout)['data']['addSubIssue']['subIssue']['number']
            print('linked #%d' % num)
        except Exception:
            ok = False
    if not ok:
        failures.append(child)
        print('FAIL', child, r.stderr.strip()[:200])

if failures:
    print('FAILURES:', failures)
    sys.exit(1)
print('all sub-issues linked')
