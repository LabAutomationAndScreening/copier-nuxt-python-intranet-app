import json
import logging
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import Any

import structlog
from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic import Field
from pydantic import JsonValue
from pydantic.json_schema import SkipJsonSchema
from pydantic_core import ErrorDetails
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from uuid_utils import uuid7

from .camel_case_model import CamelCaseModel
from .openapi_schema_simplifier import collapse_nullable_anyof

logger = logging.getLogger(__name__)


_HTTP_STATUS_SCHEMA: dict[str, JsonValue] = {"format": "int32", "minimum": 100, "maximum": 599}


PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"
EXAMPLE_TRACE_ID = "0193b5e2-4c1f-7a8d-9e3b-2f6c8d1a5b74"
TRACE_ID_LOG_FIELD = "trace_id"


class ProblemDetails(CamelCaseModel):
    """RFC 9457 problem details describing an error response.

    Returned (as application/problem+json) for error responses so clients and codegen tools such as Kiota
    have a consistent, machine-readable error shape.
    """

    type: str = Field(
        default="about:blank", examples=["about:blank"], description="A URI reference identifying the problem type."
    )
    title: str = Field(
        examples=["Internal Server Error"], description="A short, human-readable summary of the problem."
    )
    status: int = Field(
        json_schema_extra=_HTTP_STATUS_SCHEMA, examples=[500], description="The HTTP status code for this problem."
    )
    # The vendor extension lets Kiota use this as the exception message.
    detail: str = Field(
        ...,
        json_schema_extra={"x-ms-primary-error-message": True},
        examples=["An unexpected error occurred."],
        description="A human-readable explanation specific to this occurrence of the problem.",
    )
    instance: str = Field(
        examples=["/api/healthcheck"],
        description="The path of the request that met this problem, without its query string.",
    )
    error_type: str | None = Field(
        default=None,
        examples=["ValueError"],
        description="The internal exception class name, when available.",
    )
    trace_id: str = Field(
        examples=[EXAMPLE_TRACE_ID],
        description="Identifies this occurrence in the server's logs: search them for it to find what led to the problem.",
    )


class ParameterLocation(StrEnum):
    """Where in the request a parameter is sent, spelled as OpenAPI's parameter `in` spells it."""

    QUERY = "query"
    PATH = "path"
    HEADER = "header"
    COOKIE = "cookie"


class ValidationIssue(CamelCaseModel):
    """One reason a request failed validation, and where in the request it is."""

    detail: str = Field(
        description="What is wrong with the value, in words a person can act on.",
        examples=["Input should be a valid integer, unable to parse string as an integer"],
    )
    code: str = Field(
        description="A machine-readable reason for the issue, from Pydantic's error types; more may be added.",
        examples=["int_parsing"],
    )
    pointer: str | SkipJsonSchema[None] = Field(
        default=None,
        description=(
            "Where the invalid value is in the JSON request body, as a JSON Pointer (RFC 6901) in URI fragment form; "
            "`#` is the whole body. Present only for an issue in the body."
        ),
        examples=["#/items/2"],
    )
    parameter: str | SkipJsonSchema[None] = Field(
        default=None,
        description="The name of the invalid query, path, header or cookie parameter. Present only with `in`.",
        examples=["prependV"],
    )
    location: ParameterLocation | SkipJsonSchema[None] = Field(
        default=None,
        alias="in",
        description="Where the invalid parameter is sent, spelled as OpenAPI's parameter `in`. Present only with `parameter`.",
        examples=[ParameterLocation.QUERY],
    )


class ValidationProblemDetails(ProblemDetails):
    """RFC 9457 problem details for a request that failed validation, listing each invalid value."""

    errors: list[ValidationIssue] = Field(
        description=(
            "Each invalid value in the request. Empty when the route itself rejected the request rather than "
            "its validation finding an invalid value."
        )
    )


def should_show_error_details() -> bool:
    return True  # pragma: no cover # TODO: implement and test the ability to specify via config, CLI, and envvar whether to show error details, and set the default to False


def _short(msg: str, max_len: int = 2000) -> str:
    return msg if len(msg) <= max_len else msg[:max_len] + "...(truncated)"


@dataclass(frozen=True, kw_only=True)
class _Occurrence:
    trace_id: str
    path: str


def _occurrence_of(request: Request) -> _Occurrence:
    trace_id = getattr(request.state, TRACE_ID_LOG_FIELD)
    assert isinstance(trace_id, str), f"Expected the request's trace ID to be a string, got {type(trace_id)}"
    return _Occurrence(trace_id=trace_id, path=request.url.path)


async def _bind_trace_id(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Give the request a trace ID that every log line it writes carries, and that its problem details report.

    The ID is bound to structlog's context for the rest of the request, so `trace_id` lands on each log line
    and searching the logs for it finds everything the request did. It is also stored on `request.state`,
    where the exception handlers read it: Starlette runs the catch-all 500 handler outside user middleware,
    after this binding has ended, but the request's state outlives it.
    """
    trace_id = str(uuid7())
    setattr(request.state, TRACE_ID_LOG_FIELD, trace_id)
    with structlog.contextvars.bound_contextvars(**{TRACE_ID_LOG_FIELD: trace_id}):
        return await call_next(request)


def _problem(*, title: str, status_code: int, detail: str, occurrence: _Occurrence, exc_type: str) -> ProblemDetails:
    return ProblemDetails(
        title=title,
        status=status_code,
        detail=detail,
        instance=occurrence.path,
        error_type=exc_type,
        trace_id=occurrence.trace_id,
    )


def _with_validation_issues(problem: ProblemDetails, issues: list[ValidationIssue]) -> ValidationProblemDetails:
    return ValidationProblemDetails.model_validate({**problem.model_dump(), "errors": issues})


def problem_model_for(status_code: int) -> type[ProblemDetails]:
    """Pick the schema a problem with this status follows.

    A 422 always lists its validation issues, even when it has none to list (one a route raises itself), so
    clients can read `errors` without first checking that it is there.
    """
    if status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
        return ValidationProblemDetails
    return ProblemDetails


def listing_its_validation_issues(problem: ProblemDetails) -> ProblemDetails:
    if problem_model_for(problem.status) is ValidationProblemDetails:
        return _with_validation_issues(problem, [])
    return problem


WHOLE_BODY_POINTER = "#"
WHOLE_BODY_LOCATION_LABEL = "request body"


def _body_pointer(error: ErrorDetails) -> str:
    """Locate a body validation error as a JSON Pointer (RFC 6901) in URI fragment form, such as `#/items/2`.

    After "body", FastAPI's `loc` is the path to the value: field names under the camelCase names the client
    sent, and list indexes. A missing body has no path, so the pointer is `#`, the whole body. So is unparsable
    JSON (Pydantic's `json_invalid`), whose `loc` carries a character offset into the text instead of a path.
    """
    if error["type"] == "json_invalid":
        return WHOLE_BODY_POINTER
    return WHOLE_BODY_POINTER + "".join(f"/{part}" for part in error["loc"][1:])


def _validation_issue(error: ErrorDetails) -> ValidationIssue:
    """Describe one of FastAPI's request validation errors by where it is in the request.

    FastAPI locates an error with a `loc` whose first element says which part of the request it is in: "body"
    for the JSON body, else the parameter's OpenAPI `in` (query, path, header or cookie), followed by the
    parameter's name as the client sent it.
    """
    location = error["loc"][0]
    if location == "body":
        return ValidationIssue(detail=error["msg"], code=error["type"], pointer=_body_pointer(error))
    return ValidationIssue(
        detail=error["msg"], code=error["type"], parameter=str(error["loc"][1]), location=ParameterLocation(location)
    )


def _validation_summary(issues: list[ValidationIssue]) -> str:
    """Summarize a failed validation in one line: where the first problem is, what it is, and how many more follow.

    Kiota surfaces a problem's `detail` as the exception message, so this is the line a UI shows the user; the
    full list is in `errors`. A body issue is located by its pointer without the leading "#/" (`items/2`), a
    parameter by its name.
    """
    first_issue = issues[0]
    if first_issue.pointer is None:
        first_location = first_issue.parameter
    elif first_issue.pointer == WHOLE_BODY_POINTER:
        first_location = WHOLE_BODY_LOCATION_LABEL
    else:
        first_location = first_issue.pointer.removeprefix(f"{WHOLE_BODY_POINTER}/")
    summary = f"{first_location}: {first_issue.detail}"
    further_issue_count = len(issues) - 1
    if further_issue_count > 0:
        summary += f" (and {further_issue_count} more)"
    return summary


class ExceptionHandler:
    def __init__(self, app: FastAPI):
        super().__init__()
        self._app = app
        generator: CORSMiddleware | None = None
        for m in app.user_middleware:
            assert isinstance(m.cls, type), f"Expected middleware class to be a type, got {type(m.cls)}"
            if issubclass(m.cls, CORSMiddleware):
                generator = CORSMiddleware(
                    app,
                    **m.kwargs,  # pyrefly: ignore[bad-argument-type] # pyrefly doesn't like kwargs, but we're just passing them through to Starlette
                )
            else:
                continue  # pragma: no cover # not worth testing a longer list right now

        if generator is None:
            raise NotImplementedError("CORS Middleware not found, cannot set CORS headers on exception responses")

        # TODO: consider if more dynamic headers would need to be used for some complex CORS setups
        self._cors_headers = generator.simple_headers

    def handle_http_exception(self, request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException), f"Expected HTTPException, got {type(exc)}"
        occurrence = _occurrence_of(request)
        logger.warning(
            f"{exc.__class__.__name__} on {request.method} {occurrence.path} [urn:uuid:{occurrence.trace_id}]",
            exc_info=exc,
        )
        # starlette annotates HTTPException.detail as str, but FastAPI's subclass widens it to Any, so a route
        # can raise one carrying a dict or list. RFC 9457 requires detail to be a string, and json.dumps keeps
        # such a payload readable as JSON rather than rendering it as a Python repr.
        if isinstance(exc.detail, str):
            detail = exc.detail
        else:
            detail = json.dumps(exc.detail)
        problem = _problem(
            title="HTTP Error",
            status_code=exc.status_code,
            detail=detail,
            occurrence=occurrence,
            exc_type=exc.__class__.__name__,
        )
        return self._json_response(listing_its_validation_issues(problem))

    def register(self):
        self._app.add_exception_handler(HTTPException, self.handle_http_exception)
        self._app.add_exception_handler(RequestValidationError, self.handle_validation_exception)
        self._app.add_exception_handler(Exception, self.handle_unhandled_exception)

    def _json_response(self, problem: ProblemDetails) -> JSONResponse:
        return JSONResponse(
            status_code=problem.status,
            content=problem.model_dump(by_alias=True, mode="json"),
            media_type=PROBLEM_JSON_MEDIA_TYPE,
            headers=self._cors_headers,
        )

    def handle_validation_exception(self, request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError), f"Expected RequestValidationError, got {type(exc)}"
        occurrence = _occurrence_of(request)
        logger.warning(
            f"{exc.__class__.__name__} on {request.method} {occurrence.path} [urn:uuid:{occurrence.trace_id}]",
            exc_info=exc,
        )
        validation_issues = [_validation_issue(error) for error in exc.errors()]
        problem = _problem(
            title="Validation Error",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_validation_summary(validation_issues),
            occurrence=occurrence,
            exc_type=exc.__class__.__name__,
        )
        return self._json_response(_with_validation_issues(problem, validation_issues))

    def handle_unhandled_exception(self, request: Request, exc: Exception) -> JSONResponse:
        occurrence = _occurrence_of(request)
        logger.error(
            f"Unhandled {exc.__class__.__name__} on {request.method} {occurrence.path} [urn:uuid:{occurrence.trace_id}]",
            exc_info=exc,
        )

        msg = _short(str(exc)) if should_show_error_details() else "An unexpected error occurred."
        problem = _problem(
            title="Internal Server Error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
            occurrence=occurrence,
            exc_type=exc.__class__.__name__,
        )
        return self._json_response(problem)


_COMPONENT_REF_TEMPLATE = "#/components/schemas/{model}"


def component_ref(model: type[BaseModel]) -> str:
    return _COMPONENT_REF_TEMPLATE.format(model=model.__name__)


def _schema_ref(model: type[BaseModel]) -> dict[str, JsonValue]:
    return {"$ref": component_ref(model)}


def _add_problem_schemas(schemas: dict[str, dict[str, JsonValue]]) -> None:
    _ = schemas.setdefault(
        ProblemDetails.__name__, ProblemDetails.model_json_schema(ref_template=_COMPONENT_REF_TEMPLATE)
    )
    validation_problem_schema = ValidationProblemDetails.model_json_schema(ref_template=_COMPONENT_REF_TEMPLATE)
    for name, definition in validation_problem_schema.pop("$defs").items():
        _ = schemas.setdefault(name, definition)
    _ = schemas.setdefault(ValidationProblemDetails.__name__, validation_problem_schema)


def _document_error_responses(responses: dict[str, JsonValue]) -> None:
    """Document the problem details an operation can answer with, beyond the responses its route declares.

    FastAPI adds a 422 to every operation that validates its input; it is replaced with the
    ValidationProblemDetails the validation handler actually sends. Every operation can also fail with a 500, and
    Kiota wants a `default` catch-all; no route declares either, so both are added.
    """
    unprocessable_content = str(status.HTTP_422_UNPROCESSABLE_CONTENT)
    if unprocessable_content in responses:
        responses[unprocessable_content] = {
            "description": "Validation Error",
            "content": {PROBLEM_JSON_MEDIA_TYPE: {"schema": _schema_ref(ValidationProblemDetails)}},
        }
    _ = responses.setdefault(
        str(status.HTTP_500_INTERNAL_SERVER_ERROR),
        {
            "description": "Internal Server Error",
            "content": {PROBLEM_JSON_MEDIA_TYPE: {"schema": _schema_ref(ProblemDetails)}},
        },
    )
    _ = responses.setdefault(
        "default",
        {"description": "Error", "content": {PROBLEM_JSON_MEDIA_TYPE: {"schema": _schema_ref(ProblemDetails)}}},
    )


def custom_openapi(app: FastAPI) -> dict[str, Any]:  # pyrefly: ignore[explicit-any] # this wraps FastAPI's get_openapi(), which is annotated as returning dict[str, Any]
    """Modify the OpenAPI schema to be more explicit about the generic errors that any route can throw.

    This helps with codegen tools such as Kiota.
    """
    if app.openapi_schema is not None:  # don't regenerate the schema on subsequent API calls if it's already been done
        return app.openapi_schema
    oas = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description=app.description,
        tags=app.openapi_tags,
        servers=app.servers,
    )

    # get_openapi() is annotated as returning dict[str, Any], so every value walked out of it is an implicit
    # Any. These annotations state the shape the OpenAPI spec guarantees, which is the only way to keep the
    # rest of this function type-checked.
    schemas: dict[str, dict[str, JsonValue]] = oas.setdefault("components", {}).setdefault("schemas", {})
    _add_problem_schemas(schemas)
    # FastAPI documents every 422 with these, but each 422 is documented as ValidationProblemDetails instead, which
    # is what the validation handler sends, so they are left unreferenced. Every app has a route that validates its
    # input (the health check's query parameter), so FastAPI always generates them.
    del schemas["HTTPValidationError"]
    del schemas["ValidationError"]

    paths: dict[str, dict[str, dict[str, JsonValue]]] = oas.get("paths", {})
    for methods in paths.values():
        for method, op in list(methods.items()):
            if method not in ("get", "put", "post", "delete", "options", "head", "patch", "trace"):
                continue  # pragma: no cover # Most schemas we create will only have those types of methods, so this line will never be hit.  But there are others that are possible (it seems), such as summary/description/servers
            assert "responses" in op, (
                f"Expected FastAPI to have generated a responses object for the {method} operation"
            )
            responses = op["responses"]
            assert isinstance(responses, dict), f"Expected the responses object to be a dict, got {type(responses)}"
            _document_error_responses(responses)

    collapse_nullable_anyof(oas)

    app.openapi_schema = oas
    return oas


def register_exception_handlers(app: FastAPI) -> None:
    handler = ExceptionHandler(app)
    handler.register()
    app.add_middleware(BaseHTTPMiddleware, dispatch=_bind_trace_id)
    app.openapi = partial(custom_openapi, app)  # pyrefly: ignore[method-assign] # replacing app.openapi is how FastAPI documents installing a custom schema generator
