import { expect, test } from "@playwright/test";

test("static entry reports backend unavailable without losing the SPA", async ({
  page,
  request,
}) => {
  const health = await request.get("/api/health", { failOnStatusCode: false });
  expect(health.status()).toBe(502);
  await expect(health.json()).resolves.toMatchObject({
    success: false,
    code: "backend_unreachable",
  });

  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: /农村人才赋能平台/ }),
  ).toBeVisible();
});

test("protected routes distinguish backend failure from anonymous access", async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      "yuexiang_session",
      JSON.stringify({
        sessionId: "legacy-session-id",
        user: {
          id: "teacher_demo",
          name: "张老师",
          role: "teacher",
          email: "",
          phone: "",
          avatar_url: "",
          company_name: "",
          region: "",
          status: "active",
        },
        capabilities: [],
      }),
    );
  });
  await page.goto("/teacher/dashboard");
  await expect(page).toHaveURL(/\/login\?unavailable=1$/);
  await expect(page.getByText("连接服务器失败，请稍后重试")).toBeVisible();
});
