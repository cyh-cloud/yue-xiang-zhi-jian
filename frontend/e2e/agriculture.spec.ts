import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";

const STUDENT = { username: "student_demo", password: "123456" };

async function sessionId(page: Page): Promise<string> {
  return page.evaluate(() => {
    const raw = localStorage.getItem("yuexiang_session");
    if (!raw) throw new Error("missing stored session");
    const stored = JSON.parse(raw) as { sessionId?: unknown };
    if (typeof stored.sessionId !== "string" || !stored.sessionId) {
      throw new Error("stored session has no sessionId");
    }
    return stored.sessionId;
  });
}

async function requestSession(page: Page): Promise<string> {
  const response = await page.request.post("/api/auth/login", {
    data: STUDENT,
  });
  expect(response.ok()).toBe(true);
  const payload = (await response.json()) as { session_id: string };
  return payload.session_id;
}

async function clearSubscription(
  page: Page,
  sid: string,
  productId: string,
): Promise<void> {
  const response = await page.request.delete(
    `/api/agriculture/subscribe/${productId}`,
    { headers: { "X-Session-Id": sid } },
  );
  expect(response.ok()).toBe(true);
}

test.describe("agriculture calendar", () => {
  test("anonymous visitors can inspect the calendar, phenophase, tasks and date basis", async ({
    page,
  }) => {
    await page.goto("/agriculture");

    await expect(
      page.getByRole("heading", { name: "智能农业技能培训" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^选择荔枝/ }),
    ).toBeVisible();
    await expect(page.getByTestId("agriculture-month")).toHaveText(/\d{1,2}月/);
    await expect(page.getByText(/当前物候期/)).toBeVisible();

    const calendarResponse = await page.request.get(
      "/api/agriculture/calendar/lychee",
    );
    expect(calendarResponse.ok()).toBe(true);
    const calendar = (await calendarResponse.json()) as {
      month: number;
      tasks: Array<{ id: number; title: string; day: number | null }>;
      sources_all: unknown[];
    };
    expect(calendar.tasks.length).toBeGreaterThan(0);

    await page.getByRole("button", { name: /展开.*详情/ }).first().click();
    await expect(page.getByText("日期依据").first()).toBeVisible();

    if (calendar.sources_all.length > 0) {
      await page.getByRole("button", { name: /查看数据依据/ }).click();
      await expect(page.locator(".fdn-sources")).toBeVisible();
    }

    const datedTask = calendar.tasks.find((task) => task.day !== null);
    expect(datedTask).toBeTruthy();
    if (datedTask) {
      await page
        .getByRole("button", {
          name: new RegExp(`^${datedTask.day}日，\\d+项农事$`),
        })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(dialog).toBeVisible();
      await expect(dialog).toContainText(datedTask.title);
      await dialog.getByRole("button", { name: "关闭" }).click();
      await expect(dialog).toBeHidden();
    }

    const riceResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agriculture/calendar/rice") &&
        response.request().method() === "GET",
    );
    await page.getByRole("button", { name: /^选择水稻/ }).click();
    expect((await riceResponse).ok()).toBe(true);
    await expect(
      page.getByRole("button", { name: /^选择水稻/ }),
    ).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  test("an empty month distinguishes missing tasks from a broken calendar", async ({
    page,
  }) => {
    await page.route("**/api/agriculture/calendar/**", (route) =>
      route.fulfill({
        json: {
          success: true,
          product: { id: "lychee", name: "荔枝", icon: "apple-alt" },
          year: 2026,
          month: 3,
          is_configured: false,
          dates_provisional: false,
          source_summary: {
            total: 0,
            verified: 0,
            sourced: 0,
            unsourced: 0,
            sources: [],
          },
          sources_all: [],
          phenophase_current: null,
          phenophases: [],
          solar_terms: [],
          tasks: [],
        },
      }),
    );

    await page.goto("/agriculture");

    await expect(page.getByTestId("agriculture-month")).toHaveText("3月");
    await expect(page.getByText("本月暂无农事数据")).toBeVisible();
    await expect(page.getByText("本月无固定日期农事")).toBeHidden();
  });

  test("anonymous subscription asks for login instead of failing silently", async ({
    page,
  }) => {
    await page.goto("/agriculture");

    await page.getByRole("button", { name: "订阅本作物" }).click();

    await expect(page.getByText("请先登录后再订阅农事提醒")).toBeVisible();
    await expect(page.getByRole("link", { name: "去登录" })).toHaveAttribute(
      "href",
      "/login?redirect=/agriculture",
    );
  });

  test("subscription survives reload and can be cancelled", async ({ page }) => {
    const sid = await requestSession(page);
    await clearSubscription(page, sid, "lychee");

    await signIn(page, STUDENT.username, STUDENT.password);
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page.getByRole("button", { name: "订阅本作物" })).toBeVisible();

    await page.getByRole("button", { name: "订阅本作物" }).click();
    await expect(page.getByRole("button", { name: "已订阅" })).toBeVisible();
    await expect(page.getByText(/已订阅「荔枝」/)).toBeVisible();

    await page.reload();
    await expect(page.getByRole("button", { name: "已订阅" })).toBeVisible();

    await page.getByRole("button", { name: "已订阅" }).click();
    await expect(page.getByRole("button", { name: "订阅本作物" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("button", { name: "订阅本作物" })).toBeVisible();
  });

  test("a logged-in visit checks due reminders and creates a farming notification", async ({
    page,
  }) => {
    const sid = await requestSession(page);
    const productsResponse = await page.request.get("/api/agriculture/products");
    expect(productsResponse.ok()).toBe(true);
    const products = (await productsResponse.json()) as {
      products: Array<{ id: string }>;
    };
    const today = new Date();
    let dueProductId = "";
    for (const product of products.products) {
      const calendarResponse = await page.request.get(
        `/api/agriculture/calendar/${encodeURIComponent(product.id)}?month=${today.getMonth() + 1}`,
      );
      if (!calendarResponse.ok()) continue;
      const calendar = (await calendarResponse.json()) as {
        tasks: Array<{ day: number | null }>;
      };
      if (
        calendar.tasks.some(
          (task) => task.day !== null && task.day <= today.getDate(),
        )
      ) {
        dueProductId = product.id;
        break;
      }
    }
    expect(dueProductId, "当前月份没有已到期的农事任务").toBeTruthy();

    await clearSubscription(page, sid, dueProductId);
    const subscribed = await page.request.post("/api/agriculture/subscribe", {
      headers: { "X-Session-Id": sid },
      data: { product_id: dueProductId },
    });
    expect(subscribed.ok()).toBe(true);

    const reminderResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/agriculture/reminders/check") &&
        response.request().method() === "POST",
    );
    await signIn(page, STUDENT.username, STUDENT.password);
    expect((await reminderResponse).ok()).toBe(true);

    const browserSessionId = await sessionId(page);
    await expect
      .poll(async () => {
        const response = await page.request.get(
          `/api/notifications?user_id=${STUDENT.username}`,
          { headers: { "X-Session-Id": browserSessionId } },
        );
        if (!response.ok()) return [];
        const payload = (await response.json()) as {
          notifications: Array<{
            type: string;
            link_type: string;
            link_id: string;
          }>;
        };
        return payload.notifications
          .filter(
            (item) =>
              item.type === "farming_reminder" &&
              item.link_type === "farming" &&
              item.link_id === dueProductId,
          )
          .map((item) => item.link_id);
      })
      .toContain(dueProductId);
  });

  test("desktop agriculture visual baseline stays stable", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/agriculture/products", (route) =>
      route.fulfill({
        json: {
          success: true,
          products: [
            { id: "lychee", name: "荔枝", icon: "apple-alt", desc: "广东特色水果" },
            { id: "longan", name: "龙眼", icon: "circle", desc: "岭南佳果" },
            { id: "citrus", name: "柑橘", icon: "lemon", desc: "广东大宗水果" },
            { id: "banana", name: "香蕉", icon: "leaf", desc: "岭南特色蕉类" },
            { id: "aquatic", name: "水产养殖", icon: "fish", desc: "鱼虾蟹贝" },
            { id: "rice", name: "水稻", icon: "seedling", desc: "主要粮食作物" },
            { id: "tea", name: "茶叶", icon: "mug-hot", desc: "广东名茶" },
            { id: "vegetable", name: "蔬菜", icon: "carrot", desc: "时令蔬菜" },
          ],
        },
      }),
    );
    await page.route("**/api/agriculture/calendar/**", (route) =>
      route.fulfill({
        json: {
          success: true,
          product: { id: "lychee", name: "荔枝", icon: "apple-alt" },
          year: 2026,
          month: 3,
          is_configured: true,
          dates_provisional: true,
          source_summary: {
            total: 2,
            verified: 0,
            sourced: 2,
            unsourced: 0,
            sources: [],
          },
          sources_all: [
            {
              key: "CARS-LZ",
              name: "荔枝龙眼产业技术体系",
              org: "国家荔枝龙眼产业技术体系",
              doc_type: "技术资料",
              doc_no: "待核",
              url: "",
            },
          ],
          phenophase_current: {
            id: 182,
            name: "花期",
            color: "#d9a227",
            description: "花穗抽发与开花期，重点保花保果",
          },
          phenophases: [
            {
              id: 182,
              name: "花期",
              start_month: 2,
              end_month: 3,
              color: "#d9a227",
              description: "花穗抽发与开花期，重点保花保果",
              in_month: true,
            },
          ],
          solar_terms: [
            { date: "2026-03-05", day: 5, name: "惊蛰" },
            { date: "2026-03-20", day: 20, name: "春分" },
          ],
          tasks: [
            {
              id: 435,
              date: "2026-03-15",
              day: 15,
              task_md: "03-15",
              title: "花期管理",
              category: "manage",
              category_label: "田间管理",
              priority: "high",
              icon: "spa",
              description: "疏花并关注花穗生长，减少无效花量。",
              tip: "花期谨慎使用农药，优先保护授粉昆虫。",
              phase_id: 182,
              phase_name: "花期",
              phase_color: "#d9a227",
              sort_order: 1,
              is_verified: 0,
              evidence_level: "sourced",
              date_basis: "谢花前后结合花穗状态安排，避免盛花期施药。",
              source: {
                key: "CARS-LZ",
                name: "荔枝龙眼产业技术体系",
                org: "国家荔枝龙眼产业技术体系",
                doc_type: "技术资料",
                doc_no: "待核",
                url: "",
              },
            },
            {
              id: 436,
              date: "2026-03-28",
              day: 28,
              task_md: "03-28",
              title: "谢花后补肥",
              category: "fertilize",
              category_label: "施肥",
              priority: "medium",
              icon: "hand-holding-heart",
              description: "补充树体营养，帮助幼果稳果。",
              tip: "薄肥勤施，避免一次施用过量。",
              phase_id: 182,
              phase_name: "花期",
              phase_color: "#d9a227",
              sort_order: 2,
              is_verified: 0,
              evidence_level: "sourced",
              date_basis: "谢花后树体营养消耗较大，应在幼果期及时补充。",
              source: {
                key: "CARS-LZ",
                name: "荔枝龙眼产业技术体系",
                org: "国家荔枝龙眼产业技术体系",
                doc_type: "技术资料",
                doc_no: "待核",
                url: "",
              },
            },
          ],
        },
      }),
    );

    await page.goto("/agriculture");
    await expect(page.getByTestId("agriculture-month")).toHaveText("3月");
    await expect(page.getByText("花期管理")).toBeVisible();
    await expect(page.getByTestId("pest-card").first()).toBeVisible();
    await page.waitForFunction(
      () =>
        document.documentElement.dataset.cdnFontAwesome !== undefined &&
        document.documentElement.dataset.cdnModelViewer !== undefined,
    );
    await page.waitForFunction(() =>
      Array.from(document.images).every((image) => image.complete),
    );
    await page.evaluate(() => document.fonts.ready);

    await expect(page).toHaveScreenshot("agriculture-anonymous-light.png", {
      fullPage: true,
    });
  });
});

test.describe("agriculture AI and pest knowledge", () => {
  test("AI answer renders streamed content, completion and follow-up suggestions", async ({
    page,
  }) => {
    let requestBody: unknown = null;
    await page.route("**/api/agriculture/ask/stream", async (route) => {
      requestBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "text/event-stream; charset=utf-8",
          "Cache-Control": "no-cache",
        },
        body: [
          'data: {"content":"先检查叶片背面，"}\n\n',
          'data: {"content":"重点看虫口密度。"}\n\n',
          "event: done\ndata: [DONE]\n\n",
          'event: suggestions\ndata: {"suggestions":["如何判断虫口密度？","什么时候防治更合适？"]}\n\n',
        ].join(""),
      });
    });
    await page.route("**/api/agriculture/suggestions?**", (route) =>
      route.fulfill({ json: { success: true, suggestions: [] } }),
    );

    await page.goto("/agriculture");
    await page.getByLabel("输入你的农业问题").fill("荔枝叶片背面有虫怎么办？");
    await page.getByRole("button", { name: "发送" }).click();

    await expect(page.getByTestId("qa-answer")).toContainText(
      "先检查叶片背面，重点看虫口密度。",
    );
    await expect(page.getByText("回答完成")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "如何判断虫口密度？" }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "什么时候防治更合适？" }),
    ).toBeVisible();
    expect(requestBody).toMatchObject({
      product: "lychee",
      question: "荔枝叶片背面有虫怎么办？",
    });
  });

  test("AI unavailable is shown as an error and never becomes a fake answer", async ({
    page,
  }) => {
    const streamRequest = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/agriculture/ask/stream") &&
        request.method() === "POST",
    );

    await page.goto("/agriculture");
    await page.getByLabel("输入你的农业问题").fill("荔枝叶子发黄怎么办？");
    await page.getByRole("button", { name: "发送" }).click();

    await streamRequest;
    await expect(page.getByRole("alert")).toContainText(
      "AI 农技问答尚未启用",
    );
    await expect(page.getByTestId("qa-answer")).toHaveCount(0);
  });

  test("pest knowledge filters and paginates on the server", async ({ page }) => {
    const fullResponse = await page.request.get(
      "/api/agriculture/pest-knowledge?limit=10",
    );
    expect(fullResponse.ok()).toBe(true);
    const full = (await fullResponse.json()) as {
      total: number;
      entries: Array<{ id: string; disease: string; crop: string }>;
    };
    expect(full.total).toBeGreaterThan(10);

    const initialResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agriculture/pest-knowledge") &&
        response.url().includes("limit=10") &&
        !response.url().includes("crop="),
    );
    await page.goto("/agriculture");
    await expect(
      page.getByRole("heading", { name: "常见病虫害速查" }),
    ).toBeVisible();
    expect((await initialResponse).ok()).toBe(true);
    await expect(page.getByText(`第 1 / ${Math.ceil(full.total / 10)} 页`)).toBeVisible();

    const nextResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agriculture/pest-knowledge") &&
        response.url().includes("offset=10"),
    );
    await page.getByRole("button", { name: "下一页" }).click();
    expect((await nextResponse).ok()).toBe(true);
    await expect(page.getByText(`第 2 / ${Math.ceil(full.total / 10)} 页`)).toBeVisible();

    const cropResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agriculture/pest-knowledge") &&
        response.url().includes("crop=lychee"),
    );
    await page.getByRole("tab", { name: /^荔枝/ }).click();
    expect((await cropResponse).ok()).toBe(true);
    await expect(page.getByTestId("pest-card").first()).toContainText("荔枝");

    await page.getByTestId("pest-card").first().click();
    const detail = page.getByRole("dialog");
    await expect(detail).toBeVisible();
    await expect(detail.getByText("数据来源")).toBeVisible();
    await expect(detail.getByText(/仅供参考/).first()).toBeVisible();
    await detail.getByRole("button", { name: "关闭" }).click();
    await expect(detail).toBeHidden();

    const keywordResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/agriculture/pest-knowledge") &&
        response.url().includes("q=%E7%82%AD%E7%96%BD"),
    );
    await page.getByLabel("搜索病虫害").fill("炭疽");
    expect((await keywordResponse).ok()).toBe(true);
    await expect(page.getByText(/「炭疽」匹配/)).toBeVisible();
  });

  test("diagnosis validation, backend failure and result source are distinct", async ({
    page,
  }) => {
    let diagnoseRequests = 0;
    page.on("request", (request) => {
      if (request.url().endsWith("/api/agriculture/diagnose")) {
        diagnoseRequests += 1;
      }
    });

    await page.goto("/agriculture");
    await page.getByRole("button", { name: /展开诊断面板/ }).click();

    await page.getByRole("button", { name: "开始诊断" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "请先上传一张作物照片，或描述症状",
    );
    expect(diagnoseRequests).toBe(0);

    await page.getByLabel("选择诊断照片").setInputFiles({
      name: "bad.gif",
      mimeType: "image/gif",
      buffer: Buffer.from("GIF89a"),
    });
    await expect(page.getByRole("alert")).toContainText(
      "照片格式不受支持",
    );
    expect(diagnoseRequests).toBe(0);

    await page.route("**/api/agriculture/diagnose", (route) =>
      route.fulfill({
        status: 503,
        json: {
          success: false,
          code: "ai_unavailable",
          message: "AI 服务暂时不可用，请稍后重试。",
        },
      }),
    );
    await page.getByLabel("描述症状").fill("叶片有褐色病斑，边缘发黄。");
    await page.getByRole("button", { name: "开始诊断" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "AI 服务暂时不可用，请稍后重试。",
    );
    await expect(page.getByTestId("diagnosis-result")).toHaveCount(0);

    await page.unroute("**/api/agriculture/diagnose");
    await page.route("**/api/agriculture/diagnose", (route) =>
      route.fulfill({
        json: {
          success: false,
          code: "no_match",
          message:
            "未能从描述中匹配到对应的病害，请补充发病部位、病斑颜色与形状等更具体的症状后重试。",
        },
      }),
    );
    await page.getByRole("button", { name: "开始诊断" }).click();
    await expect(page.getByRole("alert")).toContainText(
      "未能从描述中匹配到对应的病害",
    );
    await expect(page.getByTestId("diagnosis-result")).toHaveCount(0);

    await page.unroute("**/api/agriculture/diagnose");
    await page.route("**/api/agriculture/diagnose", (route) =>
      route.fulfill({
        json: {
          success: true,
          diagnosis: {
            disease: "荔枝炭疽病",
            severity: "中度",
            symptoms: ["叶片出现圆形褐色斑点"],
            treatment: ["剪除病枝病叶并集中处理"],
            prevention: ["增施有机肥增强树势"],
            timing: "发病初期",
            note: "建议结合当地农技站指导进行防治",
            crop: "荔枝",
            crop_icon: "🍎",
            source: "knowledge_base",
            source_label: "本地知识库匹配",
            source_note:
              "AI 服务当前不可用，本条结论由平台内置知识库按关键词匹配得出，仅供参考，请以当地农技站指导为准。",
          },
        },
      }),
    );
    await page.getByRole("button", { name: "开始诊断" }).click();

    const result = page.getByTestId("diagnosis-result");
    await expect(result).toContainText("荔枝炭疽病");
    await expect(result).toContainText("本地知识库匹配");
    await expect(result).toContainText("仅供参考");
    await expect(result).toContainText("用药免责声明");
    await expect(page.getByRole("alert")).toHaveCount(0);
  });

  test("failed crop metadata shows an error instead of a stale fallback list", async ({
    page,
  }) => {
    await page.route("**/api/agriculture/pest-knowledge?limit=1", (route) =>
      route.abort(),
    );
    await page.goto("/agriculture");
    await page.getByRole("button", { name: /展开诊断面板/ }).click();

    await expect(page.getByTestId("pest-crop-error")).toContainText(
      "作物数据加载失败",
    );
    await expect(
      page.getByRole("button", { name: "🍎 荔枝" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "🌾 水稻" }),
    ).toHaveCount(0);
  });

  test("a real image is included in the diagnosis request", async ({ page }) => {
    let imageCount = 0;
    await page.route("**/api/agriculture/diagnose", async (route) => {
      const payload = route.request().postDataJSON() as {
        image?: string[];
      };
      imageCount = payload.image?.length ?? 0;
      await route.fulfill({
        json: {
          success: true,
          diagnosis: {
            disease: "荔枝霜疫霉病",
            severity: "重度",
            symptoms: ["果实出现褐色病斑"],
            treatment: ["重点保护果穗"],
            prevention: ["采后彻底清园"],
            timing: "花穗期",
            note: "注意天气变化",
            crop: "荔枝",
            crop_icon: "🍎",
            source: "ai",
            source_label: "AI 模型生成",
            source_note: "结论由 AI 模型生成，仅供参考，请以当地农技站指导为准。",
          },
        },
      });
    });

    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64",
    );

    await page.goto("/agriculture");
    await page.getByRole("button", { name: /展开诊断面板/ }).click();
    await page.getByLabel("选择诊断照片").setInputFiles({
      name: "leaf.png",
      mimeType: "image/png",
      buffer: png,
    });
    await expect(page.getByText("已选择 1 张照片")).toBeVisible();
    await page.getByRole("button", { name: "开始诊断" }).click();

    await expect(page.getByTestId("diagnosis-result")).toContainText(
      "荔枝霜疫霉病",
    );
    expect(imageCount).toBe(1);
  });
});
