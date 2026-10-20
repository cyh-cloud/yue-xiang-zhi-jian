import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

test("农事订阅：需登录、订阅→列表含→幂等→退订→列表不含", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(student, "student 登录失败").toBeTruthy();

  const products = await call(request, "GET", "/api/agriculture/products", { sessionId: student });
  const list = products.json?.products ?? [];
  const pid = (Array.isArray(list) ? list : []).find((p) => p.is_active !== 0)?.id ?? list?.[0]?.id;
  expect(pid, "未取到有效 product_id").toBeTruthy();

  const noAuth = await call(request, "GET", "/api/agriculture/subscriptions");
  expect(noAuth.status, "未登录订阅列表应 401").toBe(401);

  const sub = await call(request, "POST", "/api/agriculture/subscribe", { sessionId: student, data: { product_id: pid } });
  expect(sub.status, `订阅应 200，实际 ${sub.status}: ${sub.snippet}`).toBe(200);
  expect(sub.json?.product_ids ?? [], "订阅返回应包含该作物").toContain(pid);

  await call(request, "POST", "/api/agriculture/subscribe", { sessionId: student, data: { product_id: pid } });
  const list1 = await call(request, "GET", "/api/agriculture/subscriptions", { sessionId: student });
  const ids1 = list1.json?.product_ids ?? [];
  expect(ids1.filter((x) => x === pid).length, "重复订阅不应产生多条").toBe(1);

  const unsub = await call(request, "DELETE", `/api/agriculture/subscribe/${pid}`, { sessionId: student });
  expect(unsub.status, `退订应 200，实际 ${unsub.status}`).toBe(200);
  const list2 = await call(request, "GET", "/api/agriculture/subscriptions", { sessionId: student });
  expect(list2.json?.product_ids ?? [], "退订后不应包含该作物").not.toContain(pid);
  record("agriculture-subscriptions.json", { pid, ids1, afterUnsub: list2.json?.product_ids });
});
