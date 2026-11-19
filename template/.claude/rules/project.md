# Project Structure

- This is a statically generated frontend---using the Nuxt and @nuxt/ui frameworks---meant to operate in an air-gapped environment. That code is in the `frontend/` directory.
- There may also be a backend that the frontend interacts with, in `backend/`. If present, it will be a Python FastAPI uvicorn server.
- Kiota is used for codegen from the OpenAPI schema
- Regenerating any generated client is `task codegen` (or an individual `gen-*-client` task from `task --list`) — never hand-edit anything under a `generated/` folder.
