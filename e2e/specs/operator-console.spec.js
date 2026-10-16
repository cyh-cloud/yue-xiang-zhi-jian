import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, record } from "./helpers.js";

// 运营工作台（operator.html）此前只做过静态检查（内联 JS 语法、url_map 路径解析、
// 页面挂载点断言），没有任何浏览器验证。这条补上：主站登录分流、六个内容块都能
// 渲染出内容、全程没有 pageerror 与 5xx。

// 六个内容块的侧栏 tab 与各自列表的 tbody
const BLOCKS = [
  { tab: "farming", panel: "#page-farming", rows: "#farming-task-rows" },
  { tab: "pest", panel: "#page-pest", rows: "#pest-entry-rows" },
  { tab: "crafts", panel: "#page-crafts", rows: "#craft-rows" },
  { tab: "dialects", panel: "#page-dialects", rows: "#dialect-rows" },
  { tab: "recruitments", panel: "#page-recruitments", rows: "#recruit-rows" },
  { tab: "cases", panel: "#page-cases", rows: "#case-rows" },
];

test("运营主站登录进入工作台，六个内容块都能渲染", async ({ page }) => {
  const problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    // 503 = AI 未配置（e2e 故意置空 AI_API_KEY），不算故障
    if (r.url().includes("/api/") && r.status() >= 500 && r.status() !== 503) {
      problems.push(`5xx: ${r.status()} ${r.url()}`);
    }
  });

  // 1) 从主站登录：运营必须被分流到运营工作台，而不是停在没有任何面板的主页
  await page.goto("/index.html", { waitUntil: "load" });
  await page.evaluate((account) => {
    document.getElementById("login-username").value = account.username;
    document.getElementById("login-password").value = account.password;
    handleLogin();
  }, ACCOUNTS.operator);
  await page.waitForURL(/operator\.html/, { timeout: 15_000 });
  expect(new URL(page.url()).pathname, "运营登录后应落在运营工作台").toBe("/operator.html");
  await expect(page.locator("#sidebar-name")).toHaveText("运营专员");

  // 2) 六个内容块的列表都要渲染出内容
  const counts = {};
  for (const block of BLOCKS) {
    const link = page.locator(`[data-page="${block.tab}"]`);
    await expect(link, `${block.tab} 侧栏入口不可见`).toBeVisible();
    await link.click();
    await expect(page.locator(block.panel), `${block.tab} 面板没切过来`).toBeVisible();
    // 列表是链式取数（先取基础数据，再取列表），用自动等待代替固定睡眠：
    // 睡眠不够会让「先切到别的页签、回来才补齐」的时序问题变成假红。
    await expect(page.locator(`${block.rows} tr`).first())
      .toBeVisible({ timeout: 15_000 })
      .catch(() => { /* 交给下面按行数断言，报出更好读的失败信息 */ });
    counts[block.tab] = await page.locator(`${block.rows} tr`).count();
  }
  record("operator-console.json", counts);
  for (const block of BLOCKS) {
    expect(
      counts[block.tab],
      `${block.tab} 列表没有渲染出任何行（见 findings/operator-console.json）`,
    ).toBeGreaterThan(0);
  }

  // 3) 全程没有前端异常、没有 5xx
  expect(problems, "运营工作台前端问题:\n" + problems.join("\n")).toEqual([]);
});

// 病虫害条目的多值字段（症状 / 防治 / 预防 / 登记药剂 / 用药参考表）此前只做只读展示，
// 列表上连「编辑」入口都没有。这条走真实浏览器：打开弹层 -> 回填 -> 改一行 -> 保存 ->
// 重新打开确认落库。
test("病虫害条目的多值字段可以编辑、保存并回填", async ({ page, request }) => {
  const session = await login(request, ACCOUNTS.operator);
  expect(session.sessionId, "operator 登录失败").toBeTruthy();
  await page.addInitScript(([sid, user]) => {
    localStorage.setItem("yuexiang_session", JSON.stringify({ sessionId: sid, user }));
  }, [session.sessionId, session.user]);

  const problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500 && r.status() !== 503) {
      problems.push(`5xx: ${r.status()} ${r.url()}`);
    }
  });

  await page.goto("/operator.html", { waitUntil: "load" });
  await page.click('[data-page="pest"]');
  await expect(page.locator("#pest-entry-rows tr").first()).toBeVisible();

  const row = page.locator("#pest-entry-rows tr").first();
  const disease = (await row.locator("td").nth(1).textContent()).trim();
  await row.locator('[data-op="pest-edit"]').click();
  await expect(page.locator("#operator-modal")).toBeVisible();

  // 回填：症状是一行一条，不能是空的
  const symptoms = page.locator("#op-field-symptoms");
  await expect(symptoms).not.toHaveValue("");
  const lines = (await symptoms.inputValue()).split("\n");
  const marker = "（e2e已改）";
  await symptoms.fill([lines[0] + marker, ...lines.slice(1)].join("\n"));
  await page.click("#operator-modal-form button[type=submit]");
  await expect(page.locator("#operator-modal")).toBeHidden();

  // 重新打开同一条：改动必须落库
  const again = page.locator("#pest-entry-rows tr").filter({ hasText: disease }).first();
  await again.locator('[data-op="pest-edit"]').click();
  await expect(page.locator("#op-field-symptoms")).toHaveValue(new RegExp(marker));
  await page.click("#op-modal-cancel");
  await expect(page.locator("#operator-modal")).toBeHidden();

  expect(problems, "病虫害编辑流程前端问题:\n" + problems.join("\n")).toEqual([]);
});
