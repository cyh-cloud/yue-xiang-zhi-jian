export {};

declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean;
    capabilities?: string[];
    backofficeRole?:
      | "teacher"
      | "government"
      | "enterprise"
      | "operator"
      | "super_admin";
    title?: string;
    defaultPath?: string;
  }
}
