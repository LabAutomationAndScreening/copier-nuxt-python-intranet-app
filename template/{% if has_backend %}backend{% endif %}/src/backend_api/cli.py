import argparse
import logging
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import uvicorn

from .app_def import app
from .jinja_constants import APP_NAME
from .jinja_constants import DEFAULT_DEPLOYED_HOST
from .jinja_constants import DEPLOYED_PORT_NUMBER
from .logger_config import configure_logging

logger = logging.getLogger(__name__)


def _get_version() -> str:
    return f"v{version('backend-api')}"


parser = argparse.ArgumentParser(description=APP_NAME, exit_on_error=False)
_ = parser.add_argument("--version", action="version", version=_get_version())
_ = parser.add_argument("--log-level", type=str, default="INFO", help="The log level to use for the logger")
_ = parser.add_argument("--log-folder", type=str, help="The folder to write logs to")
_ = parser.add_argument("--port", type=int, default=DEPLOYED_PORT_NUMBER, help="What port to serve the app on")
_ = parser.add_argument("--host", type=str, default=DEFAULT_DEPLOYED_HOST, help="What hosts to allow connections from")


def _app_specific_setup():
    pass


def entrypoint(argv: Sequence[str]) -> int:
    try:
        launched_by_uvicorn = len(argv) > 0 and argv[0] == "src.entrypoint:app"
        if not launched_by_uvicorn:
            try:
                cli_args = parser.parse_args(argv)
            except argparse.ArgumentError:
                logger.exception("Error parsing command line arguments")
                return 2  # this is the exit code that is normally returned when exit_on_error=True for argparse
            log_folder = Path("logs")
            if cli_args.log_folder is not None:
                log_folder = Path(cli_args.log_folder)
            configure_logging(log_level=cli_args.log_level, log_filename_prefix=str(log_folder / f"{APP_NAME}-"))
        _app_specific_setup()
        if not launched_by_uvicorn:
            assert cli_args  # type: ignore[reportPossiblyUnboundVariable] # false positive, the conditional above ensures this is always set
            uvicorn.run(
                app,
                host=cli_args.host,
                port=cli_args.port,
                log_level=cli_args.log_level.lower(),
                workers=1,  # explicitly ensure only single threaded so we don't need to deal with race conditions
            )
    except Exception:
        logger.exception("An unhandled exception occurred")
        raise
    return 0
