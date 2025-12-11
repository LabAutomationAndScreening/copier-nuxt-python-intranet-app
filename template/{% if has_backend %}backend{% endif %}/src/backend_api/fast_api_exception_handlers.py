import logging
from collections.abc import Mapping
from functools import partial
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic import Field
from pydantic import JsonValue
from starlette.exceptions import HTTPException
from uuid_utils import uuid7

logger = logging.getLogger(__name__)


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    # The vendor extension lets Kiota use this as the exception message.
    detail: str = Field(..., json_schema_extra={"x-ms-primary-error-message": True})
    instance: str
    error_type: str | None = Field(default=None, alias="errorType")


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
    return ProblemDetails(
        type="about:blank",
        title=title,
        status=status,
        detail=detail,
        instance=f"urn:uuid:{trace_id}",
        errorType=exc_type,
    ).model_dump(by_alias=True, mode="json")


class ExceptionHandler:
    def __init__(self, app: FastAPI):
        super().__init__()
        self._app = app
        generator: CORSMiddleware | None = None
        for m in app.user_middleware:
            assert isinstance(m.cls, type), f"Expected middleware class to be a type, got {type(m.cls)}"
            if issubclass(m.cls, CORSMiddleware):
                generator = CORSMiddleware(app, **m.kwargs)
            else:
                continue  # pragma: no cover # not worth testing a longer list right now

        if generator is None:
            raise NotImplementedError("CORS Middleware not found, cannot set CORS headers on exception responses")
        assert isinstance(
            generator.simple_headers,  # pyright: ignore[reportUnknownMemberType] # that's why we're asserting
            dict,
        ), f"Expected simple_headers to be a dict, got {type(generator.simple_headers)}"
        # TODO: consider if more dynamic headers would need to be used for some complex CORS setups
        self._cors_headers: dict[str, str] = generator.simple_headers  # pyright: ignore[reportUnknownMemberType] # the simple_headers is not fully typed

    def handle_http_exception(self, request: Request, exc: Exception) -> JSONResponse:
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
        return self._json_response(status_code=exc.status_code, body=body)

    def register(self):
        self._app.add_exception_handler(HTTPException, self.handle_http_exception)
        self._app.add_exception_handler(RequestValidationError, self.handle_validation_exception)
        self._app.add_exception_handler(Exception, self.handle_unhandled_exception)

    def _json_response(self, *, status_code: int, body: dict[str, Any]) -> JSONResponse:
        return JSONResponse(
            status_code=status_code,
            content=body,
            media_type="application/problem+json",
            headers=self._cors_headers,
        )

    def handle_validation_exception(self, request: Request, exc: Exception) -> JSONResponse:
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
        return self._json_response(status_code=422, body=body)

    def handle_unhandled_exception(self, request: Request, exc: Exception) -> JSONResponse:
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
        return self._json_response(status_code=500, body=body)


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Modify the OpenAPI schema to be more explicit about the generic errors that any route can throw.

    This helps with codegen tools such as Kiota.
    """
    if app.openapi_schema:  # don't regenerate the schema on subsequent API calls if it's already been done
        return app.openapi_schema
    oas = get_openapi(title=app.title, version=app.version, routes=app.routes)

    # Ensure ProblemDetails schema exists
    comps = oas.setdefault("components", {}).setdefault("schemas", {})
    comps.setdefault(
        "ProblemDetails",
        ProblemDetails.model_json_schema(ref_template="#/components/schemas/{model}"),
    )

    def problem_ref() -> Mapping[str, JsonValue]:
        return {"$ref": "#/components/schemas/ProblemDetails"}

    def problem_content() -> Mapping[str, JsonValue]:
        return {
            "application/problem+json": {
                "schema":  # pyright: ignore[reportReturnType] # I don't understand why Pyright gets upset at things being subsets of JsonValue
                problem_ref()
            }
        }

    paths = oas.get("paths", {})
    for methods in paths.values():
        for method, op in list(methods.items()):
            if method not in ("get", "put", "post", "delete", "options", "head", "patch", "trace"):
                continue  # pragma: no cover # Most schemas we create will only have those types of methods, so this line will never be hit.  But there are others that are possible (it seems), such as summary/description/servers
            responses = op.setdefault("responses", {})

            # Do NOT touch 422 if FastAPI added it, only add additional responses:
            # 500 should never be present in any defined route, so always add it
            responses.setdefault(
                "500",
                {
                    "description": "Internal Server Error",
                    "content": problem_content(),
                },
            )

            # Optional but recommended for Kiota: add default catch-all.  'default' should never be present in a route, so no need to check for it before adding it
            responses.setdefault(
                "default",
                {
                    "description": "Error",
                    "content": problem_content(),
                },
            )

    app.openapi_schema = oas
    return oas


def register_exception_handlers(app: FastAPI) -> None:
    handler = ExceptionHandler(app)
    handler.register()
    app.openapi = partial(custom_openapi, app)
