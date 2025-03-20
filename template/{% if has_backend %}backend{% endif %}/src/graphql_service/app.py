import logging
from pathlib import Path

import strawberry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

logger = logging.getLogger(__name__)


schema = strawberry.Schema(query=int)
sdl_path = Path(__file__).parent / "schema.graphql"
_ = sdl_path.write_text(f"{schema.as_str()}\n")
graphql_app = GraphQLRouter(schema)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Super permissive CORS setting since this is for intranet
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(graphql_app, prefix="/graphql")
