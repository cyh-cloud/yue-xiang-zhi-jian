import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAgricultureSuggestions,
  streamAgricultureQuestion,
} from "@/api/agriculture";

import AgricultureQa from "./AgricultureQa.vue";

vi.mock("@/api/agriculture", () => ({
  getAgricultureSuggestions: vi.fn(),
  streamAgricultureQuestion: vi.fn(),
}));

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve!: () => void;
  const promise = new Promise<void>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

describe("AgricultureQa product scope", () => {
  beforeEach(() => {
    vi.mocked(getAgricultureSuggestions).mockResolvedValue({
      success: true,
      suggestions: [],
    });
  });

  it("keeps the conversation when only the display name refreshes", async () => {
    const stream = deferred();
    vi.mocked(streamAgricultureQuestion).mockReturnValue(stream.promise);

    const wrapper = mount(AgricultureQa, {
      props: {
        productId: "lychee",
        productName: "本作物",
        sessionId: "session-t20",
      },
    });
    await flushPromises();

    const question = "荔枝花期怎么管理？";
    await wrapper.get("textarea").setValue(question);
    await wrapper.get('button[aria-label="发送"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(question);

    await wrapper.setProps({ productName: "荔枝" });
    await flushPromises();

    expect(wrapper.text()).toContain(question);
    expect(streamAgricultureQuestion).toHaveBeenCalledTimes(1);

    stream.resolve();
    await flushPromises();
    wrapper.unmount();
  });

  it("resets the conversation when the product id changes", async () => {
    const stream = deferred();
    vi.mocked(streamAgricultureQuestion).mockReturnValue(stream.promise);

    const wrapper = mount(AgricultureQa, {
      props: {
        productId: "lychee",
        productName: "荔枝",
        sessionId: "session-t20",
      },
    });
    await flushPromises();

    const question = "荔枝叶片发黄怎么办？";
    await wrapper.get("textarea").setValue(question);
    await wrapper.get('button[aria-label="发送"]').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain(question);

    await wrapper.setProps({ productId: "longan", productName: "龙眼" });
    await flushPromises();

    expect(wrapper.text()).not.toContain(question);
    expect(getAgricultureSuggestions).toHaveBeenLastCalledWith("longan");

    stream.resolve();
    await flushPromises();
    wrapper.unmount();
  });
});
