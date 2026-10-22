import { ApiError } from "@/api/client";

export function describeApiError(
  error: unknown,
  fallback = "请求失败，请稍后重试",
): string {
  if (!(error instanceof ApiError)) return fallback;
  if (error.status === 0) return "无法连接服务，请检查网络后重试";
  if (error.status === 429) return "请求过于频繁，请稍后再试";
  if (error.status === 503 || error.code === "ai_unavailable") {
    return error.message || "AI 服务暂时不可用，请稍后重试";
  }
  return error.message || fallback;
}
