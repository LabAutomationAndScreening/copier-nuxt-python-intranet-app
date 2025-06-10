import { defineVitestConfig } from "@nuxt/test-utils/config";
import { coverageConfigDefaults } from "vitest/config";

const fakerSeed = Number(process.env.TEST_FAKER_SEED) || Math.floor(Math.random() * 1e9); // to use this, you'll need to create a setup.ts file and add it to the vitest `setupFiles` config

export default defineVitestConfig({
  define: {
    __TEST_FAKER_SEED__: JSON.stringify(fakerSeed),
  },
  test: {
    sequence: {
      shuffle: true,
    },
    include: ["tests/**/*.spec.ts"],
    coverage: {
      provider: "istanbul",
      reporter: ["text", "json", "html"],
      reportsDirectory: ".coverage",
      thresholds: {
        "100": true,
      },
      exclude: ["**/generated/graphql.ts", "**/codegen.ts", "**/nuxt.config.ts", ...coverageConfigDefaults.exclude],
    },
    setupFiles: ["./tests/setup/faker.ts", "./tests/setup/app.ts"],
    globalSetup: "./tests/setup/globalSetup.ts",
  },
});
