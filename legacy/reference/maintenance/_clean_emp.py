# -*- coding: utf-8 -*-
"""清理 script.js 中就业侧边栏相关的死代码"""
import io, re

path = r"D:\gameitem\粤乡智匠项目\粤乡智匠项目\script.js"
with io.open(path, 'r', encoding='utf-8') as f:
    text = f.read()

def cut(text, start_marker, end_marker, label, exclusive_end=True):
    s = text.find(start_marker)
    if s < 0:
        print(f"[FAIL] {label}: start not found"); return text, False
    e = text.find(end_marker, s)
    if e < 0:
        print(f"[FAIL] {label}: end not found"); return text, False
    if not exclusive_end:
        e += len(end_marker)
    lines = text[s:e].count('\n') + 1
    text = text[:s] + text[e:]
    print(f"[OK] {label}: removed ~{lines} lines")
    return text, True

ok = True

# 1. STARTUP_SERVICES + setupStartupSupportLinks + openStartupOverview + openStartupDetail
text, o = cut(text,
    "const STARTUP_SERVICES = [",
    "async function loadEmploymentData() {",
    "startup services block")
ok &= o

# 2. loadEmploymentStats + loadCertificateSummary
text, o = cut(text,
    "async function loadEmploymentStats() {",
    "async function loadUserApplications(",
    "stats + cert summary functions")
ok &= o

# 3. setupPointsExchange
text, o = cut(text,
    "// ==================== 积分兑换 ====================",
    "function showDetailModal(",
    "points exchange block")
ok &= o

# 4. setupEmploymentTab 中的两个调用
old_tab = """    setupEmploymentSubTabs();
    setupEmploymentSearch();
    setupApplicationStatusTabs();
    setupStartupSupportLinks();
    setupPointsExchange();
"""
new_tab = """    setupEmploymentSubTabs();
    setupEmploymentSearch();
    setupApplicationStatusTabs();
"""
if old_tab in text:
    text = text.replace(old_tab, new_tab)
    print("[OK] setupEmploymentTab calls trimmed")
else:
    print("[FAIL] setupEmploymentTab calls"); ok = False

# 5. loadEmploymentData 简化
old_load = """async function loadEmploymentData() {
    // 职位列表不需要登录即可加载
    await loadJobListings();
    if (!AppState.user) return;
    await Promise.all([
        loadEmploymentStats(),
        loadCertificateSummary()
    ]);
}"""
new_load = """async function loadEmploymentData() {
    // 职位列表不需要登录即可加载
    await loadJobListings();
}"""
if old_load in text:
    text = text.replace(old_load, new_load)
    print("[OK] loadEmploymentData simplified")
else:
    print("[FAIL] loadEmploymentData"); ok = False

# 6. loadUserData 中侧边栏积分 el2
old_el2 = """            const el2 = document.getElementById('emp-points-balance');
            if (el2) el2.textContent = ptsData.points.toLocaleString();
"""
if old_el2 in text:
    text = text.replace(old_el2, "")
    print("[OK] loadUserData el2 removed")
else:
    print("[FAIL] loadUserData el2"); ok = False

# 清理连续空行
text = re.sub(r'\n{4,}', '\n\n\n', text)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("ALL OK" if ok else "PARTIAL FAIL")
