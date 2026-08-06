"""Shared pytest fixtures for the Veriducta test suite."""

import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("VERIDUCTA_ENV", "testing")
os.environ.setdefault("LOG_FORMAT", "json")


@pytest.fixture(scope="session")
def app() -> FastAPI:
    """Return the FastAPI application configured for testing."""
    from api.app import create_app

    return create_app()


@pytest.fixture(scope="session")
def client(app: FastAPI) -> TestClient:
    """Return a synchronous test client wrapping the FastAPI app."""
    return TestClient(app, raise_server_exceptions=True)
