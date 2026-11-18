from uuid import uuid4

from backend_api.fast_api_exception_handlers import ValidationProblemDetails
from backend_api.openapi_problem_responses import PROBLEM_DETAILS_REF
from backend_api.openapi_problem_responses import PROBLEM_JSON_MEDIA_TYPE
from backend_api.openapi_problem_responses import ProblemExample
from backend_api.openapi_problem_responses import problem_response
from fastapi import status


def _random_instance() -> str:
    return f"/api/{uuid4()}"


def test_Given_status_and_description__Then_responses_entry_is_keyed_by_status_code() -> None:
    responses = problem_response(status.HTTP_404_NOT_FOUND, "Widget not found", instance=_random_instance())

    assert set(responses) == {status.HTTP_404_NOT_FOUND}
    assert responses[status.HTTP_404_NOT_FOUND]["description"] == "Widget not found"


def test_Given_status_and_description__Then_content_uses_problem_json_and_problem_details_ref() -> None:
    content = problem_response(status.HTTP_404_NOT_FOUND, "Widget not found", instance=_random_instance())[
        status.HTTP_404_NOT_FOUND
    ]["content"]

    assert set(content) == {PROBLEM_JSON_MEDIA_TYPE}
    assert content[PROBLEM_JSON_MEDIA_TYPE]["schema"] == {"$ref": PROBLEM_DETAILS_REF}


def test_Given_a_422_status__Then_content_documents_validation_problem_details_with_no_issues() -> None:
    description = str(uuid4())

    content = problem_response(status.HTTP_422_UNPROCESSABLE_CONTENT, description, instance=_random_instance())[
        status.HTTP_422_UNPROCESSABLE_CONTENT
    ]["content"][PROBLEM_JSON_MEDIA_TYPE]

    assert content["schema"] == {"$ref": f"#/components/schemas/{ValidationProblemDetails.__name__}"}
    assert content["example"]["detail"] == description
    assert content["example"]["errors"] == []


def test_Given_status_description_and_instance__Then_example_is_synthesized_from_them() -> None:
    instance = _random_instance()

    example = problem_response(status.HTTP_404_NOT_FOUND, "Widget not found", instance=instance)[
        status.HTTP_404_NOT_FOUND
    ]["content"][PROBLEM_JSON_MEDIA_TYPE]["example"]

    assert example["title"] == "Not Found"
    assert example["status"] == status.HTTP_404_NOT_FOUND
    assert example["detail"] == "Widget not found"
    assert example["instance"] == instance


def test_Given_named_examples__Then_content_carries_an_entry_per_name() -> None:
    examples = {
        "missing_widget": ProblemExample(summary=str(uuid4()), detail=str(uuid4())),
        "missing_bin": ProblemExample(summary=str(uuid4()), detail=str(uuid4())),
    }

    responses = problem_response(
        status.HTTP_404_NOT_FOUND, "Widget not found", instance=_random_instance(), examples=examples
    )

    content = responses[status.HTTP_404_NOT_FOUND]["content"][PROBLEM_JSON_MEDIA_TYPE]

    assert set(content["examples"]) == set(examples)
    assert content["examples"]["missing_widget"]["summary"] == examples["missing_widget"].summary
    assert content["examples"]["missing_bin"]["summary"] == examples["missing_bin"].summary


def test_Given_named_examples__Then_each_value_is_a_complete_problem_details_body() -> None:
    detail = str(uuid4())
    instance = _random_instance()

    responses = problem_response(
        status.HTTP_409_CONFLICT,
        "Widget conflicts with another widget",
        instance=instance,
        examples={"conflicting_widget": ProblemExample(summary=str(uuid4()), detail=detail)},
    )

    value = responses[status.HTTP_409_CONFLICT]["content"][PROBLEM_JSON_MEDIA_TYPE]["examples"]["conflicting_widget"][
        "value"
    ]

    assert value["title"] == "Conflict"
    assert value["status"] == status.HTTP_409_CONFLICT
    assert value["detail"] == detail
    assert value["instance"] == instance
