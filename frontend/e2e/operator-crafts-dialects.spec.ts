import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { signIn } from "./auth-route";

const OPERATOR = { username: "operator_demo", password: "123456" };

async function loginWithRequest(
  request: APIRequestContext,
  username = OPERATOR.username,
  password = OPERATOR.password,
): Promise<string> {
  const response = await request.post("/api/auth/login", {
    data: { username, password },
  });
  expect(response.ok()).toBeTruthy();
  return ((await response.json()) as { session_id: string }).session_id;
}

function headers(sessionId: string): Record<string, string> {
  return { "X-Session-Id": sessionId };
}

async function openOperator(page: Page): Promise<void> {
  await signIn(page, OPERATOR.username, OPERATOR.password);
  await expect(page).toHaveURL(/\/operator\/overview$/);
}

async function openSection(
  page: Page,
  label: "手工技艺" | "方言知识",
  path: RegExp,
): Promise<void> {
  await page
    .getByRole("navigation", { name: "后台导航" })
    .getByRole("link", { name: label })
    .click();
  await expect(page).toHaveURL(path);
}

async function fillDialog(
  page: Page,
  values: Record<string, string>,
): Promise<void> {
  const dialog = page.getByTestId("operator-record-dialog");
  await expect(dialog).toBeVisible();
  for (const [label, value] of Object.entries(values)) {
    await dialog.getByLabel(label, { exact: true }).fill(value);
  }
  await dialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(dialog).toHaveCount(0);
}

async function createCraftStep(
  page: Page,
  title: string,
  sortOrder: number,
): Promise<void> {
  await page.getByRole("button", { name: "新建步骤" }).click();
  await fillDialog(page, {
    步骤标题: title,
    步骤说明: `${title} 说明`,
    操作提示: `${title} 提示`,
    排序: String(sortOrder),
  });
}

test.describe("operator crafts and dialects", () => {
  test.describe.configure({ timeout: 60_000 });

  test("operator opens the crafts maintenance workspace", async ({ page }) => {
    await openOperator(page);
    await openSection(page, "手工技艺", /\/operator\/crafts$/);
    await expect(page.getByTestId("operator-crafts")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "新建技艺" }),
    ).toBeVisible();
  });

  test("crafts, ordered steps, purchase guide and videos stay in sync with the public page", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const craftId = `e2e_t21_craft_${stamp}`;
    const craftName = `T21 测试技艺 ${stamp}`;
    const categoryKey = `t21_tools_${stamp}`;
    const stepA = `T21 步骤甲 ${stamp}`;
    const stepB = `T21 步骤乙 ${stamp}`;
    const stepAChanged = `${stepA} 已改`;
    const itemName = `T21 材料 ${stamp}`;
    const itemChanged = `${itemName} 已改`;
    const videoTitle = `T21 视频 ${stamp}`;
    const videoChanged = `${videoTitle} 已改`;

    try {
      await openOperator(page);
      await openSection(page, "手工技艺", /\/operator\/crafts$/);

      await page.getByRole("button", { name: "新建技艺" }).click();
      await fillDialog(page, {
        "技艺 id": craftId,
        技艺名称: craftName,
        产地: "广州",
        等级: "入门",
        排序: "980",
        历史沿革: "T21 技艺历史",
      });
      const craftRow = page
        .locator('[data-testid="operator-craft-row"]')
        .filter({ hasText: craftName });
      await expect(craftRow).toBeVisible();

      await createCraftStep(page, stepB, 20);
      await createCraftStep(page, stepA, 10);
      const stepRows = page.locator(
        '[data-testid="operator-craft-detail-row"]',
      );
      await expect(stepRows.first()).toContainText(stepA);
      await expect(stepRows.nth(1)).toContainText(stepB);

      await page.getByRole("tab", { name: "采购分类", exact: true }).click();
      await page.getByRole("button", { name: "新建采购分类" }).click();
      await fillDialog(page, {
        "分类 key": categoryKey,
        分类标签: `T21 工具 ${stamp}`,
        分类说明: "T21 分类说明",
        排序: "10",
      });

      await page.getByRole("tab", { name: "采购条目", exact: true }).click();
      await page.getByRole("button", { name: "新建采购条目" }).click();
      const itemDialog = page.getByTestId("operator-record-dialog");
      await itemDialog
        .getByLabel("所属分类", { exact: true })
        .selectOption(categoryKey);
      await itemDialog.getByLabel("物品名称", { exact: true }).fill(itemName);
      await itemDialog.getByLabel("价格", { exact: true }).fill("10-20 元");
      await itemDialog.getByLabel("规格说明", { exact: true }).fill("T21 规格");
      await itemDialog.getByLabel("避坑提示", { exact: true }).fill("T21 提示");
      await itemDialog.getByLabel("购买渠道", { exact: true }).fill("T21 渠道");
      await itemDialog.getByLabel("排序", { exact: true }).fill("10");
      await itemDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(itemDialog).toHaveCount(0);

      await page.getByRole("button", { name: "编辑预算" }).click();
      await fillDialog(page, {
        入门档预算: "100-150 元",
        进阶档预算: "300-400 元",
        采购建议: "T21 采购建议",
      });

      await page.getByRole("tab", { name: "视频", exact: true }).click();
      await page.getByRole("button", { name: "新建视频" }).click();
      await fillDialog(page, {
        bvid: `BV1T21${stamp}`,
        视频标题: videoTitle,
        "UP 主": "T21 UP 主",
        "时长（秒）": "125",
        播放量: "88",
        弹幕数: "6",
        点赞数: "9",
        排序: "10",
      });

      await page.getByRole("tab", { name: "步骤", exact: true }).click();
      const firstStepRow = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: stepA });
      await firstStepRow.getByRole("button", { name: "编辑", exact: true }).click();
      const stepDialog = page.getByTestId("operator-record-dialog");
      await stepDialog.getByLabel("步骤标题", { exact: true }).fill(stepAChanged);
      await stepDialog.getByLabel("排序", { exact: true }).fill("5");
      await stepDialog.getByRole("button", { name: "保存", exact: true }).click();
      await expect(stepDialog).toHaveCount(0);

      await page.getByRole("tab", { name: "采购条目", exact: true }).click();
      const itemRow = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: itemName });
      await itemRow.getByRole("button", { name: "编辑", exact: true }).click();
      const editItemDialog = page.getByTestId("operator-record-dialog");
      await editItemDialog
        .getByLabel("物品名称", { exact: true })
        .fill(itemChanged);
      await editItemDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(editItemDialog).toHaveCount(0);

      await page.getByRole("tab", { name: "视频", exact: true }).click();
      const videoRow = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: videoTitle });
      await videoRow.getByRole("button", { name: "编辑", exact: true }).click();
      const videoDialog = page.getByTestId("operator-record-dialog");
      await videoDialog
        .getByLabel("视频标题", { exact: true })
        .fill(videoChanged);
      await videoDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(videoDialog).toHaveCount(0);

      await page.goto("/crafts");
      const publicCraft = page
        .locator(
          `[data-testid="crafts-card"][data-craft-id="${craftId}"]`,
        );
      await expect(publicCraft).toBeVisible();
      await expect(publicCraft).toContainText(craftName);
      await publicCraft.click();
      await expect(
        page.getByTestId("crafts-step").filter({ hasText: stepAChanged }),
      ).toBeVisible();
      await expect(
        page
          .getByTestId("crafts-purchase-item")
          .filter({ hasText: itemChanged }),
      ).toBeVisible();
      await expect(page.getByText("100-150 元")).toBeVisible();
      await expect(page.getByText("T21 采购建议")).toBeVisible();
      const publicVideo = page
        .locator('[data-testid="crafts-video-card"]')
        .filter({ hasText: videoChanged });
      await expect(publicVideo).toBeVisible();
      await expect(publicVideo).toHaveAttribute("data-video-id", /.+/);

      const publicDetail = await request.get(
        `/api/crafts/${encodeURIComponent(craftId)}`,
      );
      expect(publicDetail.ok()).toBeTruthy();
      const detailBody = (await publicDetail.json()) as {
        data: {
          steps: Array<{ title: string }>;
          videos: Array<{ title: string }>;
          purchase_guide: {
            budget: { starter: string };
            categories: Array<{ items: Array<{ name: string }> }>;
          };
        };
      };
      expect(detailBody.data.steps.map((step) => step.title)).toEqual([
        stepAChanged,
        stepB,
      ]);
      expect(detailBody.data.videos[0]?.title).toBe(videoChanged);
      expect(detailBody.data.purchase_guide.budget.starter).toBe("100-150 元");
      expect(
        detailBody.data.purchase_guide.categories[0]?.items[0]?.name,
      ).toBe(itemChanged);

      await page.goto("/operator/crafts");
      const liveCraft = page
        .locator('[data-testid="operator-craft-row"]')
        .filter({ hasText: craftName });
      await liveCraft.getByRole("button", { name: "管理内容" }).click();
      await page.getByRole("tab", { name: "采购条目", exact: true }).click();
      const liveItem = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: itemChanged });
      page.once("dialog", (dialog) => dialog.accept());
      await liveItem.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveItem).toHaveCount(0);

      await page.getByRole("tab", { name: "采购分类", exact: true }).click();
      const categoryRow = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: categoryKey });
      page.once("dialog", (dialog) => dialog.accept());
      await categoryRow.getByRole("button", { name: "删除", exact: true }).click();
      await expect(categoryRow).toHaveCount(0);

      await page.getByRole("tab", { name: "视频", exact: true }).click();
      const liveVideo = page
        .locator('[data-testid="operator-craft-detail-row"]')
        .filter({ hasText: videoChanged });
      page.once("dialog", (dialog) => dialog.accept());
      await liveVideo.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveVideo).toHaveCount(0);

      page.once("dialog", (dialog) => dialog.accept());
      await liveCraft.getByRole("button", { name: "删除", exact: true }).click();
      await expect(liveCraft).toHaveCount(0);

      const publicList = await request.get("/api/crafts/list");
      const publicCrafts = ((await publicList.json()) as {
        crafts: Array<{ id: string }>;
      }).crafts;
      expect(publicCrafts.some((craft) => craft.id === craftId)).toBe(false);
    } finally {
      await request
        .delete(`/api/operator/crafts/${encodeURIComponent(craftId)}`, {
          headers: headers(sessionId),
        })
        .catch(() => undefined);
    }
  });

  test("dialects, ordered phrases and quick questions stay in sync with resources", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const dialectId = `e2e_t21_dialect_${stamp}`;
    const dialectName = `T21 测试方言 ${stamp}`;
    const dialectChanged = `${dialectName} 已改`;
    const phraseText = `T21 方言说法 ${stamp}`;
    const mandarinText = `T21 普通话 ${stamp}`;
    const questionA = `T21 快问甲 ${stamp}`;
    const questionB = `T21 快问乙 ${stamp}`;

    try {
      await openOperator(page);
      await openSection(page, "方言知识", /\/operator\/dialects$/);

      await page.getByRole("button", { name: "新建方言" }).click();
      await fillDialog(page, {
        "方言 id": dialectId,
        方言名称: dialectName,
        地区: "广东",
        图标: "🗣️",
        使用范围: "T21 使用范围",
        使用人数: "约 100 人",
        问候语: "你好",
        问候语意思: "T21 问候",
        "特色标签（一行一条）": "T21 特色甲\nT21 特色乙",
        排序: "990",
      });
      const dialectRow = page
        .locator('[data-testid="operator-dialect-row"]')
        .filter({ hasText: dialectName });
      await expect(dialectRow).toBeVisible();

      await page.getByRole("button", { name: "新建短语" }).click();
      await fillDialog(page, {
        方言说法: phraseText,
        普通话说法: mandarinText,
        拼音: "t21 pin yin",
        排序: "10",
      });

      await page.getByRole("tab", { name: "快捷问题", exact: true }).click();
      await page.getByRole("button", { name: "新建快捷问题" }).click();
      await fillDialog(page, { 快捷问题: questionB, 排序: "20" });
      await expect(
        page
          .locator('[data-testid="operator-dialect-detail-row"]')
          .filter({ hasText: questionB }),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "新建快捷问题" }),
      ).toBeEnabled();
      await page.getByRole("button", { name: "新建快捷问题" }).click();
      await fillDialog(page, { 快捷问题: questionA, 排序: "10" });
      const questionRows = page.locator(
        '[data-testid="operator-dialect-detail-row"]',
      );
      await expect(questionRows.first()).toContainText(questionA);
      await expect(questionRows.nth(1)).toContainText(questionB);

      await dialectRow.getByRole("button", { name: "编辑", exact: true }).click();
      const dialectDialog = page.getByTestId("operator-record-dialog");
      await dialectDialog
        .getByLabel("方言名称", { exact: true })
        .fill(dialectChanged);
      await dialectDialog
        .getByLabel("特色标签（一行一条）", { exact: true })
        .fill("T21 特色甲已改");
      await dialectDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(dialectDialog).toHaveCount(0);

      await page.getByRole("tab", { name: "短语", exact: true }).click();
      const phraseRow = page
        .locator('[data-testid="operator-dialect-detail-row"]')
        .filter({ hasText: mandarinText });
      await phraseRow.getByRole("button", { name: "编辑", exact: true }).click();
      const phraseDialog = page.getByTestId("operator-record-dialog");
      await phraseDialog
        .getByLabel("普通话说法", { exact: true })
        .fill(`${mandarinText} 已改`);
      await phraseDialog
        .getByRole("button", { name: "保存", exact: true })
        .click();
      await expect(phraseDialog).toHaveCount(0);

      await page.goto("/resources");
      const publicDialect = page
        .getByTestId("dialect-card")
        .filter({ hasText: dialectChanged });
      await expect(publicDialect).toBeVisible();
      await publicDialect.click();
      await expect(page.getByTestId("dialect-greeting")).toContainText("你好");
      await expect(
        page
          .getByTestId("dialect-phrase")
          .filter({ hasText: `${mandarinText} 已改` }),
      ).toBeVisible();
      await expect(page.getByText("T21 特色甲已改")).toBeVisible();
      await expect(
        page.getByTestId("dialect-quick-question").filter({ hasText: questionA }),
      ).toBeVisible();
      const publicQuestions = page.getByTestId("dialect-quick-question");
      await expect(publicQuestions.first()).toContainText(questionA);
      await expect(publicQuestions.nth(1)).toContainText(questionB);

      await page.goto("/operator/dialects");
      const liveDialect = page
        .locator('[data-testid="operator-dialect-row"]')
        .filter({ hasText: dialectChanged });
      await liveDialect.getByRole("button", { name: "管理内容" }).click();
      await page.getByRole("tab", { name: "快捷问题", exact: true }).click();
      const liveQuestion = page
        .locator('[data-testid="operator-dialect-detail-row"]')
        .filter({ hasText: questionA });
      page.once("dialog", (dialog) => dialog.accept());
      await liveQuestion
        .getByRole("button", { name: "删除", exact: true })
        .click();
      await expect(liveQuestion).toHaveCount(0);

      await page.getByRole("tab", { name: "短语", exact: true }).click();
      const livePhrase = page
        .locator('[data-testid="operator-dialect-detail-row"]')
        .filter({ hasText: `${mandarinText} 已改` });
      page.once("dialog", (dialog) => dialog.accept());
      await livePhrase.getByRole("button", { name: "删除", exact: true }).click();
      await expect(livePhrase).toHaveCount(0);

      page.once("dialog", (dialog) => dialog.accept());
      await liveDialect
        .getByRole("button", { name: "删除", exact: true })
        .click();
      await expect(liveDialect).toHaveCount(0);
    } finally {
      await request
        .delete(`/api/operator/dialects/${encodeURIComponent(dialectId)}`, {
          headers: headers(sessionId),
        })
        .catch(() => undefined);
    }
  });

  test("empty, failure and role-denial states stay explicit", async ({
    page,
    request,
  }) => {
    await openOperator(page);
    await page.route("**/api/operator/crafts", (route) =>
      route.fulfill({
        json: { success: true, crafts: [] },
      }),
    );
    await openSection(page, "手工技艺", /\/operator\/crafts$/);
    await expect(page.getByText("暂无手工技艺")).toBeVisible();
    await page.unroute("**/api/operator/crafts");

    await page.route("**/api/operator/dialects", (route) =>
      route.abort("connectionfailed"),
    );
    await page
      .getByRole("navigation", { name: "后台导航" })
      .getByRole("link", { name: "方言知识" })
      .click();
    await expect(page.getByText("方言知识加载失败")).toBeVisible();
    await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
    await page.unroute("**/api/operator/dialects");

    await page.goto("/operator/crafts");
    await page.getByRole("tab", { name: "步骤", exact: true }).click();
    const firstStep = page
      .locator('[data-testid="operator-craft-detail-row"]')
      .first();
    await expect(firstStep).toBeVisible();
    const originalText = await firstStep.textContent();
    await firstStep.getByRole("button", { name: "编辑", exact: true }).click();
    const dialog = page.getByTestId("operator-record-dialog");
    await dialog.getByLabel("步骤标题", { exact: true }).fill("不应写入的标题");
    await page.route("**/api/operator/crafts/steps/*", (route) =>
      route.fulfill({
        status: 500,
        json: { success: false, message: "模拟保存失败" },
      }),
    );
    await dialog.getByRole("button", { name: "保存", exact: true }).click();
    await expect(page.getByTestId("operator-dialog-error")).toContainText(
      "模拟保存失败",
    );
    await dialog.getByRole("button", { name: "取消", exact: true }).click();
    await expect(firstStep).toHaveText(originalText ?? "");
    await page.unroute("**/api/operator/crafts/steps/*");

    const deniedAccounts = [
      { username: "student_demo", password: "123456" },
      { username: "teacher_demo", password: "123456" },
      { username: "enterprise_demo", password: "123456" },
      { username: "gov_demo", password: "123456" },
    ];
    for (const account of deniedAccounts) {
      const sessionId = await loginWithRequest(
        request,
        account.username,
        account.password,
      );
      for (const path of ["/api/operator/crafts", "/api/operator/dialects"]) {
        const denied = await request.get(path, {
          headers: headers(sessionId),
        });
        expect(denied.status()).toBe(403);
      }
    }

    const adminSession = await loginWithRequest(
      request,
      "admin_demo",
      "admin123",
    );
    for (const path of ["/api/operator/crafts", "/api/operator/dialects"]) {
      const allowed = await request.get(path, {
        headers: headers(adminSession),
      });
      expect(allowed.status()).toBe(200);
    }
  });
});
