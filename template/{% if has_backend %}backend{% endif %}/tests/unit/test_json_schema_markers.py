from typing import Annotated

import pytest
from backend_api.json_schema_markers import NotNullableSchemaError
from backend_api.json_schema_markers import NullHiddenFromJsonSchema
from faker import Faker
from pydantic import AfterValidator
from pydantic import BaseModel
from pydantic import Field
from pydantic import IPvAnyAddress
from pydantic import TypeAdapter
from pydantic import ValidationError
from pydantic.json_schema import JsonSchemaValue

# arbitrary: any type that pydantic validates as nullable once it is unioned with None
_NonNullValue = list[str]


class _Payload(BaseModel):
    values: Annotated[_NonNullValue | None, NullHiddenFromJsonSchema()] = None


class _PayloadWithoutNone(BaseModel):
    values: Annotated[_NonNullValue, NullHiddenFromJsonSchema()]


def _unchanged(values: list[str]) -> list[str]:
    return values


# arbitrary limits: any that pydantic renders into the schema
_ConstrainedAndAfterValidatedValue = Annotated[list[str], Field(min_length=1, max_length=2), AfterValidator(_unchanged)]


class _ConstrainedAndAfterValidatedPayload(BaseModel):
    values: Annotated[_ConstrainedAndAfterValidatedValue | None, NullHiddenFromJsonSchema()] = None


# pydantic gets IPvAnyAddress's JSON schema only from a class-level hook; its validator alone can't be rendered
_ValueWithItsOwnJsonSchemaHook = IPvAnyAddress


class _PayloadWithItsOwnJsonSchemaHook(BaseModel):
    values: Annotated[_ValueWithItsOwnJsonSchemaHook | None, NullHiddenFromJsonSchema()] = None


# arbitrary: any union of two or more non-null types
_UnionOfNonNullValues = int | str


class _UnionPayload(BaseModel):
    values: Annotated[_UnionOfNonNullValues | None, NullHiddenFromJsonSchema()] = None


class _NestedModel(BaseModel):
    value: str


class _NestedModelPayload(BaseModel):
    values: Annotated[_NestedModel | None, NullHiddenFromJsonSchema()] = None


class TestNullHiddenFromJsonSchema:
    """Tests for NullHiddenFromJsonSchema directly.

    It is meant to become part of a standalone library, so its tests must not depend on this project: they check it on
    throwaway models instead of through this project's routes.
    """

    @pytest.mark.parametrize(
        ("payload_model", "non_null_schema"),
        [
            pytest.param(_Payload, TypeAdapter(_NonNullValue).json_schema(), id="plain"),
            pytest.param(
                _ConstrainedAndAfterValidatedPayload,
                TypeAdapter(_ConstrainedAndAfterValidatedValue).json_schema(),
                id="constrained-and-after-validated",
            ),
            pytest.param(
                _PayloadWithItsOwnJsonSchemaHook,
                TypeAdapter(_ValueWithItsOwnJsonSchemaHook).json_schema(),
                id="type-with-its-own-json-schema-hook",
            ),
        ],
    )
    def test_When_json_schema_generated__Then_the_field_documents_its_non_null_value_and_not_null(
        self, payload_model: type[BaseModel], non_null_schema: JsonSchemaValue
    ):
        field_schema = payload_model.model_json_schema()["properties"]["values"]

        assert {key: field_schema.get(key) for key in non_null_schema} == non_null_schema
        assert "anyOf" not in field_schema

    def test_When_json_schema_generated_for_a_union_of_non_null_types__Then_the_field_offers_each_of_them_and_not_null(
        self,
    ):
        field_schema = _UnionPayload.model_json_schema()["properties"]["values"]

        assert field_schema["anyOf"] == TypeAdapter(_UnionOfNonNullValues).json_schema()["anyOf"]

    def test_When_json_schema_generated_for_a_model__Then_the_field_references_the_model_and_not_null(self):
        payload_schema = _NestedModelPayload.model_json_schema()

        field_schema = payload_schema["properties"]["values"]
        referenced_definition = field_schema["$ref"].removeprefix("#/$defs/")

        assert payload_schema["$defs"][referenced_definition] == _NestedModel.model_json_schema()
        assert "anyOf" not in field_schema

    def test_When_a_value_failing_the_non_null_type_validated__Then_one_error_located_at_the_field(self, faker: Faker):
        not_a_list = faker.pyint()

        with pytest.raises(ValidationError) as exc_info:  # noqa: PT011 # the errors' locations, asserted below, are the point; their message text is pydantic's
            _ = _Payload.model_validate({"values": not_a_list})

        error_locations = [error["loc"] for error in exc_info.value.errors()]

        assert error_locations == [("values",)]

    def test_Given_the_marker_on_a_type_that_does_not_admit_none__When_json_schema_generated__Then_not_nullable_error_naming_the_schema_type_it_got(
        self,
    ):
        schema_type = TypeAdapter(_NonNullValue).core_schema["type"]

        with pytest.raises(NotNullableSchemaError, match=rf"\b{schema_type}\b"):
            _ = _PayloadWithoutNone.model_json_schema()
