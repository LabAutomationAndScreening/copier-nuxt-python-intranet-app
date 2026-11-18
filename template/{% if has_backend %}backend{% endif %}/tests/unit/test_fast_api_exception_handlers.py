import json
import random
from collections.abc import Callable
from typing import NoReturn
from uuid import uuid4

import pytest
import structlog
from backend_api import fast_api_exception_handlers
from backend_api.app_def import HealthcheckResponse
from backend_api.app_def import app
from backend_api.camel_case_model import CamelCaseModel
from backend_api.fast_api_exception_handlers import TRACE_ID_LOG_FIELD
from backend_api.fast_api_exception_handlers import WHOLE_BODY_LOCATION_LABEL
from backend_api.fast_api_exception_handlers import WHOLE_BODY_POINTER
from backend_api.fast_api_exception_handlers import ParameterLocation
from backend_api.fast_api_exception_handlers import ProblemDetails
from backend_api.fast_api_exception_handlers import ValidationIssue
from backend_api.fast_api_exception_handlers import ValidationProblemDetails
from backend_api.fast_api_exception_handlers import register_exception_handlers
from backend_api.openapi_problem_responses import PROBLEM_JSON_MEDIA_TYPE
from backend_api.openapi_problem_responses import ProblemExample
from backend_api.openapi_problem_responses import problem_response
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from pydantic import Field
from pytest_mock import MockerFixture

from .spy_helpers import logged_message


def _random_error_status_code() -> int:
    return random.choice(
        (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_409_CONFLICT,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    )


# The route is arbitrary in every respect: any route that takes a boolean query parameter would do, and this is one
# every app from the template has. So is everything else the tests use about it: its path, its method, the boolean
# parameter they send, and the method it does not answer. A test that needs the route to fail makes its response
# model's constructor raise.
_ARBITRARY_ROUTE = "/api/healthcheck"
_ARBITRARY_ROUTE_METHOD = "GET"
_ARBITRARY_ROUTE_BOOLEAN_QUERY_PARAMETER = "prependV"
_METHOD_THE_ARBITRARY_ROUTE_DOES_NOT_ANSWER = "DELETE"


def _make_the_arbitrary_route_raise(mocker: MockerFixture, side_effect: Exception | Callable[..., NoReturn]) -> None:
    _ = mocker.patch.object(HealthcheckResponse, HealthcheckResponse.__init__.__name__, side_effect=side_effect)


class _BodyPayload(CamelCaseModel):
    item_count: int
    item_sizes: list[int] = Field(default_factory=list)
    item_counts_by_label: dict[str, int] = Field(default_factory=dict)


# The path and method are arbitrary: any route that takes a JSON body works, and the app's own routes have none.
_BODY_ROUTE = "/items"


def _wire_name(field_name: str) -> str:
    alias = _BodyPayload.model_fields[field_name].alias
    assert alias is not None  # CamelCaseModel's alias generator gives every field one
    return alias


def _validation_issue_wire_name(field_name: str) -> str:
    alias = ValidationIssue.model_fields[field_name].alias
    assert alias is not None  # CamelCaseModel's alias generator gives every field one
    return alias


def _client_for_an_app_with_a_body_route() -> TestClient:
    body_app = FastAPI()
    body_app.add_middleware(CORSMiddleware, allow_origins=["*"])

    @body_app.post(_BODY_ROUTE)
    def create_item(payload: _BodyPayload) -> None:
        pass

    register_exception_handlers(body_app)
    return TestClient(body_app, raise_server_exceptions=False)


def test_When_openapi_schema_generated__Then_a_route_with_parameters_documents_its_422_as_validation_problem_details():
    app.openapi_schema = None  # reset the cache other tests populate

    schema = app.openapi()

    responses = schema["paths"][_ARBITRARY_ROUTE][_ARBITRARY_ROUTE_METHOD.lower()]["responses"]
    schemas = schema["components"]["schemas"]

    assert responses[str(status.HTTP_422_UNPROCESSABLE_CONTENT)]["content"] == {
        PROBLEM_JSON_MEDIA_TYPE: {"schema": {"$ref": f"#/components/schemas/{ValidationProblemDetails.__name__}"}}
    }
    assert ValidationProblemDetails.__name__ in schemas


# Arbitrary in every respect: any path, and any method (the tests use GET), works.
_ROUTE_DECLARING_ITS_OWN_422 = "/declared"
_ROUTE_LEAVING_ITS_422_TO_FASTAPI = "/undeclared"


def _app_with_a_route_leaving_its_422_to_fastapi() -> FastAPI:
    """Build an app whose one route validates a query parameter without declaring a 422, as every app's health check does.

    That route is what makes FastAPI generate its own validation schemas, which the schema generator removes.
    """
    route_app = FastAPI()
    route_app.add_middleware(CORSMiddleware, allow_origins=["*"])

    @route_app.get(_ROUTE_LEAVING_ITS_422_TO_FASTAPI)
    def undeclared(count: int) -> None:
        pass

    return route_app


def test_Given_a_route_documenting_its_own_422__When_openapi_schema_generated__Then_its_description_and_examples_are_kept():
    description = str(uuid4())
    example_name = str(uuid4())
    route_app = _app_with_a_route_leaving_its_422_to_fastapi()

    @route_app.get(
        _ROUTE_DECLARING_ITS_OWN_422,
        responses=problem_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            description,
            instance=_ROUTE_DECLARING_ITS_OWN_422,
            examples={example_name: ProblemExample(summary=str(uuid4()), detail=str(uuid4()))},
        ),
    )
    def declared(count: int) -> None:
        pass

    register_exception_handlers(route_app)

    schema = route_app.openapi()

    unprocessable_content = schema["paths"][_ROUTE_DECLARING_ITS_OWN_422]["get"]["responses"][
        str(status.HTTP_422_UNPROCESSABLE_CONTENT)
    ]

    assert unprocessable_content["description"] == description
    assert list(unprocessable_content["content"][PROBLEM_JSON_MEDIA_TYPE]["examples"]) == [example_name]


def test_Given_a_route_declaring_a_422_with_no_content__When_openapi_schema_generated__Then_its_422_documents_validation_problem_details():
    route_app = _app_with_a_route_leaving_its_422_to_fastapi()

    @route_app.get(
        _ROUTE_DECLARING_ITS_OWN_422, responses={status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": str(uuid4())}}
    )
    def declared(count: int) -> None:
        pass

    register_exception_handlers(route_app)

    schema = route_app.openapi()

    unprocessable_content = schema["paths"][_ROUTE_DECLARING_ITS_OWN_422]["get"]["responses"][
        str(status.HTTP_422_UNPROCESSABLE_CONTENT)
    ]

    assert unprocessable_content["content"] == {
        PROBLEM_JSON_MEDIA_TYPE: {"schema": {"$ref": f"#/components/schemas/{ValidationProblemDetails.__name__}"}}
    }


class TestGivenARouteTakingAJsonBody:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.client = _client_for_an_app_with_a_body_route()

    def test_When_a_body_field_fails_validation__Then_the_issue_points_at_the_field_by_its_wire_name__and_detail_names_only_that_field(
        self,
    ):
        wire_name = _wire_name("item_count")

        response = self.client.post(_BODY_ROUTE, json={wire_name: str(uuid4())})

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert len(problem.errors) == 1
        issue = problem.errors[0]
        assert issue.pointer == f"#/{wire_name}"
        assert issue.parameter is None
        assert issue.location is None
        assert issue.code == "int_parsing"
        assert problem.detail == f"{wire_name}: {issue.detail}"

    def test_When_a_body_field_fails_validation__Then_the_issue_sends_its_pointer_and_leaves_out_the_parameter_fields(
        self,
    ):
        response = self.client.post(_BODY_ROUTE, json={_wire_name("item_count"): str(uuid4())})

        issue_keys = set(response.json()["errors"][0])

        assert _validation_issue_wire_name("pointer") in issue_keys
        assert _validation_issue_wire_name("parameter") not in issue_keys
        assert _validation_issue_wire_name("location") not in issue_keys

    def test_When_a_body_value_under_a_key_holding_json_pointer_and_uri_special_characters_fails_validation__Then_the_issue_points_at_it_escaped_per_rfc_6901_and_percent_encoded(
        self,
    ):
        count_wire_name = _wire_name("item_count")
        counts_wire_name = _wire_name("item_counts_by_label")
        # "/" and "~" are the characters RFC 6901 escapes (as ~1 and ~0); a space is one a URI fragment percent-encodes
        label = "a/b~c d"

        response = self.client.post(
            _BODY_ROUTE, json={count_wire_name: random.randint(1, 100), counts_wire_name: {label: str(uuid4())}}
        )

        problem = ValidationProblemDetails.model_validate(response.json())

        assert len(problem.errors) == 1
        assert problem.errors[0].pointer == f"#/{counts_wire_name}/a~1b~0c%20d"

    def test_When_one_item_of_a_body_list_fails_validation__Then_the_issue_points_at_that_item_by_its_index(self):
        count_wire_name = _wire_name("item_count")
        sizes_wire_name = _wire_name("item_sizes")
        sizes: list[int | str] = [random.randint(1, 100) for _ in range(random.randint(1, 5))]
        invalid_index = random.randint(0, len(sizes))
        sizes.insert(invalid_index, str(uuid4()))

        response = self.client.post(_BODY_ROUTE, json={count_wire_name: random.randint(1, 100), sizes_wire_name: sizes})

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert len(problem.errors) == 1
        assert problem.errors[0].pointer == f"#/{sizes_wire_name}/{invalid_index}"

    def test_When_several_body_values_fail_validation__Then_detail_names_where_the_first_is_and_counts_the_rest(
        self,
    ):
        count_wire_name = _wire_name("item_count")
        sizes_wire_name = _wire_name("item_sizes")
        further_invalid_count = random.randint(1, 3)
        invalid_sizes = [str(uuid4()) for _ in range(further_invalid_count)]

        response = self.client.post(_BODY_ROUTE, json={count_wire_name: str(uuid4()), sizes_wire_name: invalid_sizes})

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert len(problem.errors) == 1 + further_invalid_count
        first_issue = problem.errors[0]
        assert first_issue.pointer == f"#/{count_wire_name}"
        assert problem.detail == f"{count_wire_name}: {first_issue.detail} (and {further_invalid_count} more)"

    def test_When_a_required_body_is_missing__Then_422_with_the_issue_pointing_at_the_whole_body__and_detail_naming_the_request_body(
        self,
    ):
        response = self.client.post(_BODY_ROUTE)

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert len(problem.errors) == 1
        issue = problem.errors[0]
        assert issue.pointer == WHOLE_BODY_POINTER
        assert issue.parameter is None
        assert issue.location is None
        assert issue.code == "missing"
        assert problem.detail == f"{WHOLE_BODY_LOCATION_LABEL}: {issue.detail}"

    def test_When_the_body_is_not_valid_json__Then_422_with_the_issue_pointing_at_the_whole_body(self):
        unquoted_text = str(uuid4())

        response = self.client.post(_BODY_ROUTE, content=unquoted_text, headers={"Content-Type": "application/json"})

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert len(problem.errors) == 1
        issue = problem.errors[0]
        assert issue.pointer == WHOLE_BODY_POINTER
        assert issue.code == "json_invalid"


class TestExceptionHandlers:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture):
        self.mocker = mocker
        self.client = TestClient(
            app,
            raise_server_exceptions=False,  # this makes sure our exception handlers get exercised
        )
        self.spied_logger_error = mocker.spy(fast_api_exception_handlers.logger, "error")
        self.spied_uuid_generator = mocker.spy(fast_api_exception_handlers, "uuid7")
        self.spied_logger_warning = mocker.spy(fast_api_exception_handlers.logger, "warning")

    def test_Given_malformed_input_to_api_route__Then_uuid_in_log_and_response_and_response_contains_details__and_names_the_invalid_query_parameter__and_cors_headers(
        self,
    ):
        response = self.client.request(
            _ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE, params={_ARBITRARY_ROUTE_BOOLEAN_QUERY_PARAMETER: str(uuid4())}
        )

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers

        problem = ValidationProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Validation Error"
        assert problem.status == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert problem.instance == _ARBITRARY_ROUTE
        assert len(problem.errors) == 1
        issue = problem.errors[0]
        assert issue.parameter == _ARBITRARY_ROUTE_BOOLEAN_QUERY_PARAMETER
        assert issue.location == ParameterLocation.QUERY
        assert issue.code == "bool_parsing"
        assert "valid boolean" in issue.detail
        assert problem.detail == f"{issue.parameter}: {issue.detail}"
        self.spied_logger_warning.assert_called_once()
        log_message = logged_message(self.spied_logger_warning)
        assert expected_uuid in log_message
        assert _ARBITRARY_ROUTE_METHOD in log_message
        assert _ARBITRARY_ROUTE in log_message

    def test_Given_malformed_input_to_api_route__Then_the_issue_sends_its_parameter_fields_and_leaves_out_the_pointer(
        self,
    ):
        response = self.client.request(
            _ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE, params={_ARBITRARY_ROUTE_BOOLEAN_QUERY_PARAMETER: str(uuid4())}
        )

        issue_keys = set(response.json()["errors"][0])

        assert _validation_issue_wire_name("parameter") in issue_keys
        assert _validation_issue_wire_name("location") in issue_keys
        assert _validation_issue_wire_name("pointer") not in issue_keys

    def test_Given_calling_route_that_triggers_http_error__Then_uuid_in_log_and_response_and_response_contains_details_and_cors_headers(
        self,
    ):
        response = self.client.request(_METHOD_THE_ARBITRARY_ROUTE_DOES_NOT_ANSWER, _ARBITRARY_ROUTE)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "HTTP Error"
        assert problem.status == status.HTTP_405_METHOD_NOT_ALLOWED
        assert problem.detail == "Method Not Allowed"
        assert problem.error_type == "HTTPException"
        assert problem.instance == _ARBITRARY_ROUTE
        assert problem.trace_id == expected_uuid
        self.spied_logger_warning.assert_called_once()
        log_message = logged_message(self.spied_logger_warning)
        assert expected_uuid in log_message
        assert _METHOD_THE_ARBITRARY_ROUTE_DOES_NOT_ANSWER in log_message
        assert _ARBITRARY_ROUTE in log_message

    def test_Given_route_raises_http_exception_with_a_non_string_detail__Then_detail_is_json_encoded(self):
        expected_status_code = _random_error_status_code()
        expected_detail = {"field": str(uuid4()), "values": [random.randint(1, 100), random.randint(1, 100)]}
        _make_the_arbitrary_route_raise(
            self.mocker, HTTPException(status_code=expected_status_code, detail=expected_detail)
        )

        response = self.client.request(_ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE)

        problem = ProblemDetails.model_validate(response.json())

        assert response.status_code == expected_status_code
        assert json.loads(problem.detail) == expected_detail

    def test_Given_route_mocked_to_raise_a_422_http_exception__Then_the_problem_lists_no_validation_issues(self):
        expected_detail = str(uuid4())
        _make_the_arbitrary_route_raise(
            self.mocker, HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=expected_detail)
        )

        response = self.client.request(_ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE)

        status_code = response.status_code
        body = response.json()

        assert status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        problem = ValidationProblemDetails.model_validate(body)
        assert problem.detail == expected_detail
        assert problem.errors == []

    def test_Given_route_mocked_to_read_its_log_context_and_then_error__Then_its_log_context_carries_the_trace_id_the_problem_reports(
        self,
    ):
        log_context_inside_the_route: dict[str, object] = {}

        def read_log_context_then_raise(*_: object, **__: object) -> NoReturn:
            log_context_inside_the_route.update(structlog.contextvars.get_contextvars())
            raise RuntimeError(str(uuid4()))

        _make_the_arbitrary_route_raise(self.mocker, read_log_context_then_raise)

        response = self.client.request(_ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE)

        problem = ProblemDetails.model_validate(response.json())

        assert problem.trace_id != ""
        assert log_context_inside_the_route.get(TRACE_ID_LOG_FIELD) == problem.trace_id

    def test_Given_route_mocked_to_error_and_error_details_should_be_displayed__Then_uuid_in_log_and_response__and_details_in_response_and_log__and_cors_headers_in_response(
        self,
    ):
        expected_error_message = str(uuid4())
        _ = self.mocker.patch.object(
            fast_api_exception_handlers,
            fast_api_exception_handlers.should_show_error_details.__name__,
            autospec=True,
            return_value=True,
        )
        expected_error = RuntimeError(expected_error_message)
        _make_the_arbitrary_route_raise(self.mocker, expected_error)

        response = self.client.request(_ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Internal Server Error"
        assert problem.status == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert expected_error_message in problem.detail
        assert problem.error_type == expected_error.__class__.__name__
        assert problem.instance == _ARBITRARY_ROUTE
        self.spied_logger_error.assert_called_once()
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = logged_message(self.spied_logger_error)
        log_stack_trace = str(log_call_kwargs["exc_info"])
        assert expected_uuid in log_message
        assert _ARBITRARY_ROUTE_METHOD in log_message
        assert _ARBITRARY_ROUTE in log_message
        assert expected_error_message in log_stack_trace

    def test_Given_route_mocked_to_error_and_error_details_should_not_be_displayed__Then_uuid_in_log_and_response__and_no_details_in_response_but_details_in_log(
        self,
    ):
        expected_error_message = str(uuid4())
        _ = self.mocker.patch.object(
            fast_api_exception_handlers,
            fast_api_exception_handlers.should_show_error_details.__name__,
            autospec=True,
            return_value=False,
        )
        expected_error = ValueError(expected_error_message)  # arbitrary error type
        _make_the_arbitrary_route_raise(self.mocker, expected_error)

        response = self.client.request(_ARBITRARY_ROUTE_METHOD, _ARBITRARY_ROUTE)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Internal Server Error"
        assert problem.status == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert problem.detail == "An unexpected error occurred."
        assert problem.error_type == expected_error.__class__.__name__
        assert problem.instance == _ARBITRARY_ROUTE
        self.spied_logger_error.assert_called_once()
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = logged_message(self.spied_logger_error)
        log_stack_trace = str(log_call_kwargs["exc_info"])
        assert expected_uuid in log_message
        assert _ARBITRARY_ROUTE_METHOD in log_message
        assert _ARBITRARY_ROUTE in log_message
        assert expected_error_message in log_stack_trace
