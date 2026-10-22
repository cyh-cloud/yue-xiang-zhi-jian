import { expect, test, type Page } from "@playwright/test";

import { signIn } from "./auth-route";

interface AuthPayload {
  session_id: string;
  user: {
    id: string;
    name: string;
    role: string;
    email: string;
    phone: string;
    avatar_url: string;
    company_name: string;
    region: string;
    status: string;
  };
  capabilities: string[];
}

interface LiveRecord {
  id: number;
  product?: string;
  score?: number | null;
  feedback?: string;
  report?: {
    coverage?: number;
    speed_cpm?: number;
    rubric_hit?: number;
    rubric_total?: number;
    overall_score?: number;
  };
}

const SCRIPT =
  "家人们看过来！这是广东产地直发的龙眼，果肉饱满，欢迎扣1。"
  + "具体价格与优惠以店铺实际活动为准。";

function installSpeechRecognition(transcript: string): void {
  class FakeSpeechRecognition {
    continuous = false;
    interimResults = false;
    lang = "";
    onstart: (() => void) | null = null;
    onresult: ((event: unknown) => void) | null = null;
    onerror: ((event: { error: string }) => void) | null = null;
    onend: (() => void) | null = null;

    start(): void {
      this.onstart?.();
      setTimeout(() => {
        const result = Object.assign(
          [{ transcript }],
          { isFinal: true },
        );
        this.onresult?.({
          resultIndex: 0,
          results: [result],
        });
      }, 40);
    }

    stop(): void {
      this.onend?.();
    }
  }

  Object.defineProperty(window, "SpeechRecognition", {
    configurable: true,
    value: FakeSpeechRecognition,
  });
  Object.defineProperty(window, "webkitSpeechRecognition", {
    configurable: true,
    value: FakeSpeechRecognition,
  });
}

async function setStoredSession(page: Page, auth: AuthPayload): Promise<void> {
  await page.addInitScript((payload) => {
    localStorage.setItem(
      "yuexiang_session",
      JSON.stringify({
        sessionId: payload.session_id,
        user: payload.user,
        capabilities: payload.capabilities,
      }),
    );
  }, auth);
}

async function loginAs(
  page: Page,
  username: string,
  password: string,
): Promise<string> {
  const response = await page.request.post("/api/auth/login", {
    data: { username, password },
  });
  expect(response.status()).toBe(200);
  const payload = (await response.json()) as AuthPayload;
  return payload.session_id;
}

test.describe("live commerce simulation and grading loop", () => {
  test("simulation, reading analysis, submission and teacher feedback form one loop", async ({
    page,
  }) => {
    await page.addInitScript(installSpeechRecognition, SCRIPT);
    await signIn(page, "student_demo", "123456");
    await expect(page).toHaveURL(/\/agriculture\/?$/);
    await page.goto("/ecommerce");

    const trainer = page.getByTestId("live-script-training");
    const simulation = page.getByTestId("live-simulation");
    await expect(simulation).toBeVisible();
    await trainer.getByLabel("直播产品").selectOption("龙眼");
    await trainer.getByLabel("直播话术我的稿").fill(SCRIPT);

    await simulation.getByLabel("训练难度").selectOption("进阶");
    await simulation.getByRole("button", { name: "开始直播" }).click();
    await expect(simulation.getByTestId("live-badge")).toContainText(
      "模拟直播中",
    );

    await simulation.getByRole("button", { name: "开始朗读" }).click();
    await expect(simulation.getByTestId("live-transcript")).toContainText(
      "家人们看过来",
    );
    await expect(simulation.getByTestId("live-comment-count")).not.toHaveText(
      "0",
    );
    await expect(simulation.getByTestId("live-session-feedback")).toContainText(
      "互动",
    );

    await simulation.getByRole("button", { name: "结束朗读" }).click();
    await simulation.getByRole("button", { name: "分析朗读" }).click();
    await expect(simulation.getByTestId("reading-overall")).not.toHaveText("-");
    await expect(simulation.getByTestId("reading-metrics")).toContainText(
      "稿子完成度",
    );
    await expect(simulation.getByTestId("reading-metrics")).toContainText(
      "必卖点命中",
    );

    await trainer.getByRole("button", { name: "提交直播实训" }).click();
    const history = trainer.getByTestId("live-records");
    await expect(history).toContainText("龙眼");
    await expect(history).toContainText("待老师批改");
    await expect(history).toContainText("教师尚未批改");
    await expect(history).toContainText("稿子完成度");

    const sessionId = await page.evaluate(() => {
      const raw = localStorage.getItem("yuexiang_session");
      return raw ? (JSON.parse(raw) as { sessionId: string }).sessionId : "";
    });
    expect(sessionId).toBeTruthy();
    const recordsResponse = await page.request.get(
      "/api/ecommerce/live/records?kind=live",
      { headers: { "X-Session-Id": sessionId } },
    );
    expect(recordsResponse.status()).toBe(200);
    const records = (await recordsResponse.json()) as {
      records: LiveRecord[];
    };
    const submitted = records.records.find(
      (record) => record.product === "龙眼",
    );
    expect(submitted).toBeTruthy();
    expect(submitted?.score).toBeNull();
    expect(submitted?.report?.coverage).toBeGreaterThan(0);

    const teacherSession = await loginAs(page, "teacher_demo", "123456");
    const gradeResponse = await page.request.post(
      "/api/teacher/assignments/grade",
      {
        headers: { "X-Session-Id": teacherSession },
        data: {
          submission_id: submitted!.id,
          score: 93,
          feedback: "卖点清楚，互动自然，价格信息仍需以店铺为准。",
        },
      },
    );
    expect(gradeResponse.status()).toBe(200);
    await expect(gradeResponse.json()).resolves.toMatchObject({
      success: true,
      message: "批改成功",
    });

    await page.reload();
    await expect(history).toContainText("已批改");
    await expect(history).toContainText("教师评分 93 分");
    await expect(history).toContainText(
      "卖点清楚，互动自然，价格信息仍需以店铺为准。",
    );
  });

  test("editing the script while analysis is in flight does not save a stale report", async ({
    page,
  }) => {
    const username = `e2e_live_stale_${Date.now()}`;
    const registration = await page.request.post("/api/auth/register", {
      data: {
        username,
        password: "123456",
        name: "朗读报告时序测试学员",
        role: "student",
      },
    });
    expect(registration.status()).toBe(200);
    const auth = (await registration.json()) as AuthPayload;
    await setStoredSession(page, auth);
    await page.addInitScript(installSpeechRecognition, SCRIPT);

    await page.goto("/ecommerce");
    const trainer = page.getByTestId("live-script-training");
    const simulation = page.getByTestId("live-simulation");
    await trainer.getByLabel("直播话术我的稿").fill(SCRIPT);
    await simulation.getByRole("button", { name: "开始朗读" }).click();
    await expect(simulation.getByTestId("live-transcript")).toContainText(
      "家人们看过来",
    );
    await simulation.getByRole("button", { name: "结束朗读" }).click();

    let releaseAnalysis!: () => void;
    const analysisGate = new Promise<void>((resolve) => {
      releaseAnalysis = resolve;
    });
    await page.route("**/api/ecommerce/live/report", async (route) => {
      await analysisGate;
      await route.continue();
    });

    const analysisRequest = page.waitForRequest(
      (request) =>
        request.url().endsWith("/api/ecommerce/live/report") &&
        request.method() === "POST",
    );
    await simulation.getByRole("button", { name: "分析朗读" }).click();
    await analysisRequest;

    const editedScript = `${SCRIPT}\n改动后补充：售后时效以店铺页面为准。`;
    await trainer.getByLabel("直播话术我的稿").fill(editedScript);
    releaseAnalysis();

    await expect(simulation.getByTestId("reading-overall")).not.toHaveText("-");
    await expect(simulation.getByText("这份朗读报告不会随本次提交保存")).toBeVisible();
    await trainer.getByRole("button", { name: "提交直播实训" }).click();
    await expect(trainer.getByTestId("live-records")).toContainText("荔枝");

    const sessionId = await page.evaluate(() => {
      const raw = localStorage.getItem("yuexiang_session");
      return raw ? (JSON.parse(raw) as { sessionId: string }).sessionId : "";
    });
    const recordsResponse = await page.request.get(
      "/api/ecommerce/live/records?kind=live",
      { headers: { "X-Session-Id": sessionId } },
    );
    expect(recordsResponse.status()).toBe(200);
    const records = (await recordsResponse.json()) as {
      records: LiveRecord[];
    };
    const submitted = records.records.find(
      (record) => record.product === "荔枝",
    );
    expect(submitted).toBeTruthy();
    expect(submitted?.report?.coverage).toBeUndefined();
  });

  test("empty history, report failure and history load failure are visible", async ({
    page,
  }) => {
    const username = `e2e_live_${Date.now()}`;
    const registration = await page.request.post("/api/auth/register", {
      data: {
        username,
        password: "123456",
        name: "直播闭环测试学员",
        role: "student",
      },
    });
    expect(registration.status()).toBe(200);
    const auth = (await registration.json()) as AuthPayload;
    await setStoredSession(page, auth);
    await page.addInitScript(installSpeechRecognition, SCRIPT);

    await page.goto("/ecommerce");
    const trainer = page.getByTestId("live-script-training");
    const simulation = page.getByTestId("live-simulation");
    await expect(trainer.getByTestId("live-records")).toContainText(
      "还没有实训记录",
    );

    await trainer.getByLabel("直播话术我的稿").fill(SCRIPT);
    await simulation.getByRole("button", { name: "开始直播" }).click();
    await simulation.getByRole("button", { name: "开始朗读" }).click();
    await expect(simulation.getByTestId("live-transcript")).toContainText(
      "家人们看过来",
    );
    await simulation.getByRole("button", { name: "结束朗读" }).click();

    await page.route("**/api/ecommerce/live/report", (route) => route.abort());
    await simulation.getByRole("button", { name: "分析朗读" }).click();
    await expect(simulation.getByTestId("reading-error")).toContainText(
      "无法连接服务",
    );

    await page.route("**/api/ecommerce/live/records?kind=live", (route) =>
      route.abort(),
    );
    await page.reload();
    await expect(trainer.getByTestId("live-records")).toContainText(
      "无法连接服务",
    );
  });
});
