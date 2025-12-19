import logging
import random
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import ANY
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from backend_api import cli
from backend_api.cli import entrypoint
from backend_api.jinja_constants import APP_NAME
from backend_api.jinja_constants import DEFAULT_DEPLOYED_HOST
from backend_api.jinja_constants import DEPLOYED_PORT_NUMBER
from pytest_mock import MockerFixture

GENERIC_REQUIRED_CLI_ARGS = ()


def random_non_info_log_level() -> str:
    return random.choice(["DEBUG", "WARNING", "ERROR", "CRITICAL"])


def test_Given_invalid_cli_args__Then_exit_code_is_2():
    # TODO: capture the log message so the stderr is not overrun with log messages during testing
    invalid_args = ["--invalid-arg"]
    argparse_exit_code = 2

    actual = entrypoint(invalid_args)

    assert actual == argparse_exit_code


def test_When_version__Then_returns_something_looking_like_semver(capsys: pytest.CaptureFixture[str]):
    expected_num_dots_in_version = 2

    with pytest.raises(SystemExit) as e:  # noqa: PT011 # there is nothing meaningful to match against for the text of this error, we are asserting later that the exit code is zero
        _ = entrypoint(["--version"])
    assert e.value.code == 0

    captured = capsys.readouterr()
    actual_version = captured.out.strip()

    assert actual_version.startswith("v")
    assert actual_version.count(".") == expected_num_dots_in_version


def test_Given_something_mocked_to_error__Then_error_logged(mocker: MockerFixture):
    expected_error = str(uuid4())
    spied_logger = mocker.spy(cli.logger, "exception")
    _ = mocker.patch.object(
        cli,
        cli._app_specific_setup.__name__,  # noqa: SLF001 # yes this is a private method, but we just need something that will always execute so we can mock it throwing an error
        autospec=True,
        side_effect=RuntimeError(expected_error),
    )

    with pytest.raises(RuntimeError, match=expected_error):
        _ = entrypoint(GENERIC_REQUIRED_CLI_ARGS)

    spied_logger.assert_called_once()


def test_Given_launched_directly_via_uvicorn__Then_return_zero():
    actual = entrypoint(["src.entrypoint:app"])

    assert actual == 0


@pytest.fixture
def spied_configure_logging(mocker: MockerFixture) -> Generator[MagicMock, None, None]:
    """Spy on configure_logging and restore default logging config after test."""
    spied = mocker.spy(cli, cli.configure_logging.__name__)
    yield spied
    # Restore default logging configuration after test
    if spied.called:
        # Restore all backend_api loggers and root logger to INFO level
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            if logger_name.startswith("backend_api"):
                logger = logging.getLogger(logger_name)
                logger.setLevel(logging.INFO)

        logging.getLogger().setLevel(logging.INFO)


class TestCliArgParsing:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture):
        self.mocker = mocker
        self.mocked_uvicorn_launch = self.mocker.patch.object(cli.uvicorn, cli.uvicorn.run.__name__, autospec=True)

    def test_Given_log_level_specified__Then_app_log_level_passed_to_configure_logging(
        self, spied_configure_logging: MagicMock
    ):
        expected_log_level = random_non_info_log_level()

        assert (
            entrypoint(
                [
                    f"--log-level={expected_log_level}",
                ]
            )
            == 0
        )

        spied_configure_logging.assert_called_once_with(log_level=expected_log_level, log_filename_prefix=ANY)

    def test_Given_log_folder_specified__Then_log_folder_passed_to_configure_logging(
        self, spied_configure_logging: MagicMock
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            expected_log_folder = temp_dir

        assert (
            entrypoint(
                [
                    f"--log-folder={expected_log_folder}",
                ]
            )
            == 0
        )

        spied_configure_logging.assert_called_once_with(
            log_filename_prefix=str(Path(expected_log_folder) / f"{APP_NAME}-"),
            log_level=ANY,
        )

    def test_Given_log_level_specified__Then_log_level_passed_to_uvicorn(self):
        expected_log_level = random_non_info_log_level()

        assert (
            entrypoint(
                [
                    f"--log-level={expected_log_level}",
                ]
            )
            == 0
        )

        self.mocked_uvicorn_launch.assert_called_once_with(
            ANY, log_level=expected_log_level.lower(), host=ANY, port=ANY, workers=ANY
        )

    def test_Given_port_specified__Then_port_passed_to_uvicorn(self):
        expected_port = random.randint(1000, 9999)

        assert (
            entrypoint(
                [
                    f"--port={expected_port}",
                ]
            )
            == 0
        )

        self.mocked_uvicorn_launch.assert_called_once_with(
            ANY, host=ANY, port=expected_port, log_level=ANY, workers=ANY
        )

    def test_Given_host_specified__Then_host_passed_to_uvicorn(self):
        expected_host = str(uuid4())

        assert (
            entrypoint(
                [
                    f"--host={expected_host}",
                ]
            )
            == 0
        )

        self.mocked_uvicorn_launch.assert_called_once_with(
            ANY, host=expected_host, port=ANY, log_level=ANY, workers=ANY
        )

    def test_Given_no_args__Then_default_port_and_host_used(self):
        expected_port = DEPLOYED_PORT_NUMBER
        expected_host = DEFAULT_DEPLOYED_HOST

        assert entrypoint(GENERIC_REQUIRED_CLI_ARGS) == 0

        self.mocked_uvicorn_launch.assert_called_once_with(
            ANY, host=expected_host, port=expected_port, log_level=ANY, workers=ANY
        )

    def test_Given_no_args__Then_default_log_config_used_for_app(self, spied_configure_logging: MagicMock):
        assert entrypoint(GENERIC_REQUIRED_CLI_ARGS) == 0

        spied_configure_logging.assert_called_once_with(
            log_filename_prefix=str(Path("logs") / f"{APP_NAME}-"), log_level="INFO"
        )

    def test_Given_no_args__Then_default_log_config_used_for_uvicorn(self):
        assert entrypoint(GENERIC_REQUIRED_CLI_ARGS) == 0

        self.mocked_uvicorn_launch.assert_called_once_with(ANY, host=ANY, port=ANY, log_level="info", workers=ANY)
