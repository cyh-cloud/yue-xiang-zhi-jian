import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

import {
  ROLE_ACCOUNTS,
  expectApiDenied,
  expectCrossRoleFallback,
  rolePortal,
  signIn,
} from "./auth-route";

const GOVERNMENT = ROLE_ACCOUNTS.government;

async function loginWithRequest(request: APIRequestContext): Promise<string> {
  const response = await request.post("/api/auth/login", {
    data: GOVERNMENT,
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { session_id: string };
  return body.session_id;
}

async function createPolicyWithApi(
  request: APIRequestContext,
  sessionId: string,
  payload: Record<string, string>,
): Promise<number> {
  const response = await request.post("/api/government/policies", {
    headers: { "X-Session-Id": sessionId },
    data: payload,
  });
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { id: number };
  return body.id;
}

async function deletePolicyWithApi(
  request: APIRequestContext,
  sessionId: string,
  policyId: number,
): Promise<void> {
  const response = await request.delete(
    `/api/government/policies/${policyId}`,
    { headers: { "X-Session-Id": sessionId } },
  );
  expect(response.ok()).toBeTruthy();
}

async function publicPolicyIds(request: APIRequestContext): Promise<number[]> {
  const response = await request.get("/api/resources/policies");
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as {
    policies: Array<{ id: number }>;
  };
  return body.policies.map((policy) => policy.id);
}

async function openGovernmentPolicies(page: Page): Promise<void> {
  await page
    .getByRole("navigation", { name: "后台导航" })
    .getByRole("link", { name: "政策管理" })
    .click();
  await expect(page).toHaveURL(/\/government\/policies$/);
}

interface GovernmentOverviewPayload {
  overview: {
    policies: {
      own: { total: number; published: number; unpublished: number };
      preset: { total: number; published: number; unpublished: number };
      categories: Array<{ category: string; count: number }>;
    };
    cases: {
      total: number;
      approved: number;
      pending: number;
      rejected: number;
      regions: Array<{ region: string; count: number }>;
      source_total: number;
      avg_sources: number;
      items: Array<{ id: number; title: string; region: string; sources: number }>;
    };
  };
}

test.describe("government dashboard and policy management", () => {
  test("dashboard renders the real policy and case overview", async ({ page }) => {
    await signIn(page, GOVERNMENT.username, GOVERNMENT.password);
    await expect(page).toHaveURL(/\/government\/dashboard$/);

    const overview = await page.evaluate(async () => {
      const stored = JSON.parse(
        localStorage.getItem("yuexiang_session") || "{}",
      ) as { sessionId?: string };
      const response = await fetch("/api/government/dashboard", {
        headers: { "X-Session-Id": stored.sessionId || "" },
      });
      if (!response.ok) {
        throw new Error(`dashboard request failed: ${response.status}`);
      }
      return ((await response.json()) as GovernmentOverviewPayload).overview;
    });

    await expect(page.getByTestId("government-own-total")).toContainText(
      String(overview.policies.own.total),
    );
    await expect(page.getByTestId("government-own-published")).toContainText(
      String(overview.policies.own.published),
    );
    await expect(page.getByTestId("government-own-unpublished")).toContainText(
      String(overview.policies.own.unpublished),
    );
    await expect(page.getByTestId("government-preset-total")).toContainText(
      String(overview.policies.preset.total),
    );
    await expect(page.getByTestId("government-category-count")).toContainText(
      String(overview.policies.categories.length),
    );
    await expect(page.getByTestId("government-approved-cases")).toContainText(
      String(overview.cases.approved),
    );
    await expect(page.getByTestId("government-dashboard-note")).toContainText(
      "只呈现政务侧产生的信息",
    );
  });

  test("policy publish, dynamic category, edit, visibility and scoped feedback work end to end", async ({
    page,
    request,
  }) => {
    const sessionId = await loginWithRequest(request);
    const stamp = Date.now();
    const dynamicCategory = `测试分类${stamp}`;
    const categoryPolicyId = await createPolicyWithApi(request, sessionId, {
      title: `__e2e_t18_category_${stamp}`,
      content: "用于验证动态政策分类。",
      category: dynamicCategory,
      summary: "动态分类探针",
      date: "2026-10-20",
    });
    let publishedPolicyId: number | null = null;
    let editedPolicyId: number | null = null;

    try {
      await signIn(page, GOVERNMENT.username, GOVERNMENT.password);
      await expect(page).toHaveURL(/\/government\/dashboard$/);

      await page
        .getByRole("navigation", { name: "后台导航" })
        .getByRole("link", { name: "发布政策" })
        .click();
      await expect(page).toHaveURL(/\/government\/publish$/);
      await expect(
        page.getByRole("heading", { level: 1, name: "发布新政策" }),
      ).toBeVisible();
      await expect(
        page.getByLabel("政策分类").locator("option", {
          hasText: dynamicCategory,
        }),
      ).toHaveCount(1);

      const title = `__e2e_t18_ui_${stamp}`;
      await page.getByLabel("政策标题").fill(title);
      await page.getByLabel("政策分类").selectOption(dynamicCategory);
      await page.getByLabel("摘要").fill("政府发布链路回归摘要");
      await page
        .getByLabel("资料来源")
        .fill(`粤乡智匠测试来源 | https://example.com/policy-${stamp}`);
      await page.getByLabel("政策内容").fill("政府政策发布与编辑回归内容。");
      await page.getByTestId("government-policy-submit").click();

      await expect(
        page.getByTestId("government-policy-form-feedback"),
      ).toContainText("已发布");
      await expect(page.getByLabel("政策标题")).toHaveValue("");
      await expect(
        page.getByRole("heading", { level: 1, name: "发布新政策" }),
      ).toBeVisible();

      const policiesResponse = await request.get("/api/government/policies", {
        headers: { "X-Session-Id": sessionId },
      });
      const policies = (await policiesResponse.json()) as {
        policies: Array<{ id: number; title: string }>;
      };
      publishedPolicyId =
        policies.policies.find((policy) => policy.title === title)?.id ?? null;
      expect(publishedPolicyId).not.toBeNull();
      expect(await publicPolicyIds(request)).toContain(publishedPolicyId);

      await openGovernmentPolicies(page);
      const card = page.locator(
        `[data-testid="government-policy-card"][data-policy-id="${publishedPolicyId}"]`,
      );
      await expect(card).toContainText(title);
      await expect(card).toContainText("已上线");
      await expect(page.getByTestId("government-policy-form-feedback")).toHaveCount(
        0,
      );

      await card.getByTestId("government-policy-edit").click();
      await expect(page).toHaveURL(
        new RegExp(`/government/publish\\?edit=${publishedPolicyId}$`),
      );
      await expect(
        page.getByRole("heading", { level: 1, name: "编辑政策" }),
      ).toBeVisible();
      await expect(page.getByLabel("政策标题")).toHaveValue(title);
      await expect(page.getByLabel("政策分类")).toHaveValue(dynamicCategory);

      const editedTitle = `${title}_已修改`;
      await page.getByLabel("政策标题").fill(editedTitle);
      await page.getByTestId("government-policy-submit").click();
      await expect(
        page.getByTestId("government-policy-form-feedback"),
      ).toContainText("修改已保存");
      await expect(page.getByLabel("政策标题")).toHaveValue("");

      await openGovernmentPolicies(page);
      await expect(
        page.locator(
          `[data-testid="government-policy-card"][data-policy-id="${publishedPolicyId}"]`,
        ),
      ).toContainText(editedTitle);

      await page
        .locator(
          `[data-testid="government-policy-card"][data-policy-id="${publishedPolicyId}"]`,
        )
        .getByTestId("government-policy-edit")
        .click();
      await expect(page.getByLabel("政策标题")).toHaveValue(editedTitle);
      await page.getByTestId("government-policy-cancel").click();
      await expect(page).toHaveURL(/\/government\/publish$/);
      await expect(page.getByLabel("政策标题")).toHaveValue("");
      await expect(
        page.getByRole("heading", { level: 1, name: "发布新政策" }),
      ).toBeVisible();

      await openGovernmentPolicies(page);
      const liveCard = page.locator(
        `[data-testid="government-policy-card"][data-policy-id="${publishedPolicyId}"]`,
      );
      await liveCard.getByTestId("government-policy-toggle").click();
      await expect(
        page.getByTestId("government-policies-feedback"),
      ).toContainText("已下架");
      await expect(liveCard).toContainText("已下架");
      expect(await publicPolicyIds(request)).not.toContain(publishedPolicyId);

      await liveCard.getByTestId("government-policy-toggle").click();
      await expect(
        page.getByTestId("government-policies-feedback"),
      ).toContainText("已上架");
      await expect(liveCard).toContainText("已上线");
      expect(await publicPolicyIds(request)).toContain(publishedPolicyId);

      await liveCard.getByTestId("government-policy-edit").click();
      editedPolicyId = publishedPolicyId;
      await expect(page.getByTestId("government-policy-form-feedback")).toHaveCount(
        0,
      );
      await page.getByTestId("government-policy-cancel").click();

      page.once("dialog", (dialog) => dialog.accept());
      await openGovernmentPolicies(page);
      await liveCard.getByTestId("government-policy-delete").click();
      await expect(
        page.getByTestId("government-policies-feedback"),
      ).toContainText("已删除");
      await expect(liveCard).toHaveCount(0);
      expect(await publicPolicyIds(request)).not.toContain(publishedPolicyId);
      publishedPolicyId = null;
      editedPolicyId = null;
    } finally {
      const remainingIds = [publishedPolicyId, editedPolicyId, categoryPolicyId];
      for (const policyId of remainingIds) {
        if (policyId !== null) {
          await deletePolicyWithApi(request, sessionId, policyId).catch(() => {
            // Cleanup tolerates a policy already deleted through the UI.
          });
        }
      }
    }
  });

  test("dashboard and policy list expose loading failures, empty states and retries", async ({
    page,
  }) => {
    await page.route("**/api/government/dashboard", (route) =>
      route.abort("connectionfailed"),
    );
    await signIn(page, GOVERNMENT.username, GOVERNMENT.password);
    await expect(page).toHaveURL(/\/government\/dashboard$/);
    await expect(page.getByText("政务概览加载失败")).toBeVisible();

    await page.unroute("**/api/government/dashboard");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(page.getByTestId("government-own-total")).toBeVisible();

    await page.route("**/api/government/policies", (route) =>
      route.fulfill({
        json: { success: true, policies: [] },
      }),
    );
    await openGovernmentPolicies(page);
    await expect(page.getByText("暂无政策")).toBeVisible();

    await page.unroute("**/api/government/policies");
    await page.route("**/api/government/policies", (route) =>
      route.abort("connectionfailed"),
    );
    await page.getByRole("button", { name: "刷新" }).click();
    await expect(page.getByText("政策列表加载失败")).toBeVisible();
    await expect(page.getByRole("button", { name: "重试" })).toBeVisible();

    await page.unroute("**/api/government/policies");
    await page.getByRole("button", { name: "重试" }).click();
    await expect(page.getByTestId("government-policy-card").first()).toBeVisible();
  });

  test("non-government roles cannot enter or call the government policy surface", async ({
    page,
    request,
  }) => {
    for (const role of [
      "student",
      "teacher",
      "enterprise",
      "operator",
    ] as const) {
      await expectCrossRoleFallback(page, ROLE_ACCOUNTS[role], "government");
    }

    for (const role of [
      "student",
      "teacher",
      "enterprise",
      "operator",
      "super_admin",
    ] as const) {
      await expectApiDenied(
        request,
        ROLE_ACCOUNTS[role],
        rolePortal("government").api,
      );
      const body = (await (
        await request.post("/api/auth/login", { data: ROLE_ACCOUNTS[role] })
      ).json()) as { session_id: string };
      const headers = { "X-Session-Id": body.session_id };
      const create = await request.post("/api/government/policies", {
        headers,
        data: { title: "越权探针", content: "不应创建" },
      });
      expect(create.status()).toBe(403);
    }
  });
});
