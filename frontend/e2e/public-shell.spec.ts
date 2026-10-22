import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";

const SECTION_LINKS = ["农业技能", "电商运营", "手工传承", "本土资源", "就业对接"];

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
}

test.describe("public shell", () => {
  test("home exposes real statistics and all five section entrances", async ({
    page,
  }) => {
    await page.goto("/");

    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "AI驱动的",
    );
    await expect(page.getByRole("heading", { level: 1 })).toContainText(
      "农村人才赋能平台",
    );

    const navigation = page.getByRole("navigation", { name: "主导航" });
    for (const label of SECTION_LINKS) {
      await expect(navigation.getByRole("link", { name: label })).toBeVisible();
    }

    const response = await page.request.get("/api/home/stats");
    expect(response.ok()).toBe(true);
    const payload = (await response.json()) as {
      stats: Record<string, number>;
    };

    for (const key of ["farmers", "courses", "jobs"] as const) {
      await expect
        .poll(async () => {
          const text = await page.getByTestId(`home-stat-${key}`).innerText();
          return Number(text.replace(/,/g, ""));
        })
        .toBe(payload.stats[key]);
    }
  });

  test("anonymous visitors browse public pages and protected entries go to login", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "登录" })).toBeVisible();

    await page.getByRole("navigation", { name: "主导航" })
      .getByRole("link", { name: "本土资源" })
      .click();
    await expect(page).toHaveURL(/\/resources$/);
    await expect(page.getByRole("heading", { name: "本土化资源库" })).toBeVisible();

    await page.goto("/teacher/dashboard");
    await expect(page).toHaveURL(/\/login\?redirect=\/teacher\/dashboard$/);
  });

  test("authenticated visitors keep public browsing and can reach their portal", async ({
    page,
  }) => {
    await signIn(page, "student_demo", "123456");
    await expect(page).toHaveURL(/\/agriculture\/?$/);

    await page.goto("/");
    await expect(page.getByRole("button", { name: "打开用户菜单" })).toBeVisible();
    await page.getByRole("button", { name: "打开用户菜单" }).click();
    await expect(page.getByRole("link", { name: "进入工作台" })).toHaveAttribute(
      "href",
      "/agriculture",
    );
  });

  test("stored theme and large text apply before the app mounts", async ({
    page,
  }) => {
    await page.addInitScript(() => {
      localStorage.setItem("yuexiang_theme", "dark");
      localStorage.setItem("yuexiang_large_text", "1");
    });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("html")).toHaveAttribute("data-large-text", "1");
    const background = await page.evaluate(() =>
      getComputedStyle(document.documentElement)
        .getPropertyValue("--bg-primary")
        .trim(),
    );
    expect(background).toBe("#10201a");
  });

  test("home scroll intent reveals the Hero transition and enters agriculture", async ({
    page,
  }) => {
    await page.route("**/api/home/stats", (route) =>
      route.fulfill({
        json: {
          success: true,
          stats: { farmers: 128, courses: 24, jobs: 16 },
        },
      }),
    );
    await page.goto("/");

    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.mouse.wheel(0, 40);

    await expect
      .poll(() =>
        page
          .getByTestId("home-scroll-hint")
          .evaluate((element) => getComputedStyle(element).opacity),
      )
      .toBe("0");

    await page.mouse.wheel(0, 200);
    await expect(page.getByTestId("home-hero")).toHaveCSS(
      "pointer-events",
      "none",
    );
    await expect(page).toHaveURL(/\/agriculture\/?$/);
  });

  test("theme and large text toggles survive a reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "切换主题" }).click();
    await page.getByRole("button", { name: "切换大字模式" }).click();

    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("html")).toHaveAttribute("data-large-text", "1");

    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("html")).toHaveAttribute("data-large-text", "1");
  });

  test("legacy html entry points and unknown public paths redirect silently", async ({
    page,
  }) => {
    const publicRedirects = [
      ["/index.html", "/"],
      ["/agriculture.html", "/agriculture"],
      ["/ecommerce.html", "/ecommerce"],
      ["/crafts.html", "/crafts"],
      ["/resources.html", "/resources"],
      ["/employment.html", "/employment"],
      ["/not-a-public-page", "/"],
    ] as const;

    for (const [source, target] of publicRedirects) {
      await page.goto(source);
      await expect(page).toHaveURL(
        new RegExp(`${target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`),
      );
    }

    const protectedRedirects = [
      ["/teacher.html", "/teacher/dashboard"],
      ["/teacher-panel.html", "/teacher/dashboard"],
      ["/admin.html", "/admin/dashboard"],
      ["/government.html", "/government/dashboard"],
      ["/enterprise.html", "/enterprise/dashboard"],
      ["/operator.html", "/operator/overview"],
    ] as const;

    for (const [source, target] of protectedRedirects) {
      await page.goto(source);
      await expect(page).toHaveURL(
        new RegExp(
          `/login\\?redirect=${target.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`,
        ),
      );
    }

    await page.goto("/case-detail.html?id=1");
    await expect(page).toHaveURL(/\/case-detail\/1$/);
    await expect(
      page.getByRole("heading", { name: "梅县南福村：一颗金柚的电商逆袭" }),
    ).toBeVisible();
  });

  test("legacy service worker cleanup leaves other site caches alone", async ({
    page,
    context,
  }) => {
    await context.route("**/sw.js", async (route) => {
      await route.fulfill({
        contentType: "text/javascript",
        body: [
          "self.addEventListener('install', () => self.skipWaiting());",
          "self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));",
        ].join("\n"),
      });
    });

    await page.goto("/");
    await page.evaluate(async () => {
      await caches.open("yuexiang-v74");
      await caches.open("other-app-cache");
      await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
    });

    await page.reload();
    await expect
      .poll(async () =>
        page.evaluate(async () => {
          const keys = (await caches.keys()).sort();
          const registrations = await navigator.serviceWorker.getRegistrations();
          const legacyWorkers = registrations.filter((registration) => {
            const scriptURL =
              registration.active?.scriptURL ??
              registration.waiting?.scriptURL ??
              registration.installing?.scriptURL ??
              "";
            return new URL(scriptURL).pathname === "/sw.js";
          });
          return {
            cacheNames: keys,
            legacyWorkerCount: legacyWorkers.length,
          };
        }),
      )
      .toEqual({
        cacheNames: ["other-app-cache"],
        legacyWorkerCount: 0,
      });
  });

  test("CDN failures are visible instead of silently dropping features", async ({
    page,
  }) => {
    await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
    await page.route("https://unpkg.com/**", (route) => route.abort());
    await page.goto("/");

    const notice = page.getByRole("status").filter({ hasText: "外部资源降级" });
    await expect(notice).toContainText("Font Awesome");
    await expect(notice).toContainText("model-viewer");
  });

  test("desktop home visual baselines stay stable", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/home/stats", (route) =>
      route.fulfill({
        json: {
          success: true,
          stats: { farmers: 128, courses: 24, jobs: 16 },
        },
      }),
    );
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({
        json: { success: true, count: 0 },
      }),
    );

    await page.goto("/");
    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await waitForCdnState(page);
    await expect
      .poll(() => page.evaluate(() => document.documentElement.dataset.cdnFontAwesome))
      .not.toBe("failed");
    await expect(page).toHaveScreenshot("home-anonymous-light.png", {
      fullPage: true,
    });

    await signIn(page, "student_demo", "123456");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await page.goto("/");
    await page.getByRole("button", { name: "切换主题" }).click();
    await page.getByRole("button", { name: "切换大字模式" }).click();
    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await expect(page).toHaveScreenshot("home-authenticated-dark-large.png", {
      fullPage: true,
    });
  });
});
