import { describe, expect, it } from "vitest";

import { resolveMediaUrl } from "./url";

describe("resolveMediaUrl", () => {
  it("normalizes stored upload paths for routes below the site root", () => {
    expect(resolveMediaUrl("uploads/models_3d/example.glb")).toBe(
      "/uploads/models_3d/example.glb",
    );
    expect(resolveMediaUrl("uploads\\models_3d\\example.glb")).toBe(
      "/uploads/models_3d/example.glb",
    );
    expect(resolveMediaUrl("/images/pest/example.jpg")).toBe("/images/pest/example.jpg");
    expect(resolveMediaUrl("\\uploads\\models_3d\\example.glb")).toBe(
      "/uploads/models_3d/example.glb",
    );
    expect(resolveMediaUrl("./uploads/models_3d/example.glb")).toBe(
      "/uploads/models_3d/example.glb",
    );
  });

  it("keeps external and protocol-relative URLs untouched", () => {
    expect(resolveMediaUrl("https://example.com/model.glb")).toBe(
      "https://example.com/model.glb",
    );
    expect(resolveMediaUrl("//cdn.example.com/model.glb")).toBe(
      "//cdn.example.com/model.glb",
    );
  });

  it("returns an empty string for empty values", () => {
    expect(resolveMediaUrl(null)).toBe("");
    expect(resolveMediaUrl(undefined)).toBe("");
    expect(resolveMediaUrl("  ")).toBe("");
  });
});
