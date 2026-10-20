"""`recallradar-alerts`: re-check every watched item and email users about new matches.

Runs after `recallradar-sync` and `recallradar-embed` in the scheduled workflow.
"""

import argparse
import json
import sys
from dataclasses import asdict

import httpx
from sqlalchemy import select

from recallradar_core.db import Recall
from recallradar_core.db.session import get_sessionmaker, get_vector_sessionmaker
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_identify.vin import decode_vpic
from recallradar_jobs.alerts import run, smtp_sender, vapid_push_sender
from recallradar_matching.embed import Embedder
from recallradar_matching.vectors import VectorStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    sessions = get_sessionmaker()
    with sessions() as session:
        ingested = list(session.scalars(select(Recall.source).distinct()))
    smtp_url = settings.smtp_url.get_secret_value() if settings.smtp_url else None
    client = httpx.Client(timeout=15)  # VIN items are re-decoded with NHTSA's vPIC
    stats = run(
        sessions,
        Embedder(settings.model_cache_dir),
        ingested=ingested,
        sender=smtp_sender(smtp_url) if smtp_url else None,
        mail_from=settings.mail_from,
        web_url=settings.web_url,
        decode_vin=lambda vin: decode_vpic(client, vin),
        push_sender=vapid_push_sender(
            settings.vapid_private_key.get_secret_value(), settings.vapid_subject
        )
        if settings.vapid_private_key
        else None,
        vector_store=VectorStore(vectors) if (vectors := get_vector_sessionmaker()) else None,
    )
    print(json.dumps(asdict(stats)))
    return 1 if stats.emails_failed or stats.pushes_failed else 0


if __name__ == "__main__":
    sys.exit(main())
