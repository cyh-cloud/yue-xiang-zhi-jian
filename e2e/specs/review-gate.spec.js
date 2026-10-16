import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 审核门禁（案例）：待审对学员隐藏，过审后可见，直链同步开门。
//
// ⚠️ 这条用例自己造一条待审案例，不去库里找一个现成的。原先它扫 /api/admin/reviews
// 找「任意一条待审案例」，实际找到的是别的用例留下的残留；开发库清理干净之后，
// 这类「靠垃圾才通过」的用例会立刻暴露。

test("审核门禁（案例）：待审对学员隐藏，过审后可见，直链同步开门", async ({ request }) => {
  const admin = (await login(request, ACCOUNTS.admin)).sessionId;
  const operator = (await login(request, ACCOUNTS.operator)).sessionId;
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(admin, "admin 登录失败").toBeTruthy();
  expect(operator, "operator 登录失败").toBeTruthy();
  expect(student, "student 登录失败").toBeTruthy();

  // 运营新建案例即进审核队列
  const created = await call(request, "POST", "/api/operator/cases", {
    sessionId: operator,
    data: { title: "__e2e门禁案例__", region: "茂名", description: "e2e 门禁用例" },
  });
  expect(created.status, `建案例失败：${created.status} ${created.snippet}`).toBeLessThan(300);
  const caseId = created.json?.result ?? created.json?.id;
  expect(caseId, `建案例没有返回 id：${created.snippet}`).toBeTruthy();

  try {
    // 新建案例必须进审核队列：从管理端审核列表里找到它
    const reviews = await call(request, "GET", "/api/admin/reviews", { sessionId: admin });
    const list = reviews.json?.reviews || reviews.json?.items || reviews.json?.data || [];
    const pending = (Array.isArray(list) ? list : []).find(
      (r) =>
        String(r.content_type || r.type || "").includes("case") &&
        Number(r.content_id ?? r.case_id ?? r.target_id) === Number(caseId),
    );
    record("review-gate-reviews.json", { caseId, pending: pending ?? null });
    expect(pending, "新建案例没有进审核队列（见 findings/review-gate-reviews.json）").toBeTruthy();
    const reviewId = pending.id ?? pending.review_id;

    // 过审前：学员端列表不含该案例，直链 403/404
    const beforeList = await call(request, "GET", "/api/resources/cases", { sessionId: student });
    const beforeIds = new Set((beforeList.json?.cases || []).map((c) => c.id));
    expect(beforeIds.has(caseId), "待审案例不应出现在学员端列表").toBe(false);
    const directBefore = await call(request, "GET", `/api/resources/cases/${caseId}`, { sessionId: student });
    expect([403, 404], `待审案例直链应 403/404，实际 ${directBefore.status}`).toContain(directBefore.status);

    // 管理员通过
    const approve = await call(request, "POST", `/api/admin/reviews/${reviewId}/approve`, {
      sessionId: admin,
      data: {},
    });
    expect(approve.status, `approve 应成功，实际 ${approve.status}: ${approve.snippet}`).toBeLessThan(300);

    // 过审后：学员端列表含该案例，直链 200
    const afterList = await call(request, "GET", "/api/resources/cases", { sessionId: student });
    const afterIds = new Set((afterList.json?.cases || []).map((c) => c.id));
    expect(afterIds.has(caseId), "过审后案例应出现在学员端列表").toBe(true);
    const directAfter = await call(request, "GET", `/api/resources/cases/${caseId}`, { sessionId: student });
    expect(directAfter.status, `过审后直链应 200，实际 ${directAfter.status}`).toBe(200);
  } finally {
    // 删案例会连带删掉它的审核记录（db_domains.content.delete_case）
    const deleted = await call(request, "DELETE", `/api/operator/cases/${caseId}`, { sessionId: operator });
    expect(deleted.status, `清理案例失败：${deleted.status} ${deleted.snippet}`).toBeLessThan(300);
  }
});
