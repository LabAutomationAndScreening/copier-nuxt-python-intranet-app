import pytest
from backend_api import configure_logging


@pytest.fixture(autouse=True, scope="session")
def configure_log():
    configure_logging(log_filename_prefix="logs/pytest-")


@pytest.fixture(autouse=True)
def vcr_config() -> dict[str, object]:
    # disable any network blocking set up for unit tests
    return {"allowed_hosts": ["127.0.0.1", "localhost", "::1"]}
