import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const PORT = Number(process.env.E2E_PORT || 5158);
const E2E_DIR = path.join(os.tmpdir(), `yuexiang-spa-e2e-${PORT}`);
const DB_PATH = path.join(E2E_DIR, "yuexiang.db");
process.env.E2E_TEMP_DIR = E2E_DIR;

const config = {
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  expect: {
    toHaveScreenshot: {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.002,
      scale: "css",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  globalTeardown: "../e2e/global-teardown.js",
  webServer: {
    command: "python e2e/serve.py",
    cwd: ROOT,
    url: `http://127.0.0.1:${PORT}/api/health`,
    env: {
      YUEXIANG_DB: DB_PATH,
      ...(process.env.YUEXIANG_BASELINE_DB
        ? { YUEXIANG_BASELINE_DB: process.env.YUEXIANG_BASELINE_DB }
        : {}),
      E2E_PORT: String(PORT),
      ...(process.env.E2E_AI_LIVE ? {} : { AI_API_KEY: "" }),
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    },
    reuseExistingServer: false,
    timeout: 90_000,
  },
};

export default defineConfig(config);
