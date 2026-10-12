import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

test("审核门禁（案例）：待审对学员隐藏，过审后可见，直链同步开门", async ({ request }) => {
  const admin = (await login(request, ACCOUNTS.admin)).sessionId;
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(admin, "admin 登录失败").toBeTruthy();
  expect(student, "student 登录失败").toBeTruthy();

  const reviews = await call(request, "GET", "/api/admin/reviews", { sessionId: admin });
  record("review-gate-reviews.json", reviews.json ?? { snippet: reviews.snippet });
  const list = reviews.json?.reviews || reviews.json?.items || reviews.json?.data || [];
  const pendingCase = (Array.isArray(list) ? list : []).find(
    (r) => String(r.content_type || r.type || "").includes("case") &&
           String(r.status || "").toLowerCase() === "pending",
  );
  expect(pendingCase, "未找到待审案例审核，无法验证门禁（见 findings/review-gate-reviews.json）").toBeTruthy();

  const reviewId = pendingCase.id ?? pendingCase.review_id;
  const caseId = pendingCase.content_id ?? pendingCase.case_id ?? pendingCase.target_id;
  expect(caseId, "待审审核记录缺少 caseId 字段").toBeTruthy();

  // 过审前：学员端列表不含该案例，直链 404/403
  const beforeList = await call(request, "GET", "/api/resources/cases", { sessionId: student });
  const beforeIds = new Set((beforeList.json?.cases || []).map((c) => c.id));
  expect(beforeIds.has(caseId), "待审案例不应出现在学员端列表").toBe(false);
  const directBefore = await call(request, "GET", `/api/resources/cases/${caseId}`, { sessionId: student });
  expect([403, 404], `待审案例直链应 403/404，实际 ${directBefore.status}`).toContain(directBefore.status);

  // 管理员通过
  const approve = await call(request, "POST", `/api/admin/reviews/${reviewId}/approve`, { sessionId: admin, data: {} });
  expect(approve.status, `approve 应成功，实际 ${approve.status}: ${approve.snippet}`).toBeLessThan(300);

  // 过审后：学员端列表含该案例，直链 200
  const afterList = await call(request, "GET", "/api/resources/cases", { sessionId: student });
  const afterIds = new Set((afterList.json?.cases || []).map((c) => c.id));
  expect(afterIds.has(caseId), "过审后案例应出现在学员端列表").toBe(true);
  const directAfter = await call(request, "GET", `/api/resources/cases/${caseId}`, { sessionId: student });
  expect(directAfter.status, `过审后直链应 200，实际 ${directAfter.status}`).toBe(200);
});
