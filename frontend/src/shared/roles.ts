import type { Role } from "@/api/types";

export interface RoleFact {
  label: string;
  backofficeLabel?: string;
  defaultPath: string;
  backofficeTitle: string;
}

export const ROLE_FACTS: Record<Role, RoleFact> = {
  student: {
    label: "学员",
    defaultPath: "/agriculture",
    backofficeTitle: "",
  },
  teacher: {
    label: "教师",
    defaultPath: "/teacher",
    backofficeTitle: "教师工作台",
  },
  enterprise: {
    label: "企业用户",
    defaultPath: "/enterprise",
    backofficeTitle: "企业中心",
  },
  government: {
    label: "政府用户",
    backofficeLabel: "政府",
    defaultPath: "/government",
    backofficeTitle: "政府工作台",
  },
  operator: {
    label: "运营用户",
    defaultPath: "/operator",
    backofficeTitle: "运营工作台",
  },
  super_admin: {
    label: "超级管理员",
    defaultPath: "/admin",
    backofficeTitle: "系统管理后台",
  },
};

export const ROLE_OPTIONS = (
  Object.keys(ROLE_FACTS) as Role[]
).map((role) => ({
  value: role,
  label: ROLE_FACTS[role].label,
}));

export function roleLabel(role: Role): string {
  return ROLE_FACTS[role].label;
}

export function defaultPathForRole(role: Role): string {
  return ROLE_FACTS[role].defaultPath;
}
