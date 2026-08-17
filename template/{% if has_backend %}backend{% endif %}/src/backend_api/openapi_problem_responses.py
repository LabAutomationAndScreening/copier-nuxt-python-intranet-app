from http import HTTPStatus
from typing import Any

from .fast_api_exception_handlers import ProblemDetails

PROBLEM_DETAILS_REF = "#/components/schemas/ProblemDetails"
PROBLEM_JSON_MEDIA_TYPE = "application/problem+json"


def problem_response(
    status_code: int,
    description: str,
    *,
    instance: str = "about:blank",
) -> dict[int | str, dict[str, Any]]:  # pyrefly: ignore[explicit-any] # OpenAPI response fragments are heterogeneous nested JSON; JsonValue would force every consumer to narrow through the union to reach a leaf
    """Build an OpenAPI ``responses`` entry documenting a ``ProblemDetails`` error.

    Holds the ~80% that every error response shares (the ``application/problem+json`` media type and the
    ``ProblemDetails`` schema ref) so route decorators only pass what differs: status and description.
    Merge several with dict unpacking: ``{**problem_response(...), **problem_response(...)}``.

    ``example`` is synthesized from ``status_code`` and ``description`` so the docs
    show a body that matches this response (e.g. a 400 titled "Bad Request") instead of the generic
    field-level example rendered from a bare ``ProblemDetails`` schema ref. Pass ``instance`` to point the
    example at the route's real path.
    """
    example = ProblemDetails(
        title=HTTPStatus(status_code).phrase, status=status_code, detail=description, instance=instance
    )
    content: dict[str, Any] = {  # pyrefly: ignore[explicit-any] # matches the return type above
        "schema": {"$ref": PROBLEM_DETAILS_REF},
        "example": example.model_dump(mode="json", by_alias=True),
    }
    return {status_code: {"description": description, "content": {PROBLEM_JSON_MEDIA_TYPE: content}}}
