import argparse
from importlib.metadata import version

from ..jinja_constants import APP_NAME
from ..jinja_constants import DEFAULT_DEPLOYED_HOST
from ..jinja_constants import DEPLOYED_PORT_NUMBER


def _get_version() -> str:
    return f"v{version('backend-api')}"


parser = argparse.ArgumentParser(description=APP_NAME, exit_on_error=False)
_ = parser.add_argument("--version", action="version", version=_get_version())
_ = parser.add_argument("--log-level", type=str, default="INFO", help="The log level to use for the logger")
_ = parser.add_argument("--log-folder", type=str, help="The folder to write logs to")
_ = parser.add_argument("--port", type=int, default=DEPLOYED_PORT_NUMBER, help="What port to serve the app on")
_ = parser.add_argument("--host", type=str, default=DEFAULT_DEPLOYED_HOST, help="What hosts to allow connections from")
