import { defineStore } from "pinia";
import { computed, ref } from "vue";

import {
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  refreshCapabilities,
  verifySession,
} from "@/api/auth";
import { ApiError, setApiSessionId } from "@/api/client";
import type { RegisterPayload, Role, User } from "@/api/types";
import { defaultPathForRole } from "@/shared/roles";
import {
  clearStoredSession,
  readStoredSession,
  writeStoredSession,
} from "@/shared/storage";

export type SessionStatus =
  | "idle"
  | "restoring"
  | "ready"
  | "anonymous"
  | "unavailable";

export const useSessionStore = defineStore("session", () => {
  const user = ref<User | null>(null);
  const sessionId = ref("");
  const capabilities = ref<string[]>([]);
  const status = ref<SessionStatus>("idle");
  let restorePromise: Promise<void> | null = null;

  const isAuthenticated = computed(
    () =>
      status.value === "ready" &&
      Boolean(user.value && sessionId.value),
  );
  const role = computed<Role | null>(() => user.value?.role ?? null);
  const defaultPath = computed(() =>
    role.value ? defaultPathForRole(role.value) : "/agriculture",
  );

  function can(capability: string): boolean {
    return capabilities.value.includes(capability);
  }

  function applySession(
    nextSessionId: string,
    nextUser: User,
    nextCapabilities: string[],
  ): void {
    sessionId.value = nextSessionId;
    user.value = nextUser;
    capabilities.value = nextCapabilities;
    setApiSessionId(nextSessionId);
    writeStoredSession({
      sessionId: nextSessionId,
      user: nextUser,
      capabilities: nextCapabilities,
    });
  }

  async function login(username: string, password: string): Promise<User> {
    status.value = "restoring";
    try {
      const response = await loginRequest(username, password);
      applySession(response.session_id, response.user, response.capabilities);
      status.value = "ready";
      return response.user;
    } catch (error) {
      status.value = "anonymous";
      throw error;
    }
  }

  async function registerAccount(payload: RegisterPayload): Promise<User> {
    status.value = "restoring";
    try {
      const response = await registerRequest(payload);
      applySession(response.session_id, response.user, response.capabilities);
      status.value = "ready";
      return response.user;
    } catch (error) {
      status.value = "anonymous";
      throw error;
    }
  }

  async function restore(): Promise<void> {
    if (status.value === "ready" || status.value === "anonymous") return;
    if (restorePromise) return restorePromise;

    restorePromise = (async () => {
      status.value = "restoring";
      const stored = readStoredSession();
      if (!stored) {
        clearSession();
        return;
      }

      setApiSessionId(stored.sessionId);
      try {
        const verified = await verifySession(stored.sessionId);
        let nextCapabilities = verified.capabilities;
        if (!nextCapabilities.length && stored.capabilities.length === 0) {
          const refreshed = await refreshCapabilities();
          nextCapabilities = refreshed.capabilities;
        }
        applySession(stored.sessionId, verified.user, nextCapabilities);
        status.value = "ready";
      } catch (error) {
        if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
          clearSession();
          return;
        }
        // Keep the stored session so a retry can still succeed, but never
        // present an unverified snapshot as an authenticated user.
        user.value = null;
        capabilities.value = [];
        status.value = "unavailable";
      }
    })().finally(() => {
      restorePromise = null;
    });

    return restorePromise;
  }

  async function refreshCapabilityList(): Promise<void> {
    if (!sessionId.value) return;
    const response = await refreshCapabilities();
    capabilities.value = response.capabilities;
  }

  async function logout(): Promise<void> {
    const currentSession = sessionId.value;
    clearSession();
    if (currentSession) {
      try {
        await logoutRequest(currentSession);
      } catch {
        // Local logout must succeed even when the API is unavailable.
      }
    }
  }

  function clearSession(): void {
    sessionId.value = "";
    user.value = null;
    capabilities.value = [];
    setApiSessionId(null);
    clearStoredSession();
    status.value = "anonymous";
  }

  return {
    user,
    sessionId,
    capabilities,
    status,
    isAuthenticated,
    role,
    defaultPath,
    can,
    login,
    registerAccount,
    restore,
    refreshCapabilityList,
    logout,
    clearSession,
  };
});
