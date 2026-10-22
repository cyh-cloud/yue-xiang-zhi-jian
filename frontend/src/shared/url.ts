const EXTERNAL_URL = /^[a-z][a-z\d+\-.]*:/i;

export function resolveInSiteRedirect(
  value: unknown,
  fallback: string,
): string {
  if (typeof value !== "string") return fallback;
  const candidate = value.trim();
  if (!candidate.startsWith("/") || candidate.startsWith("//")) {
    return fallback;
  }
  if (candidate.includes("\\") || /[\r\n]/.test(candidate)) {
    return fallback;
  }
  return candidate;
}

export function resolveMediaUrl(value: string | null | undefined): string {
  const candidate = (value ?? "")
    .trim()
    .replace(/^(?:\.\/)+/, "")
    .replace(/\\/g, "/");
  if (!candidate || candidate.startsWith("//") || EXTERNAL_URL.test(candidate)) {
    return candidate;
  }
  return candidate.startsWith("/") ? candidate : `/${candidate}`;
}
