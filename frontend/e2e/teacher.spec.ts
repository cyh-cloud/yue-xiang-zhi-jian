import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { signIn } from "./auth-route";

interface SessionPayload {
  session_id: string;
  user: { id: string; name: string; role: string };
  capabilities: string[];
}

interface TeacherTraining {
  id: number;
  student_id: string;
  student_name: string;
  kind: string;
  product: string;
  script: string;
  score: number | null;
  feedback: string;
  status: string;
  status_label: string;
}

const TEACHER = { username: "teacher_demo", password: "123456" } as const;
const STUDENT = { username: "student_demo", password: "123456" } as const;
const OTHER_ROLES = {
  student: {
    account: STUDENT,
    landing: /\/agriculture\/?$/,
  },
  enterprise: {
    account: { username: "enterprise_demo", password: "123456" },
    landing: /\/enterprise\/dashboard$/,
  },
  government: {
    account: { username: "gov_demo", password: "123456" },
    landing: /\/government\/dashboard$/,
  },
  operator: {
    account: { username: "operator_demo", password: "123456" },
    landing: /\/operator\/overview$/,
  },
} as const;

async function login(
  request: APIRequestContext,
  account: { username: string; password: string },
): Promise<SessionPayload> {
  const response = await request.post("/api/auth/login", { data: account });
  expect(response.status()).toBe(200);
  return (await response.json()) as SessionPayload;
}

function marker(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function studentRow(page: Page, studentId: string) {
  return page.locator(
    `[data-testid="teacher-student-row"][data-student-id="${studentId}"]`,
  );
}

async function openStudentEditor(page: Page, studentId: string) {
  const row = await studentRow(page, studentId);
  await row.getByTestId("teacher-student-edit").click();
  const editor = page.getByTestId("teacher-student-editor");
  await expect(editor).toBeVisible();
  return editor;
}

test.describe("teacher dashboard and roster", () => {
  test("real statistics, search, add, detail, edit and delete work together", async ({
    page,
  }) => {
    const name = marker("E2E教师学员");
    const updatedName = `${name}-改名`;

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await expect(page.getByTestId("teacher-dashboard")).toBeVisible();
    await expect(page.getByTestId("teacher-stat-total")).not.toHaveText("-");
    await expect(page.getByTestId("teacher-stat-certificates")).not.toHaveText(
      "-",
    );

    const search = page.getByLabel("搜索学员");
    await search.fill("STU001");
    await expect(
      page.locator(
        '[data-testid="teacher-student-row"][data-student-id="STU001"]',
      ),
    ).toBeVisible();
    await search.fill("");

    await page.getByRole("button", { name: "添加学员" }).click();
    const add = page.getByTestId("teacher-student-editor");
    await expect(add).toBeVisible();
    await add.getByLabel("学员姓名").fill(name);
    await add.getByLabel("学习方向").selectOption("电商运营");
    await add.getByLabel("平台账号").selectOption("none");
    await add.getByRole("button", { name: "确认添加" }).click();
    await expect(page.getByTestId("teacher-dashboard-feedback")).toContainText(
      "添加成功",
    );

    const created = page
      .locator('[data-testid="teacher-student-row"]')
      .filter({ hasText: name });
    await expect(created).toContainText("未关联");
    const studentId = await created.getAttribute("data-student-id");
    expect(studentId).toBeTruthy();

    await created.getByTestId("teacher-student-view").click();
    const detail = page.getByTestId("teacher-student-detail");
    await expect(detail).toContainText(name);
    await expect(detail).toContainText("未关联");
    await detail
      .getByRole("button", { name: "关闭", exact: true })
      .last()
      .click();

    const editor = await openStudentEditor(page, studentId!);
    await editor.getByLabel("学员姓名").fill(updatedName);
    await editor.getByLabel("学习方向").selectOption("荔枝种植");
    await editor.getByRole("button", { name: "保存修改" }).click();
    await expect(page.getByTestId("teacher-dashboard-feedback")).toContainText(
      "已保存",
    );
    await expect(
      page
        .locator('[data-testid="teacher-student-row"]')
        .filter({ hasText: updatedName }),
    ).toBeVisible();

    const updatedRow = await studentRow(page, studentId!);
    await updatedRow.getByTestId("teacher-student-delete").click();
    const confirm = page.getByTestId("teacher-confirm-delete");
    await expect(confirm).toContainText("仅删除名册记录");
    await confirm.getByRole("button", { name: "确认删除" }).click();
    await expect(updatedRow).toHaveCount(0);
  });

  test("a roster row can link to a student account and unlink again", async ({
    page,
    request,
  }) => {
    const username = marker("e2e_teacher_link");
    const name = marker("E2E绑定学员");
    const registration = await request.post("/api/auth/register", {
      data: {
        username,
        password: "123456",
        name,
        role: "student",
      },
    });
    expect(registration.status()).toBe(200);

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.getByRole("button", { name: "添加学员" }).click();
    const editor = page.getByTestId("teacher-student-editor");
    await editor.getByLabel("学员姓名").fill(`${name}-名册`);
    await editor.getByLabel("平台账号").selectOption("link");
    await editor.getByLabel("选择要关联的账号").selectOption(username);
    await editor.getByRole("button", { name: "确认添加" }).click();

    const row = page
      .locator('[data-testid="teacher-student-row"]')
      .filter({ hasText: `${name}-名册` });
    await expect(row).toContainText("已关联");
    await expect(row).toContainText(username);

    const studentId = await row.getAttribute("data-student-id");
    const edit = await openStudentEditor(page, studentId!);
    await edit
      .getByLabel("平台账号")
      .selectOption({ label: "（改为不关联账号）" });
    await edit.getByRole("button", { name: "保存修改" }).click();
    await expect(page.getByTestId("teacher-dashboard-feedback")).toContainText(
      "已解除账号关联",
    );
    await expect(row).toContainText("未关联");
  });

  test("degraded AI reports are visibly marked as fallback content", async ({
    page,
  }) => {
    await page.route("**/api/teacher/reports/generate", (route) =>
      route.fulfill({
        json: {
          success: true,
          report: {
            title: "AI 教学报告",
            generated_at: "2026-10-20T10:00:00",
            content: "## 生成失败\n\nAI 服务暂时不可用，请稍后重试。",
            degraded: true,
            degraded_reason: "ai_unavailable",
          },
        },
      }),
    );

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.getByLabel("分析需求").fill("分析风险学员");
    await page.getByRole("button", { name: "生成报告" }).click();

    await expect(page.getByTestId("teacher-report-degraded")).toContainText(
      "降级结果",
    );
    await expect(page.getByTestId("teacher-report-degraded")).toContainText(
      "AI 服务暂时不可用",
    );
    await expect(page.getByTestId("teacher-report")).toContainText(
      "生成失败",
    );
  });
});

test.describe("teacher announcements", () => {
  test("publish reaches students and delete removes it", async ({
    page,
    request,
  }) => {
    const title = marker("E2E教师公告");
    const content = `${title}-正文`;

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/announcements");
    await expect(
      page.getByRole("heading", { level: 1, name: "通知公告" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "发布通知" }).click();
    const editor = page.getByTestId("teacher-announcement-editor");
    await editor.getByLabel("标题").fill(title);
    await editor.getByLabel("分类").selectOption("通知");
    await editor.getByLabel("内容").fill(content);
    await editor.getByLabel("置顶显示").check();
    await editor.getByRole("button", { name: "发布" }).click();

    const card = page
      .locator('[data-testid="teacher-announcement-card"]')
      .filter({ hasText: title });
    await expect(card).toBeVisible();
    await expect(card).toContainText("置顶");

    const student = await login(request, STUDENT);
    const studentAnnouncements = await request.get("/api/student/announcements", {
      headers: { "X-Session-Id": student.session_id },
    });
    expect(studentAnnouncements.status()).toBe(200);
    const announcements = (await studentAnnouncements.json()) as {
      announcements: Array<{ id: number; title: string }>;
    };
    expect(announcements.announcements.some((item) => item.title === title)).toBe(
      true,
    );

    const notifications = await request.get(
      `/api/notifications?user_id=${STUDENT.username}&limit=200`,
      { headers: { "X-Session-Id": student.session_id } },
    );
    expect(notifications.status()).toBe(200);
    const notificationPayload = (await notifications.json()) as {
      notifications: Array<{ type: string; content: string }>;
    };
    expect(
      notificationPayload.notifications.some(
        (item) => item.type === "announcement" && item.content === title,
      ),
    ).toBe(true);

    await card.getByTestId("teacher-announcement-delete").click();
    const confirm = page.getByTestId("teacher-confirm-delete");
    await confirm.getByRole("button", { name: "确认删除" }).click();
    await expect(card).toHaveCount(0);
  });
});

test.describe("teacher analytics", () => {
  test("progress and direction data render from the real API", async ({ page }) => {
    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/analytics");
    await expect(page.getByTestId("teacher-analytics")).toBeVisible();
    await expect(page.getByTestId("teacher-analytics")).toContainText(
      "证书真实完成度",
    );
    await expect(page.getByTestId("teacher-progress-chart")).toBeVisible();
    await expect(page.getByTestId("teacher-direction-chart")).toBeVisible();
    await expect(page.getByTestId("teacher-direction-detail")).toContainText(
      "平均完成度",
    );
  });

  test("an empty roster has an explicit empty state", async ({ page }) => {
    await page.route("**/api/teacher/analytics", (route) =>
      route.fulfill({
        status: 200,
        json: {
          success: true,
          analytics: {
            basis: "certificates",
            basis_label: "证书真实完成度（学员名下证书进度的平均值）",
            roster_count: 0,
            no_cert_count: 0,
            progress_distribution: [],
            direction_distribution: [],
            direction_progress: [],
          },
        },
      }),
    );
    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/analytics");
    await expect(page.getByTestId("teacher-analytics-empty")).toContainText(
      "暂无学员数据",
    );
  });
});

test.describe("teacher training review", () => {
  test("teacher sees the submitted work, grades it and reloads the result", async ({
    page,
    request,
  }) => {
    const script = marker("E2E教师批改作品");
    const student = await login(request, STUDENT);
    const submitted = await request.post("/api/ecommerce/live/submit", {
      headers: { "X-Session-Id": student.session_id },
      data: {
        product: "龙眼",
        script,
        feedback: { overall_score: 88 },
        report: { coverage: 92, speed_cpm: 120, rubric_hit: 2, rubric_total: 3 },
      },
    });
    expect(submitted.status()).toBe(200);

    const teacher = await login(request, TEACHER);
    const trainingsResponse = await request.get("/api/teacher/trainings", {
      headers: { "X-Session-Id": teacher.session_id },
    });
    expect(trainingsResponse.status()).toBe(200);
    const payload = (await trainingsResponse.json()) as {
      trainings: TeacherTraining[];
    };
    const training = payload.trainings.find((item) => item.script === script);
    expect(training).toBeTruthy();

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/trainings");
    await expect(
      page.getByRole("heading", { level: 1, name: "实训提交" }),
    ).toBeVisible();
    const row = page.locator(
      `[data-testid="teacher-training-row"][data-submission-id="${training!.id}"]`,
    );
    await expect(row).toContainText("龙眼");
    await row.getByTestId("teacher-training-open").click();

    const dialog = page.getByTestId("teacher-grade-dialog");
    await expect(dialog).toContainText(script);
    await dialog.getByLabel("我的评分（0-100）").fill("93");
    await dialog
      .getByLabel("评语（可留空，学员会在消息中心看到）")
      .fill("卖点清楚，互动自然。");
    await dialog.getByRole("button", { name: "确认批改" }).click();
    await expect(page.getByTestId("teacher-trainings-feedback")).toContainText(
      "批改成功",
    );
    await expect(row).toContainText("93");
    await expect(row).toContainText("卖点清楚，互动自然。");
  });

  test("customer-service transcripts are readable before grading", async ({
    page,
    request,
  }) => {
    const product = `客服-${Date.now()}`;
    const customerText = "请问这批荔枝怎么保存？";
    const studentText = "建议冷藏保存，并在三天内食用。";
    const student = await login(request, STUDENT);
    const submitted = await request.post("/api/ecommerce/cs/submit", {
      headers: { "X-Session-Id": student.session_id },
      data: {
        product,
        transcript: [
          { role: "customer", content: customerText },
          { role: "user", content: studentText },
        ],
      },
    });
    expect(submitted.status()).toBe(200);

    const teacher = await login(request, TEACHER);
    const trainingsResponse = await request.get("/api/teacher/trainings", {
      headers: { "X-Session-Id": teacher.session_id },
    });
    const payload = (await trainingsResponse.json()) as {
      trainings: TeacherTraining[];
    };
    const training = payload.trainings.find((item) => item.product === product);
    expect(training).toBeTruthy();

    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/trainings");
    const row = page.locator(
      `[data-testid="teacher-training-row"][data-submission-id="${training!.id}"]`,
    );
    await row.getByTestId("teacher-training-open").click();
    const dialog = page.getByTestId("teacher-grade-dialog");
    await expect(dialog).toContainText(customerText);
    await expect(dialog).toContainText(studentText);
  });
});

test.describe("teacher role denial", () => {
  for (const [role, config] of Object.entries(OTHER_ROLES)) {
    test(`${role} cannot enter the teacher portal or teacher APIs`, async ({
      page,
      request,
    }) => {
      const session = await login(request, config.account);
      const denied = await request.get("/api/teacher/students", {
        headers: { "X-Session-Id": session.session_id },
      });
      expect(denied.status()).toBe(403);

      await signIn(page, config.account.username, config.account.password);
      await expect(page).toHaveURL(config.landing);
      await page.goto("/teacher/dashboard");
      await expect(page).toHaveURL(config.landing);
    });
  }
});
