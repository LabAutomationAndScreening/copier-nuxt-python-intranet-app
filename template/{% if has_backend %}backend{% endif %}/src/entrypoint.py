import logging

from backend_api.app_def import app

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)
logger.info("App booting up")
try:
    # using `PYTEST_CURRENT_TEST` doesn't work to protect against executing this code, because pytest hasn't really started yet during imports
    # using `if __name__ == "__main__":` doesn't work with the current way uvicorn launches the app
    # ...so just trying to make sure we never import this file during test suite execution
    # which means inherently this file is excluded from test coverage analysis...so put the minimal amount possible in here
    _ = app
except Exception:
    logger.exception("Unhandled error")
    raise
