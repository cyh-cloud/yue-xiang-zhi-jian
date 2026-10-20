import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { createMemoryHistory, createRouter } from "vue-router";
import { describe, expect, it } from "vitest";

import { routes } from "./routes";

const SOURCE_ROOT = join(process.cwd(), "src");
const STATIC_ROUTE_PATTERNS = [
  /\bto="(\/[^"#?]+)"/g,
  /\bto:\s*"(\/[^"#?]+)"/g,
  /\brouter\.(?:push|replace)\(\s*"(\/[^"#?]+)"/g,
  /\bpath:\s*"(\/[^"#?]+)"/g,
];

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.(vue|ts)$/.test(name) ? [path] : [];
  });
}

function staticLinks(): Array<{ path: string; source: string }> {
  const links: Array<{ path: string; source: string }> = [];
  for (const file of sourceFiles(SOURCE_ROOT)) {
    if (file.endsWith(".test.ts")) continue;
    const source = readFileSync(file, "utf8");
    for (const pattern of STATIC_ROUTE_PATTERNS) {
      for (const match of source.matchAll(pattern)) {
        links.push({ path: match[1]!, source: file });
      }
    }
  }
  return links;
}

describe("active route links", () => {
  it("does not leave migration placeholders in the SPA", () => {
    const source = sourceFiles(SOURCE_ROOT)
      .filter((file) => !file.endsWith(".test.ts"))
      .map((file) => readFileSync(file, "utf8"))
      .join("\n");
    expect(source).not.toContain("业务页面将在后续阶段迁移");
    expect(source).not.toContain("区块已预留");
    expect(source).not.toContain("等待业务迁移");
    expect(source).not.toContain("PlaceholderView");
    expect(source).not.toContain("BackofficeSectionView");
  });

  it("resolves every static internal link to a real route", () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes,
    });

    for (const link of staticLinks()) {
      const resolved = router.resolve(link.path);
      expect(
        resolved.matched.some((record) => record.path === link.path),
        `${link.path} from ${link.source} fell into the catch-all route`,
      ).toBe(true);
    }
  });
});
