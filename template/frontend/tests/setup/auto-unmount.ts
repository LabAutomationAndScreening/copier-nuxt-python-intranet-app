import { enableAutoUnmount } from "@vue/test-utils";
import { afterEach } from "vitest";

// Prevent wrapper accumulation across tests, which causes exponential work in reactive watchers and timeouts.
enableAutoUnmount(afterEach);
