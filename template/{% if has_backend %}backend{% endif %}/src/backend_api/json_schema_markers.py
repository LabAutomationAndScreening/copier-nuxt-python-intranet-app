from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema


class NotNullableSchemaError(TypeError):
    def __init__(self, *, schema_type: str) -> None:
        super().__init__(
            f"NullHiddenFromJsonSchema needs a nullable schema (X | None, with the marker outside it), got {schema_type}"
        )


class NullHiddenFromJsonSchema:
    """Accept null for an optional field without documenting it, by rendering only the schema of its non-null value.

    Use it as ``Annotated[X | None, NullHiddenFromJsonSchema()]``. The obvious spelling, ``X | SkipJsonSchema[None]``,
    renders the same schema, but pydantic doesn't read that union as ``Optional[X]``: it validates it as a union of two
    branches, so a value that fails ``X`` is reported once per branch, with the real error located under a segment
    naming the ``X`` branch and a second ``none_required`` error beside it. Validating ``X | None`` as nullable and
    hiding null only here keeps a single error, located at the value that failed.

    Constraints and validators belong inside ``X``, with the marker outside the ``| None``; it raises
    NotNullableSchemaError when generating the schema of a field whose type isn't nullable at that point.

    It renders the whole ``X | None`` and drops the null branch, rather than passing ``X``'s inner schema to the
    handler alone: only the full render runs ``X``'s own JSON-schema hooks (``IPvAnyAddress`` gets its schema from one,
    and fails to render without it) and keeps a pydantic model ``X`` as a ``$ref`` rather than inlining it. Pydantic
    renders that union as ``anyOf`` by default, or, under ``union_format="primitive_type_array"`` when every branch is a
    primitive type, as one ``type`` array; null is dropped from either.
    """

    def __get_pydantic_json_schema__(self, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        if core_schema["type"] != "nullable":
            raise NotNullableSchemaError(schema_type=core_schema["type"])
        nullable_json_schema = handler(core_schema)
        if "anyOf" in nullable_json_schema:
            return _without_null_branch(nullable_json_schema=nullable_json_schema)
        return _without_null_type(nullable_json_schema=nullable_json_schema)


def _without_null_branch(*, nullable_json_schema: JsonSchemaValue) -> JsonSchemaValue:
    non_null_branches = [branch for branch in nullable_json_schema["anyOf"] if branch != {"type": "null"}]
    if len(non_null_branches) == 1:
        return dict(non_null_branches[0])
    return {"anyOf": non_null_branches}


def _without_null_type(*, nullable_json_schema: JsonSchemaValue) -> JsonSchemaValue:
    non_null_types = [json_type for json_type in nullable_json_schema["type"] if json_type != "null"]
    if len(non_null_types) == 1:
        return {**nullable_json_schema, "type": non_null_types[0]}
    return {**nullable_json_schema, "type": non_null_types}
