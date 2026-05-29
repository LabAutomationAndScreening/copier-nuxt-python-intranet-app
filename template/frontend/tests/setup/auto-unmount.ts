import { enableAutoUnmount } from "@vue/test-utils";
import { afterEach } from "vitest";

// Without this, wrappers from mountSuspended accumulate across tests in the same file.
// Reactive composables (e.g. watchers on the shared route from @lab-sync/nuxt-common's
// IdFromRoute) then fan out triangle-number work on every subsequent route change,
// blowing past per-test timeouts in larger spec files.
enableAutoUnmount(afterEach);
