import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import {
  ROLE_ACCOUNTS,
  expectApiDenied,
  rolePortal,
  signIn,
} from "./auth-route";

const STUDENT = ROLE_ACCOUNTS.student;
const TEACHER = ROLE_ACCOUNTS.teacher;
const ENTERPRISE = ROLE_ACCOUNTS.enterprise;
const OPERATOR = ROLE_ACCOUNTS.operator;
const ADMIN = ROLE_ACCOUNTS.super_admin;

interface SessionPayload {
  session_id: string;
}

interface IdPayload {
  id: number;
}

interface CaseCreatePayload {
  result: number;
}

interface DiscussionPayload {
  discussions: Array<{ id: number; comment_count: number }>;
}

interface CommentPayload {
  comments: Array<{ id: number; content: string }>;
}

async function api<T>(
  request: APIRequestContext,
  method: "GET" | "POST" | "DELETE",
  path: string,
  sessionId?: string,
  data?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (sessionId) headers["X-Session-Id"] = sessionId;
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const response = await request.fetch(path, { method, headers, data });
  expect(
    response.ok(),
    `${method} ${path} failed with ${response.status()}: ${await response.text()}`,
  ).toBeTruthy();
  return (await response.json()) as T;
}

async function login(
  request: APIRequestContext,
  account: { username: string; password: string },
): Promise<SessionPayload> {
  return api<SessionPayload>(request, "POST", "/api/auth/login", undefined, account);
}

async function resetBrowserSession(page: Page): Promise<void> {
  await page.goto("/login");
  await page.evaluate(() => localStorage.clear());
  await page.reload();
}

test("review actions filter by type/status and update public and owner state", async ({
  page,
  request,
}) => {
  const marker = `T23-REVIEW-${Date.now()}`;
  const [teacher, enterprise, operator] = await Promise.all([
    login(request, TEACHER),
    login(request, ENTERPRISE),
    login(request, OPERATOR),
  ]);

  const course = await api<IdPayload>(
    request,
    "POST",
    "/api/teacher/courses",
    teacher.session_id,
    {
      title: `${marker} 课程`,
      description: "用于验证驳回理由。",
      category: "综合",
    },
  );
  const job = await api<IdPayload>(
    request,
    "POST",
    "/api/enterprise/jobs",
    enterprise.session_id,
    {
      title: `${marker} 岗位`,
      salary: "5K-8K",
      location: "广州",
      category: "农业技术",
      description: "用于验证审核通过后的公开可见性。",
      requirements: ["会沟通"],
    },
  );
  const successCase = await api<CaseCreatePayload>(
    request,
    "POST",
    "/api/operator/cases",
    operator.session_id,
    {
      title: `${marker} 案例`,
      region: "茂名",
      description: "用于验证撤销审核后的公开可见性。",
    },
  );
  const modelResponse = await request.post("/api/teacher/models-3d", {
    headers: { "X-Session-Id": teacher.session_id },
    multipart: {
      file: {
        name: `${marker}.glb`,
        mimeType: "model/gltf-binary",
        buffer: Buffer.from("glTF T23 review"),
      },
      title: `${marker} 模型`,
      description: "用于验证模型驳回理由。",
      craft_type: "embroidery",
    },
  });
  expect(modelResponse.ok(), await modelResponse.text()).toBeTruthy();
  const model = (await modelResponse.json()) as IdPayload;

  try {
    await signIn(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin/reviews");

    const typeFilter = page.getByLabel("内容类型");
    await typeFilter.selectOption("course");
    const courseRow = page
      .getByTestId("admin-review-row")
      .filter({ hasText: `${marker} 课程` });
    await expect(courseRow).toBeVisible();
    await courseRow.getByRole("button", { name: "驳回" }).click();
    const rejectDialog = page.getByTestId("admin-review-reject-dialog");
    await rejectDialog.getByLabel("驳回理由").fill("课程说明缺少实训步骤");
    await rejectDialog.getByRole("button", { name: "确认驳回" }).click();
    await expect(page.getByTestId("admin-reviews-feedback")).toContainText(
      "已驳回",
    );
    await page.getByTestId("admin-review-status-rejected").click();
    await expect(
      page.getByTestId("admin-review-row").filter({ hasText: `${marker} 课程` }),
    ).toContainText("课程说明缺少实训步骤");

    await page.getByTestId("admin-review-status-pending").click();
    await typeFilter.selectOption("job");
    const jobRow = page
      .getByTestId("admin-review-row")
      .filter({ hasText: `${marker} 岗位` });
    await jobRow.getByRole("button", { name: "通过" }).click();
    await expect(page.getByTestId("admin-reviews-feedback")).toContainText(
      "已审核通过",
    );
    const publicJobs = await api<{ jobs: Array<{ id: number }> }>(
      request,
      "GET",
      `/api/employment/jobs?keyword=${encodeURIComponent(marker)}`,
    );
    expect(publicJobs.jobs.some((entry) => entry.id === job.id)).toBe(true);

    await typeFilter.selectOption("success_case");
    const caseRow = page
      .getByTestId("admin-review-row")
      .filter({ hasText: `${marker} 案例` });
    await caseRow.getByRole("button", { name: "通过" }).click();
    await expect(page.getByTestId("admin-reviews-feedback")).toContainText(
      "已审核通过",
    );
    const publicCases = await api<{ cases: Array<{ id: number }> }>(
      request,
      "GET",
      "/api/resources/cases",
    );
    expect(publicCases.cases.some((entry) => entry.id === successCase.result)).toBe(
      true,
    );
    await page.getByTestId("admin-review-status-approved").click();
    const approvedCaseRow = page
      .getByTestId("admin-review-row")
      .filter({ hasText: `${marker} 案例` });
    await approvedCaseRow.getByRole("button", { name: "撤销审核" }).click();
    await page
      .getByTestId("admin-review-confirm-dialog")
      .getByRole("button", { name: "确认撤销" })
      .click();
    await expect(page.getByTestId("admin-reviews-feedback")).toContainText(
      "已撤销",
    );
    const casesAfterRevoke = await api<{ cases: Array<{ id: number }> }>(
      request,
      "GET",
      "/api/resources/cases",
    );
    expect(
      casesAfterRevoke.cases.some((entry) => entry.id === successCase.result),
    ).toBe(false);

    await page.getByTestId("admin-review-status-pending").click();
    await typeFilter.selectOption("model_3d");
    const modelRow = page
      .getByTestId("admin-review-row")
      .filter({ hasText: `${marker} 模型` });
    await modelRow.getByRole("button", { name: "驳回" }).click();
    await page
      .getByTestId("admin-review-reject-dialog")
      .getByLabel("驳回理由")
      .fill("模型缺少正面展示");
    await page
      .getByTestId("admin-review-reject-dialog")
      .getByRole("button", { name: "确认驳回" })
      .click();

    await resetBrowserSession(page);
    await signIn(page, TEACHER.username, TEACHER.password);
    await page.goto("/teacher/models");
    const ownerRow = page
      .getByTestId("teacher-model-row")
      .filter({ hasText: `${marker} 模型` });
    await expect(ownerRow).toContainText("已驳回");
    await expect(ownerRow).toContainText("驳回理由：模型缺少正面展示");
  } finally {
    await api(
      request,
      "DELETE",
      `/api/teacher/courses/${course.id}`,
      teacher.session_id,
    ).catch(() => undefined);
    await api(
      request,
      "DELETE",
      `/api/enterprise/jobs/${job.id}`,
      enterprise.session_id,
    ).catch(() => undefined);
    await api(
      request,
      "DELETE",
      `/api/operator/cases/${successCase.result}`,
      operator.session_id,
    ).catch(() => undefined);
    await api(
      request,
      "DELETE",
      `/api/teacher/models-3d/${model.id}`,
      teacher.session_id,
    ).catch(() => undefined);
  }
});

test("system announcements enter and leave the shared message center", async ({
  page,
  request,
}) => {
  const marker = `T23-ANN-${Date.now()}`;
  const title = `${marker} 系统公告`;
  const admin = await login(request, ADMIN);

  try {
    await signIn(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin/announcements");
    await page.getByLabel("公告标题").fill(title);
    await page.getByLabel("公告内容").fill(`${marker} 公告正文`);
    await page.getByLabel("置顶公告").check();
    await page.getByRole("button", { name: "发布公告" }).click();
    await expect(page.getByTestId("admin-announcements-feedback")).toContainText(
      "发布成功",
    );
    const announcementRow = page
      .getByTestId("admin-announcement-row")
      .filter({ hasText: title });
    await expect(announcementRow).toContainText("置顶");

    await resetBrowserSession(page);
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.getByTestId("message-center-trigger").click();
    await expect(
      page
        .getByTestId("message-center-item")
        .filter({ hasText: title }),
    ).toBeVisible();

    await resetBrowserSession(page);
    await signIn(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin/announcements");
    await page
      .getByTestId("admin-announcement-row")
      .filter({ hasText: title })
      .getByRole("button", { name: "删除" })
      .click();
    await page
      .getByTestId("admin-announcement-delete-dialog")
      .getByRole("button", { name: "确认删除" })
      .click();
    await expect(page.getByTestId("admin-announcements-feedback")).toContainText(
      "已删除",
    );
    await expect(
      page.getByTestId("admin-announcement-row").filter({ hasText: title }),
    ).toHaveCount(0);
    const publicAnnouncements = await api<{
      announcements: Array<{ title: string }>;
    }>(request, "GET", "/api/system-announcements");
    expect(
      publicAnnouncements.announcements.some((item) => item.title === title),
    ).toBe(false);

    await resetBrowserSession(page);
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.getByTestId("message-center-trigger").click();
    await expect(
      page
        .getByTestId("message-center-item")
        .filter({ hasText: title }),
    ).toHaveCount(0);
  } finally {
    const announcements = await api<{
      announcements: Array<{ id: number; title: string }>;
    }>(request, "GET", "/api/admin/system-announcements", admin.session_id);
    const created = announcements.announcements.find(
      (item) => item.title === title,
    );
    if (created) {
      await api(
        request,
        "DELETE",
        `/api/admin/system-announcements/${created.id}`,
        admin.session_id,
      ).catch(() => undefined);
    }
  }
});

test("content moderation removes discussions/comments and denies other roles", async ({
  page,
  request,
}) => {
  const marker = `T23-CONTENT-${Date.now()}`;
  const [student, admin] = await Promise.all([
    login(request, STUDENT),
    login(request, ADMIN),
  ]);
  const discussion = await api<IdPayload>(
    request,
    "POST",
    "/api/discussions",
    student.session_id,
    {
      title: `${marker} 讨论帖`,
      content: "用于验证内容监管。",
      category: "general",
    },
  );
  const comment = await api<IdPayload>(
    request,
    "POST",
    "/api/comments",
    student.session_id,
    {
      target_type: "discussion",
      target_id: discussion.id,
      content: `${marker} 违规评论`,
    },
  );

  try {
    await signIn(page, ADMIN.username, ADMIN.password);
    await page.goto("/admin/content");
    const commentRow = page
      .getByTestId("admin-content-comment-row")
      .filter({ hasText: `${marker} 违规评论` });
    await expect(commentRow).toContainText(`${marker} 讨论帖`);
    await commentRow.getByRole("button", { name: "删除评论" }).click();
    await page
      .getByTestId("admin-content-delete-dialog")
      .getByRole("button", { name: "确认删除" })
      .click();
    await expect(page.getByTestId("admin-content-feedback")).toContainText(
      "已删除违规评论",
    );
    await expect(commentRow).toHaveCount(0);

    const comments = await api<CommentPayload>(
      request,
      "GET",
      `/api/comments?target_type=discussion&target_id=${discussion.id}`,
    );
    expect(comments.comments.some((item) => item.id === comment.id)).toBe(false);
    const discussionDetail = await api<{
      discussion: { comment_count: number };
    }>(request, "GET", `/api/discussions/${discussion.id}`);
    expect(discussionDetail.discussion.comment_count).toBe(0);

    const discussionRow = page
      .getByTestId("admin-content-discussion-row")
      .filter({ hasText: `${marker} 讨论帖` });
    await discussionRow.getByRole("button", { name: "删除帖子" }).click();
    await page
      .getByTestId("admin-content-delete-dialog")
      .getByRole("button", { name: "确认删除" })
      .click();
    await expect(page.getByTestId("admin-content-feedback")).toContainText(
      "已删除违规帖子",
    );
    const discussions = await api<DiscussionPayload>(
      request,
      "GET",
      "/api/discussions",
    );
    expect(
      discussions.discussions.some((item) => item.id === discussion.id),
    ).toBe(false);

    for (const role of [
      "student",
      "teacher",
      "enterprise",
      "government",
      "operator",
    ] as const) {
      await expectApiDenied(
        request,
        ROLE_ACCOUNTS[role],
        rolePortal("super_admin").api,
      );
    }
    await resetBrowserSession(page);
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/admin/content");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
  } finally {
    await api(
      request,
      "DELETE",
      `/api/admin/comments/${comment.id}`,
      admin.session_id,
    ).catch(() => undefined);
    await api(
      request,
      "DELETE",
      `/api/admin/discussions/${discussion.id}`,
      admin.session_id,
    ).catch(() => undefined);
  }
});

test("moderation pages expose failure and empty states", async ({ page }) => {
  await signIn(page, ADMIN.username, ADMIN.password);

  await page.route("**/api/admin/reviews**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ success: false, message: "review unavailable" }),
    }),
  );
  await page.goto("/admin/reviews");
  await expect(page.getByTestId("admin-reviews-error")).toBeVisible();
  await expect(page.getByTestId("admin-reviews-error")).toContainText(
    "review unavailable",
  );
  await page.unroute("**/api/admin/reviews**");

  await page.route("**/api/admin/content", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        discussions: [],
        comments: [],
        total: 0,
      }),
    }),
  );
  await page.goto("/admin/content");
  await expect(page.getByTestId("admin-content-empty")).toBeVisible();
});
