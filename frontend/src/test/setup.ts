import { afterEach } from "vitest";

Object.defineProperty(window, "scrollTo", {
  configurable: true,
  value: () => undefined,
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-large-text");
});
