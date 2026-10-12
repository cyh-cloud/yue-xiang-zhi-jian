import { test, expect } from "@playwright/test";
import { record } from "./helpers.js";

// 轻量前端巡查：各门户页加载不抛未捕获异常、不触发服务端 5xx（503=AI 未配置，排除）。
// 就业门户（enterprise.html）按范围排除。未登录访问可能被重定向，只看“硬崩”，不验功能。
const PAGES = ["/teacher.html", "/admin.html", "/government.html", "/case-detail.html?id=1"];

test("各门户页加载不崩、无 5xx", async ({ page }) => {
  await page.addInitScript(() => {
    window.APP_CONFIG = { apiBaseUrl: window.location.origin };
  });
  const problems = {};
  for (const p of PAGES) {
    const pageerrors = [];
    const server5xx = [];
    const onPageError = (e) => pageerrors.push(e.message);
    const onResponse = (r) => {
      if (r.url().includes("/api/") && r.status() >= 500 && r.status() !== 503) server5xx.push(`${r.status()} ${r.url()}`);
    };
    page.on("pageerror", onPageError);
    page.on("response", onResponse);
    try {
      await page.goto(p, { waitUntil: "load" });
      await page.waitForTimeout(1200);
    } catch (err) {
      pageerrors.push("goto threw: " + err.message);
    }
    page.off("pageerror", onPageError);
    page.off("response", onResponse);
    problems[p] = { pageerrors, server5xx };
  }
  record("portals-smoke.json", problems);
  const flat = [];
  for (const [p, v] of Object.entries(problems)) {
    for (const e of v.pageerrors) flat.push(`${p}: pageerror ${e}`);
    for (const s of v.server5xx) flat.push(`${p}: 5xx ${s}`);
  }
  expect(flat, "门户页前端问题:\n" + flat.join("\n")).toEqual([]);
});
