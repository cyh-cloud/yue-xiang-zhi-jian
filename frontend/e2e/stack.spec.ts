import { expect, test } from "@playwright/test";

const TEACHER = { username: "teacher_demo", password: "123456" };

test("built SPA history routes and API requests reach the real backend", async ({
  page,
  request,
}) => {
  const response = await page.goto("/teacher/dashboard");
  expect(response).not.toBeNull();
  const html = await response!.text();

  expect(html).toContain("/assets/");
  expect(html).not.toContain("/src/main.ts");
  await expect(page).toHaveURL(/\/login\?redirect=\/teacher\/dashboard$/);
  await expect(
    page.getByRole("heading", { name: "登录粤乡智匠" }),
  ).toBeVisible();

  const health = await request.get("/api/health");
  expect(health.status()).toBe(200);
  await expect(health.json()).resolves.toMatchObject({
    success: true,
    healthy: true,
    service: "粤乡智匠API",
  });
});

test("real backend accepts a session while built SPA survives a history reload", async ({
  page,
  request,
}) => {
  const login = await request.post("/api/auth/login", { data: TEACHER });
  expect(login.status()).toBe(200);
  const session = await login.json();
  expect(session).toMatchObject({
    success: true,
    user: { role: "teacher" },
  });
  expect(session.session_id).toBeTruthy();

  const verify = await request.post("/api/auth/verify", {
    data: { session_id: session.session_id },
  });
  expect(verify.status()).toBe(200);

  await page.goto("/agriculture");
  await expect(page).toHaveURL(/\/agriculture$/);
  await expect(
    page.getByRole("heading", { name: "农业技能" }),
  ).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(/\/agriculture$/);
  await expect(
    page.getByRole("heading", { name: "农业技能" }),
  ).toBeVisible();
});
