import {
  expect,
  type APIRequestContext,
  type Page,
  type Route,
} from "@playwright/test";

export const ROLE_ACCOUNTS = {
  student: {
    username: "student_demo",
    password: "123456",
    landing: "/agriculture",
    shellPath: "/agriculture",
    roleLabel: "学员",
    navigationName: "主导航",
    navigationLabel: "农业技能",
  },
  teacher: {
    username: "teacher_demo",
    password: "123456",
    landing: "/teacher/dashboard",
    shellPath: "/teacher",
    roleLabel: "教师",
    navigationName: "后台导航",
    navigationLabel: "3D 模型",
  },
  enterprise: {
    username: "enterprise_demo",
    password: "123456",
    landing: "/enterprise/dashboard",
    shellPath: "/enterprise",
    roleLabel: "企业用户",
    navigationName: "后台导航",
    navigationLabel: "职位管理",
  },
  government: {
    username: "gov_demo",
    password: "123456",
    landing: "/government/dashboard",
    shellPath: "/government",
    roleLabel: "政府",
    navigationName: "后台导航",
    navigationLabel: "政策管理",
  },
  operator: {
    username: "operator_demo",
    password: "123456",
    landing: "/operator/overview",
    shellPath: "/operator",
    roleLabel: "运营用户",
    navigationName: "后台导航",
    navigationLabel: "农时日历",
  },
  super_admin: {
    username: "admin_demo",
    password: "admin123",
    landing: "/admin/dashboard",
    shellPath: "/admin",
    roleLabel: "超级管理员",
    navigationName: "后台导航",
    navigationLabel: "用户管理",
  },
} as const;

export type Role = keyof typeof ROLE_ACCOUNTS;
export type RoleAccount = (typeof ROLE_ACCOUNTS)[Role];

export const BACKOFFICE_ROLES = [
  "teacher",
  "government",
  "enterprise",
  "operator",
  "super_admin",
] as const satisfies readonly Role[];

export type BackofficeRole = (typeof BACKOFFICE_ROLES)[number];
export type NonAdminBackofficeRole = Exclude<BackofficeRole, "super_admin">;

export const NON_ADMIN_BACKOFFICE_ROLES = [
  "teacher",
  "government",
  "enterprise",
  "operator",
] as const satisfies readonly NonAdminBackofficeRole[];

const PATH_BY_ROLE: Record<BackofficeRole, string> = {
  teacher: "/teacher/dashboard",
  government: "/government/dashboard",
  enterprise: "/enterprise/jobs",
  operator: "/operator/farming",
  super_admin: "/admin/content",
};

const CAPABILITY_PROBE_PATH_BY_ROLE: Record<BackofficeRole, string> = {
  teacher: "/teacher/models",
  government: "/government/dashboard",
  enterprise: "/enterprise/jobs",
  operator: "/operator/farming",
  super_admin: "/admin/content",
};

const API_BY_ROLE: Record<BackofficeRole, string> = {
  teacher: "/api/teacher/students",
  government: "/api/government/policies",
  enterprise: "/api/enterprise/jobs",
  operator: "/api/operator/farming/tasks",
  super_admin: "/api/admin/content",
};

export async function signIn(
  page: Page,
  username: string,
  password: string,
  options: { blockCdn?: boolean } = { blockCdn: true },
): Promise<import("@playwright/test").Response> {
  let blockCdn: ((route: Route) => Promise<void>) | undefined;
  if (options.blockCdn) {
    blockCdn = (route) => route.abort();
    await page.route("https://cdn.bootcdn.net/**", blockCdn);
    await page.route("https://unpkg.com/**", blockCdn);
  }

  try {
    await page.goto("/login");
    await page.getByLabel("用户名").fill(username);
    await page.getByLabel("密码").fill(password);
    const responsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/auth/login") &&
        response.request().method() === "POST",
    );
    await page.getByRole("button", { name: "登录", exact: true }).last().click();
    const response = await responsePromise;
    await page.waitForURL((url) => url.pathname !== "/login");
    return response;
  } finally {
    if (blockCdn) {
      await page.unroute("https://cdn.bootcdn.net/**", blockCdn);
      await page.unroute("https://unpkg.com/**", blockCdn);
    }
  }
}

export async function loginWithRequest(
  request: APIRequestContext,
  account: Pick<RoleAccount, "username" | "password">,
): Promise<string> {
  const response = await request.post("/api/auth/login", { data: account });
  expect(response.ok(), await response.text()).toBeTruthy();
  const body = (await response.json()) as { session_id: string };
  return body.session_id;
}

export async function expectApiDenied(
  request: APIRequestContext,
  account: Pick<RoleAccount, "username" | "password">,
  path: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: unknown,
): Promise<void> {
  const sessionId = await loginWithRequest(request, account);
  const response = await request.fetch(path, {
    method,
    headers: { "X-Session-Id": sessionId },
    data,
  });
  expect(
    response.status(),
    `${account.username} unexpectedly accessed ${path}`,
  ).toBe(403);
}

export async function expectApiAllowed(
  request: APIRequestContext,
  account: Pick<RoleAccount, "username" | "password">,
  path: string,
  method: "GET" | "POST" | "PUT" | "DELETE" = "GET",
  data?: unknown,
): Promise<void> {
  const sessionId = await loginWithRequest(request, account);
  const response = await request.fetch(path, {
    method,
    headers: { "X-Session-Id": sessionId },
    data,
  });
  expect(response.ok(), `${account.username} could not access ${path}`).toBe(
    true,
  );
}

export async function expectRefreshPreservesRole(
  page: Page,
  account: RoleAccount,
): Promise<void> {
  await signIn(page, account.username, account.password);
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(account.landing)}/?$`));
  await expectRoleNavigation(page, account);

  await page.reload();
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(account.landing)}/?$`));
  await expectRoleNavigation(page, account);
}

export async function expectCrossRoleFallback(
  page: Page,
  account: RoleAccount,
  targetRole: BackofficeRole,
): Promise<void> {
  await signIn(page, account.username, account.password);
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(account.landing)}/?$`));
  await page.goto(PATH_BY_ROLE[targetRole]);
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(account.landing)}/?$`));
}

export async function expectSuperAdminCapabilityFallback(
  page: Page,
  targetRole: BackofficeRole,
): Promise<void> {
  await page.goto(CAPABILITY_PROBE_PATH_BY_ROLE[targetRole]);
  await expect(page).toHaveURL(
    new RegExp(`${escapeRegExp(ROLE_ACCOUNTS.super_admin.landing)}$`),
  );
  await expect(page.getByTestId("backoffice-role")).toHaveText(
    ROLE_ACCOUNTS.super_admin.roleLabel,
  );
  await expect(
    page
      .getByRole("navigation", { name: ROLE_ACCOUNTS.super_admin.navigationName })
      .getByRole("link", { name: ROLE_ACCOUNTS.super_admin.navigationLabel }),
  ).toBeVisible();
}

export function roleLanding(role: Role): string {
  return ROLE_ACCOUNTS[role].landing;
}

export function rolePortal(
  role: BackofficeRole,
): { path: string; shellPath: string; api: string } {
  return {
    path: PATH_BY_ROLE[role],
    shellPath: ROLE_ACCOUNTS[role].shellPath,
    api: API_BY_ROLE[role],
  };
}

async function expectRoleNavigation(
  page: Page,
  account: RoleAccount,
): Promise<void> {
  await expect(
    page
      .getByRole("navigation", { name: account.navigationName })
      .getByRole("link", { name: account.navigationLabel }),
  ).toBeVisible();
  if (account.navigationName === "后台导航") {
    await expect(page.getByTestId("backoffice-role")).toHaveText(
      account.roleLabel,
    );
  }
}

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
