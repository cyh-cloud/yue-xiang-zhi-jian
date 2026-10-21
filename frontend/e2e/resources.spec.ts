import { expect, test, type Page } from "@playwright/test";

async function waitForCdnState(page: Page): Promise<void> {
  await page.waitForFunction(
    () =>
      document.documentElement.dataset.cdnFontAwesome !== undefined &&
      document.documentElement.dataset.cdnModelViewer !== undefined,
  );
}

test.describe("local resources", () => {
  test("all three dialects expose their Q&A, phrases and quick questions", async ({
    page,
  }) => {
    await page.goto("/resources");

    await expect(
      page.getByRole("heading", { name: "本土化资源库" }),
    ).toBeVisible();
    const dialectCards = page.getByTestId("dialect-card");
    await expect(dialectCards).toHaveCount(3);

    const dialects = [
      { name: "粤语", greeting: "你好！食咗饭未？" },
      { name: "客家话", greeting: "你好！食咗饭无？" },
      { name: "潮汕话", greeting: "你好！食未？" },
    ];
    for (const dialect of dialects) {
      await dialectCards.filter({ hasText: dialect.name }).click();
      await expect(page.getByTestId("dialect-greeting")).toHaveText(
        dialect.greeting,
      );
      await expect(page.getByTestId("dialect-phrase")).toHaveCount(8);
      await expect(page.getByTestId("dialect-quick-question")).toHaveCount(4);
      await expect(
        dialectCards.filter({ hasText: dialect.name }),
      ).toHaveAttribute("aria-pressed", "true");
    }
  });

  test("unsupported voice input and an AI fallback are both visible", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "SpeechRecognition", {
        configurable: true,
        value: undefined,
      });
      Object.defineProperty(window, "webkitSpeechRecognition", {
        configurable: true,
        value: undefined,
      });
    });
    await page.goto("/resources");

    await page.getByRole("button", { name: "语音输入" }).click();
    await expect(
      page.getByText("当前浏览器不支持语音识别，请改用文字输入提问"),
    ).toBeVisible();
    await expect(page.getByTestId("dialect-quick-question")).toHaveCount(4);

    const question = page
      .getByTestId("dialect-quick-question")
      .filter({ hasText: "荔枝" })
      .first();
    const answerResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/resources/voice") &&
        response.request().method() === "POST",
    );
    await question.click();
    expect((await answerResponse).ok()).toBe(true);

    await expect(
      page
        .locator('[data-testid="dialect-message"][data-message-role="user"]')
        .last(),
    ).toContainText("荔枝");
    await expect(
      page
        .locator('[data-testid="dialect-message"][data-message-role="bot"]')
        .last(),
    ).toContainText("本地方言语料库回答，仅供学习参考");
  });

  test("approved cases open a detail page with sources and lessons", async ({
    page,
  }) => {
    const casesResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/resources/cases") &&
        response.request().method() === "GET",
    );
    await page.goto("/resources");
    const payload = (await (await casesResponse).json()) as {
      cases: Array<{ id: number; title: string }>;
    };
    expect(payload.cases).toHaveLength(5);

    const firstCase = payload.cases[0];
    expect(firstCase).toBeTruthy();
    const card = page
      .getByTestId("case-card")
      .filter({ hasText: firstCase?.title ?? "" });
    await expect(card).toBeVisible();
    await card.getByRole("link", { name: /查看详情/ }).click();

    await expect(page).toHaveURL(new RegExp(`/case-detail/${firstCase?.id}$`));
    await expect(
      page.getByRole("heading", { name: firstCase?.title ?? "" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "借鉴与启示" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "资料来源" }),
    ).toBeVisible();
    await expect(
      page.getByTestId("case-sources").getByRole("link").first(),
    ).toBeVisible();
  });

  test("pending review is shown as an audit state instead of a load failure", async ({
    page,
  }) => {
    await page.route("**/api/resources/cases", (route) =>
      route.fulfill({
        json: {
          success: true,
          cases: [],
          case_review: {
            approved: 0,
            pending: 2,
            rejected: 0,
            total: 2,
          },
          source_note: "资料来源说明",
          lessons_note: "借鉴点说明",
        },
      }),
    );

    await page.goto("/resources");

    await expect(
      page.getByText("案例内容正在审核中（2 条待审）"),
    ).toBeVisible();
    await expect(
      page.getByText("案例加载失败"),
    ).toHaveCount(0);
  });

  test("policies use dynamic category filters and open real detail content", async ({
    page,
  }) => {
    const policiesResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/resources/policies") &&
        response.request().method() === "GET",
    );
    await page.goto("/resources");
    const payload = (await (await policiesResponse).json()) as {
      policies: Array<{ title: string; category: string }>;
    };
    const categories = Array.from(
      new Set(payload.policies.map((policy) => policy.category)),
    );
    expect(categories.length).toBeGreaterThan(1);

    const filters = page.getByTestId("policy-filters");
    for (const category of categories) {
      await expect(
        filters.getByRole("button", { name: category, exact: true }),
      ).toBeVisible();
    }

    const category = categories.find((item) => item === "电商") ?? categories[0];
    expect(category).toBeTruthy();
    const expected = payload.policies.find(
      (policy) => policy.category === category,
    );
    expect(expected).toBeTruthy();

    await filters
      .getByRole("button", { name: category ?? "", exact: true })
      .click();
    await expect(page.getByTestId("policy-card")).not.toHaveCount(0);
    const visibleTags = await page
      .getByTestId("policy-card")
      .getByTestId("policy-tag")
      .allTextContents();
    expect(new Set(visibleTags)).toEqual(new Set([category ?? ""]));
    await page
      .getByTestId("policy-card")
      .filter({ hasText: expected?.title ?? "" })
      .click();

    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole("heading", { name: expected?.title ?? "" }),
    ).toBeVisible();
    await expect(dialog).toContainText("政策概述");
    await expect(
      dialog.getByTestId("policy-detail-content").locator("strong").first(),
    ).toBeVisible();
    await expect(
      dialog.getByTestId("policy-detail-content").locator("li").first(),
    ).toBeVisible();
    await expect(dialog).toContainText("不替代官方文件");
    await dialog.getByRole("button", { name: "关闭" }).click();
    await expect(dialog).toBeHidden();
  });

  test("desktop resources visual baseline stays stable", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/resources/dialects", (route) =>
      route.fulfill({
        json: {
          success: true,
          dialects: [
            {
              id: "cantonese",
              name: "粤语",
              region: "广州话",
              emoji: "🗣️",
              areas: "广州、佛山、深圳",
              speakers: "约7000万使用者",
            },
            {
              id: "hakka",
              name: "客家话",
              region: "梅州话",
              emoji: "🏔️",
              areas: "梅州、惠州、河源",
              speakers: "约4500万使用者",
            },
            {
              id: "teochew",
              name: "潮汕话",
              region: "汕头话",
              emoji: "🌊",
              areas: "汕头、潮州、揭阳",
              speakers: "约1500万使用者",
            },
          ],
        },
      }),
    );
    await page.route("**/api/resources/dialect-info?*", (route) => {
      const dialect = new URL(route.request().url()).searchParams.get(
        "dialect",
      );
      const isHakka = dialect === "hakka";
      const isTeochew = dialect === "teochew";
      route.fulfill({
        json: {
          success: true,
          info: {
            id: dialect,
            name: isHakka ? "客家话" : isTeochew ? "潮汕话" : "粤语",
            region: isHakka ? "梅州话" : isTeochew ? "汕头话" : "广州话",
            emoji: isHakka ? "🏔️" : isTeochew ? "🌊" : "🗣️",
            areas: isHakka
              ? "梅州、惠州、河源"
              : isTeochew
                ? "汕头、潮州、揭阳"
                : "广州、佛山、深圳",
            speakers: isHakka
              ? "约4500万使用者"
              : isTeochew
                ? "约1500万使用者"
                : "约7000万使用者",
            greeting: isHakka
              ? "你好！食咗饭无？"
              : isTeochew
                ? "你好！食未？"
                : "你好！食咗饭未？",
            greeting_meaning: "你好！吃饭了吗？",
            features: isHakka
              ? ["六声调", "保留入声", "古汉语活化石"]
              : isTeochew
                ? ["八声调", "保留古汉语入声", "文白异读丰富"]
                : ["九声六调", "保留古汉语词汇", "大量外来语借词"],
            phrases: [
              {
                dialect: "你好",
                mandarin: "你好",
                pinyin: "nei5 hou2",
              },
              {
                dialect: "多谢",
                mandarin: "谢谢",
                pinyin: "do1 ze6",
              },
            ],
            quick_questions: [
              "荔枝点样施肥最好？",
              "龙眼几时可以摘？",
              "香蕉点样防虫？",
              "柑橘落叶点处理？",
            ],
          },
        },
      });
    });
    await page.route("**/api/resources/cases", (route) =>
      route.fulfill({
        json: {
          success: true,
          cases: [
            {
              id: 1,
              title: "梅县南福村：一颗金柚的电商逆袭",
              description:
                "九成农户种柚的客家山村，靠直播把金柚卖向全国，电商销售占比提升至七成。",
              location: "梅州市梅县区",
              stats: [
                {
                  icon: "fa-leaf",
                  label: "全村金柚种植面积",
                  value: "5000+ 亩",
                },
                {
                  icon: "fa-store",
                  label: "电商销售占比",
                  value: "70%",
                },
              ],
            },
            {
              id: 2,
              title: "潮州湘桥：让非遗技艺在直播间活起来",
              description: "潮绣、潮州木雕与手钩花借直播打开销路。",
              location: "潮州市湘桥区",
              stats: [
                {
                  icon: "fa-users",
                  label: "妇女稳定就业",
                  value: "20 余名",
                },
                {
                  icon: "fa-chart-line",
                  label: "妇女创业担保贷款",
                  value: "超 1070 万元",
                },
              ],
            },
          ],
          case_review: {
            approved: 2,
            pending: 0,
            rejected: 0,
            total: 2,
          },
          source_note: "案例依据公开报道整理。",
          lessons_note: "借鉴点基于公开报道整理。",
        },
      }),
    );
    await page.route("**/api/resources/policies", (route) =>
      route.fulfill({
        json: {
          success: true,
          policies: [
            {
              id: 25,
              title: "农业补贴申请指南",
              summary: "耕地地力保护补贴等惠农补贴的申领要点。",
              category: "补贴",
              date: "2026-04-17",
              content: "【政策概述】\n惠农补贴按年度通知执行。",
              sources: [],
            },
            {
              id: 26,
              title: "农村电商扶持政策",
              summary: "电子商务进农村示范站与地市奖补政策汇编。",
              category: "电商",
              date: "2025-09-20",
              content: "【政策概述】\n支持农村电商公共服务体系。",
              sources: [],
            },
            {
              id: 27,
              title: "非遗传承人认定办法",
              summary: "省级非遗代表性传承人的认定依据与补助标准。",
              category: "非遗",
              date: "2024-09-25",
              content: "【政策概述】\n完善四级名录体系。",
              sources: [],
            },
          ],
          source_note: "本页依据公开政策文件整理。",
          disclaimer: "本平台仅作政策索引与解读，不替代官方文件。",
        },
      }),
    );

    await page.goto("/resources");
    await expect(page.getByTestId("dialect-card")).toHaveCount(3);
    await expect(page.getByTestId("case-card")).toHaveCount(2);
    await expect(page.getByTestId("policy-card")).toHaveCount(3);
    await waitForCdnState(page);
    await expect
      .poll(
        () =>
          page.evaluate(
            () => document.documentElement.dataset.cdnFontAwesome,
          ),
      )
      .not.toBe("failed");
    await page.evaluate(() => document.fonts.ready);

    await expect(page).toHaveScreenshot("resources-anonymous-light.png", {
      fullPage: true,
    });
  });
});
