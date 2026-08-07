"""Tests for observability.middleware - ObservabilityMiddleware."""

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from observability.context import get_current_context
from observability.middleware import ObservabilityMiddleware


def _make_app() -> Starlette:
    async def handler(request: Request) -> PlainTextResponse:
        ctx = get_current_context()
        body = f"{ctx.request_id}:{ctx.trace_id}" if ctx else "no-ctx"
        return PlainTextResponse(body)

    app = Starlette(routes=[Route("/", handler)])
    app.add_middleware(ObservabilityMiddleware)
    return app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(_make_app())


def test_middleware_sets_x_request_id_header(client: TestClient) -> None:
    response = client.get("/")
    assert "X-Request-Id" in response.headers
    assert response.headers["X-Request-Id"]


def test_middleware_sets_x_trace_id_header(client: TestClient) -> None:
    response = client.get("/")
    assert "X-Trace-Id" in response.headers
    assert response.headers["X-Trace-Id"]


def test_middleware_propagates_incoming_trace_id(client: TestClient) -> None:
    response = client.get("/", headers={"X-Trace-Id": "custom-trace-42"})
    assert response.headers["X-Trace-Id"] == "custom-trace-42"


def test_middleware_propagates_incoming_request_id(client: TestClient) -> None:
    response = client.get("/", headers={"X-Request-Id": "custom-req-99"})
    assert response.headers["X-Request-Id"] == "custom-req-99"


def test_middleware_context_accessible_in_handler(client: TestClient) -> None:
    response = client.get("/", headers={"X-Request-Id": "r1", "X-Trace-Id": "t1"})
    body = response.text
    # The handler reads ctx.request_id and ctx.trace_id and returns "r1:t1"
    assert "r1" in body
    assert "t1" in body


def test_middleware_generates_ids_when_headers_absent(client: TestClient) -> None:
    response = client.get("/")
    request_id = response.headers["X-Request-Id"]
    trace_id = response.headers["X-Trace-Id"]
    assert request_id != trace_id
    assert len(request_id) > 8
    assert len(trace_id) > 8


def test_middleware_different_requests_get_different_ids(client: TestClient) -> None:
    r1 = client.get("/")
    r2 = client.get("/")
    assert r1.headers["X-Request-Id"] != r2.headers["X-Request-Id"]
