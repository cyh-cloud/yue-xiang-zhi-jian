import json
import subprocess
import sys

REPO = 'cyh-cloud/yue-xiang-zhi-jian'
PARENT_NODE = 'I_kwDOTqUXTs8AAAABWcFm9w'
NUMBERS = list(range(3, 21))

query = '''
query($owner:String!,$name:String!,$n:Int!){
  repository(owner:$owner,name:$name){ issue(number:$n){ id number } }
}
'''
mutation = '''
mutation($issueId: ID!, $subIssueId: ID!) {
  addSubIssue(input: {issueId: $issueId, subIssueId: $subIssueId}) {
    subIssue { number }
  }
}
'''

nodes = {}
for n in NUMBERS:
    r = subprocess.run(['gh', 'api', 'graphql', '-f', 'query=' + query,
                        '-F', 'owner=cyh-cloud', '-F', 'name=yue-xiang-zhi-jian',
                        '-F', 'n=%d' % n],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        print('FAIL lookup', n, r.stderr.strip()[:160])
        sys.exit(1)
    nodes[n] = json.loads(r.stdout)['data']['repository']['issue']['id']

failures = []
for n in NUMBERS:
    r = subprocess.run(['gh', 'api', 'graphql', '-f', 'query=' + mutation,
                        '-F', 'issueId=' + PARENT_NODE, '-F', 'subIssueId=' + nodes[n]],
                       capture_output=True, text=True, encoding='utf-8')
    if r.returncode != 0:
        failures.append(n)
        print('FAIL link', n, r.stderr.strip()[:160])
    else:
        print('linked #%d under #2' % n)

if failures:
    print('FAILURES:', failures)
    sys.exit(1)
print('all sub-issues linked')
