import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from .schema_def import schema

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

# using `PYTEST_CURRENT_TEST` doesn't work to protect against executing this code, because pytest hasn't really started yet during imports
# using `if __name__ == "__main__":` doesn't work with the current way uvicorn launches the app
# ...so just trying to make sure we never import this file during test suite execution
# which means inherently this file is excluded from test coverage analysis...so put the minimal amount possible in here
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
