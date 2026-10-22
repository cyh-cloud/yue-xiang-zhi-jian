import { expect, test } from "@playwright/test";

test("SPA shell loads and keeps backend API calls behind /api", async ({ page }) => {
  const serverErrors: string[] = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/") && response.status() >= 500) {
      serverErrors.push(`${response.status()} ${response.url()}`);
    }
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "农村人才赋能平台",
  );
  expect(serverErrors).toEqual([]);
});

test("legacy entry points land on SPA routes", async ({ page }) => {
  await page.goto("/teacher-panel.html");
  await expect(page).toHaveURL(/\/login\?redirect=\/teacher\/dashboard$/);
});
