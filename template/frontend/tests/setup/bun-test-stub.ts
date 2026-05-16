// Empty stub for the "bun:test" module so that Vite can resolve it under Node.
// @nuxt/test-utils v4 dynamically imports "bun:test" inside a Bun-only code branch that never runs
// under Node; without this stub Vite errors with "Cannot bundle built-in module 'bun:test'".
// Tracked upstream: https://github.com/nuxt/test-utils/issues/1490
export default {};
