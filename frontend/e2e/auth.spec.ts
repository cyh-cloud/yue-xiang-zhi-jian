import { expect, test } from "@playwright/test";
import {
  BACKOFFICE_ROLES,
  NON_ADMIN_BACKOFFICE_ROLES,
  ROLE_ACCOUNTS,
  expectApiDenied,
  expectApiAllowed,
  expectCapabilityFallback,
  expectCrossRoleFallback,
  expectRefreshPreservesRole,
  rolePortal,
  signIn,
} from "./auth-route";

test.use({ serviceWorkers: "block" });

test.describe("authentication entry and role landing", () => {
  for (const role of Object.keys(ROLE_ACCOUNTS) as (keyof typeof ROLE_ACCOUNTS)[]) {
    const account = ROLE_ACCOUNTS[role];
    test(`${role} signs in and lands on the role portal`, async ({ page }) => {
      await signIn(page, account.username, account.password);
      await expect(page).toHaveURL(landingPattern(account.landing));
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
  for (const role of Object.keys(ROLE_ACCOUNTS) as (keyof typeof ROLE_ACCOUNTS)[]) {
    const account = ROLE_ACCOUNTS[role];
    test(`${role} refresh restores the session and keeps the portal`, async ({
      page,
    }) => {
      await expectRefreshPreservesRole(page, account);
    });
  }

  test("legacy session without capabilities refreshes them once", async ({
    page,
  }) => {
    const login = await page.request.post("/api/auth/login", {
      data: {
        username: ROLE_ACCOUNTS.teacher.username,
        password: ROLE_ACCOUNTS.teacher.password,
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
    await signIn(
      page,
      ROLE_ACCOUNTS.student.username,
      ROLE_ACCOUNTS.student.password,
    );
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page).not.toHaveURL(/evil\.example/);
  });

  for (const role of NON_ADMIN_BACKOFFICE_ROLES) {
    test(`${role} returns to its own default portal from another backoffice`, async ({
      page,
    }) => {
      const account = ROLE_ACCOUNTS[role];
      const nextIndex =
        (BACKOFFICE_ROLES.indexOf(role) + 1) % BACKOFFICE_ROLES.length;
      const targetRole = BACKOFFICE_ROLES[nextIndex];
      if (!targetRole) throw new Error("backoffice role matrix is empty");
      await expectCrossRoleFallback(page, account, targetRole);
    });
  }

  test("super-admin enters every backoffice shell but keeps capability API boundaries", async ({
    page,
    request,
  }) => {
    await signIn(
      page,
      ROLE_ACCOUNTS.super_admin.username,
      ROLE_ACCOUNTS.super_admin.password,
    );
    await expect(page).toHaveURL(/\/admin\/dashboard$/);

    for (const role of BACKOFFICE_ROLES) {
      const portal = rolePortal(role);
      await page.goto(portal.shellPath);
      await expect(page.getByTestId("backoffice-shell")).toBeVisible();
    }

    await expectApiAllowed(
      request,
      ROLE_ACCOUNTS.super_admin,
      rolePortal("operator").api,
    );
    for (const role of ["teacher", "government", "enterprise"] as const) {
      await expectCapabilityFallback(
        page,
        ROLE_ACCOUNTS.super_admin,
        role,
      );
    }
    await expectApiDenied(
      request,
      ROLE_ACCOUNTS.super_admin,
      "/api/teacher/courses",
      "POST",
      { title: "T26 超管越权探针", description: "不应创建", category: "综合" },
    );
    await expectApiDenied(
      request,
      ROLE_ACCOUNTS.super_admin,
      "/api/government/policies",
      "POST",
      { title: "T26 超管越权探针", content: "不应创建" },
    );
    await expectApiDenied(
      request,
      ROLE_ACCOUNTS.super_admin,
      "/api/enterprise/jobs",
      "POST",
      {
        title: "T26 超管越权探针",
        salary: "5K-8K",
        location: "广州",
        category: "农业技术",
        description: "不应创建",
        requirements: ["不应创建"],
      },
    );
  });

  test("unknown backend paths stay inside that portal", async ({ page }) => {
    await signIn(
      page,
      ROLE_ACCOUNTS.teacher.username,
      ROLE_ACCOUNTS.teacher.password,
    );
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/not-a-section");
    await expect(page).toHaveURL(/\/teacher(?:\/dashboard)?$/);
    await expect(page.getByRole("heading", { name: "教师工作台" })).toBeVisible();
  });

  test("trailing slashes keep the known portal section", async ({ page }) => {
    await signIn(
      page,
      ROLE_ACCOUNTS.student.username,
      ROLE_ACCOUNTS.student.password,
    );
    await page.goto("/agriculture/");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await expect(page.getByRole("heading", { name: "农业技能" })).toBeVisible();
  });
});

function landingPattern(path: string): RegExp {
  return new RegExp(`${escapeRegExp(path)}/?$`);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
