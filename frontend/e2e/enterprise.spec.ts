import {
  expect,
  test,
  type APIRequestContext,
} from "@playwright/test";

import { signIn } from "./auth-route";

const ENTERPRISE = { username: "enterprise_demo", password: "123456" } as const;
const ADMIN = { username: "admin_demo", password: "admin123" } as const;
const STUDENT = { username: "student_demo", password: "123456" } as const;

interface SessionPayload {
  session_id: string;
}

interface JobPayload {
  id: number;
}

interface ReviewPayload {
  reviews: Array<{
    id: number;
    content_id: number;
    content_type: string;
  }>;
}

async function api<T>(
  request: APIRequestContext,
  method: "GET" | "POST" | "PUT" | "DELETE",
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

async function findReview(
  request: APIRequestContext,
  adminSession: string,
  jobId: number,
): Promise<number> {
  const pending = await api<ReviewPayload>(
    request,
    "GET",
    "/api/admin/reviews?content_type=job&status=pending&sort=created",
    adminSession,
  );
  const review = pending.reviews.find(
    (item) => item.content_type === "job" && item.content_id === jobId,
  );
  expect(review, "新岗位应进入待审核队列").toBeTruthy();
  return review!.id;
}

test.describe("enterprise portal", () => {
  test("dashboard renders the real enterprise counts", async ({
    page,
    request,
  }) => {
    await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
    await page.route("https://unpkg.com/**", (route) => route.abort());

    const login = await request.post("/api/auth/login", {
      data: ENTERPRISE,
    });
    expect(login.ok()).toBe(true);
    const session = (await login.json()) as { session_id: string };
    const statsResponse = await request.get("/api/enterprise/stats", {
      headers: { "X-Session-Id": session.session_id },
    });
    expect(statsResponse.ok()).toBe(true);
    const stats = (await statsResponse.json()) as {
      stats: {
        total_jobs: number;
        pending_jobs: number;
        total_applications: number;
      };
    };
    const applicationsResponse = await request.get(
      "/api/enterprise/applications",
      { headers: { "X-Session-Id": session.session_id } },
    );
    expect(applicationsResponse.ok()).toBe(true);
    const applications = (await applicationsResponse.json()) as {
      applications: Array<{ status: string }>;
    };
    const statusCounts = applications.applications.reduce(
      (counts, application) => {
        counts[application.status] = (counts[application.status] || 0) + 1;
        return counts;
      },
      {} as Record<string, number>,
    );

    await signIn(page, ENTERPRISE.username, ENTERPRISE.password);
    await expect(page).toHaveURL(/\/enterprise\/dashboard$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "企业中心" }),
    ).toBeVisible();
    await expect(page.getByTestId("enterprise-stat-approved")).toContainText(
      String(stats.stats.total_jobs),
    );
    await expect(page.getByTestId("enterprise-stat-pending")).toContainText(
      String(stats.stats.pending_jobs),
    );
    await expect(page.getByTestId("enterprise-stat-applications")).toContainText(
      String(stats.stats.total_applications),
    );
    for (const status of ["pending", "interview", "approved", "rejected"]) {
      await expect(
        page.getByTestId(`enterprise-application-status-${status}`),
      ).toContainText(String(statusCounts[status] || 0));
    }
  });

  test("jobs publish, edit, delete and show the real review gate", async ({
    page,
    request,
  }) => {
    await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
    await page.route("https://unpkg.com/**", (route) => route.abort());
    const marker = `ENT-JOB-${Date.now()}`;
    const admin = await login(request, ADMIN);

    await signIn(page, ENTERPRISE.username, ENTERPRISE.password);
    await page.getByRole("link", { name: "职位管理" }).click();
    await expect(page).toHaveURL(/\/enterprise\/jobs$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "职位管理" }),
    ).toBeVisible();

    await page.getByLabel("职位标题").fill(`${marker} 原岗位`);
    await page.getByLabel("薪资").fill("5K-8K");
    await page.getByLabel("工作地点").fill("茂名");
    await page.getByLabel("职位类别").fill("电商运营");
    await page.getByLabel("职位描述").fill("负责农产品线上运营。");
    await page.getByLabel("任职要求（每行一条）").fill("熟悉直播运营\n会基础数据分析");
    await page.getByRole("button", { name: "发布职位" }).click();
    await expect(page.getByTestId("enterprise-jobs-feedback")).toContainText(
      "职位发布成功，等待审核",
    );

    const row = page
      .getByTestId("enterprise-job-row")
      .filter({ hasText: `${marker} 原岗位` });
    await expect(row).toContainText("待审核");
    const jobId = Number(await row.getAttribute("data-job-id"));
    expect(jobId).toBeTruthy();

    const reviewId = await findReview(request, admin.session_id, jobId);
    await api(
      request,
      "POST",
      `/api/admin/reviews/${reviewId}/approve`,
      admin.session_id,
      {},
    );
    await page.getByRole("button", { name: "刷新职位" }).click();
    await expect(row).toContainText("已通过");

    const publicJobs = await api<{
      jobs: Array<{ id: number; title: string }>;
    }>(
      request,
      "GET",
      `/api/employment/jobs?keyword=${encodeURIComponent(marker)}`,
    );
    expect(publicJobs.jobs.some((job) => job.id === jobId)).toBe(true);

    await row.getByRole("button", { name: "编辑" }).click();
    await page.getByLabel("职位标题").fill(`${marker} 修改岗位`);
    await page.getByRole("button", { name: "保存并重新审核" }).click();
    await expect(page.getByTestId("enterprise-jobs-feedback")).toContainText(
      "需重新审核",
    );
    const editedRow = page
      .getByTestId("enterprise-job-row")
      .filter({ hasText: `${marker} 修改岗位` });
    await expect(editedRow).toContainText("待审核");

    const hiddenDetail = await request.get(`/api/employment/jobs/${jobId}`);
    expect(hiddenDetail.status()).toBe(404);

    await editedRow.getByRole("button", { name: "删除" }).click();
    const confirm = page.getByTestId("enterprise-job-delete-confirm");
    await expect(confirm).toContainText(`${marker} 修改岗位`);
    await confirm.getByRole("button", { name: "确认删除" }).click();
    await expect(page.getByTestId("enterprise-jobs-feedback")).toContainText(
      "删除成功",
    );
    await expect(editedRow).toHaveCount(0);

    await page.getByLabel("职位标题").fill(`${marker} 驳回岗位`);
    await page.getByLabel("薪资").fill("面议");
    await page.getByLabel("工作地点").fill("广州");
    await page.getByLabel("职位类别").fill("农业技术");
    await page.getByLabel("职位描述").fill("用于验证驳回理由。");
    await page.getByRole("button", { name: "发布职位" }).click();
    const rejectedRow = page
      .getByTestId("enterprise-job-row")
      .filter({ hasText: `${marker} 驳回岗位` });
    await expect(rejectedRow).toContainText("待审核");
    const rejectedJobId = Number(await rejectedRow.getAttribute("data-job-id"));
    const rejectedReviewId = await findReview(
      request,
      admin.session_id,
      rejectedJobId,
    );
    await api(
      request,
      "POST",
      `/api/admin/reviews/${rejectedReviewId}/reject`,
      admin.session_id,
      { comment: "岗位描述缺少工作职责" },
    );
    await page.getByRole("button", { name: "刷新职位" }).click();
    await expect(rejectedRow).toContainText("已驳回");
    await expect(rejectedRow).toContainText("驳回理由：岗位描述缺少工作职责");
  });

  test("applications show resumes and status changes reach the shared message center", async ({
    page,
    request,
  }) => {
    await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
    await page.route("https://unpkg.com/**", (route) => route.abort());
    const marker = `ENT-APP-${Date.now()}`;
    const jobTitle = `${marker} 投递岗位`;
    const [enterprise, admin, student] = await Promise.all([
      login(request, ENTERPRISE),
      login(request, ADMIN),
      login(request, STUDENT),
    ]);

    const job = await api<JobPayload>(
      request,
      "POST",
      "/api/enterprise/jobs",
      enterprise.session_id,
      {
        title: jobTitle,
        salary: "5K-8K",
        requirements: ["会沟通", "熟悉农产品"],
        description: "处理农产品电商运营与客户沟通。",
        location: "茂名",
        category: "电商运营",
      },
    );
    const reviewId = await findReview(request, admin.session_id, job.id);
    await api(
      request,
      "POST",
      `/api/admin/reviews/${reviewId}/approve`,
      admin.session_id,
      {},
    );
    await api(
      request,
      "PUT",
      "/api/employment/resume/student_demo",
      student.session_id,
      {
        title: `${marker} 简历岗位`,
        education: "大专",
        work_years: "2年",
        skills: "直播运营、客户沟通",
        self_eval: "熟悉农村电商与本地农产品。",
      },
    );
    await api(
      request,
      "POST",
      "/api/employment/apply",
      student.session_id,
      { user_id: STUDENT.username, job_id: job.id },
    );

    await signIn(page, ENTERPRISE.username, ENTERPRISE.password);
    await page.goto("/enterprise/messages");
    await expect(page).toHaveURL(/\/enterprise\/dashboard$/);
    await expect(
      page
        .getByRole("navigation", { name: "后台导航" })
        .getByRole("link", { name: "消息" }),
    ).toHaveCount(0);

    await page.getByRole("link", { name: "简历管理" }).click();
    await expect(page).toHaveURL(/\/enterprise\/applications$/);
    await expect(
      page.getByRole("heading", { level: 1, name: "简历管理" }),
    ).toBeVisible();

    const row = page
      .getByTestId("enterprise-application-row")
      .filter({ hasText: jobTitle });
    await expect(row).toContainText("李同学");
    await expect(row).toContainText("待处理");
    await row.getByRole("button", { name: "查看简历" }).click();
    const resume = page
      .getByTestId("enterprise-resume-detail")
      .filter({ hasText: `${marker} 简历岗位` });
    await expect(resume).toContainText("大专");
    await expect(resume).toContainText("2年");
    await expect(resume).toContainText("直播运营、客户沟通");
    await expect(resume).toContainText("熟悉农村电商与本地农产品");

    await row.getByRole("button", { name: "通知面试" }).click();
    await expect(page.getByTestId("enterprise-applications-feedback")).toContainText(
      "已通知面试",
    );
    await expect(row).toContainText("已通知面试");

    const applications = await api<{
      applications: Array<{ id: number; status: string; title: string }>;
    }>(
      request,
      "GET",
      `/api/employment/applications/${STUDENT.username}`,
      student.session_id,
    );
    expect(
      applications.applications.some(
        (application) =>
          application.title === jobTitle && application.status === "interview",
      ),
    ).toBe(true);

    await signIn(page, STUDENT.username, STUDENT.password);
    await page.getByTestId("message-center-trigger").click();
    await expect(
      page
        .getByTestId("message-center-item")
        .filter({ hasText: jobTitle }),
    ).toContainText("已通知面试");
  });

  test("empty, failure and role-denied states stay explicit", async ({
    page,
    request,
  }) => {
    await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
    await page.route("https://unpkg.com/**", (route) => route.abort());
    const username = `e2e_enterprise_${Date.now()}`;
    await api<SessionPayload>(
      request,
      "POST",
      "/api/auth/register",
      undefined,
      {
        username,
        password: "123456",
        name: "空企业测试",
        role: "enterprise",
        company_name: "空企业测试",
      },
    );

    await signIn(page, username, "123456");
    await expect(page).toHaveURL(/\/enterprise\/dashboard$/);
    for (const testid of [
      "enterprise-stat-approved",
      "enterprise-stat-pending",
      "enterprise-stat-applications",
      "enterprise-application-status-pending",
      "enterprise-application-status-interview",
      "enterprise-application-status-approved",
      "enterprise-application-status-rejected",
    ]) {
      await expect(page.getByTestId(testid)).toContainText("0");
    }

    await page.getByRole("link", { name: "职位管理" }).click();
    await expect(page.getByText("暂无职位", { exact: true })).toBeVisible();

    await page.route("**/api/enterprise/jobs", (route) =>
      route.abort("connectionfailed"),
    );
    await page.getByRole("button", { name: "刷新职位" }).click();
    await expect(page.getByRole("alert")).toContainText("职位列表加载失败");
    await page.unroute("**/api/enterprise/jobs");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(page.getByText("暂无职位", { exact: true })).toBeVisible();

    await page.getByRole("link", { name: "简历管理" }).click();
    await expect(page.getByText("暂无简历投递", { exact: true })).toBeVisible();

    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/enterprise/jobs");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    const student = await login(request, STUDENT);
    const denied = await request.get("/api/enterprise/jobs", {
      headers: { "X-Session-Id": student.session_id },
    });
    expect(denied.status()).toBe(403);
  });
});
