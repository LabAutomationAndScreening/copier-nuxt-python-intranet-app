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
    NotNullableSchemaError when generating the schema of a field whose type isn't nullable at that point. It is meant
    for non-model types: a pydantic model ``X`` is inlined into the field's schema rather than referenced by ``$ref``
    as it is for a plain ``X | None``, so clients generated from the schema would see an anonymous object.
    """

    def __get_pydantic_json_schema__(self, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        if core_schema["type"] != "nullable":
            raise NotNullableSchemaError(schema_type=core_schema["type"])
        return handler(core_schema["schema"])
