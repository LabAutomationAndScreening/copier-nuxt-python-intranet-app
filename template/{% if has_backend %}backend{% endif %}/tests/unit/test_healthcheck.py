import time

from backend_api import app_def
from backend_api.app_def import app
from fastapi.testclient import TestClient
from httpx import codes
from pytest_mock import MockerFixture


def test_Given_healthy__When_healthcheck__Then_version_in_response():
    client = TestClient(app)

    response = client.get("/api/healthcheck")

    assert response.status_code == 200  # noqa: PLR2004 # this is the standard HTTP status code for OK
    response_json = response.json()
    assert "version" in response_json
    actual_version = response_json["version"]

    assert len(actual_version) > 2  # noqa: PLR2004 # just asserting there's some content that isn't just the period
    assert "." in actual_version


def test_When_swagger_route_called__Then_rendered():
    client = TestClient(app)

    response = client.get("/api-docs")

    assert response.status_code == codes.OK
    assert "Swagger UI" in response.text


def test_When_shutdown_route_called__Then_system_exit(mocker: MockerFixture):
    client = TestClient(app)
    mocked_os_exit = mocker.patch.object(app_def.os, "_exit", autospec=True)

    response = client.get("/api/shutdown")

    assert response.status_code == codes.OK

    for _ in range(1000):  # wait for the thread to finish
        if mocked_os_exit.call_count > 0:
            break
        time.sleep(0.001)
    mocked_os_exit.assert_called_once_with(0)
