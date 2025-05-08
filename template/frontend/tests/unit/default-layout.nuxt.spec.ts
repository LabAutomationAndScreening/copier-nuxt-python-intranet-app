import { mountSuspended } from "@nuxt/test-utils/runtime";
import { describe, expect, test } from "vitest";

import DefaultLayout from "~/layouts/default.vue";

describe("default layout", () => {
  test("component mounts without error", async () => {
    expect.assertions(1);

    const wrapper = await mountSuspended(DefaultLayout);

    expect(wrapper.text()).toContain("Hello");
  });
});
