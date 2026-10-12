import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ACCOUNTS = {
  admin: { username: "admin_demo", password: "admin123" },
  gov: { username: "gov_demo", password: "123456" },
  teacher: { username: "teacher_demo", password: "123456" },
  student: { username: "student_demo", password: "123456" },
};

export async function login(request, account) {
  const res = await request.post("/api/auth/login", { data: account });
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* ignore */
  }
  return { status: res.status(), sessionId: body?.session_id ?? null, user: body?.user ?? null, body };
}

// 统一请求封装：带可选会话头，始终尝试解析 JSON，非 JSON 也返回片段便于排查。
export async function call(request, method, url, { sessionId, data } = {}) {
  const headers = {};
  if (sessionId) headers["X-Session-Id"] = sessionId;
  if (data !== undefined) headers["Content-Type"] = "application/json";
  const res = await request.fetch(url, { method, headers, data });
  const text = await res.text().catch(() => "");
  let json = null;
  let nonJson = false;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    nonJson = true;
  }
  return { status: res.status(), json, nonJson, snippet: text.slice(0, 300) };
}

const FINDINGS_DIR = path.resolve(__dirname, "..", "findings");
export function record(name, obj) {
  fs.mkdirSync(FINDINGS_DIR, { recursive: true });
  fs.writeFileSync(path.join(FINDINGS_DIR, name), JSON.stringify(obj, null, 2));
}
