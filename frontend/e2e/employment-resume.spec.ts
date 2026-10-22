import { expect, test } from "@playwright/test";

import { signIn } from "./auth-route";

const STUDENT = { username: "student_demo", password: "123456" };

test.describe("employment resume", () => {
  test("a learner sees real capability data and resume edits survive reload", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    await expect(
      page.getByRole("heading", { name: "能力档案", level: 2 }),
    ).toBeVisible();
    await expect(page.getByTestId("resume-profile")).toContainText("学习积分");
    await expect(page.getByTestId("resume-profile")).toContainText("学习证书");
    await expect(page.getByTestId("resume-profile")).toContainText("实训成绩");
    await expect(page.getByTestId("resume-profile")).toContainText("求职统计");

    const marker = `农产品电商运营 ${Date.now()}`;
    await page.getByLabel("求职意向岗位").fill(marker);
    await page.getByLabel("自我评价").fill("认真负责，熟悉本地农产品。");
    await page.getByLabel("专业技能").fill("直播运营、店铺管理");
    await page.getByRole("button", { name: "保存简历" }).click();
    await expect(page.getByTestId("resume-feedback")).toContainText("简历已保存");

    await page.reload();
    await page.getByRole("tab", { name: "我的简历" }).click();
    await expect(page.getByLabel("求职意向岗位")).toHaveValue(marker);
    await expect(page.getByLabel("自我评价")).toHaveValue(
      "认真负责，熟悉本地农产品。",
    );
  });

  test("AI draft and polish label generated sections without hiding AI involvement", async ({
    page,
  }) => {
    await page.route("**/api/employment/resume/ai", async (route) => {
      const request = route.request().postDataJSON() as {
        section: "self_eval" | "skills" | "experience";
      };
      const text =
        request.section === "experience"
          ? "负责农产品直播策划与店铺日常运营，并按周复盘数据。"
          : "根据平台学习经历整理，具备农产品电商运营基础。";
      await route.fulfill({
        json: {
          success: true,
          section: request.section,
          section_label: request.section,
          text,
          notice: "本段由 AI 根据平台学习数据起草，请核对事实后再使用。",
        },
      });
    });

    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    await page.getByLabel("自我评价").fill("认真负责");
    await page
      .getByTestId("resume-block-self_eval")
      .filter({ has: page.getByLabel("自我评价") })
      .getByRole("button", { name: "AI 起草" })
      .click();
    await expect(page.getByLabel("自我评价")).toHaveValue(
      "根据平台学习经历整理，具备农产品电商运营基础。",
    );
    await expect(
      page.getByTestId("resume-ai-flag-self_eval"),
    ).toContainText("已用 AI 辅助");
    await expect(page.getByTestId("resume-ai-summary")).toContainText(
      "使用过 AI 辅助",
    );

    await page.getByRole("button", { name: "添加经历" }).click();
    await page.getByLabel("经历 1 单位").fill("粤乡合作社");
    await page.getByLabel("经历 1 角色").fill("运营助理");
    await page.getByLabel("经历 1 描述").fill("协助店铺运营");
    await page.getByRole("button", { name: "AI 润色" }).click();
    await expect(page.getByLabel("经历 1 描述")).toHaveValue(
      "负责农产品直播策划与店铺日常运营，并按周复盘数据。",
    );
    await expect(
      page.getByTestId("resume-ai-flag-experience"),
    ).toContainText("已用 AI 辅助");
  });

  test("AI failure keeps the learner's original text intact", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    const original = "这是我本人填写的自我评价，AI 失败时不能丢。";
    await page.getByLabel("自我评价").fill(original);
    await page
      .getByTestId("resume-block-self_eval")
      .filter({ has: page.getByLabel("自我评价") })
      .getByRole("button", { name: "AI 起草" })
      .click();

    await expect(page.getByTestId("resume-feedback")).toContainText(
      "AI 辅助功能尚未启用",
    );
    await expect(page.getByLabel("自我评价")).toHaveValue(original);
    await expect(
      page.getByTestId("resume-ai-flag-self_eval"),
    ).toHaveCount(0);
  });

  test("print preview uses only the learner's profile and form data", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    const marker = `本人填写的求职意向 ${Date.now()}`;
    await page.getByLabel("求职意向岗位").fill(marker);
    await page.getByLabel("自我评价").fill("只属于当前学员的简历内容。");

    const popupPromise = page.waitForEvent("popup");
    await page.getByRole("button", { name: "打印 / 导出 PDF" }).click();
    const popup = await popupPromise;
    await expect(
      popup.getByTestId("resume-export-text"),
    ).toContainText(marker);
    await expect(
      popup.getByTestId("resume-export-text"),
    ).toContainText("只属于当前学员的简历内容。");
    await expect(
      popup.getByTestId("resume-export-text"),
    ).toContainText("平台学习证书（已获得）");
    await expect(
      popup.getByTestId("resume-export-text"),
    ).not.toContainText("teacher_demo");
  });

  test("empty capability data is explained instead of looking like a failure", async ({
    page,
  }) => {
    await page.route("**/api/employment/profile/student_demo", (route) =>
      route.fulfill({
        json: {
          success: true,
          profile: {
            basic: {
              username: "student_demo",
              name: "演示学员",
              email: "",
              phone: "",
              bio: "",
              region: "",
            },
            certificates: [],
            points: 0,
            learning: null,
            training: [],
          },
        },
      }),
    );
    await page.route("**/api/employment/stats/student_demo", (route) =>
      route.fulfill({
        json: {
          success: true,
          stats: { applied: 0, saved: 0, intents: 0, messages: 0 },
        },
      }),
    );
    await page.route("**/api/employment/resume/student_demo", (route) =>
      route.fulfill({
        json: { success: true, resume: null },
      }),
    );

    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    await expect(page.getByTestId("resume-profile")).toContainText(
      "暂无证书记录",
    );
    await expect(page.getByTestId("resume-profile")).toContainText(
      "暂无实训记录",
    );
    await expect(page.getByText("还没有添加经历")).toBeVisible();
  });

  test("profile loading failure offers a retry", async ({ page }) => {
    await page.route("**/api/employment/profile/student_demo", (route) =>
      route.abort(),
    );

    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/employment");
    await page.getByRole("tab", { name: "我的简历" }).click();

    await expect(page.getByRole("alert")).toContainText(
      "连接服务器失败，请检查网络后重试",
    );
    await expect(page.getByRole("button", { name: "重试" })).toBeVisible();
  });
});
