import { mountSuspended } from "@nuxt/test-utils/runtime";
import { describe, expect, test } from "vitest";

import Index from "~/pages/index.vue";

describe("index page", () => {
  test("component renders Hello world properly", async () => {
    expect.assertions(1);
    const wrapper = await mountSuspended(Index);
    expect(wrapper.text()).toContain("Hello");
  });
});
