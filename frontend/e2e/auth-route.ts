import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const ROLE_ACCOUNTS = {
  student: {
    username: "student_demo",
    password: "123456",
    landing: "/agriculture",
    portal: "/agriculture",
  },
  teacher: {
    username: "teacher_demo",
    password: "123456",
    landing: "/teacher/dashboard",
    portal: "/teacher",
  },
  enterprise: {
    username: "enterprise_demo",
    password: "123456",
    landing: "/enterprise/dashboard",
    portal: "/enterprise",
  },
  government: {
    username: "gov_demo",
    password: "123456",
    landing: "/government/dashboard",
    portal: "/government",
  },
  operator: {
    username: "operator_demo",
    password: "123456",
    landing: "/operator/overview",
    portal: "/operator",
  },
  super_admin: {
    username: "admin_demo",
    password: "admin123",
    landing: "/admin/dashboard",
    portal: "/admin",
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

const SHELL_PATH_BY_ROLE: Record<BackofficeRole, string> = {
  teacher: "/teacher",
  government: "/government",
  enterprise: "/enterprise",
  operator: "/operator",
  super_admin: "/admin/dashboard",
};

const CAPABILITY_FALLBACK_BY_ROLE: Record<BackofficeRole, string> = {
  teacher: "/teacher/dashboard",
  government: "/admin/dashboard",
  enterprise: "/admin/dashboard",
  operator: "/admin/dashboard",
  super_admin: "/admin/dashboard",
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
): Promise<import("@playwright/test").Response> {
  // Login itself has no business dependency on remote icon/3D assets. Keeping
  // them off the login critical path prevents an external CDN stall from
  // turning every role-matrix case into a navigation timeout.
  await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
  await page.route("https://unpkg.com/**", (route) => route.abort());
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
  await page.unroute("https://cdn.bootcdn.net/**");
  await page.unroute("https://unpkg.com/**");
  return response;
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
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  await page.reload();
  await expect(page).toHaveURL(new RegExp(`${escapeRegExp(account.landing)}/?$`));
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
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

export async function expectCapabilityFallback(
  page: Page,
  account: RoleAccount,
  targetRole: BackofficeRole,
): Promise<void> {
  await signIn(page, account.username, account.password);
  await page.goto(PATH_BY_ROLE[targetRole]);
  await expect(page).toHaveURL(
    new RegExp(`${escapeRegExp(CAPABILITY_FALLBACK_BY_ROLE[targetRole])}$`),
  );
}

export function roleLanding(role: Role): string {
  return ROLE_ACCOUNTS[role].landing;
}

export function rolePortal(
  role: BackofficeRole,
): { path: string; shellPath: string; api: string } {
  return {
    path: PATH_BY_ROLE[role],
    shellPath: SHELL_PATH_BY_ROLE[role],
    api: API_BY_ROLE[role],
  };
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
