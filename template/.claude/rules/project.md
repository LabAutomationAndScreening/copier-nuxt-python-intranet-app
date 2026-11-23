# Project Structure

- This is a statically generated frontend---using the Nuxt and @nuxt/ui frameworks---meant to operate in an air-gapped environment. That code is in the `frontend/` directory.
- There may also be a backend that the frontend interacts with, in `backend/`. If present, it will be a Python FastAPI uvicorn server.
- Kiota generates the API clients of the backend from the committed OpenAPI snapshot. Those clients (`frontend/app/generated/open-api/backend/` and `backend/tests/e2e/generated/open_api/backend/`) are not committed: `task gen-openapi-clients` brings them up to date and does nothing when they already are. Git hooks run it before commits and after checkouts, merges and rebases, but creating a git worktree fires no hook, so run it yourself in a new worktree.
- Regenerating any generated client is `task codegen` (or an individual `gen-*` task from `task --list`) — never hand-edit anything under a `generated/` folder. After changing the backend's API, `task gen-openapi-snapshot` refreshes the OpenAPI snapshot and the clients together; a bare `pytest --snapshot-update` leaves the clients stale until the next hook or task run.
