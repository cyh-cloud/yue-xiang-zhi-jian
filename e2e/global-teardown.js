import fs from "node:fs";
import os from "node:os";
import path from "node:path";

// 跑完清理临时种子库目录，不在磁盘留残值。
export default async () => {
  const dir = path.join(os.tmpdir(), "yuexiang-e2e");
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* ignore */
  }
};
