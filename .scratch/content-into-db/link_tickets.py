import json, subprocess, sys

REPO = "cyh-cloud/yue-xiang-zhi-jian"
PARENT = 21
CHILDREN = [22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38]
DEPS = {
    23: [22],
    24: [22],
    26: [25],
    27: [26], 28: [26], 29: [26], 30: [26],
    31: [27, 28, 29, 30],
    32: [31],
    33: [28],
    34: [22],
    35: [31, 34],
    36: [31, 34],
}

def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

q = "query($o:String!,$n:String!,$i:Int!){repository(owner:$o,name:$n){issue(number:$i){id number}}}"
m = "mutation($i:ID!,$s:ID!){addSubIssue(input:{issueId:$i,subIssueId:$s}){subIssue{number}}}"
dep = "mutation($i:ID!,$b:ID!){addIssueDependency(input:{issueId:$i,blockedBy:$b}){issue{number}}}"

ids = {}
for n in [PARENT] + CHILDREN:
    r = run(["gh","api","graphql","-f","query="+q,"-F","o=cyh-cloud","-F","n=yue-xiang-zhi-jian","-F","i=%d"%n])
    if r.returncode != 0:
        print("FAIL id", n, r.stderr.strip()[:200]); sys.exit(1)
    ids[n] = json.loads(r.stdout)["data"]["repository"]["issue"]["id"]
print("ids resolved")

fails = []
for n in CHILDREN:
    r = run(["gh","api","graphql","-f","query="+m,"-F","i="+ids[PARENT],"-F","s="+ids[n]])
    if r.returncode != 0:
        fails.append(("sub", n, r.stderr.strip()[:200]))
    else:
        print("sub-issue #%d under #%d" % (n, PARENT))

for child, blockers in DEPS.items():
    for b in blockers:
        r = run(["gh","api","graphql","-f","query="+dep,"-F","i="+ids[child],"-F","b="+ids[b]])
        if r.returncode != 0:
            fails.append(("dep", (child,b), r.stderr.strip()[:200]))
        else:
            print("#%d blocked_by #%d" % (child, b))

if fails:
    print("FAILURES:", fails); sys.exit(1)
print("all linked")
