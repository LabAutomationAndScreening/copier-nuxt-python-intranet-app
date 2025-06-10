import { inject } from "vitest";

export function url(path: string): string {
  if (!path.startsWith("/")) {
    path = `/${path}`;
  }
  return `${inject("baseUrl")}${path}`;
}
