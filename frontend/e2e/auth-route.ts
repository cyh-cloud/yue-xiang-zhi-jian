import type { Page } from "@playwright/test";

const LANDINGS = {
  student: "/agriculture",
  teacher: "/teacher",
  enterprise: "/enterprise",
  government: "/government",
  operator: "/operator/overview",
  super_admin: "/admin",
} as const;

export async function signIn(
  page: Page,
  username: string,
  password: string,
): Promise<import("@playwright/test").Response> {
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
}

export function roleLanding(role: keyof typeof LANDINGS): string {
  return LANDINGS[role];
}
