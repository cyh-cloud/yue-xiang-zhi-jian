import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 仅在 E2E_AI_LIVE=1 且 .env 配好 AI 时运行：验契约（200 + 结构），不判内容质量。
test.skip(!process.env.E2E_AI_LIVE, "设 E2E_AI_LIVE=1 且 .env 配好 AI 后运行");

test("AI 真实冒烟：ask/script/suggestions/diagnose 返回 200 且结构正确", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(student).toBeTruthy();
  const problems = [];

  const ask = await call(request, "POST", "/api/agriculture/ask", {
    sessionId: student, data: { question: "荔枝叶子发黄怎么办", product: "lychee" },
  });
  if (ask.status !== 200 || !ask.json?.answer) problems.push(`ask -> ${ask.status} answer=${!!ask.json?.answer}`);

  const script = await call(request, "POST", "/api/ecommerce/script", {
    sessionId: student, data: { product: "荔枝", style: "热情" },
  });
  if (script.status !== 200) problems.push(`script -> ${script.status} code=${script.json?.code ?? ""}`);

  const sug = await call(request, "GET", "/api/agriculture/suggestions?product=lychee", { sessionId: student });
  if (sug.status !== 200) problems.push(`suggestions -> ${sug.status}`);

  const diag = await call(request, "POST", "/api/agriculture/diagnose", {
    sessionId: student, data: { crop: "lychee", symptoms: "叶片出现褐色斑点，边缘枯黄" },
  });
  if (diag.status !== 200 || !diag.json?.diagnosis) problems.push(`diagnose -> ${diag.status} diagnosis=${!!diag.json?.diagnosis}`);

  record("ai-live.json", { ask: ask.status, script: script.status, sug: sug.status, diag: diag.status, problems });
  expect(problems, "AI 真实冒烟问题:\n" + problems.join("\n")).toEqual([]);
});
