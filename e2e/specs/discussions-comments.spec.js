import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

test("讨论区+评论：发帖→详情→评论→出现在详情与评论列表", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(student, "student 登录失败").toBeTruthy();

  const title = "__e2e帖__" + Date.now();
  const disc = await call(request, "POST", "/api/discussions", {
    sessionId: student, data: { title, content: "e2e 内容", category: "general" },
  });
  expect(disc.status, `发帖应 200，实际 ${disc.status}: ${disc.snippet}`).toBe(200);
  const discId = disc.json?.id;
  expect(discId, "发帖应返回 id").toBeTruthy();

  const detail = await call(request, "GET", `/api/discussions/${discId}`);
  expect(detail.status, `详情应 200，实际 ${detail.status}`).toBe(200);
  expect(detail.json?.discussion, "详情应含帖子").toBeTruthy();

  const comment = await call(request, "POST", "/api/comments", {
    sessionId: student, data: { target_type: "discussion", target_id: discId, content: "e2e 评论" },
  });
  expect(comment.status, `评论应 200，实际 ${comment.status}: ${comment.snippet}`).toBe(200);

  const detail2 = await call(request, "GET", `/api/discussions/${discId}`);
  const comments2 = detail2.json?.comments ?? [];
  expect(comments2.some((c) => (c.content || "").includes("e2e 评论")), "详情应含新评论").toBe(true);

  const list = await call(request, "GET", `/api/comments?target_type=discussion&target_id=${discId}`);
  expect(list.status, `评论列表应 200，实际 ${list.status}`).toBe(200);
  const lc = list.json?.comments ?? [];
  expect(lc.some((c) => (c.content || "").includes("e2e 评论")), "评论列表应含新评论").toBe(true);
  record("discussions-comments.json", { discId, comment: comment.json, detailComments: comments2.length });
});
