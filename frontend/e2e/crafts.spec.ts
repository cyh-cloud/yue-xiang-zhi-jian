import { expect, test } from "@playwright/test";

async function waitForCdnState(page: import("@playwright/test").Page): Promise<void> {
  await page.waitForFunction(
    () =>
      document.documentElement.dataset.cdnFontAwesome !== undefined &&
      document.documentElement.dataset.cdnModelViewer !== undefined,
  );
}

test.describe("crafts heritage", () => {
  test("craft cards use database origin and level instead of local presentation", async ({
    page,
  }) => {
    await page.route("**/api/crafts/list", (route) =>
      route.fulfill({
        json: {
          success: true,
          crafts: [
            {
              id: "embroidery",
              name: "广绣",
              origin: "运营维护的产地",
              level: "运营维护的等级",
            },
          ],
        },
      }),
    );
    await page.route("**/api/crafts/embroidery", (route) =>
      route.fulfill({
        json: {
          success: true,
          data: {
            name: "广绣",
            origin: "运营维护的产地",
            history: "数据库正文",
            videos: [],
            steps: [],
            purchase_guide: null,
          },
        },
      }),
    );
    await page.route("**/api/teacher/public-models-3d?craft_type=embroidery", (route) =>
      route.fulfill({ json: { success: true, models: [] } }),
    );

    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    const card = page.locator(".craft-grid .craft-card").filter({
      hasText: "广绣",
    });
    await expect(card).toContainText("运营维护的产地");
    await expect(card).toContainText("运营维护的等级");
    await expect(card).not.toContainText("国家级非物质文化遗产");
    await expect(card).not.toContainText("入门级");
  });

  test("visitors can select a craft and inspect its complete learning material", async ({
    page,
  }) => {
    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByRole("heading", { name: "非遗手工技能传承" }),
    ).toBeVisible();
    const craftButtons = page.locator(".craft-grid .craft-card");
    await expect(craftButtons).toHaveCount(4);

    await expect(
      page.getByRole("heading", { name: "广绣", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".craft-intro-origin")).toHaveText("广州");
    await expect(page.getByText(/起源于唐代/)).toBeVisible();
    await expect(page.getByText(/已完成 0\/\d+ 步/)).toBeVisible();

    const videoCards = page.locator(".craft-video-card");
    await expect(videoCards).toHaveCount(4);
    await expect(page.getByText(/视频来源：哔哩哔哩/)).toBeVisible();

    await expect(page.getByText("入门全套预算")).toBeVisible();
    await expect(page.getByText("约130-320元")).toBeVisible();
    await expect(page.getByText("必买基础工具")).toBeVisible();
    await page.getByRole("button", { name: /常用耗材/ }).click();
    await expect(page.getByText("绣线单色补充装")).toBeVisible();

    await page
      .locator(".craft-grid .craft-card")
      .filter({ hasText: "潮汕木雕" })
      .click();
    await expect(
      page.getByRole("heading", { name: "潮汕木雕", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/始于唐代，盛于明清/)).toBeVisible();
    await expect(page.getByText("约150-330元")).toBeVisible();
    await expect
      .poll(() =>
        page
          .locator("model-viewer")
          .evaluate((node) => (node as HTMLElement & { src: string }).src),
      )
      .toContain("chaoshan_mudiao.glb");
  });

  test("a craft without videos shows an explicit empty state", async ({ page }) => {
    await page.route("**/api/crafts/embroidery", async (route) => {
      await route.fulfill({
        json: {
          success: true,
          data: {
            name: "广绣",
            origin: "广州",
            history: "国家级非物质文化遗产，起源于唐代。",
            videos: [],
            steps: [
              { title: "准备工具与材料", desc: "准备绣架、绣针与丝线。", tips: "" },
            ],
            purchase_guide: null,
          },
        },
      });
    });

    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(page.getByText("该手工艺暂无视频教学")).toBeVisible();
    await expect(page.getByText("内容正在整理中，请稍后再来查看。")).toBeVisible();
  });

  test("a failed craft detail keeps video, steps and materials in explicit error states", async ({
    page,
  }) => {
    await page.route("**/api/crafts/embroidery", (route) => route.abort());
    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByText("手工艺内容加载失败，视频教学暂不可用"),
    ).toBeVisible();
    await expect(
      page.getByText("手工艺内容加载失败，制作步骤暂不可用"),
    ).toBeVisible();
    await expect(
      page.getByText("手工艺内容加载失败，材料采购指南暂不可用"),
    ).toBeVisible();
  });

  test("unsupported model formats explain why preview is unavailable", async ({
    page,
  }) => {
    await page.route("**/api/teacher/public-models-3d?craft_type=embroidery", (route) =>
      route.fulfill({
        json: {
          success: true,
          models: [
            {
              id: 901,
              title: "OBJ 模型",
              description: "",
              craft_type: "embroidery",
              file_path: "uploads/models_3d/demo.obj",
              file_name: "demo.obj",
              file_size: 1024,
              thumbnail_url: "",
              review_status: "approved",
              is_published: 1,
              created_at: "",
            },
          ],
        },
      }),
    );

    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(page.getByText(/暂不支持 \.obj 格式/)).toBeVisible();
    await expect(page.getByRole("button", { name: "多角度" })).toBeDisabled();
  });

  test("multiple published models can be switched", async ({ page }) => {
    await page.route("**/api/teacher/public-models-3d?craft_type=embroidery", (route) =>
      route.fulfill({
        json: {
          success: true,
          models: [
            {
              id: 101,
              title: "广绣基础模型",
              description: "",
              craft_type: "embroidery",
              file_path: "uploads/models_3d/guangxiu_xiubeng.glb",
              file_name: "guangxiu_xiubeng.glb",
              file_size: 1,
              thumbnail_url: "",
              review_status: "approved",
              is_published: 1,
              created_at: "",
            },
            {
              id: 102,
              title: "木雕备选模型",
              description: "",
              craft_type: "embroidery",
              file_path: "uploads/models_3d/chaoshan_mudiao.glb",
              file_name: "chaoshan_mudiao.glb",
              file_size: 1,
              thumbnail_url: "",
              review_status: "approved",
              is_published: 1,
              created_at: "",
            },
          ],
        },
      }),
    );

    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    const tabs = page.locator(".craft-model-tab");
    await expect(tabs).toHaveCount(2);
    await expect
      .poll(() => page.locator("model-viewer").getAttribute("src"))
      .toContain("guangxiu_xiubeng.glb");
    await tabs.filter({ hasText: "木雕备选模型" }).click();
    await expect
      .poll(() => page.locator("model-viewer").getAttribute("src"))
      .toContain("chaoshan_mudiao.glb");
  });

  test("model-viewer CDN failure keeps the page usable and explains the loss", async ({
    page,
  }) => {
    await page.route("https://unpkg.com/**", (route) => route.abort());
    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByRole("status").filter({ hasText: "外部资源降级" }),
    ).toContainText("model-viewer");
    await expect(page.getByText(/3D 查看器资源加载失败/)).toBeVisible();
    await expect(page.getByText("准备工具与材料")).toBeVisible();
  });

  test("a model file that fails to load reports the failure", async ({ page }) => {
    await page.goto("/crafts", { waitUntil: "domcontentloaded" });
    const viewer = page.locator("model-viewer");
    await expect(viewer).toHaveAttribute("src", /guangxiu_xiubeng\.glb/);
    await viewer.evaluate((node) => {
      node.dispatchEvent(new Event("error"));
    });

    await expect(
      page.getByText(/3D 模型文件加载失败或格式不支持/),
    ).toBeVisible();
  });

  test("a failed craft directory offers a retry instead of a blank page", async ({
    page,
  }) => {
    await page.route("**/api/crafts/list", (route) => route.abort());
    await page.goto("/crafts", { waitUntil: "domcontentloaded" });

    await expect(
      page.getByText("手工艺目录加载失败，请检查网络后重试"),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "重新加载" })).toBeVisible();
  });

  test("desktop crafts visual baseline stays stable", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/teacher/public-models-3d?craft_type=embroidery", (route) =>
      route.fulfill({ json: { success: true, models: [] } }),
    );
    await page.route("http://i0.hdslb.com/**", (route) => route.abort());
    await page.route("http://i1.hdslb.com/**", (route) => route.abort());
    await page.route("http://i2.hdslb.com/**", (route) => route.abort());
    await page.route("https://i0.hdslb.com/**", (route) => route.abort());
    await page.route("https://i1.hdslb.com/**", (route) => route.abort());
    await page.route("https://i2.hdslb.com/**", (route) => route.abort());

    await page.goto("/crafts", { waitUntil: "domcontentloaded" });
    await expect(
      page.getByRole("heading", { name: "广绣", exact: true }),
    ).toBeVisible();
    await expect(page.getByText("该手工艺暂无可展示的 3D 模型")).toBeVisible();
    await waitForCdnState(page);
    await expect
      .poll(
        () =>
          page.evaluate(
            () => document.documentElement.dataset.cdnFontAwesome,
          ),
      )
      .not.toBe("failed");
    await page.waitForFunction(() =>
      Array.from(document.images).every((image) => image.complete),
    );
    await page.evaluate(() => document.fonts.ready);

    await expect(page).toHaveScreenshot("crafts-anonymous-light.png", {
      fullPage: true,
    });
  });
});
