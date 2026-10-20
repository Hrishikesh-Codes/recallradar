"""The signed-in user's list, settings, export, and account deletion."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from recallradar_api import schemas
from recallradar_api.auth import CurrentUser
from recallradar_api.checking import build_query, recall_summary
from recallradar_api.ratelimit import enforce
from recallradar_api.state import DbSession, State
from recallradar_core.db import (
    Alert,
    AuthUser,
    AuthVerification,
    PushSubscription,
    Recall,
    UserSettings,
    WatchItem,
    WatchMatch,
)
from recallradar_matching.engine import Tier
from recallradar_matching.watch import refresh

router = APIRouter(prefix="/v1/me", tags=["account"])

MAX_ITEMS = 500
MAX_DEMO_ITEMS = 25
# Real products from the evaluation set (data/labels/m1_smoke.jsonl), covering every verdict.
DEMO_ITEMS: list[tuple[str, str, str]] = [
    ("text", "Peloton bike PL01", "Peloton Bike"),
    ("text", "Anker PowerCore 10000 power bank A1263", "Anker PowerCore 10000"),
    ("text", "Fisher-Price Rock 'n Play sleeper", "Fisher-Price Rock 'n Play"),
    ("barcode", "686148007370", "Shakespeare's frozen pizza"),
    ("text", "Hydro Flask 32 oz water bottle", "Hydro Flask bottle"),
    ("text", "Graco 4Ever car seat", "Graco 4Ever car seat"),
]


def _settings(session: Session, user: AuthUser) -> UserSettings:
    settings = session.get(UserSettings, user.id)
    if settings is None:
        settings = UserSettings(
            user_id=user.id, email_alerts=True, alert_tiers=["recalled", "check_unit"]
        )
        session.add(settings)
        session.flush()
    return settings


def _settings_out(settings: UserSettings) -> schemas.SettingsOut:
    tiers = [t for t in settings.alert_tiers if t in ("recalled", "check_unit")]
    return schemas.SettingsOut(email_alerts=settings.email_alerts, alert_tiers=tiers)  # type: ignore[arg-type]


def _items_out(session: Session, items: list[WatchItem]) -> list[schemas.ItemOut]:
    if not items:
        return []
    rows = session.execute(
        select(WatchMatch, Recall)
        .join(Recall, Recall.id == WatchMatch.recall_id)
        .where(WatchMatch.item_id.in_([i.id for i in items]))
        .order_by(WatchMatch.first_matched_at)
    ).all()
    by_item: dict[int, list[schemas.ItemMatchOut]] = {}
    for match, recall in rows:
        by_item.setdefault(match.item_id, []).append(
            schemas.ItemMatchOut(
                recall=recall_summary(recall),
                tier=Tier(match.tier),
                reasons=[str(r) for r in match.reasons],
                first_matched_at=match.first_matched_at,
                dismissed=match.dismissed_at is not None,
            )
        )
    return [
        schemas.ItemOut(
            id=item.id,
            label=item.label,
            input_type=item.input_type,  # type: ignore[arg-type]
            input_value=item.input_value,
            purchase_date=item.purchase_date,
            verdict=Tier(item.verdict),
            last_checked_at=item.last_checked_at,
            created_at=item.created_at,
            matches=by_item.get(item.id, []),
        )
        for item in items
    ]


def _own_item(session: Session, user: AuthUser, item_id: int) -> WatchItem:
    item = session.get(WatchItem, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Item not found.")
    return item


def _count(session: Session, user: AuthUser) -> int:
    return session.scalar(select(func.count()).where(WatchItem.user_id == user.id)) or 0


@router.get("")
def me(user: CurrentUser, session: DbSession) -> schemas.Me:
    return schemas.Me(
        id=user.id,
        email=None if user.is_anonymous else user.email,
        is_anonymous=bool(user.is_anonymous),
        settings=_settings_out(_settings(session, user)),
        items=_count(session, user),
    )


@router.get("/items")
def list_items(user: CurrentUser, session: DbSession) -> list[schemas.ItemOut]:
    items = session.scalars(
        select(WatchItem).where(WatchItem.user_id == user.id).order_by(WatchItem.created_at.desc())
    ).all()
    return _items_out(session, list(items))


def _add_item(session: Session, state: State, user: AuthUser, body: schemas.NewItem) -> WatchItem:
    request = schemas.CheckRequest(input=body.input, purchase_date=body.purchase_date)
    query = build_query(session, request, state.barcodes, state.vins)
    label = (body.label or query.product_name or query.brand or body.input.value)[:200]
    item = WatchItem(
        user_id=user.id,
        label=label.strip(),
        input_type=body.input.type,
        input_value=body.input.value.strip(),
        purchase_date=body.purchase_date,
        verdict=Tier.UNIDENTIFIED.value,
    )
    session.add(item)
    session.flush()
    sources = [s.source for s in state.coverage.get(session)]
    refresh(
        session,
        item,
        embedder=state.embedder,
        ingested=sources,
        query=query,
        vector_store=state.vectors,
    )
    session.flush()
    return item


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(
    body: schemas.NewItem, user: CurrentUser, state: State, session: DbSession
) -> schemas.ItemOut:
    """Save a product to the list. It's checked now, then again whenever new recalls arrive."""
    enforce(state.check_limits, f"user:{user.id}")
    limit = MAX_DEMO_ITEMS if user.is_anonymous else MAX_ITEMS
    if _count(session, user) >= limit:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Your list is full ({limit} items).")
    item = _add_item(session, state, user, body)
    return _items_out(session, [item])[0]


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item(item_id: int, user: CurrentUser, session: DbSession) -> Response:
    session.delete(_own_item(session, user, item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _set_dismissed(
    session: Session, user: AuthUser, item_id: int, recall_id: int, dismissed: bool
) -> schemas.ItemOut:
    item = _own_item(session, user, item_id)
    match = session.scalar(
        select(WatchMatch).where(WatchMatch.item_id == item.id, WatchMatch.recall_id == recall_id)
    )
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="That recall isn't on this item.")
    match.dismissed_at = datetime.now(UTC) if dismissed else None
    session.flush()
    _recompute_verdict(session, item)
    return _items_out(session, [item])[0]


def _recompute_verdict(session: Session, item: WatchItem) -> None:
    matches = session.scalars(select(WatchMatch).where(WatchMatch.item_id == item.id)).all()
    order = [Tier.RECALLED.value, Tier.CHECK_UNIT.value]
    active = sorted((m.tier for m in matches if m.dismissed_at is None), key=order.index)
    if active:
        item.verdict = active[0]
    elif item.verdict in order:
        item.verdict = Tier.ALL_CLEAR.value


@router.post("/items/{item_id}/matches/{recall_id}/dismiss")
def dismiss_match(
    item_id: int, recall_id: int, user: CurrentUser, session: DbSession
) -> schemas.ItemOut:
    """ "Not my product": this recall stops counting for the item, and stays dismissed."""
    return _set_dismissed(session, user, item_id, recall_id, dismissed=True)


@router.post("/items/{item_id}/matches/{recall_id}/restore")
def restore_match(
    item_id: int, recall_id: int, user: CurrentUser, session: DbSession
) -> schemas.ItemOut:
    return _set_dismissed(session, user, item_id, recall_id, dismissed=False)


@router.put("/settings")
def update_settings(
    body: schemas.SettingsOut, user: CurrentUser, session: DbSession
) -> schemas.SettingsOut:
    settings = _settings(session, user)
    settings.email_alerts = body.email_alerts
    settings.alert_tiers = list(dict.fromkeys(body.alert_tiers))
    settings.updated_at = datetime.now(UTC)
    return _settings_out(settings)


@router.post("/demo", status_code=status.HTTP_201_CREATED)
def seed_demo(user: CurrentUser, state: State, session: DbSession) -> list[schemas.ItemOut]:
    """Fill a new demo (anonymous) account's list with real examples of every verdict."""
    if not user.is_anonymous:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Only demo accounts get examples.")
    if _count(session, user) == 0:
        for kind, value, label in DEMO_ITEMS:
            new = schemas.NewItem(input=schemas.CheckInput(type=kind, value=value), label=label)  # type: ignore[arg-type]
            _add_item(session, state, user, new)
    return list_items(user, session)


@router.put("/push", status_code=status.HTTP_204_NO_CONTENT)
def save_push(body: schemas.PushSubscriptionIn, user: CurrentUser, session: DbSession) -> Response:
    """Turn on push notifications for this browser (re-subscribing moves it to this user)."""
    if user.is_anonymous:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Sign in with email to get alerts.")
    values = {
        "user_id": user.id,
        "endpoint": body.endpoint,
        "p256dh": body.keys.p256dh,
        "auth": body.keys.auth,
    }
    statement = insert(PushSubscription).values(**values)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[PushSubscription.endpoint],
            set_={k: statement.excluded[k] for k in ("user_id", "p256dh", "auth")},
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/push/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_push(body: schemas.PushEndpoint, user: CurrentUser, session: DbSession) -> Response:
    session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user.id, PushSubscription.endpoint == body.endpoint
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/export")
def export(user: CurrentUser, session: DbSession) -> schemas.Export:
    alerts = session.scalars(select(Alert).where(Alert.user_id == user.id)).all()
    return schemas.Export(
        exported_at=datetime.now(UTC),
        account={
            "id": user.id,
            "email": None if user.is_anonymous else user.email,
            "created_at": user.created_at.isoformat(),
        },
        settings=_settings_out(_settings(session, user)),
        items=list_items(user, session),
        alerts=[_alert_dict(a) for a in alerts],
        push_devices=session.scalar(select(func.count()).where(PushSubscription.user_id == user.id))
        or 0,
    )


def _alert_dict(alert: Alert) -> dict[str, Any]:
    return {
        "item_id": alert.item_id,
        "recall_id": alert.recall_id,
        "channel": alert.channel,
        "tier": alert.tier,
        "status": alert.status,
        "created_at": alert.created_at.isoformat(),
        "sent_at": alert.sent_at.isoformat() if alert.sent_at else None,
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUser, session: DbSession) -> Response:
    """Delete the account and everything derived from it: sessions, list, matches, alerts."""
    session.execute(delete(AuthVerification).where(AuthVerification.identifier == user.email))
    session.delete(user)  # ON DELETE CASCADE removes the rest
    return Response(status_code=status.HTTP_204_NO_CONTENT)
