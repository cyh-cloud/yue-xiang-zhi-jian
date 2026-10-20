import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";
import {
  ADMIN_OVERVIEW,
  AGRICULTURE_CALENDAR,
  AGRICULTURE_PRODUCTS,
  AGRICULTURE_SUGGESTIONS,
  COMMUNITY_DISCUSSIONS,
  CRAFT_DETAIL,
  CRAFTS_LIST,
  EMPLOYMENT_JOBS,
  ENTERPRISE_APPLICATIONS,
  ENTERPRISE_STATS,
  GOVERNMENT_OVERVIEW,
  HOME_STATS,
  LEARNER_PROFILE,
  LEARNER_RESUME,
  LEARNER_STATS,
  OPERATOR_CATEGORY,
  OPERATOR_ENTRY,
  OPERATOR_PEST_CROP,
  OPERATOR_PEST_SOURCE,
  OPERATOR_PHENOPHASE,
  OPERATOR_PRODUCT,
  OPERATOR_SOURCE,
  OPERATOR_TASK,
  PEST_KNOWLEDGE,
  RESOURCE_CASES,
  RESOURCE_DIALECTS,
  RESOURCE_DIALECT_INFO,
  RESOURCE_POLICIES,
  TEACHER_STATS,
  TEACHER_STUDENTS,
} from "./visual-matrix.fixtures";

const DESKTOP = { width: 1280, height: 900 } as const;
const MOBILE = { width: 390, height: 844 } as const;

interface VisualOptions {
  viewport?: { width: number; height: number };
  theme?: "light" | "dark";
  largeText?: boolean;
}

async function preparePage(
  page: Page,
  options: VisualOptions = {},
): Promise<void> {
  await page.setViewportSize(options.viewport ?? DESKTOP);
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
  await page.addInitScript(
    ({ theme, largeText }) => {
      localStorage.setItem("yuexiang_theme", theme);
      localStorage.setItem("yuexiang_large_text", largeText ? "1" : "0");
    },
    {
      theme: options.theme ?? "light",
      largeText: options.largeText ?? false,
    },
  );
  await page.route("**/api/notifications/unread*", (route) =>
    route.fulfill({ json: { success: true, count: 0 } }),
  );
}

async function blockCdn(page: Page): Promise<void> {
  await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
  await page.route("https://unpkg.com/**", (route) => route.abort());
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
}

async function waitForCdnLoaded(page: Page): Promise<void> {
  await waitForCdnState(page);
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.dataset.cdnFontAwesome),
    )
    .not.toBe("failed");
  await expect
    .poll(() =>
      page.evaluate(() => document.documentElement.dataset.cdnModelViewer),
    )
    .not.toBe("failed");
}

async function capture(
  page: Page,
  name: string,
  fullPage = true,
): Promise<void> {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() =>
    Array.from(document.images).every((image) => image.complete),
  );
  await expect(page).toHaveScreenshot(name, { fullPage });
}

async function mockHome(page: Page): Promise<void> {
  await page.route("**/api/home/stats", (route) =>
    route.fulfill({ json: HOME_STATS }),
  );
}

async function mockAgriculture(page: Page): Promise<void> {
  await page.route("**/api/agriculture/products", (route) =>
    route.fulfill({ json: AGRICULTURE_PRODUCTS }),
  );
  await page.route("**/api/agriculture/calendar/**", (route) =>
    route.fulfill({ json: AGRICULTURE_CALENDAR }),
  );
  await page.route("**/api/agriculture/pest-knowledge*", (route) =>
    route.fulfill({ json: PEST_KNOWLEDGE }),
  );
  await page.route("**/api/agriculture/suggestions?*", (route) =>
    route.fulfill({ json: AGRICULTURE_SUGGESTIONS }),
  );
  await page.route("**/api/agriculture/subscriptions", (route) =>
    route.fulfill({ json: { success: true, product_ids: [] } }),
  );
}

async function mockCrafts(page: Page): Promise<void> {
  await page.route("**/api/crafts/list", (route) =>
    route.fulfill({ json: CRAFTS_LIST }),
  );
  await page.route("**/api/crafts/embroidery", (route) =>
    route.fulfill({ json: CRAFT_DETAIL }),
  );
  await page.route(
    "**/api/teacher/public-models-3d?craft_type=embroidery",
    (route) => route.fulfill({ json: { success: true, models: [] } }),
  );
}

async function mockResources(page: Page): Promise<void> {
  await page.route("**/api/resources/dialects", (route) =>
    route.fulfill({ json: RESOURCE_DIALECTS }),
  );
  await page.route("**/api/resources/dialect-info?*", (route) =>
    route.fulfill({ json: RESOURCE_DIALECT_INFO }),
  );
  await page.route("**/api/resources/cases", (route) =>
    route.fulfill({ json: RESOURCE_CASES }),
  );
  await page.route("**/api/resources/policies", (route) =>
    route.fulfill({ json: RESOURCE_POLICIES }),
  );
}

async function mockEmployment(page: Page): Promise<void> {
  await page.route("**/api/employment/jobs*", (route) =>
    route.fulfill({ json: EMPLOYMENT_JOBS }),
  );
}

async function mockCommunity(page: Page): Promise<void> {
  await page.route("**/api/discussions*", (route) =>
    route.fulfill({ json: COMMUNITY_DISCUSSIONS }),
  );
}

async function mockTeacherDashboard(page: Page): Promise<void> {
  await page.route("**/api/teacher/dashboard", (route) =>
    route.fulfill({
      json: { success: true, dashboard: { stats: TEACHER_STATS } },
    }),
  );
  await page.route("**/api/teacher/students*", (route) =>
    route.fulfill({ json: TEACHER_STUDENTS }),
  );
}

async function mockGovernmentDashboard(page: Page): Promise<void> {
  await page.route("**/api/government/dashboard", (route) =>
    route.fulfill({ json: GOVERNMENT_OVERVIEW }),
  );
}

async function mockEnterpriseDashboard(page: Page): Promise<void> {
  await page.route("**/api/enterprise/stats", (route) =>
    route.fulfill({ json: ENTERPRISE_STATS }),
  );
  await page.route("**/api/enterprise/applications", (route) =>
    route.fulfill({ json: ENTERPRISE_APPLICATIONS }),
  );
}

async function mockOperatorOverview(page: Page): Promise<void> {
  await page.route("**/api/operator/**", (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith("/farming/tasks")) {
      return route.fulfill({
        json: { success: true, tasks: [OPERATOR_TASK] },
      });
    }
    if (path.endsWith("/pest/entries")) {
      return route.fulfill({
        json: { success: true, entries: [OPERATOR_ENTRY] },
      });
    }
    if (path.endsWith("/farming/products")) {
      return route.fulfill({
        json: { success: true, products: [OPERATOR_PRODUCT] },
      });
    }
    if (path.endsWith("/farming/phenophases")) {
      return route.fulfill({
        json: { success: true, phenophases: [OPERATOR_PHENOPHASE] },
      });
    }
    if (path.endsWith("/farming/sources")) {
      return route.fulfill({
        json: { success: true, sources: [OPERATOR_SOURCE] },
      });
    }
    if (path.endsWith("/farming/categories")) {
      return route.fulfill({
        json: { success: true, categories: [OPERATOR_CATEGORY] },
      });
    }
    if (path.endsWith("/pest/crops")) {
      return route.fulfill({
        json: { success: true, crops: [OPERATOR_PEST_CROP] },
      });
    }
    if (path.endsWith("/pest/sources")) {
      return route.fulfill({
        json: { success: true, sources: [OPERATOR_PEST_SOURCE] },
      });
    }
    return route.fulfill({
      json: { success: true, tasks: [], entries: [], products: [] },
    });
  });
}

async function mockAdminDashboard(page: Page): Promise<void> {
  await page.route("**/api/admin/dashboard", (route) =>
    route.fulfill({ json: ADMIN_OVERVIEW }),
  );
}

async function mockResumePanel(page: Page): Promise<void> {
  await mockEmployment(page);
  await page.route("**/api/employment/profile/student_demo", (route) =>
    route.fulfill({ json: LEARNER_PROFILE }),
  );
  await page.route("**/api/employment/stats/student_demo", (route) =>
    route.fulfill({ json: LEARNER_STATS }),
  );
  await page.route("**/api/employment/resume/student_demo", (route) =>
    route.fulfill({ json: LEARNER_RESUME }),
  );
}

test.use({ locale: "zh-CN", timezoneId: "Asia/Shanghai" });
test.describe.configure({ timeout: 60_000 });

test.describe("visual matrix: public pages", () => {
  test("home desktop light", async ({ page }) => {
    await preparePage(page);
    await mockHome(page);
    await page.goto("/");
    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await waitForCdnLoaded(page);
    await capture(page, "public-home-desktop-light.png");
  });

  test("agriculture desktop light", async ({ page }) => {
    await preparePage(page);
    await mockAgriculture(page);
    await page.goto("/agriculture");
    await expect(page.getByTestId("agriculture-month")).toHaveText("3月");
    await expect(page.getByTestId("pest-card").first()).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-agriculture-desktop-light.png");
  });

  test("ecommerce desktop light", async ({ page }) => {
    await preparePage(page);
    await page.goto("/ecommerce");
    await expect(page.getByTestId("ecommerce-page")).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-ecommerce-desktop-light.png");
  });

  test("crafts desktop light", async ({ page }) => {
    await preparePage(page);
    await mockCrafts(page);
    await page.goto("/crafts");
    await expect(
      page.getByRole("heading", { name: "广绣", exact: true }),
    ).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-crafts-desktop-light.png");
  });

  test("resources desktop light", async ({ page }) => {
    await preparePage(page);
    await mockResources(page);
    await page.goto("/resources");
    await expect(page.getByText("粤语", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("农业补贴申请指南")).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-resources-desktop-light.png");
  });

  test("employment desktop light", async ({ page }) => {
    await preparePage(page);
    await mockEmployment(page);
    await page.goto("/employment");
    await expect(
      page.getByRole("button", {
        name: "农产品电商运营专员",
        exact: true,
      }),
    ).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-employment-desktop-light.png");
  });

  test("case detail desktop light", async ({ page }) => {
    await preparePage(page);
    await page.route("**/api/resources/cases", (route) =>
      route.fulfill({ json: RESOURCE_CASES }),
    );
    await page.goto("/case-detail/1");
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: "梅县南福村：一颗金柚的电商逆袭",
      }),
    ).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-case-detail-desktop-light.png");
  });

  test("login desktop light", async ({ page }) => {
    await preparePage(page);
    await page.goto("/login");
    await expect(
      page.getByRole("heading", { level: 1, name: "粤乡智匠" }),
    ).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "public-login-desktop-light.png");
  });

  test("community desktop light", async ({ page }) => {
    await preparePage(page);
    await mockCommunity(page);
    await page.goto("/community");
    await expect(page.getByTestId("community-discussion")).toHaveCount(2);
    await waitForCdnLoaded(page);
    await capture(page, "public-community-desktop-light.png");
  });
});

test.describe("visual matrix: backoffice roles", () => {
  const roles = [
    {
      name: "teacher",
      username: "teacher_demo",
      password: "123456",
      landing: /\/teacher\/dashboard$/,
      setup: mockTeacherDashboard,
      ready: async (page: Page) => {
        await expect(page.getByTestId("teacher-stat-total")).toContainText("32");
        await expect(page.getByTestId("teacher-student-row")).toHaveCount(2);
      },
    },
    {
      name: "government",
      username: "gov_demo",
      password: "123456",
      landing: /\/government\/dashboard$/,
      setup: mockGovernmentDashboard,
      ready: async (page: Page) => {
        await expect(page.getByTestId("government-own-total")).toContainText(
          "12",
        );
      },
    },
    {
      name: "enterprise",
      username: "enterprise_demo",
      password: "123456",
      landing: /\/enterprise\/dashboard$/,
      setup: mockEnterpriseDashboard,
      ready: async (page: Page) => {
        await expect(page.getByTestId("enterprise-stat-approved")).toContainText(
          "6",
        );
      },
    },
    {
      name: "operator",
      username: "operator_demo",
      password: "123456",
      landing: /\/operator\/overview$/,
      setup: mockOperatorOverview,
      ready: async (page: Page) => {
        await expect(
          page.getByTestId("operator-stat-overdue-tasks"),
        ).toContainText("1");
      },
    },
    {
      name: "super-admin",
      username: "admin_demo",
      password: "admin123",
      landing: /\/admin\/dashboard$/,
      setup: mockAdminDashboard,
      ready: async (page: Page) => {
        await expect(page.getByTestId("admin-stat-users-total")).toContainText(
          "128",
        );
      },
    },
  ] as const;

  for (const role of roles) {
    test(`${role.name} dashboard desktop light`, async ({ page }) => {
      await preparePage(page);
      await role.setup(page);
      await signIn(page, role.username, role.password);
      await expect(page).toHaveURL(role.landing);
      await role.ready(page);
      await waitForCdnLoaded(page);
      await capture(
        page,
        `backoffice-${role.name}-dashboard-desktop-light.png`,
      );
    });
  }
});

test.describe("visual matrix: themes and responsive samples", () => {
  test("home desktop dark large text", async ({ page }) => {
    await preparePage(page, { theme: "dark", largeText: true });
    await mockHome(page);
    await page.goto("/");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("html")).toHaveAttribute("data-large-text", "1");
    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await waitForCdnLoaded(page);
    await capture(page, "public-home-desktop-dark-large.png");
  });

  test("admin desktop dark large text", async ({ page }) => {
    await preparePage(page, { theme: "dark", largeText: true });
    await mockAdminDashboard(page);
    await signIn(page, "admin_demo", "admin123");
    await expect(page).toHaveURL(/\/admin\/dashboard$/);
    await expect(page.getByTestId("admin-stat-users-total")).toContainText(
      "128",
    );
    await waitForCdnLoaded(page);
    await capture(page, "backoffice-super-admin-dark-large.png");
  });

  test("home desktop with CDN degraded", async ({ page }) => {
    await preparePage(page);
    await blockCdn(page);
    await mockHome(page);
    await page.goto("/");
    await waitForCdnState(page);
    await expect(
      page.getByRole("status").filter({ hasText: "外部资源降级" }),
    ).toBeVisible();
    await capture(page, "public-home-desktop-cdn-degraded.png");
  });

  test("home mobile sample", async ({ page }) => {
    await preparePage(page, { viewport: MOBILE });
    await mockHome(page);
    await page.goto("/");
    await expect(page.getByTestId("home-stat-farmers")).toHaveText("128");
    await waitForCdnLoaded(page);
    await capture(page, "public-home-mobile-light.png", false);
  });

  test("admin mobile sample", async ({ page }) => {
    await preparePage(page, { viewport: MOBILE });
    await mockAdminDashboard(page);
    await signIn(page, "admin_demo", "admin123");
    await expect(page).toHaveURL(/\/admin\/dashboard$/);
    await expect(page.getByTestId("admin-stat-users-total")).toContainText(
      "128",
    );
    await waitForCdnLoaded(page);
    await capture(page, "backoffice-super-admin-mobile-light.png", false);
  });
});

test.describe("visual matrix: empty, loading and error states", () => {
  test("community empty state", async ({ page }) => {
    await preparePage(page);
    await page.route("**/api/discussions*", (route) =>
      route.fulfill({ json: { success: true, discussions: [], total: 0 } }),
    );
    await page.goto("/community");
    await expect(page.getByTestId("community-empty")).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "community-empty-desktop-light.png");
  });

  test("community error state", async ({ page }) => {
    await preparePage(page);
    await page.route("**/api/discussions*", (route) => route.abort());
    await page.goto("/community");
    await expect(page.getByTestId("community-load-error")).toContainText(
      "讨论加载失败",
    );
    await waitForCdnLoaded(page);
    await capture(page, "community-error-desktop-light.png");
  });

  test("admin announcements loading state", async ({ page }) => {
    await preparePage(page);
    await mockAdminDashboard(page);
    let release: (() => void) | undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/admin/system-announcements", async (route) => {
      await gate;
      await route.fulfill({ json: { success: true, announcements: [] } });
    });

    await signIn(page, "admin_demo", "admin123");
    await page.goto("/admin/announcements");
    await expect(page.getByText("正在加载系统公告")).toBeVisible();
    await capture(page, "admin-announcements-loading-desktop-light.png");
    release?.();
  });

  test("admin announcements empty state", async ({ page }) => {
    await preparePage(page);
    await mockAdminDashboard(page);
    await page.route("**/api/admin/system-announcements", (route) =>
      route.fulfill({ json: { success: true, announcements: [] } }),
    );
    await signIn(page, "admin_demo", "admin123");
    await page.goto("/admin/announcements");
    await expect(page.getByTestId("admin-announcements-empty")).toBeVisible();
    await waitForCdnLoaded(page);
    await capture(page, "admin-announcements-empty-desktop-light.png");
  });

  test("admin announcements error state", async ({ page }) => {
    await preparePage(page);
    await mockAdminDashboard(page);
    await page.route("**/api/admin/system-announcements", (route) =>
      route.fulfill({
        status: 503,
        json: { success: false, message: "公告服务暂时不可用" },
      }),
    );
    await signIn(page, "admin_demo", "admin123");
    await page.goto("/admin/announcements");
    await expect(page.getByTestId("admin-announcements-error")).toContainText(
      "公告服务暂时不可用",
    );
    await waitForCdnLoaded(page);
    await capture(page, "admin-announcements-error-desktop-light.png");
  });
});

test.describe("visual matrix: print resume", () => {
  test("resume print preview", async ({ page }) => {
    await preparePage(page);
    await mockResumePanel(page);
    await signIn(page, "student_demo", "123456");
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();
    await expect(page.getByTestId("resume-profile")).toBeVisible();

    const popupPromise = page.waitForEvent("popup");
    await page.getByRole("button", { name: "打印 / 导出 PDF" }).click();
    const popup = await popupPromise;
    await popup.getByTestId("resume-export-text").waitFor();
    await popup.setViewportSize({ width: 794, height: 1123 });
    await popup.emulateMedia({ media: "print", reducedMotion: "reduce" });
    await popup.evaluate(() => document.fonts.ready);
    await expect(popup).toHaveScreenshot("resume-print.png", {
      fullPage: true,
    });
    await popup.close();
  });
});
