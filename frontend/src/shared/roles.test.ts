import { describe, expect, it } from "vitest";

import {
  ROLE_FACTS,
  ROLE_OPTIONS,
  defaultPathForRole,
  roleLabel,
} from "./roles";

describe("role facts", () => {
  it.each([
    ["student", "学员", "/agriculture"],
    ["teacher", "教师", "/teacher"],
    ["enterprise", "企业用户", "/enterprise"],
    ["government", "政府用户", "/government"],
    ["operator", "运营用户", "/operator"],
    ["super_admin", "超级管理员", "/admin"],
  ] as const)("covers %s consistently", (role, label, path) => {
    expect(ROLE_FACTS[role].label).toBe(label);
    expect(roleLabel(role)).toBe(label);
    expect(defaultPathForRole(role)).toBe(path);
    expect(ROLE_OPTIONS).toContainEqual({ value: role, label });
  });
});
