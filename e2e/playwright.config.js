import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const E2E_DIR = path.join(os.tmpdir(), "yuexiang-e2e");
const DB_PATH = path.join(E2E_DIR, "yuexiang.db");
const PORT = 5057;
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
    reuseExistingServer: false,
    timeout: 90_000,
    stdout: "pipe",
    stderr: "pipe",
  },
});
