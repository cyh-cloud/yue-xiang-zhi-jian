import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// 跑完清理临时种子库目录，不在磁盘留残值。E2E_TEMP_DIR 由 Playwright 配置传入，
// 与 webServer 的 YUEXIANG_DB 同源；未设置时保留旧版 e2e 的默认目录。
export default async () => {
  const dir = process.env.E2E_TEMP_DIR || path.join(os.tmpdir(), "yuexiang-e2e");
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
};
