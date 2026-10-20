import { describe, expect, it } from "vitest";

import { resolveCapabilityFallback } from "./guards";
import {
  resolveLegacyCaseRedirect,
  resolveLegacyRedirect,
} from "./legacyRedirects";
import { routes } from "./routes";

describe("legacy route redirects", () => {
  it.each([
    ["/index.html", "/"],
    ["/agriculture.html", "/agriculture"],
    ["/ecommerce.html", "/ecommerce"],
    ["/crafts.html", "/crafts"],
    ["/resources.html", "/resources"],
    ["/employment.html", "/employment"],
    ["/teacher.html", "/teacher"],
    ["/teacher-panel.html", "/teacher"],
    ["/admin.html", "/admin"],
    ["/government.html", "/government"],
    ["/enterprise.html", "/enterprise"],
    ["/operator.html", "/operator"],
  ])("maps %s onto %s", (legacyPath, spaPath) => {
    expect(resolveLegacyRedirect(legacyPath)).toBe(spaPath);
  });

  it("leaves current SPA paths alone", () => {
    expect(resolveLegacyRedirect("/agriculture")).toBeNull();
    expect(resolveLegacyRedirect("/admin")).toBeNull();
  });

  it("moves legacy case detail links onto their stable route", () => {
    expect(resolveLegacyCaseRedirect("/case-detail.html", "7")).toBe(
      "/case-detail/7",
    );
    expect(resolveLegacyCaseRedirect("/case-detail.html", "案例 7")).toBe(
      "/case-detail/%E6%A1%88%E4%BE%8B%207",
    );
    expect(resolveLegacyCaseRedirect("/case-detail.html", null)).toBe("/resources");
  });
});

describe("backoffice route seams", () => {
  const childrenOf = (path: string) => {
    const record = routes.find((route) => route.path === path);
    expect(record).toBeDefined();
    return record?.children ?? [];
  };

  it.each([
    ["/teacher", "teacher"],
    ["/government", "government"],
    ["/enterprise", "enterprise"],
    ["/operator", "operator"],
    ["/admin", "super_admin"],
  ] as const)("%s is guarded as the %s shell", (path, role) => {
    const record = routes.find((route) => route.path === path);
    expect(record?.meta).toMatchObject({
      requiresAuth: true,
      backofficeRole: role,
    });
    expect(record?.children?.length).toBeGreaterThan(1);
  });

  it("keeps the teacher model upload page inside the shared shell", () => {
    const models = childrenOf("/teacher").find(
      (route) => route.path === "models",
    );
    expect(models?.name).toBe("teacher-models");
    expect(models?.component).toBeTypeOf("function");
    expect(models?.meta?.title).toBe("3D 模型");
  });

  it("mounts the enterprise dashboard, jobs and applications without a second message page", () => {
    const children = childrenOf("/enterprise");
    for (const [path, title] of [
      ["dashboard", "工作台"],
      ["jobs", "职位管理"],
      ["applications", "简历管理"],
    ] as const) {
      const record = children.find((route) => route.path === path);
      expect(record?.component).toBeTypeOf("function");
      expect(record?.meta?.title).toBe(title);
    }
    expect(children.some((route) => route.path === "messages")).toBe(false);
  });

  it("declares capability and fallback path on every backoffice child", () => {
    for (const parentPath of [
      "/teacher",
      "/government",
      "/enterprise",
      "/operator",
      "/admin",
    ] as const) {
      for (const child of childrenOf(parentPath)) {
        if (child.redirect) continue;
        expect(child.meta?.capabilities, `${parentPath}/${child.path}`).toBeInstanceOf(
          Array,
        );
        expect(child.meta?.defaultPath, `${parentPath}/${child.path}`).toMatch(
          /^\/(teacher|government|enterprise|operator|admin)\//,
        );
      }
    }
  });

  it("guards admin reviews with review.moderate instead of inheriting user.manage", () => {
    const parent = routes.find((route) => route.path === "/admin");
    expect(parent?.meta?.capabilities).toBeUndefined();
    const reviews = childrenOf("/admin").find((route) => route.path === "reviews");
    expect(reviews?.meta?.capabilities).toEqual(["review.moderate"]);
    expect(reviews?.meta?.defaultPath).toBe("/admin/dashboard");
  });

  it("does not redirect a denied route back to itself", () => {
    expect(
      resolveCapabilityFallback(
        "/government/dashboard",
        "/government/dashboard",
        "/admin",
      ),
    ).toBe("/admin");
    expect(
      resolveCapabilityFallback(
        "/admin/reviews",
        "/admin/dashboard",
        "/admin",
      ),
    ).toBe("/admin/dashboard");
  });
});
