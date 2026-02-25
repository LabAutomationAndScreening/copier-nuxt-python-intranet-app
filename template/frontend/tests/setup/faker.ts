import { faker } from "@faker-js/faker";
import { beforeAll } from "vitest";

declare const __TEST_FAKER_SEED__: number;

console.log("[seed passed to faker]", __TEST_FAKER_SEED__);
beforeAll(() => {
  // ensure faker has specified seed so that test runs could be recreated with the logged seed.
  faker.seed(__TEST_FAKER_SEED__);
});
