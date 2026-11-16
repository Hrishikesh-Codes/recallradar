"""Which address a rate limit counts against."""

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from recallradar_api.main import create_app
from recallradar_api.ratelimit import RateLimiter, client_key
from recallradar_core.settings import Settings


def keyed_app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/_key")
    def key(request: Request) -> dict[str, str]:
        return {"key": client_key(request)}

    return app


def test_the_connection_address_is_the_default_and_headers_are_ignored() -> None:
    client = TestClient(keyed_app(Settings()), client=("203.0.113.9", 4000))
    response = client.get("/_key", headers={"CF-Connecting-IP": "198.51.100.1"})
    assert response.json() == {"key": "203.0.113.9"}


def test_a_configured_edge_header_wins_and_falls_back_when_missing() -> None:
    app = keyed_app(Settings(client_ip_header="CF-Connecting-IP"))
    client = TestClient(app, client=("10.0.0.5", 4000))
    forged = {"CF-Connecting-IP": "198.51.100.1", "X-Forwarded-For": "1.2.3.4"}
    assert client.get("/_key", headers=forged).json() == {"key": "198.51.100.1"}
    assert client.get("/_key").json() == {"key": "10.0.0.5"}


def test_limit_and_retry_after() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("a", now=0) and limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.retry_after("a", now=2) == 58
    assert limiter.allow("b", now=2)
    assert limiter.allow("a", now=61)
