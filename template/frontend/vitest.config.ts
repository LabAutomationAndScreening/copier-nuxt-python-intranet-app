import { defineVitestConfig } from "@nuxt/test-utils/config";
import { coverageConfigDefaults } from "vitest/config";

const fakerSeed = Number(process.env.TEST_FAKER_SEED) || Math.floor(Math.random() * 1e9); // to use this, you'll need to create a setup.ts file and add it to the vitest `setupFiles` config
const isE2E = process.env.USE_DOCKER_COMPOSE_FOR_VITEST_E2E || process.env.USE_BUILT_BACKEND_FOR_VITEST_E2E;

export default defineVitestConfig({
  define: {
    __TEST_FAKER_SEED__: JSON.stringify(fakerSeed),
  },
  test: {
    fileParallelism: !isE2E, // Disable parallelism for E2E tests // TODO: consider when we start making better use of "workspaces" if we want to only disable it for some files in the E2E test suite
    sequence: {
      shuffle: true,
    },
    include: ["tests/**/*.spec.ts"],
    root: ".",
    coverage: {
      provider: "istanbul",
      reporter: ["text", "json", "html"],
      reportsDirectory: ".coverage",
      thresholds: {
        "100": true,
      },
      exclude: [
        "**/generated/graphql.ts",
        "**/codegen.ts",
        "**/generated/open-api",
        "**/nuxt.config.ts",
        ...coverageConfigDefaults.exclude,
      ],
    },
    setupFiles: ["./tests/setup/faker.ts", "./tests/setup/app.ts"],
    globalSetup: "./tests/setup/globalSetup.ts",
  },
});
