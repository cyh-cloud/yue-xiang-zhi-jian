const LEGACY_REDIRECTS: Readonly<Record<string, string>> = {
  "/index.html": "/",
  "/agriculture.html": "/agriculture",
  "/ecommerce.html": "/ecommerce",
  "/crafts.html": "/crafts",
  "/resources.html": "/resources",
  "/employment.html": "/employment",
  "/teacher.html": "/teacher",
  "/teacher-panel.html": "/teacher",
  "/admin.html": "/admin",
  "/government.html": "/government",
  "/enterprise.html": "/enterprise",
  "/operator.html": "/operator",
};

export function resolveLegacyRedirect(path: string): string | null {
  return LEGACY_REDIRECTS[path] ?? null;
}

export function resolveLegacyCaseRedirect(
  path: string,
  id: string | null,
): string | null {
  if (path !== "/case-detail.html") return null;
  return id ? `/case-detail/${encodeURIComponent(id)}` : "/resources";
}
