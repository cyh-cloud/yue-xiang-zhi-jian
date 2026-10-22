/// <reference types="vite/client" />

declare global {
  interface WindowEventMap {
    "yuexiang:connection": Event & { detail: { unavailable: boolean } };
  }
}

export {};

declare module "*.vue" {
  import type { DefineComponent } from "vue";

  const component: DefineComponent<object, object, unknown>;
  export default component;
}
