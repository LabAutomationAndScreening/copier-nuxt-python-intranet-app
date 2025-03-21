import { test, expect } from "vitest";
import { mount } from "@vue/test-utils";

import Index from "~/pages/index.vue";

test("component renders Hello world properly", () => {
  const wrapper = mount(Index);
  expect(wrapper.text()).toContain("Hello");
});
