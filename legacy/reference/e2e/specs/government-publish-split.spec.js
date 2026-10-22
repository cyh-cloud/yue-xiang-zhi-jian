import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 政务工作台「发布政策」拆分回归。
// 背景：发布表单原先堆在「政策管理」页顶部，拆成独立页后有三条不能坏的约定：
//   · 侧栏有「发布政策」入口，两页内容隔离（列表页无表单、发布页无列表）
//   · 列表里的「编辑」必须跳到发布页回填，否则用户点了看不到表单
//   · 列表页操作（下架等）的反馈落在列表页，不飘到看不见的表单页

async function enterGov(page, request) {
  const { sessionId, user } = await login(request, ACCOUNTS.gov);
  expect(sessionId, "gov 登录失败").toBeTruthy();
  await page.addInitScript(([sid, usr]) => {
    localStorage.setItem("yuexiang_session", JSON.stringify({ sessionId: sid, user: usr }));
  }, [sessionId, user]);
  await page.goto("/government.html", { waitUntil: "load" });
  await expect(page.locator("#page-dashboard")).toBeVisible();
  return sessionId;
}

test("政务端：发布政策独立成页，侧栏进入，编辑跳转回填，反馈按页路由", async ({ page, request }) => {
  const sid = await enterGov(page, request);

  // —— 侧栏三项：大屏 → 管理 → 发布 ——
  const navTexts = (await page.locator(".portal-sidebar nav a").allTextContents()).map((t) => t.trim());
  expect(navTexts).toEqual(["数据大屏", "政策管理", "发布政策"]);

  // —— 「政策管理」只剩列表，没有表单 ——
  await page.click('.portal-sidebar nav a[data-page="policies"]');
  await expect(page.locator("#page-policies")).toBeVisible();
  await expect(page.locator("#policy-list")).toBeVisible();
  expect(await page.locator("#page-policies #policy-title").count(), "列表页不应残留表单").toBe(0);
  await expect(page.locator("#page-title")).toHaveText("政策管理");

  // —— 「发布政策」只剩表单，没有列表；顶栏标题同步 ——
  await page.click('.portal-sidebar nav a[data-page="publish"]');
  await expect(page.locator("#page-publish")).toBeVisible();
  await expect(page.locator("#page-publish #policy-title")).toBeVisible();
  expect(await page.locator("#page-publish #policy-list").count(), "发布页不应残留列表").toBe(0);
  await expect(page.locator("#page-title")).toHaveText("发布政策");
  // 首次进入是干净的新篇表单
  await expect(page.locator("#policy-form-title")).toHaveText("发布新政策");
  await expect(page.locator("#policy-submit")).toHaveText("发布政策");
  await expect(page.locator("#policy-title")).toHaveValue("");

  // —— 表单发布：成功反馈落在发布页，发布后复位成新篇，列表随后可见 ——
  const title = "__e2e拆分__" + Date.now();
  await page.fill("#policy-title", title);
  await page.fill("#policy-content", "拆分回归：发布表单独立成页。");
  await page.selectOption("#policy-cat", "综合");
  await page.click("#policy-submit");
  await expect(page.locator("#policy-msg")).toContainText("已发布");
  await expect(page.locator("#policy-form-title")).toHaveText("发布新政策");
  await expect(page.locator("#policy-title")).toHaveValue("");
  await page.click('.portal-sidebar nav a[data-page="policies"]');
  await expect(page.locator("#policy-list")).toContainText(title);

  // —— 列表点「编辑」：跳到发布页并回填，表单进入编辑态 ——
  const card = page.locator("#policy-list .card", { hasText: title });
  await card.locator("button", { hasText: "编辑" }).click();
  await expect(page.locator("#page-publish")).toBeVisible();
  await expect(page.locator("#policy-title")).toHaveValue(title);
  await expect(page.locator("#policy-content")).toHaveValue("拆分回归：发布表单独立成页。");
  await expect(page.locator("#policy-form-title")).toHaveText("编辑政策");
  await expect(page.locator("#policy-submit")).toHaveText("保存修改");
  await expect(page.locator("#policy-msg")).toContainText("正在编辑");

  // —— 取消编辑：回到干净新篇 ——
  await page.click("#policy-cancel");
  await expect(page.locator("#policy-form-title")).toHaveText("发布新政策");
  await expect(page.locator("#policy-title")).toHaveValue("");

  // —— 列表页操作的反馈落在列表页，不飘到表单页 ——
  await page.click('.portal-sidebar nav a[data-page="policies"]');
  const card2 = page.locator("#policy-list .card", { hasText: title });
  await card2.locator("button", { hasText: "下架" }).click();
  await expect(page.locator("#policy-list-msg")).toContainText("已下架");
  await expect(page.locator("#policy-list-msg")).toBeVisible();
  await expect(page.locator("#policy-msg")).toBeHidden();
  await expect(card2).toContainText("已下架");

  // 清理：删掉本轮造的政策（走 API，避开 confirm 弹窗）
  const list = await call(request, "GET", "/api/government/policies", { sessionId: sid });
  const mine = ((list.json && list.json.policies) || []).filter((p) => (p.title || "").startsWith("__e2e拆分__"));
  for (const p of mine) {
    await call(request, "DELETE", `/api/government/policies/${p.id}`, { sessionId: sid });
  }
  record("government-publish-split.json", { navTexts, createdTitle: title, cleanedUp: mine.length });
});
