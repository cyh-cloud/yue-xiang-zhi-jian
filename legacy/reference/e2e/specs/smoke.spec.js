import { test, expect } from "@playwright/test";
import { record } from "./helpers.js";

// 前端默认连 localhost:5000；注入 APP_CONFIG 让它打到 E2E 实例（同源）。
test("门户首页：无服务端 5xx、无失败 API、主体可见", async ({ page }) => {
  const serverErrors = [];
  const aiUnavailable = [];
  const failed = [];
  const consoleErrors = [];

  page.on("response", (r) => {
    if (!r.url().includes("/api/")) return;
    if (r.status() >= 500) {
      // 503 = AI 未配置的预期返回，单独归类，不当 bug
      (r.status() === 503 ? aiUnavailable : serverErrors).push(`${r.status()} ${r.url()}`);
    }
  });
  page.on("requestfailed", (r) => {
    if (r.url().includes("/api/")) failed.push(`${r.method()} ${r.url()} -> ${r.failure()?.errorText}`);
  });
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));

  await page.addInitScript(() => {
    window.APP_CONFIG = { apiBaseUrl: window.location.origin };
  });
  await page.goto("/", { waitUntil: "load" });
  await expect(page.locator("body")).toBeVisible();
  await page.waitForTimeout(2000); // 给首屏 API 收敛的时间

  record("smoke-index.json", { url: page.url(), serverErrors, aiUnavailable, failed, consoleErrors });
  expect(serverErrors, "首页触发后端服务端错误(5xx):\n" + serverErrors.join("\n")).toEqual([]);
  expect(failed, "首页 API 请求失败:\n" + failed.join("\n")).toEqual([]);
});
