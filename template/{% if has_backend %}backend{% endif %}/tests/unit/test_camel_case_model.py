from backend_api.camel_case_model import CamelCaseModel
from pydantic import Field


class _Sample(CamelCaseModel):
    remote_url: str = Field(description="x")
    sparse_checkout_patterns: list[str] | None = None


def test_field_names_serialize_as_camel_case() -> None:
    schema = _Sample.model_json_schema()
    assert set(schema["properties"]) == {"remoteUrl", "sparseCheckoutPatterns"}


def test_titles_derive_from_snake_case_field_name_not_camel_alias() -> None:
    # Regression: with alias_generator=to_camel, pydantic derives `title` from the alias,
    # producing "Remoteurl" / "Sparsecheckoutpatterns" which breaks frontend code generation.
    props = _Sample.model_json_schema()["properties"]
    assert props["remoteUrl"]["title"] == "Remote Url"
    assert props["sparseCheckoutPatterns"]["title"] == "Sparse Checkout Patterns"
