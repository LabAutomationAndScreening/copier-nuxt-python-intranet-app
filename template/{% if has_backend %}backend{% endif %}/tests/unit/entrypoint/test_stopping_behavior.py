import logging
import os
import signal
import socket
import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import override

import httpx
import pytest
import uvicorn
from backend_api.entrypoint.cli import entrypoint
from httpx import codes
from pytest_mock import MockerFixture

from .fixtures import GENERIC_REQUIRED_CLI_ARGS
from .fixtures import blocking_serve
from .fixtures import patch_server_run
from .fixtures import restore_logging_levels  # noqa: F401 # autouse fixture imported for side effect
from .fixtures import restore_signal_handlers  # noqa: F401 # autouse fixture imported for side effect


@pytest.mark.timeout(10)
class TestStoppingBehavior:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture):
        self.stop_event = threading.Event()
        self._server_started = threading.Event()
        self._server_instance: uvicorn.Server | None = None
        self._entrypoint_thread: threading.Thread | None = None

        def _blocking_serve(self_server: uvicorn.Server) -> None:
            self._server_instance = self_server
            self._server_started.set()
            blocking_serve(self_server)

        _ = mocker.patch.object(uvicorn.Server, uvicorn.Server.run.__name__, autospec=True, side_effect=_blocking_serve)

    def _run_entrypoint(self) -> None:
        self._entrypoint_thread = threading.Thread(
            target=entrypoint,
            args=(GENERIC_REQUIRED_CLI_ARGS,),
            kwargs={"stop_event": self.stop_event},
            daemon=True,
        )
        self._entrypoint_thread.start()
        assert self._server_started.wait(timeout=2), "server never started"

    def _wait_for_entrypoint_to_exit(self) -> None:
        assert self._entrypoint_thread is not None, "_run_entrypoint must be called before waiting for exit"
        self._entrypoint_thread.join(timeout=2)
        assert not self._entrypoint_thread.is_alive(), "entrypoint thread did not exit within 2s"

    def test_Given_stop_event_pre_set__Then_server_should_exit_flipped_true(self):
        self.stop_event.set()

        self._run_entrypoint()
        self._wait_for_entrypoint_to_exit()

        assert self._server_instance is not None
        assert self._server_instance.should_exit is True

    def test_Given_stop_event_not_set__Then_server_should_exit_false_at_serve_start(self):
        self._run_entrypoint()

        assert self._server_instance is not None
        captured_should_exit = self._server_instance.should_exit

        self.stop_event.set()
        self._wait_for_entrypoint_to_exit()
        assert captured_should_exit is False

    def test_Given_stop_event_set_during_serve__Then_server_should_exit_flipped_true(self):
        self._run_entrypoint()

        self.stop_event.set()

        self._wait_for_entrypoint_to_exit()
        assert self._server_instance is not None
        assert self._server_instance.should_exit is True


def test_Given_entrypoint_invoked_without_stop_event__Then_sigint_handler_installed(mocker: MockerFixture):
    patch_server_run(mocker)
    spied_signal_fn = mocker.spy(signal, signal.signal.__name__)

    _ = entrypoint(GENERIC_REQUIRED_CLI_ARGS)

    signals_registered = [call.args[0] for call in spied_signal_fn.call_args_list]
    assert signal.SIGINT in signals_registered


@pytest.mark.timeout(10)
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="os.kill(SIGINT/SIGTERM) on Windows sends CTRL_C_EVENT to the process group and terminates the CI process rather than invoking the Python signal handler",
)
@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_Given_signal_received__Then_entrypoint_exits(mocker: MockerFixture, sig: signal.Signals):
    server_started = threading.Event()

    def _blocking_serve(self_server: uvicorn.Server) -> None:
        server_started.set()
        blocking_serve(self_server)

    patch_server_run(mocker, side_effect=_blocking_serve)

    def fire_signal() -> None:
        assert server_started.wait(timeout=2), "server never started"
        os.kill(os.getpid(), sig)

    t = threading.Thread(target=fire_signal, daemon=True)
    t.start()

    _ = entrypoint(GENERIC_REQUIRED_CLI_ARGS)

    t.join(timeout=2)
    assert not t.is_alive()


class _RecordingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def _get_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert isinstance(port, int)
    return port


def _wait_until_healthy(*, base_url: str) -> None:
    for _ in range(100):
        try:
            if httpx.get(f"{base_url}/api/healthcheck", timeout=1.0).is_success:
                return
        except httpx.TransportError:
            pass
        _ = threading.Event().wait(timeout=0.05)
    pytest.fail(f"server at {base_url} never became healthy")


@dataclass(frozen=True)
class RunningServer:
    base_url: str
    thread: threading.Thread
    exit_codes: list[int]
    uvicorn_log: _RecordingHandler


@pytest.fixture
def running_server(tmp_path: Path) -> Iterator[RunningServer]:
    port = _get_open_port()
    stop_event = threading.Event()
    exit_codes: list[int] = []
    thread = threading.Thread(
        target=lambda: exit_codes.append(
            entrypoint(
                ["--host", "127.0.0.1", "--port", str(port), "--log-folder", str(tmp_path)],
                stop_event=stop_event,
            )
        ),
        daemon=True,
    )
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    _wait_until_healthy(base_url=base_url)
    uvicorn_log = _RecordingHandler()
    uvicorn_error_logger = logging.getLogger(
        "uvicorn.error"
    )  # attached after startup because uvicorn reconfigures its loggers while starting
    uvicorn_error_logger.addHandler(uvicorn_log)
    try:
        yield RunningServer(base_url=base_url, thread=thread, exit_codes=exit_codes, uvicorn_log=uvicorn_log)
    finally:
        uvicorn_error_logger.removeHandler(uvicorn_log)
        stop_event.set()
        thread.join(timeout=10)


@pytest.mark.timeout(30)
def test_When_shutdown_route_called_on_running_server__Then_lifespan_shut_down_and_entrypoint_returns_zero(
    running_server: RunningServer,
):
    response = httpx.post(f"{running_server.base_url}/api/shutdown", timeout=5.0)

    running_server.thread.join(timeout=10)

    assert response.status_code == codes.OK
    assert not running_server.thread.is_alive()
    assert running_server.exit_codes == [0]
    assert "Application shutdown complete." in running_server.uvicorn_log.messages


@pytest.mark.timeout(30)
def test_When_restart_route_called_on_running_server__Then_lifespan_shut_down_and_entrypoint_returns_one(
    running_server: RunningServer,
):
    response = httpx.post(f"{running_server.base_url}/api/restart", timeout=5.0)

    running_server.thread.join(timeout=10)

    assert response.status_code == codes.OK
    assert not running_server.thread.is_alive()
    assert running_server.exit_codes == [1]
    assert "Application shutdown complete." in running_server.uvicorn_log.messages
