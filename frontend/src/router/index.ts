import { createRouter, createWebHistory } from "vue-router";

import { restoreSessionGuard, routeAccessGuard } from "./guards";
import {
  resolveLegacyCaseRedirect,
  resolveLegacyRedirect,
} from "./legacyRedirects";
import { routes } from "./routes";

export function createAppRouter() {
  const router = createRouter({
    history: createWebHistory(),
    routes,
    scrollBehavior: () => ({ top: 0 }),
  });

  router.beforeEach((to) => {
    const caseRedirect = resolveLegacyCaseRedirect(
      to.path,
      typeof to.query.id === "string" ? to.query.id : null,
    );
    if (caseRedirect) return { path: caseRedirect, replace: true };

    const redirect = resolveLegacyRedirect(to.path);
    if (!redirect) return true;
    return { path: redirect, replace: true };
  });

  router.beforeEach(restoreSessionGuard);
  router.beforeEach(routeAccessGuard);

  return router;
}
