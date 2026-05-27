import { execSync } from "node:child_process";

export default async function globalTeardown(): Promise<void> {
  execSync("docker compose --file=../docker-compose.yaml down --volumes", { stdio: "inherit" });
}
