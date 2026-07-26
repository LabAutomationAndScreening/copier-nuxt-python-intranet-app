from backend_api.openapi_problem_responses import PROBLEM_DETAILS_REF
from backend_api.openapi_problem_responses import PROBLEM_JSON_MEDIA_TYPE
from backend_api.openapi_problem_responses import problem_response
from httpx import codes


def test_Given_status_and_description__Then_responses_entry_is_keyed_by_status_code() -> None:
    responses = problem_response(codes.NOT_FOUND, "Widget not found")

    assert set(responses) == {codes.NOT_FOUND}
    assert responses[codes.NOT_FOUND]["description"] == "Widget not found"


def test_Given_status_and_description__Then_content_uses_problem_json_and_problem_details_ref() -> None:
    content = problem_response(codes.NOT_FOUND, "Widget not found")[codes.NOT_FOUND]["content"]

    assert set(content) == {PROBLEM_JSON_MEDIA_TYPE}
    assert content[PROBLEM_JSON_MEDIA_TYPE]["schema"] == {"$ref": PROBLEM_DETAILS_REF}


def test_Given_status_and_description__Then_example_is_synthesized_from_them() -> None:
    example = problem_response(codes.NOT_FOUND, "Widget not found")[codes.NOT_FOUND]["content"][
        PROBLEM_JSON_MEDIA_TYPE
    ]["example"]

    assert example["title"] == "Not Found"
    assert example["status"] == codes.NOT_FOUND
    assert example["detail"] == "Widget not found"
    assert example["instance"] == "about:blank"


def test_Given_explicit_instance__Then_example_points_at_it() -> None:
    example = problem_response(codes.NOT_FOUND, "Widget not found", instance="/api/widgets/7")[codes.NOT_FOUND][
        "content"
    ][PROBLEM_JSON_MEDIA_TYPE]["example"]

    assert example["instance"] == "/api/widgets/7"
