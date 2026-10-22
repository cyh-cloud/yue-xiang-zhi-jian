import { get, post, setApiSessionId } from "./client";
import type {
  AuthResponse,
  CapabilitiesResponse,
  LogoutResponse,
  RegisterPayload,
  VerifyResponse,
} from "./types";

export async function login(username: string, password: string): Promise<AuthResponse> {
  const response = await post<AuthResponse>("/api/auth/login", {
    username,
    password,
  });
  setApiSessionId(response.session_id);
  return response;
}

export async function verifySession(sessionId: string): Promise<VerifyResponse> {
  setApiSessionId(sessionId);
  return post<VerifyResponse>("/api/auth/verify", { session_id: sessionId });
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  const response = await post<AuthResponse>("/api/auth/register", payload);
  setApiSessionId(response.session_id);
  return response;
}

export function logout(sessionId: string): Promise<LogoutResponse> {
  return post<LogoutResponse>("/api/auth/logout", { session_id: sessionId });
}

export function refreshCapabilities(): Promise<CapabilitiesResponse> {
  return get<CapabilitiesResponse>("/api/auth/capabilities");
}
