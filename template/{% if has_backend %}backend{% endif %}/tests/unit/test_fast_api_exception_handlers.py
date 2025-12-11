from uuid import uuid4

import pytest
from backend_api import fast_api_exception_handlers
from backend_api.app_def import HealthcheckResponse
from backend_api.app_def import app
from fastapi.testclient import TestClient
from httpx import codes
from pytest_mock import MockerFixture


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
        response = self.client.get("/api/healthcheck?prepend_v=not_a_bool")

        self.spied_uuid_generator.assert_called_once()
        expected_uuid = str(self.spied_uuid_generator.spy_return)
        assert response.status_code == codes.UNPROCESSABLE_ENTITY
        assert response.headers["Content-Type"] == "application/problem+json"
        assert "Access-Control-Allow-Origin" in response.headers
        assert "Access-Control-Allow-Credentials" in response.headers

        response_json = response.json()
        assert response_json["type"] == "about:blank"
        assert response_json["title"] == "Validation Error"
        assert response_json["status"] == codes.UNPROCESSABLE_ENTITY
        assert "prepend_v" in response_json["detail"]
        assert "valid boolean" in response_json["detail"]
        assert response_json["instance"] == f"urn:uuid:{expected_uuid}"
        self.spied_logger_warning.assert_called_once()
        log_call_args = self.spied_logger_warning.call_args[0]
        log_message = log_call_args[0]
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
        response_json = response.json()
        assert response_json["type"] == "about:blank"
        assert response_json["title"] == "HTTP Error"
        assert response_json["status"] == codes.METHOD_NOT_ALLOWED
        assert response_json["detail"] == "Method Not Allowed"
        assert response_json["errorType"] == "HTTPException"
        assert response_json["instance"] == f"urn:uuid:{expected_uuid}"
        self.spied_logger_warning.assert_called_once()
        log_call_args = self.spied_logger_warning.call_args[0]
        log_message = log_call_args[0]
        assert expected_uuid in log_message
        assert "DELETE" in log_message
        assert expected_route in log_message

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
        response_json = response.json()
        assert response_json["type"] == "about:blank"
        assert response_json["title"] == "Internal Server Error"
        assert response_json["status"] == codes.INTERNAL_SERVER_ERROR
        assert expected_error_message in response_json["detail"]
        assert response_json["errorType"] == expected_error.__class__.__name__
        assert response_json["instance"] == f"urn:uuid:{expected_uuid}"
        self.spied_logger_error.assert_called_once()
        log_call_args = self.spied_logger_error.call_args[0]
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = log_call_args[0]
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
        response_json = response.json()
        assert response_json["type"] == "about:blank"
        assert response_json["title"] == "Internal Server Error"
        assert response_json["status"] == codes.INTERNAL_SERVER_ERROR
        assert response_json["detail"] == "An unexpected error occurred."
        assert response_json["errorType"] == expected_error.__class__.__name__
        assert response_json["instance"] == f"urn:uuid:{expected_uuid}"
        self.spied_logger_error.assert_called_once()
        log_call_args = self.spied_logger_error.call_args[0]
        log_call_kwargs = self.spied_logger_error.call_args[1]
        log_message = log_call_args[0]
        log_stack_trace = str(log_call_kwargs["exc_info"])
        assert expected_uuid in log_message
        assert "GET" in log_message
        assert expected_route in log_message
        assert expected_error_message in log_stack_trace
