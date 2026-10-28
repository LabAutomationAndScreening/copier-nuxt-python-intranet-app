import argparse
import logging
import os
import signal
import threading
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path

import uvicorn

from .app_def import app
from .jinja_constants import APP_NAME
from .logger_config import configure_logging

logger = logging.getLogger(__name__)


def app_specific_setup():
    pass


@dataclass
class ServerControl:
    stop_event: threading.Event
    exit_code: int = 0
    force_exit_after_seconds: float = 30.0
    _force_exit_timer: threading.Timer | None = field(default=None, init=False)
    _request_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def request_stop(self, *, exit_code: int) -> None:
        with self._request_lock:  # the routes run in the threadpool, so overlapping requests must not both pass the check
            if self._force_exit_timer is not None:
                return
            self.exit_code = exit_code
            self.stop_event.set()
            self._force_exit_timer = threading.Timer(self.force_exit_after_seconds, self._force_exit)
            self._force_exit_timer.daemon = True
            self._force_exit_timer.start()

    def stop_completed(self) -> None:
        if self._force_exit_timer is not None:
            self._force_exit_timer.cancel()

    def _force_exit(self) -> None:
        logger.warning(
            f"Server did not stop within {self.force_exit_after_seconds}s of the stop request; forcing exit with code {self.exit_code}"
        )
        os._exit(self.exit_code)


def run(*, stop_event: threading.Event, host: str, port: int, log_level: str) -> int:
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level=log_level))
    server_control = ServerControl(stop_event=stop_event)
    app.state.server_control = server_control

    def watch_for_stop():
        _ = stop_event.wait()
        server.should_exit = True

    watcher = threading.Thread(target=watch_for_stop, daemon=True)
    watcher.start()
    server.run()
    stop_event.set()
    watcher.join()
    server_control.stop_completed()
    return server_control.exit_code


def start_app(cli_args: argparse.Namespace, *, stop_event: threading.Event | None = None) -> int:
    log_folder = Path("logs")
    if cli_args.log_folder is not None:
        log_folder = Path(cli_args.log_folder)
    configure_logging(log_level=cli_args.log_level, log_filename_prefix=str(log_folder / f"{APP_NAME}-"))
    app_specific_setup()
    logger.info(f"Starting uvicorn server based on CLI arguments: {cli_args}")
    if stop_event is None:
        effective_stop_event = threading.Event()
        _ = signal.signal(signal.SIGINT, lambda _sig, _frame: effective_stop_event.set())  # noqa: ARG005 # signal handler signature requires these args but they are unused
        _ = signal.signal(signal.SIGTERM, lambda _sig, _frame: effective_stop_event.set())  # noqa: ARG005 # signal handler signature requires these args but they are unused
    else:
        effective_stop_event = stop_event
    assert isinstance(cli_args.log_level, str), f"Expected log_level to be a str, got {type(cli_args.log_level)}"
    return run(
        stop_event=effective_stop_event,
        host=cli_args.host,
        port=cli_args.port,
        log_level=cli_args.log_level.lower(),
    )
