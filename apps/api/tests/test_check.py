"""POST /v1/check, /v1/feedback, /v1/recalls, /v1/stats against real fixture recalls."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from recallradar_api.checking import BarcodeLookups, CoverageCache
from recallradar_api.main import create_app
from recallradar_api.ratelimit import RateLimiter
from recallradar_api.state import AppState
from recallradar_core.db import BarcodeLookup, Event, Feedback, Recall
from recallradar_core.settings import Settings
from recallradar_matching.embed import Embedder

pytestmark = [pytest.mark.db, pytest.mark.model]

OFF_PRODUCT = {
    "status": 1,
    "product": {"product_name": "Yogurt Raisins", "brands": "Sunny Snacks, Other"},
}


@pytest.fixture(scope="module")
def sessions(loaded_database_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(loaded_database_url)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


class FakeOpenFoodFacts:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if "0041498111113" in request.url.path:
            return httpx.Response(200, json=OFF_PRODUCT)
        return httpx.Response(200, json={"status": 0})


@pytest.fixture
def off() -> FakeOpenFoodFacts:
    return FakeOpenFoodFacts()


@pytest.fixture
def state(sessions: sessionmaker[Session], embedder: Embedder, off: FakeOpenFoodFacts) -> AppState:
    client = httpx.Client(transport=httpx.MockTransport(off.handler))
    return AppState(
        sessions=sessions,
        embedder=embedder,
        barcodes=BarcodeLookups(client, RateLimiter(limit=100, window_seconds=60)),
        coverage=CoverageCache(),
        check_limits=[RateLimiter(limit=5, window_seconds=60)],
        feedback_limits=[RateLimiter(limit=5, window_seconds=60)],
    )


@pytest.fixture
def client(state: AppState) -> Iterator[TestClient]:
    app = create_app(Settings(cors_origins=["http://localhost:3000"]), state=state)
    with TestClient(app) as test_client:
        yield test_client


def post_check(client: TestClient, kind: str, value: str, **extra: Any) -> dict[str, Any]:
    response = client.post("/v1/check", json={"input": {"type": kind, "value": value}, **extra})
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def test_text_check_returns_verdict_reasons_and_coverage(client: TestClient) -> None:
    body = post_check(client, "text", "DR Power leaf vacuum WL33006DMN")
    assert body["verdict"] == "recalled"
    match = body["matches"][0]
    assert match["recall"]["source_recall_id"] == "10541"
    assert match["recall"]["official_url"].startswith("https://www.cpsc.gov/")
    assert match["recall"]["image_url"].startswith("https://")
    assert any("WL33006DMN" in reason for reason in match["reasons"])
    assert body["query"]["model_numbers"] == ["WL33006DMN"]
    coverage = body["coverage"]
    assert {s["label"] for s in coverage["checked"]} == {"CPSC", "FDA"}
    assert coverage["recalls_checked"] == sum(s["recalls"] for s in coverage["checked"])


def test_check_records_an_event_without_the_product(
    client: TestClient, sessions: sessionmaker[Session]
) -> None:
    body = post_check(client, "text", "Yolaah bed rail")
    with sessions() as session:
        event = session.scalars(select(Event).order_by(Event.id.desc()).limit(1)).one()
    assert event.name == "check"
    assert event.properties["check_id"] == body["id"]
    assert "yolaah" not in str(event.properties).lower()


def test_barcode_lookup_is_cached(
    client: TestClient, off: FakeOpenFoodFacts, sessions: sessionmaker[Session]
) -> None:
    first = post_check(client, "barcode", "041498111113")
    assert first["query"]["product_name"] == "Yogurt Raisins"
    assert first["query"]["brand"] == "Sunny Snacks"
    post_check(client, "barcode", "041498111113")
    assert len(off.calls) == 1
    with sessions() as session:
        cached = session.get(BarcodeLookup, "00041498111113")
    assert cached is not None and cached.found
    assert cached.fetched_at > datetime(2026, 1, 1, tzinfo=UTC)


def test_listed_barcode_matches_without_a_lookup_hit(client: TestClient) -> None:
    body = post_check(client, "barcode", "843461115513")  # BUILT tumbler, CPSC 10664
    assert body["verdict"] == "recalled"
    assert body["matches"][0]["recall"]["source_recall_id"] == "10664"


def test_invalid_input_is_rejected(client: TestClient) -> None:
    response = client.post("/v1/check", json={"input": {"type": "vin", "value": "x"}})
    assert response.status_code == 422
    response = client.post("/v1/check", json={"input": {"type": "text", "value": ""}})
    assert response.status_code == 422


def test_checks_are_rate_limited(client: TestClient) -> None:
    statuses = [
        client.post("/v1/check", json={"input": {"type": "text", "value": "blender"}}).status_code
        for _ in range(6)
    ]
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 429


def test_feedback_is_stored_once_per_check_and_recall(
    client: TestClient, sessions: sessionmaker[Session]
) -> None:
    body = post_check(client, "text", "Yolaah bed rail")
    recall_id = body["matches"][0]["recall"]["id"]
    for label in ("not_mine", "mine"):
        response = client.post(
            "/v1/feedback",
            json={
                "check_id": body["id"],
                "recall_id": recall_id,
                "label": label,
                "tier_shown": body["verdict"],
                "query": body["query"],
            },
        )
        assert response.status_code == 202
    with sessions() as session:
        rows = session.scalars(select(Feedback).where(Feedback.check_id == body["id"])).all()
    assert [(r.label, r.recall_id) for r in rows] == [("mine", recall_id)]


def test_feedback_for_unknown_recall_is_404(client: TestClient) -> None:
    response = client.post(
        "/v1/feedback",
        json={
            "check_id": "00000000-0000-4000-8000-000000000000",
            "recall_id": 999_999_999,
            "label": "mine",
        },
    )
    assert response.status_code == 404


def test_recall_detail_and_stats(client: TestClient, sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        recall_id = session.scalar(select(Recall.id).where(Recall.source_recall_id == "10541"))
    detail = client.get(f"/v1/recalls/{recall_id}").json()
    assert detail["recall"]["source_label"] == "CPSC"
    assert detail["products"][0]["model_numbers"][0] == "WL33006DMN"
    assert client.get("/v1/recalls/0").status_code == 404

    stats = client.get("/v1/stats").json()
    assert stats["recalls"] == sum(s["recalls"] for s in stats["sources"]) > 0
    assert stats["products"] >= stats["recalls"]
