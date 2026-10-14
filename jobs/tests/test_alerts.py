"""The alerts job against real fixture recalls: who gets an email, and only once."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.db import Alert, AuthUser, Recall, RecallProduct, UserSettings, WatchItem
from recallradar_core.enums import RecallSource
from recallradar_jobs.alerts import delete_old_demo_accounts, run
from recallradar_matching.embed import Embedder

pytestmark = [pytest.mark.db, pytest.mark.model]
INGESTED = [
    RecallSource.CPSC,
    RecallSource.FDA_FOOD,
    RecallSource.FDA_DRUG,
    RecallSource.FDA_DEVICE,
]


@pytest.fixture
def sessions(writable_database_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(writable_database_url)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


def user(session: Session, user_id: str, **fields: object) -> AuthUser:
    values: dict[str, object] = {
        "id": user_id,
        "name": "",
        "email": f"{user_id}@example.com",
        "email_verified": True,
    }
    values.update(fields)
    account = AuthUser(**values)
    session.add(account)
    return account


def watch(session: Session, user_id: str, value: str, kind: str = "text") -> None:
    # Saved before the recall existed: no matches stored yet, so the job finds them as new.
    session.add(
        WatchItem(
            user_id=user_id, label=value, input_type=kind, input_value=value, verdict="all_clear"
        )
    )


class Outbox:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def __call__(self, message: EmailMessage) -> None:
        self.sent.append(message)


def go(sessions: sessionmaker[Session], embedder: Embedder, outbox: Outbox) -> dict[str, object]:
    stats = run(
        sessions,
        embedder,
        ingested=INGESTED,
        sender=outbox,
        mail_from="RecallRadar <alerts@example.com>",
        web_url="https://recallradar.example",
    )
    return {"sent": stats.emails_sent, "skipped": dict(stats.skipped), "new": stats.new_matches}


def test_new_cpsc_match_is_emailed_once(
    sessions: sessionmaker[Session], embedder: Embedder
) -> None:
    with sessions.begin() as session:
        user(session, "u1")
        watch(session, "u1", "DR Power leaf vacuum WL33006DMN")
    outbox = Outbox()
    first = go(sessions, embedder, outbox)
    assert first["sent"] == 1
    (message,) = outbox.sent
    assert message["To"] == "u1@example.com"
    assert "DR Power leaf vacuum WL33006DMN" in message["Subject"]
    body = message.get_body(("plain",))
    assert body is not None
    text = body.get_content()
    assert "Verdict: Recalled" in text
    assert "https://www.cpsc.gov/" in text
    assert "https://recallradar.example/account" in text

    again = go(sessions, embedder, outbox)
    assert again["sent"] == 0 and again["new"] == 0
    with sessions() as session:
        (alert,) = session.scalars(select(Alert)).all()
    assert alert.status == "sent" and alert.provider_message_id


def test_who_gets_no_email(sessions: sessionmaker[Session], embedder: Embedder) -> None:
    with sessions.begin() as session:
        fda_upc = session.scalar(
            select(RecallProduct.upcs[1])
            .join(Recall)
            .where(Recall.source == RecallSource.FDA_FOOD, RecallProduct.upcs != [])
            .limit(1)
        )
        assert fda_upc
        user(session, "fda")
        watch(session, "fda", fda_upc, kind="barcode")
        user(session, "demo", is_anonymous=True)
        watch(session, "demo", "DR Power leaf vacuum WL33006DMN")
        user(session, "off")
        session.add(UserSettings(user_id="off", email_alerts=False, alert_tiers=["recalled"]))
        watch(session, "off", "DR Power leaf vacuum WL33006DMN")
        user(session, "unverified", email_verified=False)
        watch(session, "unverified", "DR Power leaf vacuum WL33006DMN")
    outbox = Outbox()
    result = go(sessions, embedder, outbox)
    assert outbox.sent == []
    assert result["skipped"] == {
        "source_terms": 1,
        "demo_account": 1,
        "alerts_off": 1,
        "unverified_email": 1,
    }
    with sessions() as session:
        statuses = {a.status for a in session.scalars(select(Alert))}
    assert statuses == {"skipped"}


def test_old_demo_accounts_are_deleted(sessions: sessionmaker[Session]) -> None:
    now = datetime.now(UTC)
    with sessions.begin() as session:
        user(session, "old-demo", is_anonymous=True, created_at=now - timedelta(days=8))
        user(session, "new-demo", is_anonymous=True, created_at=now - timedelta(days=1))
        user(session, "old-real", created_at=now - timedelta(days=400))
        watch(session, "old-demo", "Peloton bike PL01")
    assert delete_old_demo_accounts(sessions, now) == 1
    with sessions() as session:
        remaining = set(session.scalars(select(AuthUser.id)))
        items = session.scalars(select(WatchItem)).all()
    assert remaining == {"new-demo", "old-real"}
    assert items == []
