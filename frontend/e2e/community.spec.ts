import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { signIn } from "./auth-route";

const STUDENT = { username: "student_demo", password: "123456" } as const;

interface SessionPayload {
  session_id: string;
}

interface DiscussionPayload {
  id: number;
}

async function api<T>(
  request: APIRequestContext,
  method: "GET" | "POST",
  path: string,
  sessionId?: string,
  data?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (sessionId) headers["X-Session-Id"] = sessionId;
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const response = await request.fetch(path, { method, headers, data });
  expect(
    response.ok(),
    `${method} ${path} failed with ${response.status()}: ${await response.text()}`,
  ).toBeTruthy();
  return (await response.json()) as T;
}

async function login(request: APIRequestContext): Promise<string> {
  const session = await api<SessionPayload>(
    request,
    "POST",
    "/api/auth/login",
    undefined,
    STUDENT,
  );
  return session.session_id;
}

async function seedDiscussion(
  request: APIRequestContext,
  marker: string,
): Promise<number> {
  const sessionId = await login(request);
  const discussion = await api<DiscussionPayload>(
    request,
    "POST",
    "/api/discussions",
    sessionId,
    {
      title: `${marker} 讨论帖`,
      content: `${marker} 讨论正文`,
      category: "general",
    },
  );
  await api(request, "POST", "/api/comments", sessionId, {
    target_type: "discussion",
    target_id: discussion.id,
    content: `${marker} 已有评论`,
  });
  return discussion.id;
}

async function signInFromCurrentLogin(page: Page): Promise<void> {
  await page.getByLabel("用户名").fill(STUDENT.username);
  await page.getByLabel("密码").fill(STUDENT.password);
  await page.getByRole("button", { name: "登录", exact: true }).last().click();
}

test.describe("community discussions", () => {
  test("the resources entry opens the public discussion area", async ({
    page,
  }) => {
    await page.goto("/resources");
    await page.getByRole("link", { name: "进入社区讨论" }).click();

    await expect(page).toHaveURL(/\/community$/);
    await expect(
      page.getByRole("heading", { name: "社区讨论", level: 1 }),
    ).toBeVisible();
  });

  test("anonymous visitors can browse discussions and comments", async ({
    page,
    request,
  }) => {
    const marker = `COMMUNITY-READ-${Date.now()}`;
    const discussionId = await seedDiscussion(request, marker);

    await page.goto("/community");

    await expect(
      page.getByRole("heading", { name: "社区讨论", level: 1 }),
    ).toBeVisible();
    const card = page
      .getByTestId("community-discussion")
      .filter({ hasText: `${marker} 讨论帖` });
    await expect(card).toBeVisible();
    await card.getByRole("link", { name: `${marker} 讨论帖` }).click();

    await expect(page).toHaveURL(new RegExp(`/community/${discussionId}$`));
    await expect(
      page.getByRole("heading", { name: `${marker} 讨论帖`, level: 1 }),
    ).toBeVisible();
    await expect(page.getByText(`${marker} 讨论正文`)).toBeVisible();
    await expect(page.getByText(`${marker} 已有评论`)).toBeVisible();
    await expect(page.getByTestId("community-login-prompt")).toBeVisible();
  });

  test("anonymous write actions return to the original target after login", async ({
    page,
  }) => {
    await page.goto("/community");
    await page.getByTestId("community-new-button").click();

    await expect(page).toHaveURL(/\/login\?redirect=/);
    await expect
      .poll(() => new URL(page.url()).searchParams.get("redirect"))
      .toBe("/community?action=new");

    await signInFromCurrentLogin(page);

    await expect(page).toHaveURL(/\/community\?action=new$/);
    await expect(page.getByTestId("community-composer")).toBeVisible();
    await expect(page.getByLabel("讨论标题")).toBeFocused();
  });

  test("anonymous comment action restores the discussion and comment focus", async ({
    page,
    request,
  }) => {
    const marker = `COMMUNITY-COMMENT-LOGIN-${Date.now()}`;
    const discussionId = await seedDiscussion(request, marker);
    await page.goto(`/community/${discussionId}`);

    await page.getByRole("button", { name: "登录后评论" }).click();
    await expect(page).toHaveURL(/\/login\?redirect=/);
    await expect
      .poll(() => new URL(page.url()).searchParams.get("redirect"))
      .toBe(`/community/${discussionId}?action=comment`);

    await signInFromCurrentLogin(page);

    await expect(page).toHaveURL(
      new RegExp(`/community/${discussionId}\\?action=comment$`),
    );
    await expect(page.getByLabel("评论内容")).toBeFocused();
  });

  test("a learner publishes and comments without refreshing the page", async ({
    page,
  }) => {
    const marker = `COMMUNITY-WRITE-${Date.now()}`;
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/community");

    await page.getByTestId("community-new-button").click();
    await page.getByLabel("讨论标题").fill(`${marker} 新讨论`);
    await page.getByLabel("讨论正文").fill(`${marker} 新正文`);
    await page
      .getByTestId("community-composer")
      .getByLabel("讨论分类")
      .selectOption("agriculture");

    const createResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/discussions") &&
        response.request().method() === "POST",
    );
    await page.getByTestId("community-submit").click();
    expect((await createResponse).ok()).toBe(true);

    await expect(page.getByTestId("community-feedback")).toContainText(
      "发布成功",
    );
    const card = page
      .getByTestId("community-discussion")
      .filter({ hasText: `${marker} 新讨论` });
    await expect(card).toBeVisible();
    await card.getByRole("link", { name: `${marker} 新讨论` }).click();

    await expect(
      page.getByRole("heading", { name: `${marker} 新讨论`, level: 1 }),
    ).toBeVisible();
    await page
      .getByLabel("评论内容")
      .fill(`${marker} 新评论`);
    const commentResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/comments") &&
        response.request().method() === "POST",
    );
    await page.getByTestId("community-comment-submit").click();
    expect((await commentResponse).ok()).toBe(true);

    await expect(page.getByTestId("community-comment-feedback")).toContainText(
      "评论成功",
    );
    await expect(page.getByText(`${marker} 新评论`)).toBeVisible();
  });

  test("empty and failed lists have explicit states", async ({ page }) => {
    await page.route("**/api/discussions*", (route) =>
      route.fulfill({
        json: { success: true, discussions: [], total: 0 },
      }),
    );
    await page.goto("/community");
    await expect(page.getByTestId("community-empty")).toContainText(
      "暂无讨论帖",
    );

    await page.unroute("**/api/discussions*");
    await page.route("**/api/discussions*", (route) => route.abort());
    await page.reload();
    await expect(page.getByTestId("community-load-error")).toContainText(
      "讨论加载失败",
    );
  });

  test("overlong content and backend rejection stay visible", async ({
    page,
  }) => {
    await signIn(page, STUDENT.username, STUDENT.password);
    await page.goto("/community?action=new");

    await page.getByLabel("讨论标题").fill("长".repeat(81));
    await page.getByLabel("讨论正文").fill("正文");
    await page.getByTestId("community-submit").click();
    await expect(page.getByTestId("community-feedback")).toContainText(
      "标题不能超过 80 字",
    );

    await page.getByLabel("讨论标题").fill("后端拒绝测试");
    await page.getByLabel("讨论正文").fill("正文");
    await page.route("**/api/discussions", (route) =>
      route.fulfill({
        status: 400,
        json: {
          success: false,
          code: "content_rejected",
          message: "讨论内容触发审核限制",
        },
      }),
    );
    await page.getByTestId("community-submit").click();
    await expect(page.getByTestId("community-feedback")).toContainText(
      "讨论内容触发审核限制",
    );
  });
});
