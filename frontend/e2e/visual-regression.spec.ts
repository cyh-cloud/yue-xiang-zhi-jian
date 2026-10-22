import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";

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

test.describe("desktop visual regression", () => {
  test("ecommerce full page", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({ json: { success: true, count: 0 } }),
    );

    await page.goto("/ecommerce");
    await expect(
      page.getByRole("heading", { level: 1, name: "电商运营实训" }),
    ).toBeVisible();
    await expect(page.getByTestId("ecommerce-page")).toBeVisible();
    await waitForCdnState(page);
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("ecommerce-desktop-light.png", {
      fullPage: true,
    });
  });

  test("login page", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/login");
    await expect(
      page.getByRole("heading", { level: 1, name: "粤乡智匠" }),
    ).toBeVisible();
    await waitForCdnState(page);
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("login-desktop-light.png", {
      fullPage: true,
    });
  });

  test("case detail", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/resources/cases", (route) =>
      route.fulfill({
        json: {
          success: true,
          cases: [
            {
              id: 1,
              title: "梅县南福村：一颗金柚的电商逆袭",
              region: "梅州",
              location: "梅县区南福村",
              background:
                "南福村以金柚种植为主，过去主要依赖线下批发。\n\n村里组织青年学习电商运营，逐步建立稳定线上渠道。",
              description: "从线下批发走向线上品牌，带动农户稳定增收。",
              quote: "把家乡的好果子讲清楚，客户自然会回来。",
              quote_author: "南福村合作社负责人",
              stats: [
                { icon: "fa-chart-line", value: "3倍", label: "线上销售额" },
                { icon: "fa-users", value: "80+", label: "带动农户" },
              ],
              milestones: [
                {
                  period: "2023",
                  title: "组建电商小组",
                  desc: "返乡青年与合作社共同梳理产品标准。",
                },
              ],
              sources: [
                {
                  title: "梅州市乡村振兴典型案例",
                  media: "梅州市人民政府",
                  date: "2025-06-01",
                  url: "https://example.com/case",
                },
              ],
              lessons: ["先统一品质，再讲品牌故事。"],
            },
          ],
          case_review: { pending: 0 },
          source_note: "案例依据公开报道与政府公开信息整理。",
          lessons_note: "借鉴点由平台根据公开材料归纳。",
        },
      }),
    );
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({ json: { success: true, count: 0 } }),
    );

    await page.goto("/case-detail/1");
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "梅县南福村：一颗金柚的电商逆袭",
      }),
    ).toBeVisible();
    await waitForCdnState(page);
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("case-detail-desktop-light.png", {
      fullPage: true,
    });
  });

  test("shared backoffice shell and admin dashboard", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.route("**/api/admin/dashboard", (route) =>
      route.fulfill({
        json: {
          success: true,
          overview: {
            users: {
              total: 128,
              suspended: 3,
              student: 96,
              teacher: 12,
              enterprise: 9,
              government: 5,
              operator: 4,
              super_admin: 2,
            },
            reviews: {
              pending: 7,
              approved: 42,
              rejected: 5,
              oldest_pending_at: "2026-10-18 09:00:00",
              oldest_pending_days: 2,
            },
            content: {
              jobs: 24,
              jobs_published: 18,
              models: 16,
              courses: 12,
              policies: 9,
              policies_published: 8,
              announcements: 6,
              cases: 5,
            },
            pending_jobs: 4,
            pending_reviews: 7,
          },
        },
      }),
    );
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({ json: { success: true, count: 0 } }),
    );

    await signIn(page, "admin_demo", "admin123", { blockCdn: false });
    await expect(page).toHaveURL(/\/admin\/dashboard$/);
    await expect(page.getByTestId("admin-stat-users-total")).toContainText(
      "128",
    );
    await waitForCdnState(page);
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("backoffice-admin-desktop.png", {
      fullPage: true,
    });
  });

  test("operator overview keeps its role accent and review reminders", async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const task = {
      id: 901,
      product_id: "lychee",
      product_name: "荔枝",
      phase_id: 1,
      phase_name: "花期",
      title: "花期水肥管理",
      category: "manage",
      category_label: "田间管理",
      priority: "high",
      task_md: "03-20",
      month: 3,
      icon: "tasks",
      description: "补水补肥",
      tip: "薄肥勤施",
      source_key: "CARS-LZ",
      date_basis: "花期需水需肥增加",
      is_verified: 0,
      verified_by: "",
      verified_at: "",
      is_active: 1,
      sort_order: 1,
    };
    await page.route("**/api/operator/farming/tasks*", (route) => {
      const overdue = new URL(route.request().url()).searchParams.has("overdue");
      route.fulfill({
        json: { success: true, tasks: overdue ? [task] : [task] },
      });
    });
    await page.route("**/api/operator/pest/entries*", (route) => {
      const overdue = new URL(route.request().url()).searchParams.has("overdue");
      route.fulfill({
        json: {
          success: true,
          entries: overdue
            ? [
                {
                  id: "pest-1",
                  crop_id: "lychee",
                  crop_name: "荔枝",
                  disease: "荔枝蝽",
                  kind: "pest",
                  is_verified: 0,
                  verified_by: "",
                  verified_at: "",
                },
              ]
            : [],
        },
      });
    });
    await page.route("**/api/operator/farming/products", (route) =>
      route.fulfill({ json: { success: true, products: [task] } }),
    );
    await page.route("**/api/operator/farming/phenophases", (route) =>
      route.fulfill({ json: { success: true, phenophases: [{}] } }),
    );
    await page.route("**/api/operator/farming/sources", (route) =>
      route.fulfill({ json: { success: true, sources: [{}] } }),
    );
    await page.route("**/api/operator/farming/categories", (route) =>
      route.fulfill({ json: { success: true, categories: [{}] } }),
    );
    await page.route("**/api/operator/pest/crops", (route) =>
      route.fulfill({ json: { success: true, crops: [{}] } }),
    );
    await page.route("**/api/operator/pest/sources", (route) =>
      route.fulfill({ json: { success: true, sources: [{}] } }),
    );
    await page.route("**/api/notifications/unread*", (route) =>
      route.fulfill({ json: { success: true, count: 0 } }),
    );

    await signIn(page, "operator_demo", "123456", { blockCdn: false });
    await expect(page).toHaveURL(/\/operator\/overview$/);
    await expect(page.getByTestId("operator-stat-overdue-tasks")).toContainText(
      "1",
    );
    await waitForCdnState(page);
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot("backoffice-operator-desktop.png", {
      fullPage: true,
    });
  });
});
