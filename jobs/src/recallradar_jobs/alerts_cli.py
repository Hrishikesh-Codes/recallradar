"""`recallradar-alerts`: re-check every watched item and email users about new matches.

Runs after `recallradar-sync` and `recallradar-embed` in the scheduled workflow.
"""

import argparse
import json
import sys
from dataclasses import asdict

from sqlalchemy import select

from recallradar_core.db import Recall
from recallradar_core.db.session import get_sessionmaker
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_jobs.alerts import run, smtp_sender
from recallradar_matching.embed import Embedder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    sessions = get_sessionmaker()
    with sessions() as session:
        ingested = list(session.scalars(select(Recall.source).distinct()))
    smtp_url = settings.smtp_url.get_secret_value() if settings.smtp_url else None
    stats = run(
        sessions,
        Embedder(settings.model_cache_dir),
        ingested=ingested,
        sender=smtp_sender(smtp_url) if smtp_url else None,
        mail_from=settings.mail_from,
        web_url=settings.web_url,
    )
    print(json.dumps(asdict(stats)))
    return 1 if stats.emails_failed else 0


if __name__ == "__main__":
    sys.exit(main())
