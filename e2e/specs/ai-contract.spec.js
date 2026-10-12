import { test, expect } from "@playwright/test";
import { ACCOUNTS, login, call, record } from "./helpers.js";

// 仅在 AI 未配置（默认 hermetic）时跑：验 fail-closed 与降级契约。
test.skip(!!process.env.E2E_AI_LIVE, "AI 已配置，跳过未配置契约（由 ai-live 覆盖）");

test("AI 未配置契约：ask 明确 503；script 可见降级；文字诊断不崩", async ({ request }) => {
  const student = (await login(request, ACCOUNTS.student)).sessionId;
  expect(student).toBeTruthy();
  const problems = [];

  const ask = await call(request, "POST", "/api/agriculture/ask", {
    sessionId: student, data: { question: "荔枝叶子发黄怎么办", product: "lychee" },
  });
  if (ask.status !== 503) problems.push(`ask -> ${ask.status} code=${ask.json?.code}（应 503）`);

  // AI 未配置时话术走「可见降级」（EC5）：必须 200 + degraded:true + 带 script，
  // 而不是静默 success:true 冒充 AI，也不是 5xx。
  const script = await call(request, "POST", "/api/ecommerce/script", {
    sessionId: student, data: { product: "荔枝", style: "热情" },
  });
  if (script.status !== 200 || script.json?.degraded !== true || !script.json?.script) {
    problems.push(`script -> ${script.status} degraded=${script.json?.degraded}（应 200 + degraded:true）`);
  }

  const stream = await call(request, "POST", "/api/agriculture/ask/stream", {
    sessionId: student, data: { question: "龙眼如何疏花", product: "longan" },
  });

  // 纯文字诊断在 AI 未配置时应降级知识库（200）或明确无匹配，但绝不 5xx、不假装 AI。
  const diag = await call(request, "POST", "/api/agriculture/diagnose", {
    sessionId: student, data: { crop: "lychee", symptoms: "叶片出现褐色斑点，边缘枯黄" },
  });
  if (diag.status >= 500) problems.push(`diagnose(文字) -> ${diag.status}（不应服务端错误）`);

  record("ai-contract.json", {
    ask: ask.status, askCode: ask.json?.code,
    script: script.status, scriptDegraded: script.json?.degraded,
    stream: stream.status, diag: diag.status, diagSource: diag.json?.diagnosis?.source, problems,
  });
  expect(problems, "AI 未配置契约问题:\n" + problems.join("\n")).toEqual([]);
});
