import type { NavigationGuardWithThis } from "vue-router";

import type { Role } from "@/api/types";
import { useSessionStore } from "@/stores/session";

const LOGIN_PATH = "/login";

export function resolveCapabilityFallback(
  toPath: string,
  routeDefaultPath: string | undefined,
  sessionDefaultPath: string,
  sessionRole?: Role | null,
): string {
  // A super admin may pass the shell role check, but domain capabilities still
  // decide whether a domain page is accessible. Keep that denial inside the
  // super-admin portal instead of landing on another role's dashboard.
  if (sessionRole === "super_admin") return sessionDefaultPath;
  const fallback = routeDefaultPath || sessionDefaultPath;
  return fallback === toPath ? sessionDefaultPath : fallback;
}

export const restoreSessionGuard: NavigationGuardWithThis<undefined> = async () => {
  const session = useSessionStore();
  await session.restore();
};

export const routeAccessGuard: NavigationGuardWithThis<undefined> = (to) => {
  const session = useSessionStore();
  const meta = to.meta;
  if (!meta.requiresAuth) return true;

  // A stored session whose verification failed due to the network is not
  // anonymous. Keep that distinction visible on the login page.
  if (session.status === "unavailable") {
    return { path: LOGIN_PATH, query: { unavailable: "1" }, replace: true };
  }

  if (!session.isAuthenticated) {
    return {
      path: LOGIN_PATH,
      query: { redirect: to.fullPath },
      replace: true,
    };
  }

  if (
    meta.backofficeRole &&
    session.role !== meta.backofficeRole &&
    session.role !== "super_admin"
  ) {
    return { path: session.defaultPath, replace: true };
  }

  if (meta.capabilities?.length) {
    const hasAllCapabilities = meta.capabilities.every(
      (capability) => session.can(capability),
    );
    if (!hasAllCapabilities) {
      return {
        path: resolveCapabilityFallback(
          to.path,
          meta.defaultPath,
          session.defaultPath,
          session.role,
        ),
        replace: true,
      };
    }
  }

  return true;
};
