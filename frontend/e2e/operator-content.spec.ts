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

const OPERATOR = ROLE_ACCOUNTS.operator;

test.use({ serviceWorkers: "block" });

interface OperatorTask {
  id: number;
  title: string;
  is_verified: number;
  verified_by: string;
  verified_at: string;
}

interface OperatorPestEntry {
  id: string;
  disease: string;
  is_verified: number;
  verified_by: string;
  verified_at: string;
}

async function loginWithRequest(
  request: APIRequestContext,
): Promise<string> {
  const response = await request.post("/api/auth/login", {
    data: OPERATOR,
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { session_id: string };
  return body.session_id;
}

function operatorHeaders(sessionId: string): Record<string, string> {
  return { "X-Session-Id": sessionId };
}

async function openOperator(page: Page): Promise<void> {
  await signIn(page, OPERATOR.username, OPERATOR.password);
  await expect(page).toHaveURL(/\/operator\/overview$/);
  await expect(page.getByTestId("backoffice-shell")).toHaveAttribute(
    "data-role",
    "operator",
  );
}

async function openOperatorSection(
  page: Page,
  label: "农时日历" | "病虫害知识",
  path: RegExp,
): Promise<void> {
  await page
    .getByRole("navigation", { name: "后台导航" })
    .getByRole("link", { name: label })
    .click();
  await expect(page).toHaveURL(path);
}

async function createReference(
  page: Page,
  tab: string,
  createLabel: string,
  values: Record<string, string>,
): Promise<void> {
  await page.getByRole("tab", { name: tab, exact: true }).click();
  await page.getByRole("button", { name: createLabel }).click();
  const dialog = page.getByTestId("operator-record-dialog");
  await expect(dialog).toBeVisible();
  for (const [label, value] of Object.entries(values)) {
    await dialog.getByLabel(label, { exact: true }).fill(value);
  }
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

async function editReference(
  page: Page,
  tab: string,
  marker: string,
  values: Record<string, string>,
): Promise<void> {
  await page.getByRole("tab", { name: tab, exact: true }).click();
  const row = page
    .locator('[data-testid="operator-reference-row"]')
    .filter({ hasText: marker })
    .first();
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "编辑", exact: true }).click();
  const dialog = page.getByTestId("operator-record-dialog");
  for (const [label, value] of Object.entries(values)) {
    await dialog.getByLabel(label, { exact: true }).fill(value);
  }
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

async function deleteReferenceWithUi(
  page: Page,
  tab: string,
  marker: string,
): Promise<void> {
  await page.getByRole("tab", { name: tab, exact: true }).click();
  const row = page
    .locator('[data-testid="operator-reference-row"]')
    .filter({ hasText: marker })
    .first();
  await expect(row).toBeVisible();
  page.once("dialog", (dialog) => dialog.accept());
  await row.getByRole("button", { name: "删除", exact: true }).click();
  await expect(row).toHaveCount(0);
}

async function deleteWithApi(
  request: APIRequestContext,
  path: string,
  sessionId: string,
): Promise<void> {
  await request
    .delete(path, { headers: operatorHeaders(sessionId) })
    .catch(() => undefined);
}

test.describe("operator overview and content maintenance", () => {
  test("overview renders real content totals and overdue review reminders", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const headers = operatorHeaders(sessionId);
    const [tasksResponse, overdueTasksResponse, entriesResponse, overdueEntriesResponse] =
      await Promise.all([
        request.get("/api/operator/farming/tasks", { headers }),
        request.get("/api/operator/farming/tasks?overdue=1", { headers }),
        request.get("/api/operator/pest/entries", { headers }),
        request.get("/api/operator/pest/entries?overdue=1", { headers }),
      ]);
    const tasks = ((await tasksResponse.json()) as { tasks: OperatorTask[] }).tasks;
    const overdueTasks = (
      (await overdueTasksResponse.json()) as { tasks: OperatorTask[] }
    ).tasks;
    const entries = (
      (await entriesResponse.json()) as { entries: OperatorPestEntry[] }
    ).entries;
    const overdueEntries = (
      (await overdueEntriesResponse.json()) as { entries: OperatorPestEntry[] }
    ).entries;

    await openOperator(page);
    await expect(page.getByTestId("operator-stat-tasks")).toContainText(
      String(tasks.length),
    );
    await expect(page.getByTestId("operator-stat-overdue-tasks")).toContainText(
      String(overdueTasks.length),
    );
    await expect(page.getByTestId("operator-stat-entries")).toContainText(
      String(entries.length),
    );
    await expect(page.getByTestId("operator-stat-overdue-entries")).toContainText(
      String(overdueEntries.length),
    );
    await expect(page.getByTestId("operator-overdue-reminders")).toContainText(
      "超 183 天或从未复核",
    );
    if (overdueTasks[0]) {
      await expect(
        page.getByTestId("operator-overdue-reminders"),
      ).toContainText(overdueTasks[0].title);
    }
    if (overdueEntries[0]) {
      await expect(
        page.getByTestId("operator-overdue-reminders"),
      ).toContainText(overdueEntries[0].disease);
    }
  });

  test("farming products, phenophases, sources, categories and tasks work end to end", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const productId = `e2e_t20_${stamp}`;
    const sourceKey = `E2E-T20-${stamp}`;
    const categoryKey = `e2e_cat_${stamp}`;
    const productName = `T20 测试作物 ${stamp}`;
    const phaseName = `T20 物候期 ${stamp}`;
    const taskTitle = `T20 农事任务 ${stamp}`;
    const month = new Date().getMonth() + 1;
    const monthText = String(month).padStart(2, "0");

    try {
      await openOperator(page);
      await openOperatorSection(page, "农时日历", /\/operator\/farming$/);

      await createReference(page, "作物", "新建作物", {
        "作物 id": productId,
        "作物名称": productName,
        "图标": "seedling",
        "摘要": "T20 e2e 作物",
        "地区": "广东",
        "排序": "920",
      });
      await editReference(page, "作物", productName, {
        "作物名称": `${productName} 已改`,
      });

      await createReference(page, "来源登记", "新建来源", {
        "来源 key": sourceKey,
        "来源名称": `T20 来源 ${stamp}`,
        "机构": "广东省农业技术推广中心",
        "文件类型": "技术指引",
        "文号": "待核",
        "链接": "https://example.com/t20",
        "排序": "921",
      });
      await editReference(page, "来源登记", sourceKey, {
        "机构": "T20 修订机构",
      });

      await createReference(page, "分类标签", "新建分类", {
        "分类 key": categoryKey,
        "分类标签": `T20 分类 ${stamp}`,
        "颜色": "#65733d",
        "排序": "922",
      });
      await editReference(page, "分类标签", categoryKey, {
        "分类标签": `T20 分类已改 ${stamp}`,
      });

      await page.getByRole("tab", { name: "物候期", exact: true }).click();
      await page.getByRole("button", { name: "新建物候期" }).click();
      const phaseDialog = page.getByTestId("operator-record-dialog");
      await phaseDialog.getByLabel("作物", { exact: true }).selectOption(productId);
      await phaseDialog.getByLabel("物候期名称", { exact: true }).fill(phaseName);
      await phaseDialog.getByLabel("起始月份", { exact: true }).fill(String(month));
      await phaseDialog.getByLabel("结束月份", { exact: true }).fill(String(month));
      await phaseDialog.getByLabel("颜色", { exact: true }).fill("#1f5e43");
      await phaseDialog.getByLabel("说明", { exact: true }).fill("T20 物候期说明");
      await phaseDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(phaseDialog).toHaveCount(0);
      await editReference(page, "物候期", phaseName, {
        "物候期名称": `${phaseName} 已改`,
      });

      await page.getByRole("button", { name: "新建任务" }).click();
      const taskDialog = page.getByTestId("operator-record-dialog");
      await taskDialog.getByLabel("作物", { exact: true }).selectOption(productId);
      const phaseSelect = taskDialog.getByLabel("物候期", { exact: true });
      const phaseValue = await phaseSelect
        .locator("option")
        .filter({ hasText: `${phaseName} 已改` })
        .getAttribute("value");
      expect(phaseValue).toBeTruthy();
      await phaseSelect.selectOption(phaseValue as string);
      await taskDialog.getByLabel("任务标题", { exact: true }).fill(taskTitle);
      await taskDialog.getByLabel("任务分类", { exact: true }).selectOption("manage");
      await taskDialog.getByLabel("月份", { exact: true }).fill(String(month));
      await taskDialog
        .getByLabel("任务日期", { exact: true })
        .fill(`${monthText}-20`);
      await taskDialog.getByLabel("优先级", { exact: true }).selectOption("high");
      await taskDialog.getByLabel("来源", { exact: true }).selectOption(sourceKey);
      await taskDialog.getByLabel("描述", { exact: true }).fill("T20 任务描述");
      await taskDialog.getByLabel("提示", { exact: true }).fill("T20 任务提示");
      await taskDialog.getByLabel("日期依据", { exact: true }).fill("T20 日期依据");
      await taskDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(taskDialog).toHaveCount(0);

      const taskRow = page
        .locator('[data-testid="operator-farming-task-row"]')
        .filter({ hasText: taskTitle });
      await expect(taskRow).toBeVisible();
      await expect(taskRow).toContainText("待复核");

      const publicBefore = await request.get(
        `/api/agriculture/calendar/${productId}?month=${month}`,
      );
      expect(publicBefore.ok()).toBeTruthy();
      const beforeTask = (
        (await publicBefore.json()) as { tasks: OperatorTask[] }
      ).tasks.find((task) => task.title === taskTitle);
      expect(beforeTask?.is_verified).toBe(0);

      await page.goto("/agriculture");
      await page
        .getByRole("button", { name: new RegExp(`选择${productName} 已改`) })
        .click();
      const publicTask = page
        .getByTestId("agriculture-task-item")
        .filter({ hasText: taskTitle });
      await expect(publicTask).toBeVisible();
      await expect(publicTask).toContainText("约 ");
      await expect(
        page.getByText("本月已安排日期（依据公开技术资料编排，待复核）"),
      ).toBeVisible();

      await page.goto("/operator/farming");
      const liveRow = page
        .locator('[data-testid="operator-farming-task-row"]')
        .filter({ hasText: taskTitle });
      await liveRow.getByRole("button", { name: "标记已复核" }).click();
      await expect(liveRow).toContainText("已复核");
      await expect(liveRow).toContainText("operator_demo");

      let releaseOverdueRequest: (() => void) | null = null;
      let overdueRequestHeld = false;
      const overdueTasksRoute = "**/*";
      await page.context().route(overdueTasksRoute, async (route) => {
        const requestUrl = route.request().url();
        if (
          !requestUrl.includes("/api/operator/farming/tasks") ||
          !requestUrl.includes("overdue=1")
        ) {
          await route.continue();
          return;
        }
        overdueRequestHeld = true;
        await new Promise<void>((resolve) => {
          releaseOverdueRequest = resolve;
        });
        await route.continue();
      });
      const overdueFilter = page.getByLabel(
        "只看该重新核的（超 183 天或从未复核）",
      );
      await overdueFilter.check();
      await expect.poll(() => overdueRequestHeld).toBe(true);

      const publicAfter = await request.get(
        `/api/agriculture/calendar/${productId}?month=${month}`,
      );
      const afterTask = (
        (await publicAfter.json()) as { tasks: OperatorTask[] }
      ).tasks.find((task) => task.title === taskTitle);
      expect(afterTask?.is_verified).toBe(1);

      await overdueFilter.uncheck();
      await expect(liveRow).toBeVisible();
      const overdueResponse = page.waitForResponse(
        (response) =>
          response.url().includes("/api/operator/farming/tasks?overdue=1") &&
          response.request().method() === "GET",
      );
      releaseOverdueRequest?.();
      await overdueResponse;
      await expect(liveRow).toBeVisible();
      await page.context().unroute(overdueTasksRoute);

      page.once("dialog", (dialog) => dialog.accept());
      await liveRow.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveRow).toHaveCount(0);

      await deleteReferenceWithUi(page, "作物", `${productName} 已改`);
      await deleteReferenceWithUi(page, "来源登记", sourceKey);
      await deleteReferenceWithUi(page, "分类标签", categoryKey);
    } finally {
      await deleteWithApi(
        request,
        `/api/operator/farming/products/${productId}`,
        sessionId,
      );
      await deleteWithApi(
        request,
        `/api/operator/farming/sources/${sourceKey}`,
        sessionId,
      );
      await deleteWithApi(
        request,
        `/api/operator/farming/categories/${categoryKey}`,
        sessionId,
      );
    }
  });

  test("pest crops, sources, multi-value entries, images and review work end to end", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const cropId = `e2e_t20_pest_${stamp}`;
    const sourceKey = `E2E-T20-PEST-${stamp}`;
    const entryId = `e2e_t20_entry_${stamp}`;
    const cropName = `T20 速查作物 ${stamp}`;
    const disease = `T20 测试病害 ${stamp}`;

    try {
      await openOperator(page);
      await openOperatorSection(page, "病虫害知识", /\/operator\/pest$/);

      await createReference(page, "作物", "新建作物", {
        "作物 id": cropId,
        "作物名称": cropName,
        "图标": "🌱",
        "摘要": "T20 病虫害作物",
        "排序": "930",
      });
      await editReference(page, "作物", cropName, {
        "作物名称": `${cropName} 已改`,
      });

      await createReference(page, "来源登记", "新建来源", {
        "来源 key": sourceKey,
        "来源名称": `T20 病虫来源 ${stamp}`,
        "机构": "广东省农业农村厅",
        "文件类型": "病虫情报",
        "文号": "待核",
        "日期": "2026-01-01",
        "链接": "https://example.com/t20-pest",
        "排序": "931",
      });
      await editReference(page, "来源登记", sourceKey, {
        "机构": "T20 病虫修订机构",
      });

      await page.getByRole("button", { name: "新建条目" }).click();
      const entryDialog = page.getByTestId("operator-record-dialog");
      await entryDialog.getByLabel("条目 id", { exact: true }).fill(entryId);
      await entryDialog
        .getByLabel("作物", { exact: true })
        .selectOption({ label: `${cropName} 已改` });
      await entryDialog.getByLabel("病害名称", { exact: true }).fill(disease);
      await entryDialog.getByLabel("类型", { exact: true }).selectOption("disease");
      await entryDialog.getByLabel("别名", { exact: true }).fill("T20 别名");
      await entryDialog.getByLabel("病原", { exact: true }).fill("T20 病原");
      await entryDialog.getByLabel("受害部位", { exact: true }).fill("叶片");
      await entryDialog.getByLabel("危害程度", { exact: true }).fill("中等");
      await entryDialog.getByLabel("发生规律", { exact: true }).fill("T20 发生规律");
      await entryDialog.getByLabel("安全提示", { exact: true }).fill("T20 安全提示");
      await entryDialog
        .getByLabel("症状（一行一条）", { exact: true })
        .fill("T20 症状甲\nT20 症状乙");
      await entryDialog
        .getByLabel("防治方法（一行一条）", { exact: true })
        .fill("T20 防治甲");
      await entryDialog
        .getByLabel("预防措施（一行一条）", { exact: true })
        .fill("T20 预防甲");
      await entryDialog
        .getByLabel("登记药剂（一行一种）", { exact: true })
        .fill("T20 药剂甲");
      await entryDialog
        .getByLabel("用药参考表（一行一条，用 | 分隔）", { exact: true })
        .fill("T20 药剂乙 | 1000倍液 | 7 | 3");
      await entryDialog.getByRole("checkbox", { name: sourceKey }).check();
      await entryDialog.getByLabel("实拍图路径", { exact: true }).fill(
        "/images/pest/citrus_psyllid.jpg",
      );
      await entryDialog.getByLabel("图片署名", { exact: true }).fill("T20 测试署名");
      await entryDialog.getByLabel("图片授权", { exact: true }).fill("CC BY 4.0");
      await entryDialog.getByLabel("图片说明", { exact: true }).fill("T20 实拍图说明");
      await entryDialog
        .getByLabel("图片来源链接", { exact: true })
        .fill("https://example.com/t20-image");
      await entryDialog.getByLabel("拍摄日期", { exact: true }).fill("2026-01-02");
      await entryDialog.getByLabel("图片备注", { exact: true }).fill("T20 图片备注");
      await entryDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(entryDialog).toHaveCount(0);

      const entryRow = page
        .locator('[data-testid="operator-pest-entry-row"]')
        .filter({ hasText: disease });
      await expect(entryRow).toBeVisible();
      await expect(entryRow).toContainText("待复核");

      await entryRow.getByRole("button", { name: "编辑", exact: true }).click();
      const editDialog = page.getByTestId("operator-record-dialog");
      await expect(
        editDialog.getByLabel("症状（一行一条）", { exact: true }),
      ).toHaveValue(/T20 症状甲/);
      await editDialog
        .getByLabel("症状（一行一条）", { exact: true })
        .fill("T20 症状甲已改\nT20 症状乙");
      await editDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(editDialog).toHaveCount(0);

      const publicResponse = await request.get(
        `/api/agriculture/pest-knowledge?crop=${cropId}`,
      );
      expect(publicResponse.ok()).toBeTruthy();
      const publicEntry = (
        (await publicResponse.json()) as {
          entries: Array<{
            id: string;
            symptoms: string[];
            chem_table: Array<{ agent: string }>;
            image: { caption: string } | null;
            sources: Array<{ key: string }>;
            is_verified: number;
          }>;
        }
      ).entries.find((entry) => entry.id === entryId);
      expect(publicEntry?.symptoms).toEqual(["T20 症状甲已改", "T20 症状乙"]);
      expect(publicEntry?.chem_table[0]?.agent).toBe("T20 药剂乙");
      expect(publicEntry?.image?.caption).toBe("T20 实拍图说明");
      expect(publicEntry?.sources[0]?.key).toBe(sourceKey);
      expect(publicEntry?.is_verified).toBe(0);

      await page.goto("/agriculture");
      const search = page.getByLabel("搜索病虫害");
      await search.fill(disease);
      await expect(page.getByTestId("pest-card").filter({ hasText: disease })).toBeVisible();
      await page.getByTestId("pest-card").filter({ hasText: disease }).click();
      await expect(page.getByRole("dialog")).toContainText("T20 症状甲已改");
      await expect(page.getByRole("dialog")).toContainText("T20 实拍图说明");
      await expect(page.getByRole("dialog")).toContainText("尚未经农技人员逐条复核");

      await page.goto("/operator/pest");
      const liveEntry = page
        .locator('[data-testid="operator-pest-entry-row"]')
        .filter({ hasText: disease });
      await liveEntry.getByRole("button", { name: "标记已复核" }).click();
      await expect(liveEntry).toContainText("已复核");
      await expect(liveEntry).toContainText("operator_demo");

      await page
        .getByLabel("只看该重新核的（超 183 天或从未复核）")
        .check();
      await expect(liveEntry).toHaveCount(0);

      await page.getByLabel("只看该重新核的（超 183 天或从未复核）").uncheck();
      const verifiedRow = page
        .locator('[data-testid="operator-pest-entry-row"]')
        .filter({ hasText: disease });
      page.once("dialog", (dialog) => dialog.accept());
      await verifiedRow.getByRole("button", { name: "删除", exact: true }).click();
      await expect(verifiedRow).toHaveCount(0);

      await deleteReferenceWithUi(page, "作物", `${cropName} 已改`);
      await deleteReferenceWithUi(page, "来源登记", sourceKey);
    } finally {
      await deleteWithApi(
        request,
        `/api/operator/pest/crops/${cropId}`,
        sessionId,
      );
      await deleteWithApi(
        request,
        `/api/operator/pest/sources/${sourceKey}`,
        sessionId,
      );
    }
  });

  test("empty, failure and role-denial states are explicit", async ({
    page,
    request,
  }) => {
    await openOperator(page);
    await page.route("**/api/operator/farming/tasks?overdue=1", (route) =>
      route.abort("connectionfailed"),
    );
    await page.getByRole("button", { name: "刷新统计" }).click();
    await expect(page.getByText("运营总览加载失败")).toBeVisible();
    await expect(page.getByRole("button", { name: "重试" })).toBeVisible();

    await page.unroute("**/api/operator/farming/tasks?overdue=1");
    await page.route("**/api/operator/farming/tasks", (route) =>
      route.fulfill({ json: { success: true, tasks: [] } }),
    );
    await openOperatorSection(page, "农时日历", /\/operator\/farming$/);
    await expect(page.getByText("暂无农事任务")).toBeVisible();

    await page.unroute("**/api/operator/farming/tasks");
    await page.route("**/api/operator/pest/entries", (route) =>
      route.fulfill({ json: { success: true, entries: [] } }),
    );
    await openOperatorSection(page, "病虫害知识", /\/operator\/pest$/);
    await expect(page.getByText("暂无病虫害条目")).toBeVisible();

    await signIn(page, "student_demo", "123456");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await page.goto("/operator/pest");
    await expect(page).toHaveURL(/\/agriculture\/?$/);

    for (const role of [
      "student",
      "teacher",
      "enterprise",
      "government",
    ] as const) {
      await expectApiDenied(
        request,
        ROLE_ACCOUNTS[role],
        rolePortal("operator").api,
      );
    }
  });
});
