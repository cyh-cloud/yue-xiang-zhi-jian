import { describe, expect, it } from "vitest";

import {
  isLegacyCacheName,
  isLegacyServiceWorker,
} from "./legacyServiceWorker";

describe("legacy service worker cleanup scope", () => {
  it("recognizes only the legacy site worker", () => {
    const registration = {
      active: { scriptURL: "https://example.test/sw.js" },
    } as ServiceWorkerRegistration;

    expect(isLegacyServiceWorker(registration)).toBe(true);
  });

  it("leaves another application worker alone", () => {
    const registration = {
      active: { scriptURL: "https://example.test/other-app/sw.js" },
    } as ServiceWorkerRegistration;

    expect(isLegacyServiceWorker(registration)).toBe(false);
  });

  it("recognizes only versioned Yuexiang caches", () => {
    expect(isLegacyCacheName("yuexiang-v74")).toBe(true);
    expect(isLegacyCacheName("other-app-cache")).toBe(false);
    expect(isLegacyCacheName("yuexiang-vue-next")).toBe(false);
  });
});
