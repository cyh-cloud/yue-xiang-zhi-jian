import { expect, test } from "@playwright/test";

import { signIn } from "./auth-route";

const STUDENT = { username: "student_demo", password: "123456" };

test.describe("employment", () => {
  test("failed taxonomy loading does not expose stale local categories", async ({
    page,
  }) => {
    await page.route("**/api/employment/jobs*", (route) => route.abort());
    await page.goto("/employment");

    const category = page.getByLabel("职位类型");
    await expect(category.locator('option[value="农业技术"]')).toHaveCount(0);
    await expect(category.locator('option[value="基层服务"]')).toHaveCount(0);
    await expect(page.getByText(/加载失败|重试/).first()).toBeVisible();
  });

  test("anonymous visitors browse approved jobs and public recruitments", async ({
    page,
  }) => {
    await page.goto("/employment");

    await expect(
      page.getByRole("heading", { name: "就业对接", level: 1 }),
    ).toBeVisible();
    await expect(page.getByText(/共 \d+ 条信息/)).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "公开招聘信息" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "企业招聘岗位" }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "申请职位" }).first()).toBeVisible();
  });

  test("anonymous actions send the visitor to login and restore the page", async ({
    page,
  }) => {
    await page.goto("/employment");
    await page.getByRole("button", { name: "收藏" }).first().click();

    await expect(page).toHaveURL(/\/login\?redirect=/);
    await expect
      .poll(() => new URL(page.url()).searchParams.get("redirect"))
      .toMatch(/^\/employment\?action=save&job=\d+&resumeAction=1$/);
    await page.getByLabel("用户名").fill(STUDENT.username);
    await page.getByLabel("密码").fill(STUDENT.password);
    await page.getByRole("button", { name: "登录", exact: true }).last().click();

    await expect(page).toHaveURL(
      /\/employment\?action=save&job=\d+&resumeAction=1$/,
    );
    await expect(page.getByRole("heading", { name: "就业对接", level: 1 })).toBeVisible();
    await expect(page.getByTestId("employment-feedback")).toBeVisible();
  });

  test("a saved job stays saved after a reload and appears in saved jobs", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");

    const jobCard = page.getByTestId("employment-job-card").filter({
      has: page.getByRole("button", { name: "申请职位" }),
    }).first();
    const jobId = await jobCard.getAttribute("data-job-id");
    expect(jobId).toMatch(/^\d+$/);
    const title = await jobCard.getByTestId("employment-job-title").innerText();
    const currentSave = jobCard.getByRole("button", { name: /收藏/ });
    if ((await currentSave.getAttribute("aria-label"))?.startsWith("取消收藏")) {
      await currentSave.click();
      await expect(
        jobCard.getByRole("button", { name: `收藏 ${title}` }),
      ).toBeVisible();
    }
    const save = jobCard.getByRole("button", { name: `收藏 ${title}` });
    await save.click();
    await expect(page.getByTestId("employment-feedback")).toContainText("收藏成功");
    await expect(jobCard.getByRole("button", { name: `取消收藏 ${title}` })).toBeVisible();

    await page.reload();
    await expect(jobCard.getByRole("button", { name: `取消收藏 ${title}` })).toBeVisible();

    await page.getByRole("tab", { name: "收藏职位" }).click();
    await expect(
      page.locator(
        `[data-testid="employment-job-card"][data-job-id="${jobId}"]`,
      ),
    ).toBeVisible();
  });

  test("a learner applies, sees the application timeline, and duplicate apply is explained", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");

    const jobCard = page.getByTestId("employment-job-card").filter({
      has: page.getByRole("button", { name: "申请职位" }),
    }).first();
    const title = await jobCard.getByTestId("employment-job-title").innerText();
    await jobCard.getByRole("button", { name: "申请职位" }).click();
    await expect(page.getByTestId("employment-feedback")).toContainText(
      /申请成功|已申请过/,
    );

    if ((await page.getByTestId("employment-feedback").innerText()).includes("申请成功")) {
      await jobCard.getByRole("button", { name: "申请职位" }).click();
      await expect(page.getByTestId("employment-feedback")).toContainText(
        "您已申请过该职位",
      );
    }

    await page.getByRole("tab", { name: "我的求职" }).click();
    const applicationCard = page
      .getByTestId("employment-application-card")
      .filter({ hasText: title });
    await expect(applicationCard).toBeVisible();
    await expect(applicationCard).toHaveAttribute("data-job-id", /.+/);
    await expect(applicationCard).toContainText(
      /待审核|已通知面试|已通过|已拒绝/,
    );
  });

  test("a recruitment detail registers and removes job intent without claiming enrolment", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");

    const activeRecruitment = page
      .getByTestId("employment-recruitment-card")
      .filter({ has: page.getByRole("button", { name: "查看公告" }) })
      .first();
    const recruitKey = await activeRecruitment.getAttribute(
      "data-recruitment-key",
    );
    expect(recruitKey).toBeTruthy();
    const title = await activeRecruitment
      .getByTestId("employment-job-title")
      .innerText();
    await activeRecruitment.getByRole("button", { name: "查看公告" }).click();

    const detail = page.getByTestId("employment-detail");
    await expect(detail).toContainText(title);
    await expect(detail).toContainText("不代办报名");
    await detail.getByRole("button", { name: "登记求职意向" }).click();
    await expect(page.getByTestId("employment-feedback")).toContainText("已记录求职意向");
    await expect(
      detail.getByRole("button", { name: "已登记意向（点击取消）" }),
    ).toBeVisible();

    await detail.getByLabel("关闭").click();
    await page.getByRole("tab", { name: "我的求职" }).click();
    const intentCard = page.locator(
      `[data-testid="employment-intent-card"][data-recruitment-key="${recruitKey}"]`,
    );
    await expect(intentCard).toBeVisible();
    await expect(intentCard).toContainText(title);
    await intentCard
      .getByRole("button", { name: "取消意向" }).click();
    await expect(intentCard).toHaveCount(0);
  });

  test("jobs awaiting review stay out of the list and cannot be opened by id", async ({
    page,
    request,
  }) => {
    const adminLogin = await request.post("/api/auth/login", {
      data: { username: "enterprise_demo", password: "123456" },
    });
    expect(adminLogin.ok()).toBe(true);
    const session = await adminLogin.json();
    const create = await request.post("/api/enterprise/jobs", {
      data: {
        title: `E2E 待审岗位 ${Date.now()}`,
        salary: "5K-8K",
        description: "用于验证审核门禁的待审职位",
        location: "广州",
        category: "电商运营",
        requirements: ["测试"],
      },
      headers: { "X-Session-Id": session.session_id },
    });
    expect(create.ok()).toBe(true);
    const created = await create.json();
    const jobId = created.job_id ?? created.id;
    expect(jobId).toBeTruthy();

    await page.goto("/employment");
    await expect(page.getByTestId("employment-job-card").filter({
      hasText: `E2E 待审岗位`,
    })).toHaveCount(0);
    const publicDetail = await request.get(`/api/employment/jobs/${jobId}`);
    expect(publicDetail.status()).toBe(404);
  });

  test("filters produce real counts, explain hidden recruitments, and keep category options", async ({
    page,
    request,
  }) => {
    const payload = (await (
      await page.request.get("/api/employment/jobs?salary=3K-5K")
    ).json()) as {
      jobs: unknown[];
      recruitments: unknown[];
      recruit_hidden_by_salary: number;
    };
    expect(payload.recruit_hidden_by_salary).toBe(payload.recruitments.length);

    await page.goto("/employment");
    await page.getByLabel("薪资范围").selectOption("3K-5K");
    await page.getByRole("button", { name: "搜索", exact: true }).click();

    await expect(page.getByTestId("employment-filter-note")).toContainText(
      `${payload.recruit_hidden_by_salary} 条公开招聘公告`,
    );
    await expect(page.getByTestId("employment-recruitment-card")).toHaveCount(0);
    await expect(page.getByLabel("职位类型").locator("optgroup")).toHaveCount(2);

    const recResponse = await request.get("/api/employment/jobs");
    const recBody = await recResponse.json();
    const firstRecruit = recBody.recruitments[0];
    expect(firstRecruit).toBeTruthy();
  });

  test("job detail shows requirements and similar approved jobs", async ({ page }) => {
    await page.goto("/employment");
    const jobCard = page.getByTestId("employment-job-card").filter({
      has: page.getByRole("button", { name: "申请职位" }),
    }).first();
    const title = await jobCard.getByTestId("employment-job-title").innerText();
    await jobCard.getByTestId("employment-job-title").click();

    const detail = page.getByTestId("employment-detail");
    await expect(detail).toContainText(title);
    await expect(detail).toContainText("职位信息");
    await expect(detail).toContainText("职位描述");
    await expect(detail).toContainText("申请建议");

    const similarHeading = detail.getByRole("heading", { name: "相似职位推荐" });
    if (await similarHeading.count()) {
      const similarJob = detail.getByTestId("employment-similar-job").first();
      await expect(similarJob).toBeVisible();
      await expect(similarJob).toHaveAttribute("data-job-id", /.+/);
      await similarJob.click();
      await expect(detail).toContainText("职位信息");
    }
  });

  test("an empty filter result explains which condition hid the content", async ({
    page,
  }) => {
    await page.goto("/employment");
    await page.getByLabel("搜索职位、公司、技能").fill("zzz-no-such-job");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await expect(page.getByTestId("employment-empty")).toContainText(
      "未找到匹配的职位",
    );
    await expect(page.getByTestId("employment-empty")).toContainText(
      "试试减少搜索关键词",
    );
  });

  test("a failed job list gives a retry instead of a blank page", async ({ page }) => {
    await page.route("**/api/employment/jobs*", (route) => route.abort());
    await page.goto("/employment");
    await expect(page.getByRole("alert")).toContainText(
      "连接服务器失败，请检查网络后重试",
    );
    await expect(page.getByRole("button", { name: "重新加载" })).toBeVisible();
  });

  test("desktop employment visual baseline stays stable", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 1400 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/employment/jobs*", (route) =>
      route.fulfill({
        json: {
          success: true,
          jobs: [
            {
              id: 501,
              title: "农产品电商运营专员",
              company: "粤乡优选（演示）",
              salary: "5K-8K",
              requirements: ["熟悉直播运营", "会基础数据分析"],
              description: "负责农产品线上店铺运营与直播策划。",
              location: "茂名",
              category: "电商运营",
              job_type: "全职",
              education: "大专",
              experience: "1年",
              company_size: "50-99人",
              industry: "农业电商",
              enterprise_id: "enterprise_demo",
              review_status: "approved",
              posted_at: "2026-10-18 09:00:00",
              source_type: "enterprise",
              is_demo: 1,
            },
          ],
          recruitments: [
            {
              key: "fixture-open",
              title: "乡村公益性岗位公开招聘",
              org: "茂名市某镇人民政府",
              region: "茂名",
              category: "基层服务",
              job_type: "公益性岗位",
              headcount: "招聘 10 人",
              education: "高中及以上",
              signup_start: "2026-10-01",
              deadline: "2026-10-31",
              signup_way: "按公告原文报名",
              publish_date: "2026-10-01",
              description: "面向就业困难人员公开招聘乡村公益性岗位。",
              sources: [
                {
                  title: "官方公告",
                  url: "https://example.com/recruit",
                  media: "政府网站",
                  date: "2026-10-01",
                },
              ],
              status: "open",
              status_label: "报名中",
              days_left: 11,
              source_type: "public_recruit",
            },
          ],
          recruit_source_note: "岗位信息来自公开渠道整理。",
          recruit_disclaimer: "岗位条件以公告原文为准，本平台不代办报名。",
          category_options: {
            enterprise: [
              { value: "农业技术", count: 0 },
              { value: "电商运营", count: 1 },
              { value: "手工工艺", count: 0 },
              { value: "乡村旅游", count: 0 },
              { value: "物流仓储", count: 0 },
            ],
            recruit: [
              { value: "基层服务", count: 1 },
              { value: "乡村治理", count: 0 },
            ],
          },
          recruit_hidden_by_salary: 0,
          enterprise_review_pending: 0,
        },
      }),
    );
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({ json: { success: true, count: 0 } }),
    );

    await page.goto("/employment");
    await expect(
      page.getByRole("button", {
        name: "农产品电商运营专员",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", {
        name: "乡村公益性岗位公开招聘",
        exact: true,
      }),
    ).toBeVisible();
    await page.waitForFunction(() =>
      Array.from(document.images).every((image) => image.complete),
    );
    await page.evaluate(() => document.fonts.ready);

    await expect(page).toHaveScreenshot("employment-anonymous-light.png", {
      fullPage: true,
    });
  });
});
