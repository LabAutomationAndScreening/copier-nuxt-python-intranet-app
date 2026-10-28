import os
import random
import threading
from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest
from backend_api.app_runner import ServerControl
from pytest_mock import MockerFixture

_REAL_FORCE_EXIT = ServerControl._force_exit  # noqa: SLF001 # captured at import, before the unit-test guard in conftest replaces it


@dataclass(frozen=True)
class ForceExitRecorder:
    """Observes the force-exit path of ServerControl without ending the test process.

    `os_exit` is the mock that replaced os._exit, so tests can assert on the exit code. `called` is set from the
    timer thread when the mock is invoked, so tests can wait for the timer without sleeping for a fixed time.
    """

    os_exit: MagicMock
    called: threading.Event


@pytest.fixture
def force_exit_recorder(mocker: MockerFixture) -> ForceExitRecorder:
    """Run the real ServerControl._force_exit against a mocked os._exit.

    Both patches are needed, and simplifying to just mocking os._exit will break these tests:
    - conftest's session-wide `refuse_unexpected_force_exit` guard replaces ServerControl._force_exit with one that
      raises, so a stray timer can't end the whole run with exit code 0. Without restoring the real method here, the
      timer would raise in its thread instead of ever reaching os._exit.
    - os._exit itself must be mocked, or the real method would terminate pytest.
    """
    called = threading.Event()

    def record_force_exit(_code: int) -> None:  # noqa: ARG001 # must accept the same argument as os._exit
        called.set()

    _ = mocker.patch.object(ServerControl, _REAL_FORCE_EXIT.__name__, _REAL_FORCE_EXIT)
    os_exit = mocker.patch.object(os, os._exit.__name__, autospec=True, side_effect=record_force_exit)
    return ForceExitRecorder(os_exit=os_exit, called=called)


def test_Given_graceful_stop_never_finishes__When_stop_requested__Then_process_force_exited_with_requested_code(
    force_exit_recorder: ForceExitRecorder,
):
    exit_code = random.randint(1, 255)
    server_control = ServerControl(stop_event=threading.Event(), force_exit_after_seconds=0.01)

    server_control.request_stop(exit_code=exit_code)

    _ = force_exit_recorder.called.wait(timeout=2)

    force_exit_recorder.os_exit.assert_called_once_with(exit_code)


def test_Given_stop_requested__When_stop_completed_before_deadline__Then_process_not_force_exited(
    force_exit_recorder: ForceExitRecorder,
):
    """Deterministically catch a broken timer cancellation.

    The real-server tests also depend on the cancellation, but a missing cancel only shows up there when their 30s
    timers fire while some later test is running; the conftest guard then fails whichever test that happens to be.
    This test fails itself on every run instead.
    """
    force_exit_after_seconds = 0.05
    server_control = ServerControl(stop_event=threading.Event(), force_exit_after_seconds=force_exit_after_seconds)
    server_control.request_stop(exit_code=random.randint(1, 255))

    server_control.stop_completed()

    forced_exit_happened = force_exit_recorder.called.wait(timeout=force_exit_after_seconds * 10)

    assert server_control.stop_event.is_set()
    assert forced_exit_happened is False
    force_exit_recorder.os_exit.assert_not_called()


def test_Given_stop_requested__When_another_stop_requested__Then_first_exit_code_kept_and_not_force_exited_after_stop_completed(
    force_exit_recorder: ForceExitRecorder,
):
    first_exit_code, second_exit_code = random.sample(range(256), 2)
    force_exit_after_seconds = 0.05
    server_control = ServerControl(stop_event=threading.Event(), force_exit_after_seconds=force_exit_after_seconds)
    server_control.request_stop(exit_code=first_exit_code)

    server_control.request_stop(exit_code=second_exit_code)
    server_control.stop_completed()

    forced_exit_happened = force_exit_recorder.called.wait(timeout=force_exit_after_seconds * 10)

    assert server_control.exit_code == first_exit_code
    assert forced_exit_happened is False
