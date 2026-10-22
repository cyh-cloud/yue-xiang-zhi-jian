import { defineConfig, devices } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(import.meta.dirname, "..");
const PORT = Number(process.env.E2E_UNAVAILABLE_PORT || 5159);
const E2E_DIR = path.join(os.tmpdir(), `yuexiang-spa-backend-unavailable-${PORT}`);
process.env.E2E_TEMP_DIR = E2E_DIR;

export default defineConfig({
  testDir: "./e2e-unavailable",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  globalTeardown: "../e2e/global-teardown.js",
  webServer: {
    command: "python e2e/serve.py",
    cwd: ROOT,
    url: `http://127.0.0.1:${PORT}/`,
    env: {
      YUEXIANG_DB: path.join(E2E_DIR, "yuexiang.db"),
      ...(process.env.YUEXIANG_BASELINE_DB
        ? { YUEXIANG_BASELINE_DB: process.env.YUEXIANG_BASELINE_DB }
        : {}),
      E2E_PORT: String(PORT),
      E2E_START_API: "0",
      AI_API_KEY: "",
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    },
    reuseExistingServer: false,
    timeout: 90_000,
  },
});
