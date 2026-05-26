import pytest

from ..e2e.conftest import configure_log  # noqa: F401 # this is an autouse fixture
from ..e2e.conftest import vcr_config  # noqa: F401 # this is an autouse fixture


def pytest_configure(config: pytest.Config):
    """Disable coverage reporting for Windows service E2E tests."""
    config.pluginmanager.set_blocked("_cov")
