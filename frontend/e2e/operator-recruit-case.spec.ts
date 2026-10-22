import { expect, test, type APIRequestContext } from "@playwright/test";

import { signIn } from "./auth-route";

const OPERATOR = { username: "operator_demo", password: "123456" } as const;

async function loginWithRequest(
  request: APIRequestContext,
): Promise<string> {
  const response = await request.post("/api/auth/login", {
    data: OPERATOR,
  });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { session_id: string }).session_id;
}

function headers(sessionId: string): Record<string, string> {
  return { "X-Session-Id": sessionId };
}

async function deleteQuietly(
  request: APIRequestContext,
  path: string,
  sessionId: string,
): Promise<void> {
  await request
    .delete(path, { headers: headers(sessionId) })
    .catch(() => undefined);
}

test.describe("operator recruitment and case maintenance", () => {
  test("recruitments and sources maintain public employment content end to end", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const key = `e2e-t22-recruit-${stamp}`;
    const title = `T22 招募公告 ${stamp}`;
    const updatedTitle = `${title} 已更新`;
    const sourceTitle = `T22 公告来源 ${stamp}`;
    const updatedMedia = `T22 来源媒体 ${stamp}`;

    try {
      await signIn(page, OPERATOR.username, OPERATOR.password);
      await page.goto("/operator/recruitments");
      await expect(
        page.getByRole("heading", { name: "招募公告", level: 1 }),
      ).toBeVisible();

      await page.getByRole("button", { name: "新建公告" }).click();
      const dialog = page.getByTestId("operator-record-dialog");
      await dialog.getByLabel("公告 key", { exact: true }).fill(key);
      await dialog.getByLabel("公告标题", { exact: true }).fill(title);
      await dialog.getByLabel("发布单位", { exact: true }).fill("T22 测试单位");
      await dialog.getByLabel("地区", { exact: true }).fill("茂名");
      await dialog
        .getByLabel("岗位类别", { exact: true })
        .selectOption("基层服务");
      await dialog.getByLabel("岗位类型", { exact: true }).fill("公益性岗位");
      await dialog.getByLabel("招聘人数", { exact: true }).fill("2 人");
      await dialog.getByLabel("学历要求", { exact: true }).fill("高中及以上");
      await dialog.getByLabel("其他条件", { exact: true }).fill("本地户籍");
      await dialog.getByLabel("薪酬待遇", { exact: true }).fill("面议");
      await dialog
        .getByLabel("公告描述", { exact: true })
        .fill("T22 招募公告公开同步测试");
      await dialog
        .getByLabel("报名开始", { exact: true })
        .fill("2026-01-01");
      await dialog
        .getByLabel("报名截止", { exact: true })
        .fill("2099-12-31");
      await dialog
        .getByLabel("报名方式", { exact: true })
        .fill("按公告原文报名");
      await dialog.getByLabel("联系方式", { exact: true }).fill("0668-1234567");
      await dialog.getByLabel("排序", { exact: true }).fill("940");
      await dialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(page.getByTestId("operator-recruitments-feedback")).toContainText(
        "公告已创建",
      );

      const row = page
        .getByTestId("operator-recruitment-row")
        .filter({ hasText: title });
      await expect(row).toBeVisible();
      await expect(row).toContainText("基层服务");

      await row.getByRole("button", { name: "来源", exact: true }).click();
      await expect(
        page.getByRole("heading", { name: new RegExp(key) }),
      ).toBeVisible();
      await page.getByRole("button", { name: "新建来源" }).click();
      const sourceDialog = page.getByTestId("operator-record-dialog");
      await sourceDialog
        .getByLabel("来源标题", { exact: true })
        .fill(sourceTitle);
      await sourceDialog
        .getByLabel("媒体 / 发布单位", { exact: true })
        .fill("T22 来源媒体");
      await sourceDialog.getByLabel("日期", { exact: true }).fill("2026-01-01");
      await sourceDialog
        .getByLabel("链接", { exact: true })
        .fill("https://example.com/t22-recruit");
      await sourceDialog.getByLabel("排序", { exact: true }).fill("1");
      await sourceDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(sourceDialog).toHaveCount(0);

      const sourceRow = page
        .getByTestId("operator-recruitment-source-row")
        .filter({ hasText: sourceTitle });
      await expect(sourceRow).toBeVisible();
      await sourceRow.getByRole("button", { name: "编辑", exact: true }).click();
      const sourceEdit = page.getByTestId("operator-record-dialog");
      await sourceEdit
        .getByLabel("媒体 / 发布单位", { exact: true })
        .fill(updatedMedia);
      await sourceEdit
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(sourceEdit).toHaveCount(0);

      const publicAfterCreate = await request.get("/api/employment/jobs");
      expect(publicAfterCreate.ok()).toBeTruthy();
      const publicBody = (await publicAfterCreate.json()) as {
        recruitments: Array<{
          key: string;
          title: string;
          sources: Array<{ title: string; media: string }>;
        }>;
      };
      const publicRecruitment = publicBody.recruitments.find(
        (item) => item.key === key,
      );
      expect(publicRecruitment?.title).toBe(title);
      expect(publicRecruitment?.sources).toContainEqual(
        expect.objectContaining({
          title: sourceTitle,
          media: updatedMedia,
        }),
      );

      await row.getByRole("button", { name: "编辑", exact: true }).click();
      const editDialog = page.getByTestId("operator-record-dialog");
      await editDialog
        .getByLabel("公告标题", { exact: true })
        .fill(updatedTitle);
      await editDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(editDialog).toHaveCount(0);

      await page.goto("/employment");
      await expect(page.getByText(updatedTitle, { exact: true })).toBeVisible();

      await page.goto("/operator/recruitments");
      const updatedRow = page
        .getByTestId("operator-recruitment-row")
        .filter({ hasText: updatedTitle });
      await updatedRow.getByRole("button", { name: "来源", exact: true }).click();
      const liveSource = page
        .getByTestId("operator-recruitment-source-row")
        .filter({ hasText: sourceTitle });
      page.once("dialog", (confirmation) => confirmation.accept());
      await liveSource.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveSource).toHaveCount(0);
      page.once("dialog", (confirmation) => confirmation.accept());
      await updatedRow.getByRole("button", { name: "删除", exact: true }).click();
      await expect(updatedRow).toHaveCount(0);

      const publicAfterDelete = await request.get("/api/employment/jobs");
      const afterDelete = (await publicAfterDelete.json()) as {
        recruitments: Array<{ key: string }>;
      };
      expect(
        afterDelete.recruitments.some((item) => item.key === key),
      ).toBe(false);
    } finally {
      await deleteQuietly(
        request,
        `/api/operator/recruitments/${encodeURIComponent(key)}`,
        sessionId,
      );
    }
  });

  test("cases keep review-gated public visibility, child tables and legacy links in sync", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const title = `T22 成功案例 ${stamp}`;
    const updatedTitle = `${title} 已更新`;
    const firstStat = `T22 指标甲 ${stamp}`;
    const secondStat = `T22 指标乙 ${stamp}`;
    const milestone = `T22 里程碑 ${stamp}`;
    const source = `T22 案例来源 ${stamp}`;
    const lesson = `T22 借鉴点 ${stamp}`;
    let caseId: number | null = null;

    try {
      await signIn(page, OPERATOR.username, OPERATOR.password);
      await page.goto("/operator/cases");
      await expect(
        page.getByRole("heading", { name: "成功案例", level: 1 }),
      ).toBeVisible();

      await page.getByRole("button", { name: "新建案例" }).click();
      const dialog = page.getByTestId("operator-record-dialog");
      await dialog.getByLabel("案例标题", { exact: true }).fill(title);
      await dialog.getByLabel("地区", { exact: true }).fill("茂名");
      await dialog.getByLabel("地点", { exact: true }).fill("高州市根子镇");
      await dialog
        .getByLabel("背景", { exact: true })
        .fill("T22 案例背景，用于验证审核门禁与公开同步。");
      await dialog
        .getByLabel("描述", { exact: true })
        .fill("T22 案例描述，公开详情应展示同一份内容。");
      await dialog.getByLabel("引语", { exact: true }).fill("T22 受访者引语");
      await dialog.getByLabel("受访者", { exact: true }).fill("T22 测试受访者");
      await dialog.getByLabel("排序", { exact: true }).fill("950");
      await dialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await expect(page.getByTestId("operator-cases-feedback")).toContainText(
        "案例已创建",
      );

      const row = page.getByTestId("operator-case-row").filter({ hasText: title });
      await expect(row).toBeVisible();
      const created = await request.get("/api/operator/cases", {
        headers: headers(sessionId),
      });
      const createdBody = (await created.json()) as {
        cases: Array<{ id: number; title: string }>;
      };
      caseId =
        createdBody.cases.find((item) => item.title === title)?.id ?? null;
      expect(caseId).toBeTruthy();

      const publicBefore = await request.get("/api/resources/cases");
      const publicBeforeBody = (await publicBefore.json()) as {
        cases: Array<{ id: number }>;
      };
      expect(
        publicBeforeBody.cases.some((item) => item.id === caseId),
      ).toBe(false);

      await page.getByRole("tab", { name: "数据指标", exact: true }).click();
      await page.getByRole("button", { name: "新建指标" }).click();
      const firstStatDialog = page.getByTestId("operator-record-dialog");
      await firstStatDialog
        .getByLabel("指标名称", { exact: true })
        .fill(firstStat);
      await firstStatDialog.getByLabel("数值", { exact: true }).fill("20%");
      await firstStatDialog.getByLabel("图标", { exact: true }).fill("fa-chart-line");
      await firstStatDialog.getByLabel("排序", { exact: true }).fill("20");
      await firstStatDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(firstStatDialog).toHaveCount(0);

      await page.getByRole("button", { name: "新建指标" }).click();
      const secondStatDialog = page.getByTestId("operator-record-dialog");
      await secondStatDialog
        .getByLabel("指标名称", { exact: true })
        .fill(secondStat);
      await secondStatDialog.getByLabel("数值", { exact: true }).fill("70%");
      await secondStatDialog.getByLabel("图标", { exact: true }).fill("fa-store");
      await secondStatDialog.getByLabel("排序", { exact: true }).fill("10");
      await secondStatDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(secondStatDialog).toHaveCount(0);

      const secondStatRow = page
        .getByTestId("operator-case-stat-row")
        .filter({ hasText: secondStat });
      await secondStatRow.getByRole("button", { name: "编辑", exact: true }).click();
      const statEdit = page.getByTestId("operator-record-dialog");
      await statEdit.getByLabel("数值", { exact: true }).fill("75%");
      await statEdit.getByRole("button", { name: "保存", exact: true }).click();
      await expect(statEdit).toHaveCount(0);

      await page.getByRole("tab", { name: "里程碑", exact: true }).click();
      await page.getByRole("button", { name: "新建里程碑" }).click();
      const milestoneDialog = page.getByTestId("operator-record-dialog");
      await milestoneDialog.getByLabel("时期", { exact: true }).fill("2025 年");
      await milestoneDialog.getByLabel("标题", { exact: true }).fill(milestone);
      await milestoneDialog
        .getByLabel("说明", { exact: true })
        .fill("T22 里程碑说明");
      await milestoneDialog.getByLabel("排序", { exact: true }).fill("1");
      await milestoneDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(milestoneDialog).toHaveCount(0);
      const milestoneRow = page
        .getByTestId("operator-case-milestone-row")
        .filter({ hasText: milestone });
      await milestoneRow.getByRole("button", { name: "编辑", exact: true }).click();
      const milestoneEdit = page.getByTestId("operator-record-dialog");
      await milestoneEdit
        .getByLabel("说明", { exact: true })
        .fill("T22 里程碑说明已更新");
      await milestoneEdit
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(milestoneEdit).toHaveCount(0);

      await page.getByRole("tab", { name: "来源", exact: true }).click();
      await page.getByRole("button", { name: "新建来源" }).click();
      const sourceDialog = page.getByTestId("operator-record-dialog");
      await sourceDialog.getByLabel("来源标题", { exact: true }).fill(source);
      await sourceDialog.getByLabel("媒体", { exact: true }).fill("T22 媒体");
      await sourceDialog.getByLabel("日期", { exact: true }).fill("2026-01-01");
      await sourceDialog
        .getByLabel("链接", { exact: true })
        .fill("https://example.com/t22-case");
      await sourceDialog.getByLabel("排序", { exact: true }).fill("1");
      await sourceDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(sourceDialog).toHaveCount(0);
      const sourceRow = page
        .getByTestId("operator-case-source-row")
        .filter({ hasText: source });
      await sourceRow.getByRole("button", { name: "编辑", exact: true }).click();
      const sourceEdit = page.getByTestId("operator-record-dialog");
      await sourceEdit.getByLabel("媒体", { exact: true }).fill("T22 媒体已更新");
      await sourceEdit.getByRole("button", { name: "保存", exact: true }).click();
      await expect(sourceEdit).toHaveCount(0);

      await page.getByRole("tab", { name: "借鉴点", exact: true }).click();
      await page.getByRole("button", { name: "新建借鉴点" }).click();
      const lessonDialog = page.getByTestId("operator-record-dialog");
      await lessonDialog.getByLabel("借鉴点", { exact: true }).fill(lesson);
      await lessonDialog.getByLabel("排序", { exact: true }).fill("1");
      await lessonDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(lessonDialog).toHaveCount(0);
      const lessonRow = page
        .getByTestId("operator-case-lesson-row")
        .filter({ hasText: lesson });
      await lessonRow.getByRole("button", { name: "编辑", exact: true }).click();
      const lessonEdit = page.getByTestId("operator-record-dialog");
      await lessonEdit
        .getByLabel("借鉴点", { exact: true })
        .fill(`${lesson} 已更新`);
      await lessonEdit.getByRole("button", { name: "保存", exact: true }).click();
      await expect(lessonEdit).toHaveCount(0);

      const adminLogin = await request.post("/api/auth/login", {
        data: { username: "admin_demo", password: "admin123" },
      });
      expect(adminLogin.ok()).toBeTruthy();
      const adminSession = (await adminLogin.json()) as { session_id: string };
      const reviews = await request.get(
        "/api/admin/reviews?status=pending&content_type=success_case",
        { headers: headers(adminSession.session_id) },
      );
      const reviewBody = (await reviews.json()) as {
        reviews: Array<{ id: number; content_id: number }>;
      };
      const review = reviewBody.reviews.find(
        (item) => item.content_id === caseId,
      );
      expect(review).toBeTruthy();
      const approved = await request.post(
        `/api/admin/reviews/${review?.id}/approve`,
        { headers: headers(adminSession.session_id), data: {} },
      );
      expect(approved.ok()).toBeTruthy();

      const publicAfter = await request.get("/api/resources/cases");
      const publicCase = (
        (await publicAfter.json()) as {
          cases: Array<{
            id: number;
            title: string;
            stats: Array<{ label: string; value: string }>;
            milestones: Array<{ title: string; desc: string }>;
            sources: Array<{ title: string; media: string }>;
            lessons: string[];
          }>;
        }
      ).cases.find((item) => item.id === caseId);
      expect(publicCase?.title).toBe(title);
      expect(publicCase?.stats.map((item) => item.label)).toEqual([
        secondStat,
        firstStat,
      ]);
      expect(publicCase?.stats[0]?.value).toBe("75%");
      expect(publicCase?.milestones[0]?.desc).toBe("T22 里程碑说明已更新");
      expect(publicCase?.sources[0]?.media).toBe("T22 媒体已更新");
      expect(publicCase?.lessons).toEqual([`${lesson} 已更新`]);

      await page.goto(`/case-detail.html?id=${caseId}`);
      await expect(page).toHaveURL(new RegExp(`/case-detail/${caseId}$`));
      await expect(page.getByRole("heading", { name: title })).toBeVisible();
      await expect(page.getByText(secondStat, { exact: true })).toBeVisible();
      await expect(page.getByText(milestone, { exact: true })).toBeVisible();
      await expect(page.getByText(`${lesson} 已更新`, { exact: true })).toBeVisible();
      await expect(page.getByText(source, { exact: true })).toBeVisible();

      await page.goto("/operator/cases");
      const liveRow = page
        .getByTestId("operator-case-row")
        .filter({ hasText: title });
      await liveRow.getByRole("button", { name: "编辑", exact: true }).click();
      const caseEdit = page.getByTestId("operator-record-dialog");
      await caseEdit
        .getByLabel("案例标题", { exact: true })
        .fill(updatedTitle);
      await caseEdit.getByRole("button", { name: "保存", exact: true }).click();
      await expect(caseEdit).toHaveCount(0);

      await page.goto(`/case-detail.html?id=${caseId}`);
      await expect(
        page.getByRole("heading", { name: updatedTitle }),
      ).toBeVisible();

      await page.goto("/operator/cases");
      const updatedRow = page
        .getByTestId("operator-case-row")
        .filter({ hasText: updatedTitle });
      await updatedRow.getByRole("button", { name: "查看内容" }).click();

      await page.getByRole("tab", { name: "数据指标", exact: true }).click();
      const firstStatRow = page
        .getByTestId("operator-case-stat-row")
        .filter({ hasText: firstStat });
      page.once("dialog", (confirmation) => confirmation.accept());
      await firstStatRow.getByRole("button", { name: "删除", exact: true }).click();
      await expect(firstStatRow).toHaveCount(0);

      await page.getByRole("tab", { name: "里程碑", exact: true }).click();
      const liveMilestone = page
        .getByTestId("operator-case-milestone-row")
        .filter({ hasText: milestone });
      page.once("dialog", (confirmation) => confirmation.accept());
      await liveMilestone
        .getByRole("button", { name: "删除", exact: true })
        .click();
      await expect(liveMilestone).toHaveCount(0);

      await page.getByRole("tab", { name: "来源", exact: true }).click();
      const liveSource = page
        .getByTestId("operator-case-source-row")
        .filter({ hasText: source });
      page.once("dialog", (confirmation) => confirmation.accept());
      await liveSource.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveSource).toHaveCount(0);

      await page.getByRole("tab", { name: "借鉴点", exact: true }).click();
      const liveLesson = page
        .getByTestId("operator-case-lesson-row")
        .filter({ hasText: lesson });
      page.once("dialog", (confirmation) => confirmation.accept());
      await liveLesson.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveLesson).toHaveCount(0);

      const publicAfterChildDelete = await request.get("/api/resources/cases");
      const clearedCase = (
        (await publicAfterChildDelete.json()) as {
          cases: Array<{
            id: number;
            stats: unknown[];
            milestones: unknown[];
            sources: unknown[];
            lessons: unknown[];
          }>;
        }
      ).cases.find((item) => item.id === caseId);
      expect(clearedCase).toMatchObject({
        stats: [
          {
            icon: "fa-store",
            label: secondStat,
            value: "75%",
          },
        ],
        milestones: [],
        sources: [],
        lessons: [],
      });
    } finally {
      if (caseId) {
        await deleteQuietly(
          request,
          `/api/operator/cases/${caseId}`,
          sessionId,
        );
      }
    }
  });

  for (const account of [
    {
      label: "学员",
      username: "student_demo",
      password: "123456",
      landing: /\/agriculture\/?$/,
    },
    {
      label: "教师",
      username: "teacher_demo",
      password: "123456",
      landing: /\/teacher\/dashboard$/,
    },
    {
      label: "企业",
      username: "enterprise_demo",
      password: "123456",
      landing: /\/enterprise\/dashboard$/,
    },
    {
      label: "政府",
      username: "gov_demo",
      password: "123456",
      landing: /\/government\/dashboard$/,
    },
  ]) {
    test(`${account.label} cannot enter the operator recruitment or case pages`, async ({
      page,
    }) => {
      await signIn(page, account.username, account.password);
      await page.goto("/operator/recruitments");
      await expect(page).toHaveURL(account.landing);
      await page.goto("/operator/cases");
      await expect(page).toHaveURL(account.landing);
    });
  }

  test("super admin can use both operator content pages", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await signIn(page, "admin_demo", "admin123");
    await page.goto("/operator/recruitments");
    await expect(
      page.getByRole("heading", { name: "招募公告", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "新建公告" }),
    ).toBeVisible();

    await page.goto("/operator/cases");
    await expect(
      page.getByRole("heading", { name: "成功案例", level: 1 }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "新建案例" }),
    ).toBeVisible();
  });

  test("empty recruitment and case responses render explicit empty states", async ({
    page,
  }) => {
    await page.route("**/api/operator/recruitments", (route) =>
      route.fulfill({
        json: {
          success: true,
          recruitments: [],
          categories: ["农业技术", "基层服务", "乡村治理"],
        },
      }),
    );
    await page.route("**/api/operator/cases", (route) =>
      route.fulfill({
        json: { success: true, cases: [] },
      }),
    );

    await signIn(page, OPERATOR.username, OPERATOR.password);
    await page.goto("/operator/recruitments");
    await expect(page.getByText("没有符合条件的公告")).toBeVisible();

    await page.goto("/operator/cases");
    await expect(page.getByText("还没有案例")).toBeVisible();
    await expect(page.getByText("先在上方选择一条案例")).toBeVisible();
  });

  test("a failed recruitment request shows an error and recovers through retry", async ({
    page,
  }) => {
    await page.route("**/api/operator/recruitments", (route) =>
      route.abort("connectionfailed"),
    );
    await signIn(page, OPERATOR.username, OPERATOR.password);
    await page.goto("/operator/recruitments");
    await expect(
      page.getByText("招募公告加载失败", { exact: true }),
    ).toBeVisible();

    await page.unroute("**/api/operator/recruitments");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(
      page.getByRole("button", { name: "新建公告" }),
    ).toBeVisible();
  });

  test("a failed case request shows an error and recovers through retry", async ({
    page,
  }) => {
    await page.route("**/api/operator/cases", (route) =>
      route.abort("connectionfailed"),
    );
    await signIn(page, OPERATOR.username, OPERATOR.password);
    await page.goto("/operator/cases");
    await expect(
      page.getByText("成功案例加载失败", { exact: true }),
    ).toBeVisible();

    await page.unroute("**/api/operator/cases");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(
      page.getByRole("button", { name: "新建案例" }),
    ).toBeVisible();
  });
});
