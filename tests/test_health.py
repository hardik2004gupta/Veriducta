"""Tests for the health and version endpoints."""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    """Health endpoint must return 200 with status 'ok'."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    assert "env" in body


def test_version_returns_200(client: TestClient) -> None:
    """Version endpoint must return 200 with version and service fields."""
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert "service" in body
    assert body["version"] == "0.1.0"


def test_unknown_route_returns_404(client: TestClient) -> None:
    """Requests to unmapped paths must return 404."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404


def test_health_response_includes_correlation_headers(client: TestClient) -> None:
    """Every response must carry X-Request-Id and X-Trace-Id headers."""
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    assert "x-trace-id" in response.headers
