import argparse
import logging
from collections.abc import Sequence

import uvicorn

from .app_def import app
from .logger_config import configure_logging

logger = logging.getLogger(__name__)
parser = argparse.ArgumentParser(description="cloud-courier", exit_on_error=False)
_ = parser.add_argument("--log-level", type=str, default="INFO", help="The log level to use for the logger")
_ = parser.add_argument("--log-folder", type=str, help="The folder to write logs to")
_ = parser.add_argument("--port", type=int, default=4000, help="What port to serve the app on")
_ = parser.add_argument("--host", type=str, default="localhost", help="What host to serve the app on")


def _app_specific_setup():
    pass


def entrypoint(argv: Sequence[str]) -> int:
    try:
        try:
            cli_args = parser.parse_args(argv)
        except argparse.ArgumentError:
            logger.exception("Error parsing command line arguments")
            return 2  # this is the exit code that is normally returned when exit_on_error=True for argparse
        configure_logging()
        _app_specific_setup()
        uvicorn.run(
            app,
            host="localhost",  # this should only be interacted with locally
            port=8000,
            log_level="info",
            workers=1,  # explicitly ensure only single threaded so we don't need to deal with race conditions
        )
    except Exception:
        logger.exception("An unhandled exception occurred")
        raise
    return 0
