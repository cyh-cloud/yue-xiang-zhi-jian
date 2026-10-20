import { expect, test } from "@playwright/test";
import { signIn } from "./auth-route";

const ACCOUNTS = {
  student: { username: "student_demo", password: "123456", landing: "/agriculture/" },
  teacher: { username: "teacher_demo", password: "123456", landing: "/teacher/" },
  enterprise: {
    username: "enterprise_demo",
    password: "123456",
    landing: "/enterprise/",
  },
  government: { username: "gov_demo", password: "123456", landing: "/government/" },
  operator: {
    username: "operator_demo",
    password: "123456",
    landing: "/operator/overview",
  },
  super_admin: {
    username: "admin_demo",
    password: "admin123",
    landing: "/admin/",
  },
} as const;

test.describe("authentication entry and role landing", () => {
  for (const [role, account] of Object.entries(ACCOUNTS)) {
    test(`${role} signs in and lands on the role portal`, async ({ page }) => {
      await signIn(page, account.username, account.password);
      const portal = account.landing.replace(/\/$/, "");
      const landing = portal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      await expect(page).toHaveURL(
        new RegExp(`^(?:https?://[^/]+)?${landing}(?:/dashboard)?$`),
      );
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    });
  }

  test("registration exposes only self-service roles", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "注册", exact: true }).first().click();

    const role = page.getByLabel("注册身份");
    await expect(role.locator("option")).toHaveCount(3);
    await expect(role.locator("option")).toHaveText([
      "学员（学习技能）",
      "教师（传授技能）",
      "企业用户（发布岗位）",
    ]);
  });

  test("student registration lands in the student portal", async ({ page }) => {
    const username = `e2e_student_${Date.now()}`;
    await page.goto("/login");
    await page.getByRole("button", { name: "注册", exact: true }).first().click();
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码").fill("123456");
    await page.getByLabel("姓名").fill("测试学员");
    await page.getByRole("button", { name: "注册", exact: true }).last().click();

    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page.getByRole("heading", { name: "农业技能" })).toBeVisible();
  });
});

test.describe("session recovery and route boundaries", () => {
  test("refresh restores user and capabilities and keeps the portal", async ({
    page,
  }) => {
    await signIn(page, ACCOUNTS.teacher.username, ACCOUNTS.teacher.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);

    await page.reload();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("legacy session without capabilities refreshes them once", async ({
    page,
  }) => {
    const login = await page.request.post("/api/auth/login", {
      data: {
        username: ACCOUNTS.teacher.username,
        password: ACCOUNTS.teacher.password,
      },
    });
    const body = await login.json();
    await page.addInitScript(({ sessionId, user }) => {
      localStorage.setItem(
        "yuexiang_session",
        JSON.stringify({ sessionId, user, capabilities: [] }),
      );
    }, { sessionId: body.session_id, user: body.user });

    let verifyCalls = 0;
    await page.route("**/auth/verify", async (intercepted) => {
      verifyCalls += 1;
      const response = await intercepted.fetch();
      const payload = await response.json();
      payload.capabilities = [];
      await intercepted.fulfill({ response, json: payload });
    });
    let capabilityRefreshes = 0;
    await page.route("**/auth/capabilities", async (intercepted) => {
      capabilityRefreshes += 1;
      await intercepted.continue();
    });
    await page.goto("/teacher/dashboard");
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await expect
      .poll(() => ({ verifyCalls, capabilityRefreshes }), { timeout: 5_000 })
      .toEqual({ verifyCalls: 1, capabilityRefreshes: 1 });

    await page.reload();
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await expect
      .poll(() => ({ verifyCalls, capabilityRefreshes }), { timeout: 5_000 })
      .toEqual({ verifyCalls: 2, capabilityRefreshes: 2 });
  });

  test("anonymous access records the in-site target", async ({ page }) => {
    await page.goto("/teacher/analytics");
    await expect(page).toHaveURL(/\/login\?redirect=\/teacher\/analytics$/);
  });

  test("external redirect targets are ignored", async ({ page }) => {
    await page.goto("/login?redirect=https%3A%2F%2Fevil.example%2Fsteal");
    await signIn(page, ACCOUNTS.student.username, ACCOUNTS.student.password);
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page).not.toHaveURL(/evil\.example/);
  });

  test("cross-role users return to their own default portal", async ({ page }) => {
    await signIn(page, ACCOUNTS.student.username, ACCOUNTS.student.password);
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
  });

  test("unknown backend paths stay inside that portal", async ({ page }) => {
    await signIn(page, ACCOUNTS.teacher.username, ACCOUNTS.teacher.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/not-a-section");
    await expect(page).toHaveURL(/\/teacher(?:\/dashboard)?$/);
    await expect(page.getByRole("heading", { name: "教师工作台" })).toBeVisible();
  });

  test("trailing slashes keep the known portal section", async ({ page }) => {
    await signIn(page, ACCOUNTS.student.username, ACCOUNTS.student.password);
    await page.goto("/agriculture/");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page.getByRole("heading", { name: "农业技能" })).toBeVisible();
  });
});
