import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 通知接口按 user_id 取数但无身份护栏；消息接口已有 _messages_self_guard（2026-10-09 修）。
// 期望安全行为：跨用户 / 未登录一律 401/403。当前返回 200 即越权，测试失败=缺陷在。
test("越权：通知接口缺身份护栏（对照消息接口已修）", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(student, "student 登录失败").toBeTruthy();

  const violations = [];

  // 对照组：消息接口已加护栏，学员读他人未读应 403
  const msgCross = await call(request, "GET", "/api/messages/unread?user_id=teacher_demo", { sessionId: student });
  if (msgCross.status !== 403) violations.push(`[对照-应通过] 消息接口跨用户未返回 403（实际 ${msgCross.status}）`);

  // 受测：通知接口无护栏
  const notifListCross = await call(request, "GET", "/api/notifications?user_id=teacher_demo", { sessionId: student });
  if (notifListCross.status === 200) violations.push(`/api/notifications?user_id=teacher_demo 学员可读他人通知 (200)`);

  const notifUnreadCross = await call(request, "GET", "/api/notifications/unread?user_id=teacher_demo", { sessionId: student });
  if (notifUnreadCross.status === 200) violations.push(`/api/notifications/unread?user_id=teacher_demo 学员可读他人未读数 (200)`);

  const notifReadAnon = await call(request, "POST", "/api/notifications/read", { data: { user_id: "teacher_demo" } });
  if (notifReadAnon.status === 200) violations.push(`/api/notifications/read 未登录可标记他人已读 (200)`);

  const notifClearAnon = await call(request, "DELETE", "/api/notifications/clear?user_id=teacher_demo");
  if (notifClearAnon.status === 200) violations.push(`/api/notifications/clear 未登录可清空他人已读通知 (200)`);

  record("notifications-idor.json", {
    msgCross: msgCross.status,
    notifListCross: notifListCross.status,
    notifUnreadCross: notifUnreadCross.status,
    notifReadAnon: notifReadAnon.status,
    notifClearAnon: notifClearAnon.status,
    violations,
  });
  expect(violations, "通知接口越权:\n" + violations.join("\n")).toEqual([]);
});
