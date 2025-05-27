import sys  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app

from backend_api.app_def import (
    app,
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
from backend_api.cli import (
    entrypoint,
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app


_ = app  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
sys.exit(
    entrypoint(sys.argv[1:])
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
