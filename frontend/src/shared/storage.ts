import type { User } from "@/api/types";
import { LARGE_TEXT_STORAGE_KEY, SESSION_STORAGE_KEY, THEME_STORAGE_KEY } from "./storageKeys";

export { LARGE_TEXT_STORAGE_KEY, SESSION_STORAGE_KEY, THEME_STORAGE_KEY };

export interface StoredSession {
  sessionId: string;
  user: User;
  capabilities: string[];
}

export function readStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed)) return null;
    const sessionId = parsed.sessionId;
    if (typeof sessionId !== "string" || !sessionId) return null;
    const user = parseUser(parsed.user);
    if (!user) return null;
    return {
      sessionId,
      user,
      capabilities: parseCapabilities(parsed.capabilities),
    };
  } catch {
    return null;
  }
}

export function writeStoredSession(session: StoredSession): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  } catch {
    // The app can still run in memory when storage is unavailable.
  }
}

export function clearStoredSession(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Ignore private-mode storage failures.
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function parseUser(value: unknown): User | null {
  if (!isRecord(value)) return null;
  if (typeof value.id !== "string" || !value.id) return null;
  if (typeof value.name !== "string") return null;
  if (!isRole(value.role)) return null;
  return {
    id: value.id,
    name: value.name,
    role: value.role,
    email: typeof value.email === "string" ? value.email : "",
    phone: typeof value.phone === "string" ? value.phone : "",
    avatar_url: typeof value.avatar_url === "string" ? value.avatar_url : "",
    company_name: typeof value.company_name === "string" ? value.company_name : "",
    region: typeof value.region === "string" ? value.region : "",
    status: typeof value.status === "string" ? value.status : "active",
  };
}

function parseCapabilities(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((capability): capability is string => typeof capability === "string");
}

function isRole(value: unknown): value is User["role"] {
  return (
    value === "student" ||
    value === "teacher" ||
    value === "enterprise" ||
    value === "government" ||
    value === "operator" ||
    value === "super_admin"
  );
}
