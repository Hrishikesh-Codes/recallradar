"""Re-check watched items and email users about recalls that newly match them (SPEC §8).

- One alert per item per recall per channel: the alert table's unique constraint enforces it.
- Email only for CPSC recalls. openFDA's terms say its data must not be used to alert the
  public, so FDA matches show up in the app's list and are recorded here as "skipped".
- No email for demo (anonymous) accounts, unverified addresses, or users who turned alerts off.
- One email per user per run, listing everything new for them, in a calm tone.
"""

import html
import logging
import smtplib
import ssl
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from urllib.parse import unquote, urlsplit

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from recallradar_core.db import Alert, AuthUser, Recall, UserSettings, WatchItem
from recallradar_core.enums import SOURCE_LABELS, NoticeType, RecallSource
from recallradar_matching.embed import Embedder
from recallradar_matching.engine import Match, Tier
from recallradar_matching.watch import refresh

logger = logging.getLogger("recallradar.jobs.alerts")

EMAIL_SOURCES = frozenset({RecallSource.CPSC})
DEFAULT_TIERS = ("recalled", "check_unit")
TIER_WORDS = {Tier.RECALLED.value: "Recalled", Tier.CHECK_UNIT.value: "Check your unit"}


DEMO_ACCOUNT_DAYS = 7  # stated on the privacy page


@dataclass
class RunStats:
    demo_accounts_deleted: int = 0
    items: int = 0
    new_matches: int = 0
    alerts_created: int = 0
    skipped: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    emails_sent: int = 0
    emails_failed: int = 0
    seconds: float = 0.0


@dataclass(frozen=True)
class Outgoing:
    """One user's email for this run."""

    to: str
    alert_ids: list[int]
    subject: str
    text: str
    html: str


Sender = Callable[[EmailMessage], None]


def skip_reason(match: Match, user: AuthUser, settings: UserSettings | None) -> str | None:
    """Why a new match gets no email, or None if it should get one."""
    if match.recall.source not in EMAIL_SOURCES:
        return "source_terms"  # openFDA's terms: no public alerts from FDA data
    if user.is_anonymous:
        return "demo_account"
    if not user.email_verified:
        return "unverified_email"
    if settings is not None and not settings.email_alerts:
        return "alerts_off"
    tiers = settings.alert_tiers if settings is not None else DEFAULT_TIERS
    if match.tier is None or match.tier.value not in tiers:
        return "tier_off"
    return None


def record_alerts(session: Session, item: WatchItem, matches: list[Match], stats: RunStats) -> None:
    user = session.get(AuthUser, item.user_id)
    if user is None:
        return
    settings = session.get(UserSettings, user.id)
    for match in matches:
        reason = skip_reason(match, user, settings)
        if reason:
            stats.skipped[reason] += 1
        statement = (
            insert(Alert)
            .values(
                user_id=user.id,
                item_id=item.id,
                recall_id=match.recall.id,
                channel="email",
                tier=(match.tier or Tier.CHECK_UNIT).value,
                status="skipped" if reason else "pending",
                details={"reason": reason} if reason else {},
            )
            .on_conflict_do_nothing(constraint="uq_alert_item_id_recall_id_channel")
            .returning(Alert.id)
        )
        if session.scalar(statement) is not None and not reason:
            stats.alerts_created += 1


def recheck_all(
    sessions: sessionmaker[Session],
    embedder: Embedder,
    ingested: list[RecallSource],
    stats: RunStats,
) -> None:
    with sessions() as session:
        item_ids = list(session.scalars(select(WatchItem.id).order_by(WatchItem.id)))
    for item_id in item_ids:
        with sessions.begin() as session:
            item = session.get(WatchItem, item_id)
            if item is None:  # deleted meanwhile
                continue
            result = refresh(session, item, embedder=embedder, ingested=ingested)
            stats.items += 1
            stats.new_matches += len(result.new_matches)
            if result.new_matches:
                record_alerts(session, item, result.new_matches, stats)


def compose(to: str, rows: list[tuple[Alert, WatchItem, Recall]], web_url: str) -> Outgoing:
    # Labels are user text: one line each, so they can't break the subject header.
    labels = list(dict.fromkeys(" ".join(item.label.split()) for _, item, _ in rows))
    if len(labels) == 1:
        subject = f"A recall matches “{labels[0]}” on your list"
    else:
        subject = f"Recalls match {len(labels)} items on your list"
    list_url = f"{web_url.rstrip('/')}/list"
    settings_url = f"{web_url.rstrip('/')}/account"
    text_parts = ["Hello,", "", "We found a recall that may affect something on your list.", ""]
    html_parts = [
        "<p>Hello,</p><p>We found a recall that may affect something on your list.</p>",
    ]
    for alert, item, recall in rows:
        verdict = TIER_WORDS.get(alert.tier, "Check your unit")
        kind = "warning" if recall.notice_type is NoticeType.WARNING else "recall"
        reference = (
            f"{SOURCE_LABELS[recall.source]} {kind} {recall.reference or recall.source_recall_id}"
        )
        lines = [
            f"Your item: {item.label}",
            f"Verdict: {verdict}",
            f"Recall: {recall.title} ({reference})",
        ]
        if recall.hazard:
            lines.append(f"Hazard: {recall.hazard}")
        if recall.remedy:
            lines.append(f"What to do: {recall.remedy}")
        if recall.official_url:
            lines.append(f"Official notice: {recall.official_url}")
        text_parts += [*lines, ""]
        html_parts.append(_card(item.label, verdict, reference, recall))
    has_check_unit = any(alert.tier == Tier.CHECK_UNIT.value for alert, _, _ in rows)
    explain = (
        '"Check your unit" means the recall covers only some models, lots, or dates, or we '
        "matched it by name. Compare the details with your product's label.\n\n"
        if has_check_unit
        else ""
    )
    footer = (
        f"{explain}See your list: {list_url}\n"
        f"Turn alerts off or change them: {settings_url}\n\n"
        "You get these because you saved items to RecallRadar. Email alerts cover CPSC "
        "recalls; FDA recalls appear on your list."
    )
    text_parts.append(footer)
    html_parts.append(
        (
            "<p style='color:#555;font-size:13px'>&ldquo;Check your unit&rdquo; means the recall "
            "covers only some models, lots, or dates, or we matched it by name. Compare the "
            "details with your product&rsquo;s label.</p>"
            if has_check_unit
            else ""
        )
        + f"<p style='color:#555;font-size:13px'><a href='{html.escape(list_url, quote=True)}'>"
        f"See your list</a> · <a href='{html.escape(settings_url, quote=True)}'>Change or "
        "turn off alerts</a></p>"
        "<p style='color:#555;font-size:13px'>You get these because you saved items to "
        "RecallRadar. Email alerts cover CPSC recalls; FDA recalls appear on your list.</p>"
    )
    return Outgoing(
        to=to,
        alert_ids=[alert.id for alert, _, _ in rows],
        subject=subject,
        text="\n".join(text_parts),
        html="".join(html_parts),
    )


def _card(label: str, verdict: str, reference: str, recall: Recall) -> str:
    """One matched item as an email-safe HTML table (inline styles, no images)."""
    paragraph = "<p style='margin:0 0 8px'>{}</p>"
    parts = [
        f"<p style='margin:0 0 4px;font-weight:600'>{html.escape(label)}</p>",
        paragraph.format(f"<strong>{html.escape(verdict)}</strong> · {html.escape(reference)}"),
        paragraph.format(html.escape(recall.title)),
    ]
    if recall.hazard:
        parts.append(paragraph.format(f"<strong>Hazard:</strong> {html.escape(recall.hazard)}"))
    if recall.remedy:
        parts.append(paragraph.format(f"<strong>What to do:</strong> {html.escape(recall.remedy)}"))
    if recall.official_url:
        href = html.escape(recall.official_url, quote=True)
        parts.append(f"<p style='margin:0'><a href='{href}'>Read the official notice</a></p>")
    return (
        "<table role='presentation' style='margin:16px 0;padding:12px;border:1px solid #ddd;"
        "border-radius:6px;width:100%'><tr><td>" + "".join(parts) + "</td></tr></table>"
    )


def pending_emails(session: Session, web_url: str) -> list[Outgoing]:
    rows = session.execute(
        select(Alert, WatchItem, Recall, AuthUser)
        .join(WatchItem, WatchItem.id == Alert.item_id)
        .join(Recall, Recall.id == Alert.recall_id)
        .join(AuthUser, AuthUser.id == Alert.user_id)
        .where(Alert.status == "pending", Alert.channel == "email")
        .order_by(Alert.user_id, Alert.id)
    ).all()
    by_user: dict[str, list[tuple[Alert, WatchItem, Recall]]] = defaultdict(list)
    emails: dict[str, str] = {}
    for alert, item, recall, user in rows:
        by_user[user.id].append((alert, item, recall))
        emails[user.id] = user.email
    return [compose(emails[uid], user_rows, web_url) for uid, user_rows in by_user.items()]


def smtp_sender(smtp_url: str) -> Sender:
    """smtp://host:port (Mailpit) or smtps://user:password@host:465 (Resend)."""
    parts = urlsplit(smtp_url)
    host, secure = parts.hostname or "localhost", parts.scheme == "smtps"
    port = parts.port or (465 if secure else 25)

    def send(message: EmailMessage) -> None:
        if secure:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                host, port, context=ssl.create_default_context(), timeout=30
            )
        else:
            server = smtplib.SMTP(host, port, timeout=30)
        with server:
            if parts.username:
                server.login(unquote(parts.username), unquote(parts.password or ""))
            server.send_message(message)

    return send


def send_all(
    sessions: sessionmaker[Session], outgoing: Iterable[Outgoing], sender: Sender, mail_from: str
) -> tuple[int, int]:
    sent = failed = 0
    domain = mail_from.rsplit("@", 1)[-1].rstrip(">") or "localhost"
    for email in outgoing:
        message = EmailMessage()
        message["From"] = mail_from
        message["To"] = email.to
        message["Subject"] = email.subject
        message["Message-ID"] = make_msgid(domain=domain)
        message.set_content(email.text)
        message.add_alternative(email.html, subtype="html")
        with sessions.begin() as session:
            alerts = session.scalars(select(Alert).where(Alert.id.in_(email.alert_ids))).all()
            try:
                sender(message)
            except (smtplib.SMTPException, OSError) as error:
                failed += 1
                logger.warning("alert email failed", exc_info=True)
                for alert in alerts:
                    alert.status, alert.error = "failed", repr(error)[:500]
                continue
            sent += 1
            for alert in alerts:
                alert.status = "sent"
                alert.sent_at = datetime.now(UTC)
                alert.provider_message_id = message["Message-ID"]
    return sent, failed


def delete_old_demo_accounts(sessions: sessionmaker[Session], now: datetime | None = None) -> int:
    """Demo (anonymous) accounts are deleted after a week, with everything in them."""
    cutoff = (now or datetime.now(UTC)) - timedelta(days=DEMO_ACCOUNT_DAYS)
    with sessions.begin() as session:
        deleted = session.scalars(
            delete(AuthUser)
            .where(AuthUser.is_anonymous.is_(True), AuthUser.created_at < cutoff)
            .returning(AuthUser.id)
        ).all()
    return len(deleted)


def run(
    sessions: sessionmaker[Session],
    embedder: Embedder,
    *,
    ingested: list[RecallSource],
    sender: Sender | None,
    mail_from: str,
    web_url: str,
) -> RunStats:
    stats = RunStats()
    started = time.perf_counter()
    stats.demo_accounts_deleted = delete_old_demo_accounts(sessions)
    recheck_all(sessions, embedder, ingested, stats)
    if sender is not None:
        with sessions() as session:
            outgoing = pending_emails(session, web_url)
        stats.emails_sent, stats.emails_failed = send_all(sessions, outgoing, sender, mail_from)
    else:
        logger.warning("no SMTP_URL: alerts stay pending")
    stats.seconds = round(time.perf_counter() - started, 1)
    return stats
