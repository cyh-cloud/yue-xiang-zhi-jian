import type { AxiosResponse, InternalAxiosRequestConfig } from "axios";
import { afterEach, describe, expect, it } from "vitest";

import { apiRequest, postForm, setApiSessionId } from "./client";

describe("postForm", () => {
  afterEach(() => {
    setApiSessionId(null);
  });

  it("sends multipart without a JSON content type or JSON encoding", async () => {
    setApiSessionId("session-probe");

    const form = new FormData();
    form.append("file", new Blob(["glTF"]), "probe.glb");
    form.append("title", "probe");

    let captured: InternalAxiosRequestConfig | undefined;
    await postForm("/api/teacher/models-3d", form, {
      adapter: async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
        captured = config;
        return {
          data: { success: true },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        };
      },
    });

    expect(captured).toBeDefined();
    expect(captured!.data).toBe(form);
    expect(captured!.headers.get("Content-Type")).toBeNull();
    expect(captured!.headers.get("X-Session-Id")).toBe("session-probe");
  });

  it("reports a lost connection and a restored connection at the API seam", async () => {
    const states: boolean[] = [];
    const listener = (event: WindowEventMap["yuexiang:connection"]) => {
      states.push(event.detail.unavailable);
    };
    window.addEventListener("yuexiang:connection", listener);
    try {
      await expect(
        apiRequest({
          method: "GET",
          url: "/api/admin/users",
          adapter: async () => {
            throw new Error("network disconnected");
          },
        }),
      ).rejects.toMatchObject({ status: 0 });
      await apiRequest({
        method: "GET",
        url: "/api/admin/users",
        adapter: async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => ({
          data: { success: true },
          status: 200,
          statusText: "OK",
          headers: {},
          config,
        }),
      });
      expect(states).toEqual([true, false]);
    } finally {
      window.removeEventListener("yuexiang:connection", listener);
    }
  });
});
