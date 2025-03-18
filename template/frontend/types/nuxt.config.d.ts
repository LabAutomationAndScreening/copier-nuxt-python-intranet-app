import { NuxtConfig } from "nuxt/schema";

declare module "nuxt/schema" {
  interface NuxtConfig {
    apollo?: {
      clients: {
        default: {
          httpEndpoint: string;
        };
      };
    };
  }
}
