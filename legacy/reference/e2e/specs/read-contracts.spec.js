import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

test("读接口契约：crafts/dialect/models-3d/home-stats/ecommerce-records", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  const problems = [];

  const crafts = await call(request, "GET", "/api/crafts/list");
  const craftId = crafts.json?.crafts?.[0]?.id;
  if (craftId) {
    const one = await call(request, "GET", `/api/crafts/${craftId}`);
    if (one.status !== 200 || one.json?.success === false) problems.push(`crafts/${craftId} -> ${one.status}`);
  }

  const dialect = await call(request, "GET", "/api/resources/dialect-info?dialect=cantonese");
  if (dialect.status !== 200) problems.push(`dialect-info -> ${dialect.status}`);

  const models = await call(request, "GET", "/api/teacher/public-models-3d?craft_type=embroidery");
  if (models.status !== 200) problems.push(`public-models-3d -> ${models.status}`);

  const stats = await call(request, "GET", "/api/home/stats");
  if (stats.status !== 200 || stats.json?.success === false) problems.push(`home/stats -> ${stats.status}`);

  const recNoAuth = await call(request, "GET", "/api/ecommerce/live/records");
  if (recNoAuth.status !== 401) problems.push(`live/records 未登录应 401，实际 ${recNoAuth.status}`);
  const rec = await call(request, "GET", "/api/ecommerce/live/records", { sessionId: student });
  if (rec.status !== 200 || rec.json?.success === false) problems.push(`live/records 登录后应 200，实际 ${rec.status}`);

  record("read-contracts.json", { craftId, dialect: dialect.status, models: models.status, stats: stats.status, recNoAuth: recNoAuth.status, rec: rec.status, problems });
  expect(problems, "读接口契约问题:\n" + problems.join("\n")).toEqual([]);
});
