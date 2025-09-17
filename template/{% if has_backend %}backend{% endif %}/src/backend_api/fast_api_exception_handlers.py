import logging
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from uuid_utils import uuid7

logger = logging.getLogger(__name__)


def should_show_error_details() -> bool:
    return True  # pragma: no cover # TODO: implement and test the ability to specify via config, CLI, and envvar whether to show error details, and set the default to False


def _short(msg: str, max_len: int = 2000) -> str:
    return msg if len(msg) <= max_len else msg[:max_len] + "...(truncated)"


def _problem_dict(
    *,
    title: str,
    status: int,
    detail: str,
    trace_id: str,
    exc_type: str,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": f"urn:uuid:{trace_id}",
        "errorType": exc_type,
    }
    return body


def handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException), f"Expected HTTPException, got {type(exc)}"
    error_trace_id = uuid7()
    logger.warning(
        f"{exc.__class__.__name__} on {request.method} {request.url.path} [urn:uuid:{error_trace_id}]",
        exc_info=exc,
    )
    body = _problem_dict(
        title="HTTP Error",
        status=exc.status_code,
        detail=str(exc.detail),
        trace_id=str(error_trace_id),
        exc_type=exc.__class__.__name__,
    )
    return JSONResponse(status_code=exc.status_code, content=body, media_type="application/problem+json")


def handle_validation_exception(request: Request, exc: Exception) -> JSONResponse:
    error_trace_id = uuid7()
    logger.warning(
        f"{exc.__class__.__name__} on {request.method} {request.url.path} [urn:uuid:{error_trace_id}]", exc_info=exc
    )
    body = _problem_dict(
        title="Validation Error",
        status=422,
        detail=_short(str(exc)),
        trace_id=str(error_trace_id),
        exc_type=exc.__class__.__name__,
    )
    return JSONResponse(status_code=422, content=body, media_type="application/problem+json")


def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    error_trace_id = uuid7()
    logger.error(
        f"Unhandled {exc.__class__.__name__} on {request.method} {request.url.path} [urn:uuid:{error_trace_id}]",
        exc_info=exc,
    )

    msg = _short(str(exc)) if should_show_error_details() else "An unexpected error occurred."
    body = _problem_dict(
        title="Internal Server Error",
        status=500,
        detail=msg,
        trace_id=str(error_trace_id),
        exc_type=exc.__class__.__name__,
    )

    return JSONResponse(status_code=500, content=body, media_type="application/problem+json")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_exception)
    app.add_exception_handler(Exception, handle_unhandled_exception)
