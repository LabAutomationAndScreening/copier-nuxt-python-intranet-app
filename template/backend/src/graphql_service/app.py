import logging
from pathlib import Path

import strawberry
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

logger = logging.getLogger(__name__)


schema = strawberry.Schema(query=int)
sdl_path = Path(__file__).parent / "schema.graphql"
_ = sdl_path.write_text(schema.as_str())
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.include_router(graphql_app, prefix="/graphql")
