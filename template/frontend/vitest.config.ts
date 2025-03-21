import { defineVitestConfig } from "@nuxt/test-utils/config";

export default defineVitestConfig({
  test: {
    sequence: {
      shuffle: true,
    },
    coverage: {
      reporter: ["text", "json", "html"],
      reportsDirectory: ".coverage",
      skipFull: true,
      ignoreEmptyLines: true,
    },
  },
});
