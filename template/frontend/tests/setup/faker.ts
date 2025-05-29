import { faker } from "@faker-js/faker";
import { beforeEach } from "vitest";

declare const __TEST_FAKER_SEED__: number;

console.log("[seed passed to faker]", __TEST_FAKER_SEED__);
beforeEach(() => {
  // reseed Faker for each test so calls are deterministic
  faker.seed(__TEST_FAKER_SEED__);
});
