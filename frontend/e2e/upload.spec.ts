import { expect, test } from "@playwright/test";

const TEACHER = { username: "teacher_demo", password: "123456" };
const MODEL_BYTES = Buffer.from("glTF T3 multipart probe");

test("a real browser multipart upload reaches Flask byte for byte", async ({
  page,
  request,
}) => {
  const login = await request.post("/api/auth/login", { data: TEACHER });
  expect(login.status()).toBe(200);
  const session = await login.json();

  await page.goto("/login");
  await page.evaluate((payload) => {
    localStorage.setItem(
      "yuexiang_session",
      JSON.stringify({
        sessionId: payload.session.session_id,
        user: payload.session.user,
        capabilities: payload.session.capabilities,
      }),
    );
  }, { session });
  await page.reload();

  await page.goto("/teacher/models");
  await expect(
    page.getByTestId("backoffice-shell").getByRole("heading", {
      level: 1,
      name: "3D 模型",
    }),
  ).toBeVisible();

  await page.locator("#model-file").setInputFiles({
    name: "t3-multipart-probe.glb",
    mimeType: "model/gltf-binary",
    buffer: MODEL_BYTES,
  });
  await page.locator("#model-title").fill("__T3 multipart__");

  const uploaded = page.waitForResponse((response) => {
    return (
      response.url().endsWith("/api/teacher/models-3d") &&
      response.request().method() === "POST"
    );
  });
  const uploadRequest = page.waitForRequest((request) => {
    return (
      request.url().endsWith("/api/teacher/models-3d") &&
      request.method() === "POST"
    );
  });

  await page.getByRole("button", { name: "上传模型" }).click();
  const outgoing = await uploadRequest;
  const response = await uploaded;

  expect(outgoing.headers()["content-type"]).toMatch(/^multipart\/form-data; boundary=/);
  expect(response.status()).toBe(200);
  await expect(response.json()).resolves.toMatchObject({
    success: true,
  });
  await expect(page.getByTestId("teacher-models-feedback")).toContainText(
    "3D模型上传成功",
  );

  const models = await request.get("/api/teacher/models-3d", {
    headers: { "X-Session-Id": session.session_id },
  });
  expect(models.status()).toBe(200);
  const model = (await models.json()).models.find(
    (candidate: { title?: string }) => candidate.title === "__T3 multipart__",
  );
  expect(model).toBeTruthy();
  expect(model.file_name).toBe("t3-multipart-probe.glb");
  expect(model.file_size).toBe(MODEL_BYTES.length);

  const stored = await request.get(`/${String(model.file_path).replace(/\\/g, "/")}`);
  expect(stored.status()).toBe(200);
  expect(Buffer.from(await stored.body())).toEqual(MODEL_BYTES);

  const removed = await request.delete(`/api/teacher/models-3d/${model.id}`, {
    headers: { "X-Session-Id": session.session_id },
  });
  expect(removed.status()).toBe(200);
});
