"""Account endpoints: the list, dismissals, settings, demo, export, and deletion."""

import secrets
import time
from collections.abc import Iterator
from typing import Any

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from recallradar_api.auth import AUDIENCE, ISSUER
from recallradar_api.checking import BarcodeLookups, CoverageCache
from recallradar_api.main import create_app
from recallradar_api.ratelimit import RateLimiter
from recallradar_api.routes.me import DEMO_ITEMS
from recallradar_api.state import AppState
from recallradar_core.db import AuthUser, PushSubscription, WatchItem, WatchMatch
from recallradar_core.settings import Settings, get_settings
from recallradar_matching.embed import Embedder

pytestmark = [pytest.mark.db, pytest.mark.model]
SECRET = secrets.token_hex(32)  # per run, so nothing secret-looking is committed


@pytest.fixture
def sessions(writable_database_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(writable_database_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add_all(
            [
                AuthUser(id="u1", name="", email="one@example.com", email_verified=True),
                AuthUser(id="u2", name="", email="two@example.com", email_verified=True),
                AuthUser(id="anon", name="Demo", email="x@anonymous.invalid", is_anonymous=True),
            ]
        )
    yield factory
    engine.dispose()


@pytest.fixture
def client(
    sessions: sessionmaker[Session], embedder: Embedder, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    monkeypatch.setenv("API_TOKEN_SECRET", SECRET)
    get_settings.cache_clear()
    offline = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    state = AppState(
        sessions=sessions,
        embedder=embedder,
        barcodes=BarcodeLookups(offline, RateLimiter(limit=0, window_seconds=60)),
        coverage=CoverageCache(),
        check_limits=[RateLimiter(limit=100, window_seconds=60)],
        feedback_limits=[RateLimiter(limit=100, window_seconds=60)],
    )
    with TestClient(create_app(Settings(), state=state)) as test_client:
        yield test_client
    get_settings.cache_clear()


def token(user_id: str, **overrides: Any) -> dict[str, str]:
    now = int(time.time())
    claims = {"sub": user_id, "aud": AUDIENCE, "iss": ISSUER, "iat": now, "exp": now + 120}
    claims.update(overrides)
    return {"Authorization": f"Bearer {jwt.encode(claims, SECRET, algorithm='HS256')}"}


def add(client: TestClient, user: str, value: str, kind: str = "text") -> dict[str, Any]:
    response = client.post(
        "/v1/me/items", json={"input": {"type": kind, "value": value}}, headers=token(user)
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def test_requires_a_valid_token(client: TestClient) -> None:
    assert client.get("/v1/me/items").status_code == 401
    assert (
        client.get("/v1/me/items", headers=token("u1", exp=int(time.time()) - 5)).status_code == 401
    )
    assert client.get("/v1/me/items", headers=token("u1", aud="someone-else")).status_code == 401
    assert client.get("/v1/me/items", headers=token("deleted-user")).status_code == 401
    forged = jwt.encode(
        {"sub": "u1", "aud": AUDIENCE, "iss": ISSUER, "iat": 0, "exp": 2**40}, "x" * 40
    )
    assert (
        client.get("/v1/me/items", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    )


def test_saved_item_is_checked_and_matches_are_stored(client: TestClient) -> None:
    item = add(client, "u1", "DR Power leaf vacuum WL33006DMN")
    assert item["verdict"] == "recalled"
    assert item["label"] == "DR Power leaf vacuum WL33006DMN"
    assert [m["recall"]["source_recall_id"] for m in item["matches"]] == ["10541"]

    listed = client.get("/v1/me/items", headers=token("u1")).json()
    assert [i["id"] for i in listed] == [item["id"]]
    assert client.get("/v1/me/items", headers=token("u2")).json() == []


def test_not_my_product_changes_the_verdict_and_survives(client: TestClient) -> None:
    item = add(client, "u1", "DR Power leaf vacuum WL33006DMN")
    recall_id = item["matches"][0]["recall"]["id"]
    url = f"/v1/me/items/{item['id']}/matches/{recall_id}"
    dismissed = client.post(f"{url}/dismiss", headers=token("u1")).json()
    assert dismissed["verdict"] == "all_clear"
    assert dismissed["matches"][0]["dismissed"] is True
    restored = client.post(f"{url}/restore", headers=token("u1")).json()
    assert restored["verdict"] == "recalled"
    # Another user can't touch it.
    assert client.post(f"{url}/dismiss", headers=token("u2")).status_code == 404


def test_settings(client: TestClient) -> None:
    me = client.get("/v1/me", headers=token("u1")).json()
    assert me["settings"] == {"email_alerts": True, "alert_tiers": ["recalled", "check_unit"]}
    assert me["email"] == "one@example.com"
    updated = client.put(
        "/v1/me/settings",
        json={"email_alerts": False, "alert_tiers": ["recalled"]},
        headers=token("u1"),
    ).json()
    assert updated == {"email_alerts": False, "alert_tiers": ["recalled"]}


def test_demo_accounts_get_examples_once(client: TestClient) -> None:
    assert client.post("/v1/me/demo", headers=token("u1")).status_code == 403
    first = client.post("/v1/me/demo", headers=token("anon")).json()
    assert len(first) == len(DEMO_ITEMS)
    again = client.post("/v1/me/demo", headers=token("anon")).json()
    assert len(again) == len(DEMO_ITEMS)
    me = client.get("/v1/me", headers=token("anon")).json()
    assert me["is_anonymous"] is True and me["email"] is None


def test_export_and_delete(client: TestClient, sessions: sessionmaker[Session]) -> None:
    add(client, "u1", "DR Power leaf vacuum WL33006DMN")
    exported = client.get("/v1/me/export", headers=token("u1")).json()
    assert exported["account"]["email"] == "one@example.com"
    assert len(exported["items"]) == 1

    assert client.delete("/v1/me", headers=token("u1")).status_code == 204
    with sessions() as session:
        assert session.get(AuthUser, "u1") is None
        assert session.scalar(select(func.count()).select_from(WatchItem)) == 0
        assert session.scalar(select(func.count()).select_from(WatchMatch)) == 0
        assert session.get(AuthUser, "u2") is not None
    assert client.get("/v1/me", headers=token("u1")).status_code == 401


def test_secret_must_be_long(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="at least 32"):
        Settings(api_token_secret=SecretStr("short"))


def test_push_subscriptions(client: TestClient, sessions: sessionmaker[Session]) -> None:
    body = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "p" * 40, "auth": "a" * 16}}
    assert client.put("/v1/me/push", json=body, headers=token("anon")).status_code == 403
    assert (
        client.put(
            "/v1/me/push", json={**body, "endpoint": "http://insecure"}, headers=token("u1")
        ).status_code
        == 422
    )
    assert client.put("/v1/me/push", json=body, headers=token("u1")).status_code == 204
    # The same browser signing in as someone else moves the subscription.
    assert client.put("/v1/me/push", json=body, headers=token("u2")).status_code == 204
    with sessions() as session:
        owners = [s.user_id for s in session.scalars(select(PushSubscription))]
    assert owners == ["u2"]
    assert client.get("/v1/me/export", headers=token("u2")).json()["push_devices"] == 1
    removed = client.post(
        "/v1/me/push/remove", json={"endpoint": body["endpoint"]}, headers=token("u2")
    )
    assert removed.status_code == 204
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(PushSubscription)) == 0
