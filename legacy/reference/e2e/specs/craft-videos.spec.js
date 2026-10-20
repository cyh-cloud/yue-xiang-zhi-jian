import { test, expect } from "@playwright/test";

// 学员端「手工技艺」的视频教学区。
// 背景：视频内容原先借代码常量下发，T10 删常量后详情不再带 videos 键，
// renderCraftVideo 对空数组会把整块收起 —— 学员端从此看不到视频教学。
// 内容现在在 craft_videos 里（migrations/0002_craft_videos.py），这条锁住它没有
// 再次消失。

test("技艺详情展示视频教学区", async ({ page }) => {
  const problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("response", (r) => {
    if (r.url().includes("/api/") && r.status() >= 500 && r.status() !== 503) {
      problems.push(`5xx: ${r.status()} ${r.url()}`);
    }
  });

  await page.goto("/crafts.html", { waitUntil: "load" });
  // 列表里选广绣（视频数据的来源技艺之一）
  const card = page.locator('[data-craft="embroidery"], [data-id="embroidery"]').first();
  if (await card.count()) await card.click();
  await expect(page.locator("#craft-video-section")).toBeVisible({ timeout: 15_000 });
  const cards = await page.locator("#craft-video-list .craft-video-card").count();
  expect(cards, "视频教学区没有渲染出任何卡片").toBeGreaterThan(0);
  await expect(page.locator("#craft-video-source")).toContainText("哔哩哔哩");

  expect(problems, "技艺页前端问题:\n" + problems.join("\n")).toEqual([]);
});
