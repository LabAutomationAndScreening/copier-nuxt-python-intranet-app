import { test, expect } from "vitest";
import { mountSuspended } from "@nuxt/test-utils/runtime";

import Index from "~/pages/index.vue";

test("component renders Hello world properly", async () => {
  const wrapper = await mountSuspended(Index);
  expect(wrapper.text()).toContain("Hello");
});
