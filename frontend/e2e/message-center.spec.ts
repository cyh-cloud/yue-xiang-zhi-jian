import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

import { signIn } from "./auth-route";

const STUDENT = { username: "student_demo", password: "123456" } as const;
const TEACHER = { username: "teacher_demo", password: "123456" } as const;
const ENTERPRISE = { username: "enterprise_demo", password: "123456" } as const;
const ADMIN = { username: "admin_demo", password: "admin123" } as const;

interface SessionPayload {
  session_id: string;
  user: { id: string; name: string };
}

interface IdPayload {
  id: number;
}

interface ReviewPayload {
  reviews: Array<{ id: number; content_id: number; content_type: string }>;
}

interface MessagePayload {
  id: number;
  content: string;
}

interface InboxPayload {
  inbox: Array<{ other_id: string; other_name: string; content: string }>;
}

interface ConversationPayload {
  messages: Array<{
    id: number | string;
    sender_id: string;
    content: string;
    created_at: string;
  }>;
}

interface NotificationPayload {
  notifications: Array<{ id: number; title: string }>;
}

interface SeededSources {
  systemTitle: string;
  noticeTitle: string;
  messageContent: string;
  jobTitle: string;
}

async function api<T>(
  request: APIRequestContext,
  method: "GET" | "POST" | "DELETE",
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

async function login(
  request: APIRequestContext,
  account: { username: string; password: string },
): Promise<SessionPayload> {
  return api<SessionPayload>(request, "POST", "/api/auth/login", undefined, account);
}

async function seedFourSources(
  request: APIRequestContext,
  marker: string,
  noticeCount = 1,
): Promise<SeededSources> {
  const [admin, teacher, enterprise, student] = await Promise.all([
    login(request, ADMIN),
    login(request, TEACHER),
    login(request, ENTERPRISE),
    login(request, STUDENT),
  ]);

  const systemTitle = `${marker} 系统公告`;
  await api(request, "POST", "/api/admin/system-announcements", admin.session_id, {
    title: systemTitle,
    content: `${marker} 系统公告正文`,
  });

  const noticeTitle = `${marker} 教师通知 1`;
  for (let index = 1; index <= noticeCount; index += 1) {
    await api(request, "POST", "/api/teacher/announcements", teacher.session_id, {
      title: `${marker} 教师通知 ${index}`,
      content: `${marker} 教师通知正文 ${index}`,
      category: "通知",
    });
  }

  const messageContent = `${marker} 互动私信`;
  await api<MessagePayload>(request, "POST", "/api/messages/send", teacher.session_id, {
    receiver_id: STUDENT.username,
    content: messageContent,
  });

  const jobTitle = `${marker} 招聘岗位`;
  const job = await api<IdPayload>(
    request,
    "POST",
    "/api/enterprise/jobs",
    enterprise.session_id,
    {
      title: jobTitle,
      salary: "5K-8K",
      requirements: ["测试投递通知"],
      description: `${marker} 岗位描述`,
      location: "广州",
      category: "农业技术",
    },
  );
  const pending = await api<ReviewPayload>(
    request,
    "GET",
    "/api/admin/reviews?content_type=job&status=pending&sort=created",
    admin.session_id,
  );
  const review = pending.reviews.find(
    (entry) => entry.content_type === "job" && entry.content_id === job.id,
  );
  expect(review, "新岗位应出现在待审核列表").toBeTruthy();
  await api(request, "POST", `/api/admin/reviews/${review!.id}/approve`, admin.session_id, {});
  await api(request, "POST", "/api/employment/apply", student.session_id, {
    user_id: STUDENT.username,
    job_id: job.id,
  });

  return { systemTitle, noticeTitle, messageContent, jobTitle };
}

async function openCenter(page: Page) {
  await page.getByTestId("message-center-trigger").click();
  await expect(page.getByTestId("message-center-panel")).toBeVisible();
}

function markerPattern(value: string): RegExp {
  return new RegExp(`${value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?!\\d)`);
}

test.describe("shared message center", () => {
  test("four existing sources keep the unread badge and unread list consistent", async ({
    page,
    request,
  }) => {
    const marker = `MC-FOUR-${Date.now()}`;
    const seeded = await seedFourSources(request, marker, 21);

    await signIn(page, STUDENT.username, STUDENT.password);
    await expect(page).toHaveURL(/\/agriculture\/?$/);

    const badge = page.getByTestId("message-center-badge");
    await expect(badge).toBeVisible();
    await expect.poll(async () => Number(await badge.innerText())).toBeGreaterThanOrEqual(4);

    await openCenter(page);
    const panel = page.getByTestId("message-center-panel");
    for (const title of [seeded.systemTitle, seeded.noticeTitle]) {
      await expect(
        panel.getByTestId("message-center-item").filter({ hasText: markerPattern(title) }),
      ).toHaveCount(1);
    }
    await expect(
      panel
        .getByTestId("message-center-item")
        .filter({ hasText: seeded.jobTitle }),
    ).toHaveCount(1);
    await expect(
      panel
        .getByTestId("message-center-item")
        .filter({ hasText: markerPattern(seeded.messageContent) }),
    ).toHaveCount(1);

    const unreadItems = panel.locator(
      '[data-testid="message-center-item"][data-unread="true"]',
    );
    expect(await unreadItems.count()).toBe(Number(await badge.innerText()));
  });

  test("single read, all read and clear read persist across reloads", async ({
    page,
    request,
  }) => {
    const marker = `MC-READ-${Date.now()}`;
    const seeded = await seedFourSources(request, marker);
    const student = await login(request, STUDENT);

    await signIn(page, STUDENT.username, STUDENT.password);
    const badge = page.getByTestId("message-center-badge");
    await expect.poll(async () => Number(await badge.innerText())).toBeGreaterThanOrEqual(4);
    const before = Number(await badge.innerText());

    await openCenter(page);
    const panel = page.getByTestId("message-center-panel");
    await panel
      .getByTestId("message-center-item")
      .filter({ hasText: seeded.noticeTitle })
      .click();

    const detail = page.getByTestId("message-center-detail");
    await expect(detail).toBeVisible();
    await expect(detail).toContainText(seeded.noticeTitle);
    await detail.getByRole("button", { name: "关闭" }).click();

    await expect.poll(async () => Number(await badge.innerText())).toBe(before - 1);
    await panel.getByTestId("message-center-tab-read").click();
    await expect(
      panel.getByTestId("message-center-item").filter({ hasText: seeded.noticeTitle }),
    ).toBeVisible();

    await page.reload();
    await openCenter(page);
    const reloadedPanel = page.getByTestId("message-center-panel");
    await reloadedPanel.getByTestId("message-center-tab-read").click();
    await expect(
      reloadedPanel
        .getByTestId("message-center-item")
        .filter({ hasText: seeded.noticeTitle }),
    ).toBeVisible();

    await reloadedPanel.getByTestId("message-center-mark-all").click();
    await expect(badge).not.toBeVisible();
    await reloadedPanel.getByTestId("message-center-tab-unread").click();
    await expect(reloadedPanel).toContainText("全部已读");

    await page.reload();
    await openCenter(page);
    await expect(page.getByTestId("message-center-badge")).not.toBeVisible();
    await page.getByTestId("message-center-tab-read").click();
    await page.getByTestId("message-center-clear-read").click();
    await expect(
      page
        .getByTestId("message-center-item")
        .filter({ hasText: seeded.noticeTitle }),
    ).toHaveCount(0);
    await expect(
      page.getByTestId("message-center-item").filter({ hasText: marker }),
    ).toHaveCount(0);
    await page.getByTestId("message-center-tab-messages").click();
    await expect(
      page
        .getByTestId("message-center-conversation-item")
        .filter({ hasText: marker }),
    ).toHaveCount(0);

    const notifications = await api<NotificationPayload>(
      request,
      "GET",
      `/api/notifications?user_id=${STUDENT.username}`,
      student.session_id,
    );
    expect(
      notifications.notifications.some((item) => item.title === seeded.noticeTitle),
    ).toBe(false);
  });

  test("conversation replies persist and polling shows new incoming messages", async ({
    page,
    request,
  }) => {
    const marker = `MC-CHAT-${Date.now()}`;
    const [teacher, student] = await Promise.all([
      login(request, TEACHER),
      login(request, STUDENT),
    ]);
    const incoming = `${marker} 老师发来的消息`;
    await api(request, "POST", "/api/messages/send", teacher.session_id, {
      receiver_id: STUDENT.username,
      content: incoming,
    });

    await signIn(page, STUDENT.username, STUDENT.password);
    await openCenter(page);
    await page.getByTestId("message-center-tab-messages").click();
    await page
      .getByTestId("message-center-conversation-item")
      .filter({ hasText: incoming })
      .click();

    const dialog = page.getByRole("dialog", { name: /的对话/ });
    await expect(dialog).toBeVisible();
    const reply = `${marker} 学员回复`;
    await dialog.getByLabel("输入消息").fill(reply);
    await dialog.getByRole("button", { name: "发送消息" }).click();
    await expect(dialog).toContainText(reply);

    await expect
      .poll(async () => {
        const conversation = await api<ConversationPayload>(
          request,
          "GET",
          `/api/messages/conversation/${STUDENT.username}?user_id=${TEACHER.username}`,
          teacher.session_id,
        );
        return conversation.messages.some((item) => item.content === reply);
      })
      .toBe(true);

    const followUp = `${marker} 轮询新消息`;
    await api(request, "POST", "/api/messages/send", teacher.session_id, {
      receiver_id: STUDENT.username,
      content: followUp,
    });
    await expect(dialog).toContainText(followUp, { timeout: 7_000 });

    const inbox = await api<InboxPayload>(
      request,
      "GET",
      `/api/messages/inbox?user_id=${STUDENT.username}`,
      student.session_id,
    );
    expect(inbox.inbox.some((item) => item.content === followUp)).toBe(true);
  });

  test("partial and total source failures have visible recovery states", async ({
    page,
    request,
  }) => {
    const marker = `MC-FAIL-${Date.now()}`;
    const admin = await login(request, ADMIN);
    const systemTitle = `${marker} 可用公告`;
    await api(request, "POST", "/api/admin/system-announcements", admin.session_id, {
      title: systemTitle,
      content: `${marker} 其他来源仍可用`,
    });

    await page.route("**/api/messages/inbox*", (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ success: false, message: "inbox unavailable" }),
      }),
    );
    await signIn(page, STUDENT.username, STUDENT.password);
    await openCenter(page);
    await expect(page.getByTestId("message-center-partial")).toBeVisible();
    await expect(page.getByTestId("message-center-panel")).toContainText(systemTitle);

    await page.unroute("**/api/messages/inbox*");
    await page.reload();
    await page.route("**/api/system-announcements", (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );
    await page.route("**/api/employment/applications/*", (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );
    await page.route("**/api/messages/inbox*", (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );
    await page.route(/\/api\/notifications\?user_id=/, (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );
    await page.route("**/api/notifications/read-state*", (route) =>
      route.fulfill({ status: 503, body: "unavailable" }),
    );

    await openCenter(page);
    await expect(page.getByTestId("message-center-error")).toBeVisible();
    await page.unroute("**/api/system-announcements");
    await page.unroute("**/api/employment/applications/*");
    await page.unroute("**/api/messages/inbox*");
    await page.unroute(/\/api\/notifications\?user_id=/);
    await page.unroute("**/api/notifications/read-state*");
    await page.getByTestId("message-center-retry").click();
    await expect(page.getByTestId("message-center-panel")).toContainText(systemTitle);
  });

  test("anonymous, disabled notification preference and empty states are explicit", async ({
    page,
    request,
  }) => {
    await page.goto("/");
    await openCenter(page);
    await expect(page.getByTestId("message-center-panel")).toContainText(
      "登录后可查看通知",
    );
    await expect(page.getByRole("link", { name: "去登录" })).toBeVisible();
    await page.getByTestId("message-center-trigger").click();

    const admin = await login(request, ADMIN);
    const marker = `MC-PREF-${Date.now()}`;
    const title = `${marker} 偏好公告`;
    await api(request, "POST", "/api/admin/system-announcements", admin.session_id, {
      title,
      content: `${marker} 开启后可见`,
    });

    let sourceRequests = 0;
    await page.route("**/api/system-announcements", async (route) => {
      sourceRequests += 1;
      await route.continue();
    });
    await page.evaluate(() => {
      localStorage.setItem("yuexiang_notif_enabled", "0");
    });
    await signIn(page, STUDENT.username, STUDENT.password);
    await openCenter(page);
    await expect(page.getByTestId("message-center-disabled")).toBeVisible();
    await expect(page.getByTestId("message-center-panel")).toContainText(
      "消息通知已关闭",
    );
    expect(sourceRequests).toBe(0);

    await page.getByTestId("message-center-enable").click();
    await expect.poll(() => sourceRequests).toBeGreaterThan(0);
    await expect(page.getByTestId("message-center-panel")).toContainText(title);
    await page.unroute("**/api/system-announcements");

    const freshUsername = `mc_empty_${Date.now()}`;
    const registered = await api<SessionPayload>(
      request,
      "POST",
      "/api/auth/register",
      undefined,
      {
        username: freshUsername,
        password: "123456",
        name: "空消息测试学员",
        role: "student",
      },
    );
    await api(
      request,
      "POST",
      "/api/notifications/read",
      registered.session_id,
      { user_id: freshUsername },
    );

    await page.evaluate(() => localStorage.removeItem("yuexiang_notif_enabled"));
    await signIn(page, freshUsername, "123456");
    await openCenter(page);
    await expect(page.getByTestId("message-center-empty")).toBeVisible();
    await expect(page.getByTestId("message-center-panel")).toContainText(
      "全部已读，没有待处理通知",
    );
  });
});
