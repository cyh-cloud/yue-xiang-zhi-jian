import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// protect: public=谁都 200; self=未登录应 401; teacher/admin/gov=学员与未登录应被拒; observe=只记录不断言
const PROBES = [
  { path: "/api/health", protect: "public" },
  { path: "/api/home/stats", protect: "public" },
  { path: "/api/agriculture/products", protect: "public" },
  { path: "/api/crafts/list", protect: "public" },
  { path: "/api/resources/dialects", protect: "public" },
  { path: "/api/resources/cases", protect: "public" },
  { path: "/api/resources/policies", protect: "public" },
  { path: "/api/teacher/public-courses", protect: "public" },
  { path: "/api/agriculture/pest-knowledge", protect: "public" },

  { path: "/api/user/profile", protect: "self" },
  { path: "/api/messages/inbox", protect: "self" },
  { path: "/api/notifications", protect: "observe" },
  { path: "/api/notifications/unread", protect: "observe" },
  { path: "/api/messages/unread", protect: "self" },

  { path: "/api/teacher/dashboard", protect: "teacher" },
  { path: "/api/teacher/students", protect: "teacher" },
  { path: "/api/teacher/analytics", protect: "teacher" },
  { path: "/api/teacher/courses", protect: "teacher" },
  { path: "/api/teacher/trainings", protect: "teacher" },

  { path: "/api/admin/dashboard", protect: "admin" },
  { path: "/api/admin/users", protect: "admin" },
  { path: "/api/admin/reviews", protect: "admin" },

  { path: "/api/government/dashboard", protect: "gov" },

  { path: "/api/comments", protect: "observe" },
  { path: "/api/discussions", protect: "observe" },
  { path: "/api/system-announcements", protect: "observe" },
  { path: "/api/teacher/announcements", protect: "observe" },
  { path: "/api/government/policies", protect: "observe" },
  { path: "/api/agriculture/subscriptions", protect: "observe" },
  { path: "/api/ecommerce/live/records", protect: "observe" },
];

test("越权矩阵：各端点在不同登录态下的状态", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  const teacher = (await login(request, ACCOUNTS.teacher)).sessionId;
  const admin = (await login(request, ACCOUNTS.admin)).sessionId;
  const gov = (await login(request, ACCOUNTS.gov)).sessionId;
  for (const [name, sid] of Object.entries({ student, teacher, admin, gov })) {
    expect(sid, `${name} 登录失败`).toBeTruthy();
  }

  const matrix = [];
  const violations = [];
  const readOk = (r) => r.status === 200 && r.json && r.json.success !== false;

  for (const p of PROBES) {
    const ctx = {
      none: await call(request, "GET", p.path),
      student: await call(request, "GET", p.path, { sessionId: student }),
      teacher: await call(request, "GET", p.path, { sessionId: teacher }),
      admin: await call(request, "GET", p.path, { sessionId: admin }),
      gov: await call(request, "GET", p.path, { sessionId: gov }),
    };
    matrix.push({
      path: p.path,
      protect: p.protect,
      status: {
        none: ctx.none.status,
        student: ctx.student.status,
        teacher: ctx.teacher.status,
        admin: ctx.admin.status,
        gov: ctx.gov.status,
      },
    });

    if (p.protect === "teacher" || p.protect === "admin" || p.protect === "gov") {
      if (readOk(ctx.student)) violations.push(`${p.path}: 学员未授权却读到数据 (200)`);
      if (readOk(ctx.none)) violations.push(`${p.path}: 未登录却读到数据 (200)`);
    }
    if (p.protect === "self") {
      if (readOk(ctx.none)) violations.push(`${p.path}: 未登录却读到个人数据 (200)`);
    }
    if (p.protect === "public" && ctx.none.status !== 200) {
      violations.push(`${p.path}: 公共端点未返回 200 (实际 ${ctx.none.status})`);
    }
  }

  record("ownership-matrix.json", { generatedAt: new Date().toISOString(), matrix, violations });
  expect(violations, "越权/契约违规:\n" + violations.join("\n")).toEqual([]);
});
