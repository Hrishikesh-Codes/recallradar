from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from recallradar_api.main import REQUEST_ID_HEADER, create_app
from recallradar_api.routes.health import database_is_reachable
from recallradar_core.db.session import get_engine
from recallradar_core.settings import Settings, get_settings


@pytest.fixture
def app() -> FastAPI:
    return create_app(Settings(cors_origins=["https://web.example"]))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


def test_liveness_never_needs_the_database(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[database_is_reachable] = lambda: pytest.fail("db was touched")
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("database_ok", "status_code", "body"),
    [
        (True, 200, {"status": "ok", "database": True}),
        (False, 503, {"status": "unavailable", "database": False}),
    ],
)
def test_readiness_reflects_the_database(
    app: FastAPI, client: TestClient, database_ok: bool, status_code: int, body: dict[str, object]
) -> None:
    app.dependency_overrides[database_is_reachable] = lambda: database_ok
    response = client.get("/readyz")
    assert response.status_code == status_code
    assert response.json() == body


def test_meta_reports_version_and_environment(client: TestClient) -> None:
    body = client.get("/v1/meta").json()
    assert body["environment"] == "local"
    assert body["version"]


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    echoed = client.get("/healthz", headers={REQUEST_ID_HEADER: "abc123"})
    assert echoed.headers[REQUEST_ID_HEADER] == "abc123"
    assert len(client.get("/healthz").headers[REQUEST_ID_HEADER]) == 32


def test_cors_allows_only_configured_origins(client: TestClient) -> None:
    preflight = {"Access-Control-Request-Method": "GET"}
    allowed = client.options("/healthz", headers={"Origin": "https://web.example", **preflight})
    assert allowed.headers["access-control-allow-origin"] == "https://web.example"
    denied = client.options("/healthz", headers={"Origin": "https://evil.example", **preflight})
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.db
def test_readiness_against_a_real_database(
    migrated_database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", migrated_database_url)
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/readyz").json() == {"status": "ok", "database": True}
    finally:
        get_engine().dispose()
        get_settings.cache_clear()
        get_engine.cache_clear()
