import {
  expect,
  test,
  type Page,
} from "@playwright/test";

const ROLES = {
  teacher: {
    username: "teacher_demo",
    password: "123456",
    landing: /\/teacher\/dashboard$/,
    title: "教师工作台",
    roleLabel: "教师",
    accent: "#2f6b4f",
  },
  government: {
    username: "gov_demo",
    password: "123456",
    landing: /\/government\/dashboard$/,
    title: "政府工作台",
    roleLabel: "政府",
    accent: "#4a6fa5",
  },
  enterprise: {
    username: "enterprise_demo",
    password: "123456",
    landing: /\/enterprise\/dashboard$/,
    title: "企业中心",
    roleLabel: "企业用户",
    accent: "#a9673a",
  },
  operator: {
    username: "operator_demo",
    password: "123456",
    landing: /\/operator\/overview$/,
    title: "运营工作台",
    roleLabel: "运营用户",
    accent: "#65733d",
  },
  super_admin: {
    username: "admin_demo",
    password: "admin123",
    landing: /\/admin\/dashboard$/,
    title: "系统管理后台",
    roleLabel: "超级管理员",
    accent: "#213b32",
  },
} as const;

interface AdminOverviewPayload {
  overview: {
    users: {
      total: number;
    };
  };
}

async function signIn(
  page: Page,
  username: string,
  password: string,
): Promise<void> {
  // The admin shell does not depend on remote icon or 3D scripts. Blocking
  // them keeps this behavior suite independent from CDN latency.
  await page.route("https://cdn.bootcdn.net/**", (route) => route.abort());
  await page.route("https://unpkg.com/**", (route) => route.abort());
  await page.goto("/login");
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).last().click();
}

test.describe("shared backoffice shell", () => {
  for (const [role, account] of Object.entries(ROLES)) {
    test(`${role} lands in the shared shell with one message center`, async ({
      page,
    }) => {
      await signIn(page, account.username, account.password);
      await expect(page).toHaveURL(account.landing);

      const shell = page.getByTestId("backoffice-shell");
      await expect(shell).toHaveAttribute("data-role", role);
      await expect(
        shell.getByRole("heading", { level: 1, name: account.title }),
      ).toBeVisible();
      await expect(
        shell.getByRole("navigation", { name: "后台导航" }),
      ).toBeVisible();
      await expect(shell.getByTestId("backoffice-role")).toHaveText(
        account.roleLabel,
      );
      await expect(shell).toHaveCSS("--bo-accent", account.accent);
      await expect(page.getByTestId("message-center-trigger")).toHaveCount(1);
    });
  }

  test("sidebar collapse supports pointer and keyboard controls", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);

    const toggle = page.getByTestId("backoffice-sidebar-toggle");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await toggle.focus();
    await page.keyboard.press("Enter");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");

    await page.keyboard.press("Control+b");
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(toggle).toBeFocused();
  });

  test("navigation keeps the current section, main focus and collapsed state", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.teacher.username,
      ROLES.teacher.password,
    );
    await expect(page).toHaveURL(ROLES.teacher.landing);

    const announcements = page
      .getByRole("navigation", { name: "后台导航" })
      .getByRole("link", { name: "通知公告" });
    await announcements.click();
    await expect(page).toHaveURL(/\/teacher\/announcements$/);
    await expect(announcements).toHaveAttribute("aria-current", "page");
    await expect(page.getByTestId("backoffice-main")).toBeFocused();

    const toggle = page.getByTestId("backoffice-sidebar-toggle");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "false");

    await page.reload();
    await expect(page).toHaveURL(/\/teacher\/announcements$/);
    await expect(page.getByTestId("backoffice-shell")).toHaveClass(
      /is-collapsed/,
    );
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await expect(announcements).toHaveAttribute("aria-current", "page");
  });

  test("connection state reflects a real API outage and recovery", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);
    const connection = page.getByTestId("backoffice-connection");
    await expect(connection).toContainText("已连接");

    await page.route("**/api/admin/dashboard", (route) =>
      route.abort("connectionfailed"),
    );
    await page.getByRole("button", { name: "刷新统计" }).click();
    await expect(connection).toContainText("连接失败");

    await page.unroute("**/api/admin/dashboard");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(connection).toContainText("已连接");
  });
});

test.describe("super-admin dashboard and user governance", () => {
  test("dashboard renders the real overview returned by the API", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);
    const overview = await page.evaluate(async () => {
      const stored = JSON.parse(
        localStorage.getItem("yuexiang_session") || "{}",
      ) as { sessionId?: string };
      const response = await fetch("/api/admin/dashboard", {
        headers: { "X-Session-Id": stored.sessionId || "" },
      });
      if (!response.ok) throw new Error(`dashboard request failed: ${response.status}`);
      return ((await response.json()) as AdminOverviewPayload).overview;
    });
    await expect(page.getByTestId("admin-stat-users-total")).toContainText(
      String(overview.users.total),
    );
    await expect(page.getByTestId("admin-dashboard-note")).toContainText(
      "仅统计库内真实可算的项",
    );
  });

  test("user lifecycle edits, suspends, restores and deletes safely", async ({
    page,
    request,
  }) => {
    const username = `e2e_admin_${Date.now()}`;
    const registered = await request.post("/api/auth/register", {
      data: {
        username,
        password: "123456",
        name: "后台治理测试",
        role: "student",
      },
    });
    expect(registered.ok()).toBeTruthy();

    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);
    await page.goto("/admin/users");

    const search = page.getByLabel("搜索用户");
    await search.fill(username);
    const row = page.locator(`[data-testid="admin-user-row"][data-username="${username}"]`);
    await expect(row).toBeVisible();

    await row.getByTestId("admin-user-edit").click();
    const editor = page.getByTestId("admin-user-editor");
    await expect(editor).toBeVisible();
    await editor.getByLabel("姓名").fill("后台改名成功");
    await editor.getByRole("button", { name: "保存" }).click();
    await expect(page.getByTestId("admin-users-feedback")).toContainText(
      "更新成功",
    );
    await expect(row).toContainText("后台改名成功");

    await row.getByTestId("admin-user-status").click();
    const statusDialog = page.getByTestId("admin-confirm-dialog");
    await expect(statusDialog).toContainText("停用后本人无法登录");
    await statusDialog.getByRole("button", { name: "确认停用" }).click();
    await expect(page.getByTestId("admin-users-feedback")).toContainText(
      "已停用",
    );
    await expect(row).toContainText("已停用");

    await row.getByTestId("admin-user-status").click();
    await page
      .getByTestId("admin-confirm-dialog")
      .getByRole("button", { name: "确认启用" })
      .click();
    await expect(page.getByTestId("admin-users-feedback")).toContainText(
      "已启用",
    );
    await expect(row).toContainText("正常");

    await row.getByTestId("admin-user-delete").click();
    const deleteDialog = page.getByTestId("admin-confirm-dialog");
    await expect(deleteDialog).toContainText("此操作不可恢复");
    await deleteDialog.getByRole("button", { name: "确认删除" }).click();
    await expect(page.getByTestId("admin-users-feedback")).toContainText(
      "删除成功",
    );
    await expect(row).toHaveCount(0);
  });

  test("user dialogs manage focus, trap Tab and close with Escape", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);
    await page.goto("/admin/users");
    const search = page.getByLabel("搜索用户");
    await search.fill("admin_demo");

    const row = page.locator(
      '[data-testid="admin-user-row"][data-username="admin_demo"]',
    );
    const edit = row.getByTestId("admin-user-edit");
    await edit.click();

    const editor = page.getByTestId("admin-user-editor");
    const name = editor.getByLabel("姓名");
    await expect(name).toBeFocused();
    await expect(editor.getByLabel("状态")).toBeDisabled();
    await expect(editor).toContainText("当前登录账号不能停用自己");
    await page.keyboard.press("Shift+Tab");
    await expect(editor.getByRole("button", { name: "关闭" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(editor).toHaveCount(0);
    await expect(edit).toBeFocused();

    await search.fill("student_demo");
    const studentRow = page.locator(
      '[data-testid="admin-user-row"][data-username="student_demo"]',
    );
    const status = studentRow.getByTestId("admin-user-status");
    await expect(status).toBeVisible();
    await status.click();
    const confirm = page.getByTestId("admin-confirm-dialog");
    const cancel = confirm.getByRole("button", { name: "取消" });
    await expect(cancel).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(confirm).toHaveCount(0);
    await expect(status).toBeFocused();
  });

  test("self, associated-data and last-super-admin protections stay visible", async ({
    page,
  }) => {
    await signIn(
      page,
      ROLES.super_admin.username,
      ROLES.super_admin.password,
    );
    await expect(page).toHaveURL(ROLES.super_admin.landing);
    await page.goto("/admin/users");

    const search = page.getByLabel("搜索用户");
    await search.fill("admin_demo");
    const adminRow = page.locator(
      '[data-testid="admin-user-row"][data-username="admin_demo"]',
    );
    await expect(adminRow).toContainText("当前登录账号，不能删除自己");

    await adminRow.getByTestId("admin-user-edit").click();
    const editor = page.getByTestId("admin-user-editor");
    await editor.getByLabel("角色").selectOption("teacher");
    await editor.getByRole("button", { name: "保存" }).click();
    await expect(page.getByTestId("admin-user-editor-error")).toContainText(
      "系统必须保留至少一个超级管理员",
    );
    await editor.getByRole("button", { name: "取消" }).click();

    await search.fill("student_demo");
    const studentRow = page.locator(
      '[data-testid="admin-user-row"][data-username="student_demo"]',
    );
    await expect(studentRow).toContainText("关联业务数据");
    await expect(studentRow.getByTestId("admin-user-delete")).toHaveCount(0);
  });
});
