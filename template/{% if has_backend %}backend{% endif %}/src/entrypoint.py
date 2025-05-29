import sys  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app

from backend_api.app_def import (
    app,
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
from backend_api.cli import (
    entrypoint,
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app

_ = app  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app

exit_code = entrypoint(
    sys.argv[1:]
)  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
if (  # needed to enable using hot-reloading with uvicorn. if we always call sys.exit even with 0, then the FastAPI app won't work correctly when launched directly by uvicorn
    exit_code != 0
):  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
    sys.exit(
        exit_code
    )  # pragma: no cover # we can't unit test the entrypoint itself. It is tested in the E2E test of the app
