import logging
from pathlib import Path

import strawberry
from backend_api.strawberry_router import AddErrorTrace

logger = logging.getLogger(__name__)

schema = strawberry.Schema(query=int, extensions=[AddErrorTrace])
sdl_path = Path(__file__).parent / "schema.graphql"
schema_lines = [line.rstrip() for line in schema.as_str().splitlines()]
_ = sdl_path.write_text("\n".join(schema_lines) + "\n")
_ = sdl_path.write_text(f"{schema.as_str()}\n")
