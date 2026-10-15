import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const E2E_DIR = path.join(os.tmpdir(), "yuexiang-e2e");
const DB_PATH = path.join(E2E_DIR, "yuexiang.db");
// 端口可用 E2E_PORT 覆盖：Windows Hyper-V 会保留一段动态端口区间，5057 有时落在
// 保留段里导致 bind 失败（症状是「以一种访问权限不允许的方式做了一个访问套接字的尝试」）。
// 换一个端口跑即可，语义不变。
const PORT = Number(process.env.E2E_PORT || 5057);
const BASE = `http://127.0.0.1:${PORT}`;
const ROOT = path.resolve(import.meta.dirname, "..");

export default defineConfig({
  testDir: "./specs",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  globalTeardown: "./global-teardown.js",
  webServer: {
    command: "python e2e/serve.py",
    cwd: ROOT,
    url: `${BASE}/api/health`,
    // AI 置空 -> _ai_configured() 为 False，AI 接口返回 503，自动化可稳定断言。
    env: {
      YUEXIANG_DB: DB_PATH,
      E2E_PORT: String(PORT),
      ...(process.env.E2E_AI_LIVE ? {} : { AI_API_KEY: "" }),
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    },
    reuseExistingServer: Boolean(process.env.E2E_REUSE_SERVER),
    timeout: 90_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
