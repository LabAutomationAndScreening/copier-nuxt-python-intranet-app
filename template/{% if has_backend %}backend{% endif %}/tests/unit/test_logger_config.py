import json
import logging
import logging.handlers
from collections.abc import Callable
from uuid import uuid4

from fastapi.encoders import jsonable_encoder


def _logged_frames(exc: BaseException) -> list[dict[str, object]]:
    file_handlers = [
        handler for handler in logging.getLogger().handlers if isinstance(handler, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    record = logging.LogRecord(
        name=__name__,
        level=logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg=str(uuid4()),
        args=None,
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    logged = json.loads(file_handlers[0].format(record))
    return [frame for stack in logged["exception"] for frame in stack["frames"]]


def _frames_named(frames: list[dict[str, object]], name: str) -> list[dict[str, object]]:
    return [frame for frame in frames if frame["name"] == name]


def _raise_inside(trigger: Callable[[Callable[[object], object]], object]) -> BaseException:
    error_message = str(uuid4())

    def raise_error(_: object) -> object:
        raise RuntimeError(error_message)

    try:
        _ = trigger(raise_error)
    except RuntimeError as e:
        return e
    raise AssertionError("expected the trigger to raise")


class TestWhenExceptionLoggedToFile:
    def test_When_raised_through_framework_frame__Then_framework_frame_has_no_locals_and_app_frames_keep_locals(self):
        exc = _raise_inside(lambda raise_error: jsonable_encoder(object(), custom_encoder={object: raise_error}))

        frames = _logged_frames(exc)

        framework_frames = _frames_named(frames, jsonable_encoder.__name__)
        app_frames = _frames_named(frames, "raise_error")
        assert len(framework_frames) == 1
        assert len(app_frames) == 1
        assert "locals" not in framework_frames[0]
        assert "locals" in app_frames[0]

    def test_When_raised_through_framework_frame_with_relative_filename_like_a_frozen_executable__Then_that_frame_has_no_locals(
        self,
    ):
        namespace: dict[str, object] = {}
        exec(  # noqa: S102 # compiling with a relative filename is the only way to reproduce a PyInstaller-style co_filename
            compile(
                "def call_through_framework(callback):\n    return callback(None)\n", "starlette/_frozen.py", "exec"
            ),
            namespace,
        )
        call_through_framework = namespace["call_through_framework"]
        assert callable(call_through_framework)
        exc = _raise_inside(call_through_framework)

        frames = _logged_frames(exc)

        framework_frames = _frames_named(frames, "call_through_framework")
        app_frames = _frames_named(frames, "raise_error")
        assert len(framework_frames) == 1
        assert len(app_frames) == 1
        assert "locals" not in framework_frames[0]
        assert "locals" in app_frames[0]
