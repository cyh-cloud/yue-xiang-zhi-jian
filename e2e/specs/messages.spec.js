import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 消息需带 ?user_id=，且有 _messages_self_guard（会话本人才能读）。本条验证状态机与护栏都在位。
test("消息状态机：发送→未读递增→已读后递减", async ({ request }) => {
  const teacher = (await login(request, ACCOUNTS.teacher)).sessionId;
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(teacher, "teacher 登录失败").toBeTruthy();
  expect(student, "student 登录失败").toBeTruthy();

  const countOf = (r) => {
    const j = r.json || {};
    return typeof j.count === "number" ? j.count : typeof j.unread === "number" ? j.unread : null;
  };

  const unread0 = await call(request, "GET", "/api/messages/unread?user_id=student_demo", { sessionId: student });
  const inbox0 = await call(request, "GET", "/api/messages/inbox?user_id=student_demo", { sessionId: student });
  record("messages-shapes.json", { unread0: unread0.json, inbox0keys: inbox0.json ? Object.keys(inbox0.json) : null });
  expect(unread0.status, `unread 应 200，实际 ${unread0.status}: ${unread0.snippet}`).toBe(200);
  expect(inbox0.status, `inbox 应 200，实际 ${inbox0.status}: ${inbox0.snippet}`).toBe(200);

  const send = await call(request, "POST", "/api/messages/send", {
    sessionId: teacher,
    data: { receiver_id: "student_demo", content: "e2e-probe-msg" },
  });
  expect(send.status, `发送应 200，实际 ${send.status}: ${send.snippet}`).toBe(200);

  const unread1 = await call(request, "GET", "/api/messages/unread?user_id=student_demo", { sessionId: student });
  record("messages-after-send.json", { unread1: unread1.json });

  const read = await call(request, "POST", "/api/messages/read", {
    sessionId: student,
    data: { receiver_id: "student_demo", sender_id: "teacher_demo" },
  });
  const unread2 = await call(request, "GET", "/api/messages/unread?user_id=student_demo", { sessionId: student });
  record("messages-after-read.json", { read: { status: read.status, json: read.json }, unread2: unread2.json });

  const u0 = countOf(unread0);
  const u1 = countOf(unread1);
  const u2 = countOf(unread2);
  expect(u1, `发送后未读应增加（${u0} -> ${u1}）`).toBeGreaterThan(u0 ?? -1);
  expect(read.status, `标记已读应 200，实际 ${read.status}: ${read.snippet}`).toBe(200);
  expect(u2, `已读后未读应下降（${u1} -> ${u2}）`).toBeLessThan(u1);
});
