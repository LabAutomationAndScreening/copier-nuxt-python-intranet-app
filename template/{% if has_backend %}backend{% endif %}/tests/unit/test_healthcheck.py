from backend_api.app_def import app
from fastapi.testclient import TestClient


def test_Given_healthy__When_healthcheck__Then_version_in_response():
    client = TestClient(app)

    response = client.get("/api/healthcheck")

    assert response.status_code == 200  # noqa: PLR2004 # this is the standard HTTP status code for OK
    response_json = response.json()
    assert "version" in response_json
    actual_version = response_json["version"]

    assert len(actual_version) > 2  # noqa: PLR2004 # just asserting there's some content that isn't just the period
    assert "." in actual_version
