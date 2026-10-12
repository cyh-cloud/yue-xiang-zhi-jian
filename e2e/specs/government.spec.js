import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

test("政府政策：非政府拒写；政府可创建/更新/删除", async ({ request }) => {
  const gov = (await login(request, ACCOUNTS.gov)).sessionId;
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(gov, "gov 登录失败").toBeTruthy();

  const forbidden = await call(request, "POST", "/api/government/policies", {
    sessionId: student, data: { title: "x", content: "y" },
  });
  expect(forbidden.status, "学员发布政策应 403").toBe(403);

  const title = "__e2e政策__" + Date.now();
  const created = await call(request, "POST", "/api/government/policies", {
    sessionId: gov, data: { title, content: "e2e 内容", category: "general", summary: "摘要" },
  });
  expect(created.status, `创建应 200，实际 ${created.status}: ${created.snippet}`).toBe(200);
  const pid = created.json?.id;
  expect(pid, "创建应返回 id").toBeTruthy();

  const list1 = await call(request, "GET", "/api/government/policies", { sessionId: gov });
  const arr1 = list1.json?.policies ?? list1.json?.items ?? list1.json?.data ?? [];
  const seenBefore = (Array.isArray(arr1) ? arr1 : []).some((p) => p.id === pid);

  const upd = await call(request, "PUT", `/api/government/policies/${pid}`, { sessionId: gov, data: { title: title + "_改" } });
  expect(upd.status, `更新应 200，实际 ${upd.status}`).toBe(200);

  const del = await call(request, "DELETE", `/api/government/policies/${pid}`, { sessionId: gov });
  expect(del.status, `删除应 200，实际 ${del.status}`).toBe(200);
  const list2 = await call(request, "GET", "/api/government/policies", { sessionId: gov });
  const arr2 = list2.json?.policies ?? list2.json?.items ?? list2.json?.data ?? [];
  if (seenBefore) {
    expect((Array.isArray(arr2) ? arr2 : []).some((p) => p.id === pid), "删除后不应还在列表").toBe(false);
  }
  record("government-policies.json", { pid, listShape: list1.json ? Object.keys(list1.json) : null, seenBefore });
});
