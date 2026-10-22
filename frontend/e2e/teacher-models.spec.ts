import { readFileSync } from "node:fs";

import { expect, test, type APIRequestContext } from "@playwright/test";

import { signIn } from "./auth-route";

const TEACHER = { username: "teacher_demo", password: "123456" } as const;
const ADMIN = { username: "admin_demo", password: "admin123" } as const;
const MODEL_BYTES = readFileSync(
  new URL("../../uploads/models_3d/seed_embroidery.gltf", import.meta.url),
);

interface SessionPayload {
  session_id: string;
}

interface TeacherModel {
  id: number;
  title: string;
  file_name: string;
  file_path: string;
  file_size: number;
  review_status: string;
  is_published: number;
}

async function login(
  request: APIRequestContext,
  account: { username: string; password: string },
): Promise<SessionPayload> {
  const response = await request.post("/api/auth/login", { data: account });
  expect(response.status()).toBe(200);
  return (await response.json()) as SessionPayload;
}

function marker(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function teacherModels(
  request: APIRequestContext,
  sessionId: string,
): Promise<TeacherModel[]> {
  const response = await request.get("/api/teacher/models-3d", {
    headers: { "X-Session-Id": sessionId },
  });
  expect(response.status()).toBe(200);
  return ((await response.json()) as { models: TeacherModel[] }).models;
}

async function uploadModel(
  request: APIRequestContext,
  sessionId: string,
  title: string,
): Promise<TeacherModel> {
  const response = await request.post("/api/teacher/models-3d", {
    headers: { "X-Session-Id": sessionId },
    multipart: {
      file: {
        name: "t17-api-probe.gltf",
        mimeType: "model/gltf+json",
        buffer: MODEL_BYTES,
      },
      title,
      description: "T17 API fixture",
      craft_type: "embroidery",
    },
  });
  expect(response.status()).toBe(200);
  const body = (await response.json()) as { id: number };
  const model = (await teacherModels(request, sessionId)).find(
    (candidate) => candidate.id === body.id,
  );
  expect(model).toBeTruthy();
  return model!;
}

test("teacher uploads, previews, sees review status and deletes a model", async ({
  page,
  request,
}) => {
  const title = marker("E2E教师模型");
  await signIn(page, TEACHER.username, TEACHER.password);
  await expect(page).toHaveURL(/\/teacher\/dashboard$/);
  await page.goto("/teacher/models");
  await expect(
    page.getByRole("heading", { level: 1, name: "3D 模型" }),
  ).toBeVisible();

  await page.locator("#model-file").setInputFiles({
    name: "t17-teacher-model.gltf",
    mimeType: "model/gltf+json",
    buffer: MODEL_BYTES,
  });
  await page.getByLabel("标题").fill(title);
  await page.getByLabel("描述").fill("T17 浏览器上传与预览");
  await page.getByLabel("技艺类型").selectOption("embroidery");

  const outgoingPromise = page.waitForRequest(
    (request) =>
      request.url().endsWith("/api/teacher/models-3d") &&
      request.method() === "POST",
  );
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/teacher/models-3d") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "上传模型" }).click();
  const outgoing = await outgoingPromise;
  const response = await responsePromise;

  expect(outgoing.headers()["content-type"]).toMatch(
    /^multipart\/form-data; boundary=/,
  );
  expect(response.status()).toBe(200);
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "3D模型上传成功",
  );

  const session = await login(request, TEACHER);
  const model = (await teacherModels(request, session.session_id)).find(
    (candidate) => candidate.title === title,
  );
  expect(model).toBeTruthy();
  expect(model!.file_name).toBe("t17-teacher-model.gltf");
  expect(model!.file_size).toBe(MODEL_BYTES.length);
  expect(model!.review_status).toBe("pending");

  const stored = await request.get(
    `/${model!.file_path.replace(/\\/g, "/").replace(/^\/+/, "")}`,
  );
  expect(stored.status()).toBe(200);
  expect(Buffer.from(await stored.body())).toEqual(MODEL_BYTES);

  const row = page
    .locator('[data-testid="teacher-model-row"]')
    .filter({ hasText: title });
  await expect(row).toContainText("t17-teacher-model.gltf");
  await expect(row).toContainText(`${MODEL_BYTES.length} B`);
  await expect(row).toContainText("待审核");

  await row.getByTestId("teacher-model-preview").click();
  const preview = page.getByTestId("teacher-model-preview-dialog");
  await expect(preview).toBeVisible();
  const viewer = preview.locator("model-viewer");
  await expect(viewer).toHaveAttribute("src", /t17-teacher-model\.gltf/);
  await viewer.evaluate((node) => node.dispatchEvent(new Event("load")));
  await expect(preview.getByTestId("teacher-model-preview-state")).toContainText(
    "预览已就绪",
  );
  await viewer.evaluate((node) => node.dispatchEvent(new Event("error")));
  await expect(preview.getByTestId("teacher-model-preview-state")).toContainText(
    "3D 模型文件加载失败",
  );
  await preview.getByRole("button", { name: "关闭预览" }).click();

  const admin = await login(request, ADMIN);
  const reviewResponse = await request.get(
    "/api/admin/reviews?content_type=model_3d&status=pending&sort=created",
    { headers: { "X-Session-Id": admin.session_id } },
  );
  expect(reviewResponse.status()).toBe(200);
  const review = (
    (await reviewResponse.json()) as {
      reviews: Array<{ id: number; detail?: { id?: number } }>;
    }
  ).reviews.find((candidate) => candidate.detail?.id === model!.id);
  expect(review).toBeTruthy();
  const approved = await request.post(
    `/api/admin/reviews/${review!.id}/approve`,
    {
      headers: { "X-Session-Id": admin.session_id },
      data: {},
    },
  );
  expect(approved.status()).toBe(200);

  await page.getByRole("button", { name: "刷新列表" }).click();
  await expect(row).toContainText("已通过");
  await expect(row).toContainText("已公开");

  const published = await request.get(
    "/api/teacher/public-models-3d?craft_type=embroidery",
  );
  expect(published.status()).toBe(200);
  expect(
    ((await published.json()) as { models: TeacherModel[] }).models.some(
      (candidate) => candidate.id === model!.id,
    ),
  ).toBe(true);

  await row.getByTestId("teacher-model-delete").click();
  const confirm = page.getByTestId("teacher-model-delete-dialog");
  await expect(confirm).toContainText(title);
  await confirm.getByRole("button", { name: "确认删除" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "删除成功",
  );
  await expect(row).toHaveCount(0);

  expect(
    (await teacherModels(request, session.session_id)).some(
      (candidate) => candidate.id === model!.id,
    ),
  ).toBe(false);
  expect(
    (
      (await (
        await request.get("/api/teacher/public-models-3d?craft_type=embroidery")
      ).json()) as { models: TeacherModel[] }
    ).models.some((candidate) => candidate.id === model!.id),
  ).toBe(false);
  expect(
    (
      await request.get(
        `/${model!.file_path.replace(/\\/g, "/").replace(/^\/+/, "")}`,
      )
    ).status(),
  ).toBe(404);
});

test("upload failures distinguish empty, format, size, network and backend rejection", async ({
  page,
}) => {
  await signIn(page, TEACHER.username, TEACHER.password);
  await expect(page).toHaveURL(/\/teacher\/dashboard$/);
  await page.goto("/teacher/models");

  await page.getByRole("button", { name: "上传模型" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "请选择一个非空的 3D 模型文件",
  );

  await page.locator("#model-file").setInputFiles({
    name: "installer.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("not a model"),
  });
  await page.getByRole("button", { name: "上传模型" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "不支持该文件格式",
  );

  await page.evaluate(() => {
    const input = document.querySelector<HTMLInputElement>("#model-file");
    if (!input) throw new Error("model file input missing");
    const oversized = new File(
      [new Uint8Array(50 * 1024 * 1024 + 1)],
      "oversized.glb",
      { type: "model/gltf-binary" },
    );
    const transfer = new DataTransfer();
    transfer.items.add(oversized);
    input.files = transfer.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.getByRole("button", { name: "上传模型" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "不能超过 50MB",
  );

  await page.locator("#model-file").setInputFiles({
    name: "network-probe.gltf",
    mimeType: "model/gltf+json",
    buffer: MODEL_BYTES,
  });
  await page.getByLabel("标题").fill(marker("E2E网络失败模型"));
  await page.route("**/api/teacher/models-3d", (route) =>
    route.abort("connectionfailed"),
  );
  await page.getByRole("button", { name: "上传模型" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "无法连接上传服务",
  );
  await page.unroute("**/api/teacher/models-3d");

  await page.route("**/api/teacher/models-3d", (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        success: false,
        code: "backend_rejected",
        message: "后端拒绝测试：模型处理失败",
      }),
    }),
  );
  await page.getByRole("button", { name: "上传模型" }).click();
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "后端拒绝测试：模型处理失败",
  );
});

test("model-viewer CDN failure keeps the model list and file link usable", async ({
  page,
  request,
}) => {
  const session = await login(request, TEACHER);
  const title = marker("E2E CDN降级模型");
  const model = await uploadModel(request, session.session_id, title);

  try {
    await page.route("https://unpkg.com/**", (route) => route.abort());
    await signIn(page, TEACHER.username, TEACHER.password);
    await expect(page).toHaveURL(/\/teacher\/dashboard$/);
    await page.goto("/teacher/models");

    const row = page
      .locator('[data-testid="teacher-model-row"]')
      .filter({ hasText: title });
    await expect(row).toBeVisible();
    await expect(
      page.getByRole("status").filter({ hasText: "外部资源降级" }),
    ).toContainText("model-viewer");
    await expect
      .poll(() =>
        page.evaluate(
          () => document.documentElement.dataset.cdnModelViewer,
        ),
      )
      .toBe("failed");

    await row.getByTestId("teacher-model-preview").click();
    const preview = page.getByTestId("teacher-model-preview-dialog");
    await expect(preview.getByTestId("teacher-model-preview-state")).toContainText(
      "3D 查看器资源加载失败",
    );
    await expect(
      preview.getByRole("link", { name: "打开原文件" }),
    ).toHaveAttribute(
      "href",
      new RegExp(model.file_path.replace(/\\/g, "/").split("/").pop()!),
    );
  } finally {
    await request.delete(`/api/teacher/models-3d/${model.id}`, {
      headers: { "X-Session-Id": session.session_id },
    });
  }
});
