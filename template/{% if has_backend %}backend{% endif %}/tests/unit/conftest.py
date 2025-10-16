import logging

import pytest
from backend_api import configure_logging

from .snapshot import snapshot_json

_imported_fixtures = (snapshot_json,)
logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True, scope="session")
def configure_log():
    configure_logging(log_filename_prefix="logs/pytest-")
