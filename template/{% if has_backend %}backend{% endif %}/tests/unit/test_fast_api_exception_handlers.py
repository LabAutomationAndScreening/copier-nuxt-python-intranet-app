import json
import logging
import random
import re
from collections.abc import Callable
from typing import NoReturn
from uuid import uuid4

import pytest
from backend_api import fast_api_exception_handlers
from backend_api.app_def import HealthcheckResponse
from backend_api.app_def import app
from backend_api.fast_api_exception_handlers import ProblemDetails
from fastapi import HTTPException
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from httpx import codes
from pytest_mock import MockerFixture

from .spy_helpers import logged_message


def _random_error_status_code() -> codes:
    return random.choice((codes.BAD_REQUEST, codes.FORBIDDEN, codes.CONFLICT, codes.SERVICE_UNAVAILABLE))


def _random_client_error_status_code() -> codes:
    return random.choice((codes.BAD_REQUEST, codes.FORBIDDEN, codes.NOT_FOUND, codes.CONFLICT))


def _random_server_error_status_code_above_500() -> codes:
    return random.choice((codes.BAD_GATEWAY, codes.SERVICE_UNAVAILABLE, codes.GATEWAY_TIMEOUT))


def _only_handler_log_record(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    records = [record for record in caplog.records if record.name == fast_api_exception_handlers.__name__]
    assert len(records) == 1
    return records[0]


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

    def test_Given_malformed_input_to_api_route__Then_uuid_in_log_and_response_and_response_contains_details_and_cors_headers(
        self,
    ):
        response = self.client.get("/api/healthcheck?prependV=not_a_bool")

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == codes.UNPROCESSABLE_ENTITY
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers

        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Validation Error"
        assert problem.status == codes.UNPROCESSABLE_ENTITY
        assert "prependV" in problem.detail
        assert "valid boolean" in problem.detail
        assert problem.instance == f"urn:uuid:{expected_uuid}"
        self.spied_logger_warning.assert_called_once()
        log_message = logged_message(self.spied_logger_warning)
        assert expected_uuid in log_message
        assert "GET" in log_message
        assert "/api/healthcheck" in log_message

    def test_Given_calling_route_that_triggers_http_error__Then_uuid_in_log_and_response_and_response_contains_details_and_cors_headers(
        self,
    ):
        expected_route = "/api/healthcheck"
        response = self.client.delete(expected_route)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == codes.METHOD_NOT_ALLOWED
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "HTTP Error"
        assert problem.status == codes.METHOD_NOT_ALLOWED
        assert problem.detail == "Method Not Allowed"
        assert problem.error_type == "HTTPException"
        assert problem.instance == f"urn:uuid:{expected_uuid}"
        self.spied_logger_warning.assert_called_once()
        log_message = logged_message(self.spied_logger_warning)
        assert expected_uuid in log_message
        assert "DELETE" in log_message
        assert expected_route in log_message

    def test_Given_route_raises_http_exception_with_a_non_string_detail__Then_detail_is_json_encoded(self):
        expected_status_code = _random_error_status_code()
        expected_detail = {"field": str(uuid4()), "values": [random.randint(1, 100), random.randint(1, 100)]}
        _ = self.mocker.patch.object(
            HealthcheckResponse,
            "__init__",
            side_effect=HTTPException(status_code=expected_status_code, detail=expected_detail),
        )

        response = self.client.get("/api/healthcheck")

        problem = ProblemDetails.model_validate(response.json())

        assert response.status_code == expected_status_code
        assert json.loads(problem.detail) == expected_detail

    def test_Given_route_mocked_to_error_and_error_details_should_be_displayed__Then_uuid_in_log_and_response__and_details_in_response_and_log__and_cors_headers_in_response(
        self,
    ):
        expected_route = "/api/healthcheck"
        expected_error_message = str(uuid4())
        _ = self.mocker.patch.object(
            fast_api_exception_handlers,
            fast_api_exception_handlers.should_show_error_details.__name__,
            autospec=True,
            return_value=True,
        )
        expected_error = RuntimeError(expected_error_message)
        _ = self.mocker.patch.object(
            HealthcheckResponse,
            "__init__",
            side_effect=expected_error,
        )

        response = self.client.get(expected_route)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == codes.INTERNAL_SERVER_ERROR
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Internal Server Error"
        assert problem.status == codes.INTERNAL_SERVER_ERROR
        assert expected_error_message in problem.detail
        assert problem.error_type == expected_error.__class__.__name__
        assert problem.instance == f"urn:uuid:{expected_uuid}"
        self.spied_logger_error.assert_called_once()
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = logged_message(self.spied_logger_error)
        log_stack_trace = str(log_call_kwargs["exc_info"])
        assert expected_uuid in log_message
        assert "GET" in log_message
        assert expected_route in log_message
        assert expected_error_message in log_stack_trace

    def test_Given_route_mocked_to_error_and_error_details_should_not_be_displayed__Then_uuid_in_log_and_response__and_no_details_in_response_but_details_in_log(
        self,
    ):
        expected_route = "/api/healthcheck"
        expected_error_message = str(uuid4())
        _ = self.mocker.patch.object(
            fast_api_exception_handlers,
            fast_api_exception_handlers.should_show_error_details.__name__,
            autospec=True,
            return_value=False,
        )
        expected_error = ValueError(expected_error_message)  # arbitrary error type
        _ = self.mocker.patch.object(
            HealthcheckResponse,
            "__init__",
            side_effect=expected_error,
        )

        response = self.client.get(expected_route)

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == codes.INTERNAL_SERVER_ERROR
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers
        problem = ProblemDetails.model_validate(response.json())
        assert problem.type == "about:blank"
        assert problem.title == "Internal Server Error"
        assert problem.status == codes.INTERNAL_SERVER_ERROR
        assert problem.detail == "An unexpected error occurred."
        assert problem.error_type == expected_error.__class__.__name__
        assert problem.instance == f"urn:uuid:{expected_uuid}"
        self.spied_logger_error.assert_called_once()
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = logged_message(self.spied_logger_error)
        log_stack_trace = str(log_call_kwargs["exc_info"])
        assert expected_uuid in log_message
        assert "GET" in log_message
        assert expected_route in log_message
        assert expected_error_message in log_stack_trace


class TestGivenRouteMockedToRaiseHttpExceptionWhenRequested:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture):
        self.mocker = mocker
        self.caplog = caplog
        self.client = TestClient(
            app,
            raise_server_exceptions=False,  # this makes sure our exception handlers get exercised
        )
        self.spied_uuid_generator = mocker.spy(fast_api_exception_handlers, fast_api_exception_handlers.uuid7.__name__)

    # _make_route_raise patches HealthcheckResponse, so the tests must request the route that builds it
    _ROUTE = "/api/healthcheck"

    def _make_route_raise(self, side_effect: Exception | Callable[..., NoReturn]) -> None:
        _ = self.mocker.patch.object(
            HealthcheckResponse, HealthcheckResponse.__init__.__name__, side_effect=side_effect
        )

    @pytest.mark.parametrize(
        "expected_status_code",
        [
            pytest.param(_random_client_error_status_code(), id="arbitrary-4xx"),
            pytest.param(status.HTTP_500_INTERNAL_SERVER_ERROR - 1, id="highest-4xx"),
        ],
    )
    def test_Given_client_error_status__Then_one_warning_line_without_traceback_naming_request_detail_and_trace_id__and_response_unchanged(
        self, expected_status_code: int
    ):
        expected_detail = str(uuid4())
        self._make_route_raise(HTTPException(status_code=expected_status_code, detail=expected_detail))

        response = self.client.get(self._ROUTE)

        expected_trace_id = f"urn:uuid:{self.spied_uuid_generator.spy_return}"
        problem = ProblemDetails.model_validate(response.json())
        record = _only_handler_log_record(self.caplog)
        message = record.getMessage()

        self.spied_uuid_generator.assert_called_once()
        assert record.levelno == logging.WARNING
        assert record.exc_info is None
        assert re.search(rf"\b{expected_status_code}\b", message) is not None
        assert "GET" in message
        assert self._ROUTE in message
        assert message.endswith(f"{expected_status_code}: {expected_detail}")
        assert expected_trace_id in message
        assert response.status_code == expected_status_code
        assert problem == ProblemDetails(
            type="about:blank",
            title="HTTP Error",
            status=expected_status_code,
            detail=expected_detail,
            instance=expected_trace_id,
            error_type=HTTPException.__name__,
        )

    @pytest.mark.parametrize(
        "expected_status_code",
        [
            pytest.param(status.HTTP_500_INTERNAL_SERVER_ERROR, id="lowest-5xx"),
            pytest.param(_random_server_error_status_code_above_500(), id="arbitrary-5xx"),
        ],
    )
    def test_Given_server_error_status__Then_warning_logged_with_traceback_and_trace_id__and_response_unchanged(
        self, expected_status_code: int
    ):
        expected_detail = str(uuid4())
        expected_error = HTTPException(status_code=expected_status_code, detail=expected_detail)
        self._make_route_raise(expected_error)

        response = self.client.get(self._ROUTE)

        expected_trace_id = f"urn:uuid:{self.spied_uuid_generator.spy_return}"
        problem = ProblemDetails.model_validate(response.json())
        record = _only_handler_log_record(self.caplog)

        assert record.levelno == logging.WARNING
        assert record.exc_info is not None
        assert record.exc_info[1] is expected_error
        assert expected_trace_id in record.getMessage()
        assert response.status_code == expected_status_code
        assert problem.detail == expected_detail

    def test_Given_client_error_status_and_detail_is_not_a_string__Then_one_warning_line_with_json_encoded_detail(
        self,
    ):
        expected_detail = {"field": str(uuid4()), "values": [random.randint(1, 100), random.randint(1, 100)]}
        self._make_route_raise(HTTPException(status_code=_random_client_error_status_code(), detail=expected_detail))

        _ = self.client.get(self._ROUTE)

        record = _only_handler_log_record(self.caplog)

        assert record.exc_info is None
        assert json.dumps(expected_detail) in record.getMessage()

    def test_Given_client_error_status_and_detail_contains_line_breaks_and_control_characters__Then_one_warning_line_with_them_escaped__and_response_detail_unchanged(
        self,
    ):
        head, middle, tail = str(uuid4()), str(uuid4()), str(uuid4())
        expected_detail = f"{head}\r{middle}\n{tail}\x1b\u2028\x85\x00"
        self._make_route_raise(HTTPException(status_code=_random_client_error_status_code(), detail=expected_detail))

        response = self.client.get(self._ROUTE)

        problem = ProblemDetails.model_validate(response.json())
        message = _only_handler_log_record(self.caplog).getMessage()

        assert f"{head}\\r{middle}\\n{tail}\\x1b\\u2028\\x85\\x00" in message
        assert len(message.splitlines()) == 1
        assert not any(character in message for character in "\r\n\x1b\u2028\x85\x00")
        assert problem.detail == expected_detail

    def test_Given_client_error_status_and_detail_of_line_breaks_that_escape_past_the_log_limit__Then_escaped_logged_detail_truncated__and_response_detail_complete(
        self,
    ):
        expected_detail = "\n" * random.randint(1500, 2000)
        self._make_route_raise(HTTPException(status_code=_random_client_error_status_code(), detail=expected_detail))

        response = self.client.get(self._ROUTE)

        problem = ProblemDetails.model_validate(response.json())
        message = _only_handler_log_record(self.caplog).getMessage()

        assert "\\n" in message
        assert message.endswith("\\n...(truncated)")
        assert expected_detail.replace("\n", "\\n") not in message
        assert problem.detail == expected_detail

    @pytest.mark.parametrize(
        ("detail_length", "expect_truncated"),
        [(2000, False), (2001, True)],
    )
    def test_Given_client_error_status_and_detail_at_the_log_limit__Then_only_longer_detail_truncated(
        self, detail_length: int, expect_truncated: bool
    ):
        expected_detail = "a" * detail_length
        self._make_route_raise(HTTPException(status_code=_random_client_error_status_code(), detail=expected_detail))

        _ = self.client.get(self._ROUTE)

        message = _only_handler_log_record(self.caplog).getMessage()

        assert message.endswith(f": {expected_detail}") is not expect_truncated
        assert ("(truncated)" in message) is expect_truncated

    def _make_route_raise_client_error_from(self, cause: Exception, *, detail: str) -> None:
        def raise_from_cause(*_: object, **__: object) -> NoReturn:
            raise HTTPException(status_code=_random_client_error_status_code(), detail=detail) from cause

        self._make_route_raise(raise_from_cause)

    def test_Given_client_error_raised_from_another_exception__Then_one_warning_line_naming_the_cause_without_traceback(
        self,
    ):
        expected_detail = str(uuid4())
        expected_cause = ValueError(str(uuid4()))
        self._make_route_raise_client_error_from(expected_cause, detail=expected_detail)

        _ = self.client.get(self._ROUTE)

        record = _only_handler_log_record(self.caplog)
        message = record.getMessage()

        assert record.exc_info is None
        assert expected_detail in message
        assert f"(caused by {expected_cause!r})" in message

    def test_Given_client_error_raised_from_a_cause_whose_repr_contains_control_characters__Then_one_warning_line_with_them_escaped_in_the_cause(
        self,
    ):
        cause_head, cause_tail = str(uuid4()), str(uuid4())

        class _ReprWithControlCharacters:
            def __repr__(self) -> str:
                return f"{cause_head}\n{cause_tail}\x1b"

        self._make_route_raise_client_error_from(ValueError(_ReprWithControlCharacters()), detail=str(uuid4()))

        _ = self.client.get(self._ROUTE)

        message = _only_handler_log_record(self.caplog).getMessage()

        assert f"(caused by ValueError({cause_head}\\n{cause_tail}\\x1b))" in message
        assert len(message.splitlines()) == 1
        assert "\x1b" not in message


class TestValidationErrorLogging:
    @pytest.fixture(autouse=True)
    def _setup(self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture):
        self.caplog = caplog
        self.client = TestClient(
            app,
            raise_server_exceptions=False,  # this makes sure our exception handlers get exercised
        )
        self.spied_uuid_generator = mocker.spy(fast_api_exception_handlers, fast_api_exception_handlers.uuid7.__name__)

    def test_When_requesting_with_a_malformed_query_parameter__Then_one_warning_line_without_traceback_and_with_escaped_line_breaks__and_response_unchanged(
        self,
    ):
        expected_route = "/api/healthcheck"

        response = self.client.get(f"{expected_route}?prependV=not_a_bool")

        expected_trace_id = f"urn:uuid:{self.spied_uuid_generator.spy_return}"
        problem = ProblemDetails.model_validate(response.json())
        record = _only_handler_log_record(self.caplog)
        message = record.getMessage()

        self.spied_uuid_generator.assert_called_once()
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert record.levelno == logging.WARNING
        assert record.exc_info is None
        assert message.startswith(
            f"{RequestValidationError.__name__} on GET {expected_route} [{expected_trace_id}] "
            f"{status.HTTP_422_UNPROCESSABLE_CONTENT}: "
        )
        assert "prependV" in message
        assert "\r" not in message
        assert "\n" not in message
        assert "\n" in problem.detail
        assert problem.title == "Validation Error"
        assert problem.status == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert problem.instance == expected_trace_id
        assert problem.error_type == RequestValidationError.__name__
