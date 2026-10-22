import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";

interface StoredSession {
  sessionId: string;
}

async function storedSessionId(page: Page): Promise<string> {
  const session = await page.evaluate(() => {
    const raw = localStorage.getItem("yuexiang_session");
    return raw ? (JSON.parse(raw) as StoredSession) : null;
  });
  expect(session?.sessionId).toBeTruthy();
  return session!.sessionId;
}

async function recordsFor(
  page: Page,
  kind: "live" | "copy" | "cs",
): Promise<Array<{ product?: string; attempts?: number; rule_score?: number }>> {
  const sessionId = await storedSessionId(page);
  const response = await page.request.get(
    `/api/ecommerce/live/records?kind=${kind}`,
    { headers: { "X-Session-Id": sessionId } },
  );
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as {
    records: Array<{
      product?: string;
      attempts?: number;
      rule_score?: number;
    }>;
  };
  return payload.records;
}

async function waitForCdnState(page: Page): Promise<void> {
  await page.waitForFunction(
    () => {
      const dataset = document.documentElement.dataset;
      return (
        dataset.cdnFontAwesome !== undefined &&
        dataset.cdnModelViewer !== undefined
      );
    },
    undefined,
    { timeout: 15_000 },
  );
  await page.waitForFunction(() => document.fonts.status === "loaded", undefined, {
    timeout: 15_000,
  });
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
      }),
  );
}

test.describe("ecommerce AI training", () => {
  test("three tools generate, score, submit and reload their own history", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await signIn(page, "student_demo", "123456");
    await expect(page).toHaveURL(/\/agriculture\/?$/, { timeout: 15_000 });
    await page.goto("/ecommerce");

    await expect(
      page.getByRole("heading", { name: "电商运营实训" }),
    ).toBeVisible();

    const live = page.getByTestId("live-script-training");
    await live.getByLabel("直播产品").selectOption("龙眼");
    await live.getByRole("button", { name: "专业型" }).click();
    const liveGenerated = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/script") &&
        response.request().method() === "POST",
    );
    await live.getByRole("button", { name: "生成 AI 初稿" }).click();
    expect((await liveGenerated).status()).toBe(200);
    await expect(live.getByTestId("live-degraded")).toContainText("非 AI 生成");
    await expect(live.getByTestId("live-generated-script")).toContainText("龙眼");

    await live
      .getByLabel("直播话术我的稿")
      .fill(
        "家人们看过来！这是广东产地直发的龙眼，果肉饱满，欢迎扣1。\n"
        + "具体价格与优惠以店铺实际活动为准。",
      );
    const liveScore = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/feedback") &&
        response.request().method() === "POST",
    );
    await live.getByRole("button", { name: "评分我的话术" }).click();
    expect((await liveScore).status()).toBe(200);
    await expect(live.getByTestId("live-score-overall")).not.toHaveText("-");

    const liveSubmit = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/live/submit") &&
        response.request().method() === "POST",
    );
    await live.getByRole("button", { name: "提交直播实训" }).click();
    const liveSubmitResponse = await liveSubmit;
    expect(liveSubmitResponse.status()).toBe(200);
    await expect(live.getByTestId("live-status")).toContainText(
      "已保存实训记录",
    );
    await expect(live.getByTestId("live-records")).toContainText("龙眼");
    expect(
      (await recordsFor(page, "live")).some(
        (record) => record.product === "龙眼" && (record.attempts ?? 0) > 0,
      ),
    ).toBe(true);

    const copy = page.getByTestId("copywriting-training");
    await copy.getByRole("button", { name: "小红书" }).click();
    const copyGenerated = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/copywriting") &&
        response.request().method() === "POST",
    );
    await copy.getByRole("button", { name: "AI生成文案" }).click();
    expect((await copyGenerated).status()).toBe(200);
    await expect(copy.getByTestId("copywriting-degraded")).toContainText("非 AI 生成");
    await expect(copy.getByTestId("copywriting-result")).toContainText("荔枝");
    await copy.getByRole("button", { name: "采用到我的稿" }).click();
    await copy
      .getByLabel("文案我的稿")
      .fill(
        "## 岭南荔枝\n\n产地直发，果肉饱满，汁水充足。\n"
        + "冷链配送，具体规格与价格以店铺页面为准。",
      );
    const copyScore = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/copy/feedback") &&
        response.request().method() === "POST",
    );
    await copy.getByRole("button", { name: "评分我的文案" }).click();
    expect((await copyScore).status()).toBe(200);
    await expect(copy.getByTestId("copywriting-score-overall")).not.toHaveText("-");

    const copySubmit = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/copy/submit") &&
        response.request().method() === "POST",
    );
    await copy.getByRole("button", { name: "提交文案实训" }).click();
    expect((await copySubmit).status()).toBe(200);
    await expect(copy.getByTestId("copywriting-status")).toContainText(
      "已保存实训记录",
    );
    await expect(copy.getByTestId("copywriting-records")).toContainText("荔枝");
    expect(
      (await recordsFor(page, "copy")).some(
        (record) => record.product === "荔枝" && (record.attempts ?? 0) > 0,
      ),
    ).toBe(true);

    const service = page.getByTestId("customer-service-training");
    const nextCustomer = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/customer-service/next") &&
        response.request().method() === "POST",
    );
    await service.getByRole("button", { name: "开始模拟" }).click();
    expect((await nextCustomer).status()).toBe(200);
    await expect(service.getByTestId("customer-service-degraded")).toContainText("非 AI 生成");
    await expect(service.getByTestId("customer-service-messages")).toContainText("荔枝");

    await service
      .getByLabel("客服回复", { exact: true })
      .fill("您好，我们的荔枝产地直发，甜度和规格都不错。");
    const customerReply = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/customer-service") &&
        response.request().method() === "POST",
    );
    await service.getByRole("button", { name: "发送客服回复" }).click();
    expect((await customerReply).status()).toBe(200);
    await expect(service.getByTestId("customer-service-messages")).toContainText("你（客服）");
    await expect(service.getByTestId("customer-service-score-overall")).not.toHaveText("-");

    const hint = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/customer-service/hint") &&
        response.request().method() === "POST",
    );
    await service.getByRole("button", { name: "获取客服提示" }).click();
    expect((await hint).status()).toBe(200);
    await expect(service.getByTestId("customer-service-hint")).toContainText("话术参考");
    await expect(service.getByTestId("customer-service-hint")).toContainText("非 AI 生成");

    const serviceSubmit = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/ecommerce/cs/submit") &&
        response.request().method() === "POST",
    );
    await service.getByRole("button", { name: "提交客服实训" }).click();
    expect((await serviceSubmit).status()).toBe(200);
    await expect(service.getByTestId("customer-service-status")).toContainText(
      "已保存实训记录",
    );
    await expect(service.getByTestId("customer-service-records")).toContainText("荔枝");
    expect(
      (await recordsFor(page, "cs")).some(
        (record) => record.product === "荔枝" && (record.attempts ?? 0) > 0,
      ),
    ).toBe(true);
  });

  test("empty input, unavailable AI and network failure stay visibly distinct", async ({
    page,
  }) => {
    await page.goto("/ecommerce");

    const live = page.getByTestId("live-script-training");
    await live.getByRole("button", { name: "提交直播实训" }).click();
    await expect(live.getByTestId("live-status")).toContainText(
      "请先写出你的直播话术",
    );

    await page.route("**/api/ecommerce/script", (route) =>
      route.fulfill({
        status: 503,
        json: {
          success: false,
          code: "ai_unavailable",
          message: "AI 服务暂时不可用",
        },
      }),
    );
    await live.getByRole("button", { name: "生成 AI 初稿" }).click();
    await expect(live.getByTestId("live-status")).toContainText(
      "AI 服务暂时不可用",
    );
    await expect(live.getByTestId("live-generated-script")).toHaveCount(0);

    const copy = page.getByTestId("copywriting-training");
    await copy.getByLabel("文案产品名称").fill("");
    await copy.getByRole("button", { name: "AI生成文案" }).click();
    await expect(copy.getByTestId("copywriting-status")).toContainText(
      "请输入产品名称",
    );

    await page.route("**/api/ecommerce/copywriting", (route) => route.abort());
    await copy.getByLabel("文案产品名称").fill("荔枝");
    await copy.getByRole("button", { name: "AI生成文案" }).click();
    await expect(copy.getByTestId("copywriting-status")).toContainText(
      "无法连接服务",
    );
    await expect(copy.getByTestId("copywriting-result")).toHaveCount(0);
  });

  test("desktop training layouts keep their legacy visual structure", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/ecommerce");
    await expect(
      page.getByRole("heading", { name: "电商运营实训" }),
    ).toBeVisible();
    await waitForCdnState(page);
    await page.addStyleTag({
      content: ".navbar { position: absolute !important; }",
    });

    await expect(page.getByTestId("live-script-training")).toHaveScreenshot(
      "ecommerce-live-script.png",
    );
    await expect(page.getByTestId("copywriting-training")).toHaveScreenshot(
      "ecommerce-copywriting.png",
    );
    await expect(page.getByTestId("customer-service-training")).toHaveScreenshot(
      "ecommerce-customer-service.png",
    );
  });
});
