import subprocess, sys, json

REPO = "cyh-cloud/yue-xiang-zhi-jian"
DEPS = {
    23: [22], 24: [22], 26: [25],
    27: [26], 28: [26], 29: [26], 30: [26],
    31: [27, 28, 29, 30],
    32: [31], 33: [28], 34: [22],
    35: [31, 34], 36: [31, 34],
}

def run(args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

def issue_id(n):
    r = run(["gh","api","repos/%s/issues/%d" % (REPO, n), "--jq",".id"])
    return r.stdout.strip()

fails = []
for child, blockers in DEPS.items():
    for b in blockers:
        r = run(["gh","api","--method","POST",
                 "repos/%s/issues/%d/dependencies/blocked_by" % (REPO, child),
                 "-F","issue_id=%s" % issue_id(b)])
        if r.returncode != 0:
            err = r.stderr.strip()[:140]
            if "already been taken" in err:
                print("#%d already blocked_by #%d" % (child, b)); continue
            fails.append((child, b, err)); continue
        print("#%d blocked_by #%d" % (child, b))

if fails:
    print("FAILURES:", fails); sys.exit(1)
print("all dependencies set")
