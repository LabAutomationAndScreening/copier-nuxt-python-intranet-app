import logging
from pathlib import Path

import strawberry

logger = logging.getLogger(__name__)

schema = strawberry.Schema(query=int)
sdl_path = Path(__file__).parent / "schema.graphql"
_ = sdl_path.write_text(f"{schema.as_str()}\n")
