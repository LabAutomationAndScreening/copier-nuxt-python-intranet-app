import threading
from collections.abc import Iterator

import pytest
from backend_api import app_def
from backend_api import fast_api_exception_handlers
from backend_api.app_def import HealthcheckResponse
from backend_api.app_def import app
from backend_api.app_runner import ServerControl
from fastapi.testclient import TestClient
from httpx import codes
from pytest_mock import MockerFixture
from syrupy.assertion import SnapshotAssertion


def test_Given_healthy__When_healthcheck__Then_version_in_response():
    client = TestClient(app)

    response = client.get("/api/healthcheck")

    assert response.status_code == codes.OK
    actual_version = HealthcheckResponse.model_validate(response.json()).version

    assert actual_version.startswith("v") is False
    assert len(actual_version) > 2  # noqa: PLR2004 # just asserting there's some content that isn't just the period
    assert "." in actual_version


def test_Given_healthy__When_healthcheck_with_prepend_v__Then_version_in_response():
    client = TestClient(app)

    response = client.get("/api/healthcheck?prependV=true")

    assert response.status_code == codes.OK
    actual_version = HealthcheckResponse.model_validate(response.json()).version

    assert actual_version.startswith("v") is True
    assert len(actual_version) > 2  # noqa: PLR2004 # just asserting there's some content that isn't just the period
    assert "." in actual_version


def test_When_swagger_route_called__Then_rendered():
    client = TestClient(app)

    response = client.get("/api-docs")

    assert response.status_code == codes.OK
    assert "Swagger UI" in response.text


@pytest.fixture
def stop_event_on_app_state(mocker: MockerFixture) -> Iterator[threading.Event]:
    stop_event = threading.Event()
    server_control = ServerControl(stop_event=stop_event)
    _ = mocker.patch.object(app.state, "server_control", server_control, create=True)
    yield stop_event
    server_control.stop_completed()  # no server is running to do this, so cancel any force-exit timer the route started


def test_Given_stop_event_on_app_state__When_shutdown_route_called__Then_stop_event_set(
    stop_event_on_app_state: threading.Event,
):
    client = TestClient(app)

    response = client.post("/api/shutdown")

    assert response.status_code == codes.OK
    assert stop_event_on_app_state.is_set()


def test_When_api_route_requested_with_a_method_only_the_frontend_serves__Then_method_not_allowed():
    client = TestClient(app)

    response = client.head("/api/healthcheck")  # GET-only API route; the frontend mount would serve HEAD

    assert response.status_code == codes.METHOD_NOT_ALLOWED


def test_When_path_without_api_prefix_requested__Then_frontend_static_file_served():
    client = TestClient(app)

    response = client.get("/favicon.ico")  # any static file works; this is the only one in every deployment mode

    assert response.status_code == codes.OK
    assert response.content == (app_def.STATIC_DIR / "favicon.ico").read_bytes()


def test_openapi_schema(snapshot_json: SnapshotAssertion, mocker: MockerFixture):
    client = TestClient(app)
    app.openapi_schema = None  # reset cache populated by other tests
    spied_get_openapi = mocker.spy(fast_api_exception_handlers, "get_openapi")

    response = client.get("/api/openapi.json")

    assert response.status_code == codes.OK
    assert response.json() == snapshot_json
    assert spied_get_openapi.call_count == 1

    re_response = client.get("/api/openapi.json")
    assert re_response.status_code == codes.OK
    assert re_response.text == response.text
    assert spied_get_openapi.call_count == 1  # still 1, not reinvoked
