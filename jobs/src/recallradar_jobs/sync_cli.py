"""`recallradar-sync`: fetch recalls from the sources into the database.

uv run recallradar-sync --mode backfill                 # since 2015 (NHTSA: 2010), not FSIS
uv run recallradar-sync --source fsis --mode backfill --file ~/Downloads/fsis.json
uv run recallradar-sync --source cpsc                   # incremental, one source
uv run recallradar-sync --source fda_device --since 2020-01-01 --mode backfill
"""

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from recallradar_core.db.session import get_sessionmaker
from recallradar_core.enums import RecallSource, SyncMode
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_ingest import sync
from recallradar_ingest.http import make_client

logger = logging.getLogger("recallradar.jobs.sync")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        choices=[s.value for s in sync.SUPPORTED] + ["all"],
        default="all",
    )
    parser.add_argument(
        "--mode", choices=[m.value for m in SyncMode], default=SyncMode.INCREMENTAL.value
    )
    parser.add_argument("--since", type=date.fromisoformat, help="window start (YYYY-MM-DD)")
    parser.add_argument("--until", type=date.fromisoformat, help="window end (default: today)")
    parser.add_argument(
        "--file",
        type=Path,
        help="FSIS only: import a copy of the Recall API response saved from a browser",
    )
    args = parser.parse_args(argv)
    if args.file and args.source != RecallSource.FSIS.value:
        parser.error("--file works with --source fsis only")

    settings = get_settings()
    configure_logging(settings.log_level)
    sources = sync.AUTOMATED if args.source == "all" else (RecallSource(args.source),)
    failed = []
    with make_client() as client:
        for source in sources:
            try:
                result = sync.run(
                    get_sessionmaker(),
                    source,
                    SyncMode(args.mode),
                    client=client,
                    since=args.since,
                    until=args.until,
                    openfda_api_key=settings.openfda_api_key,
                    file=args.file,
                )
            except Exception:
                failed.append(source.value)  # already logged and recorded in sync_run
                continue
            print(
                json.dumps(
                    {
                        "source": source.value,
                        "window": [d.isoformat() for d in result.window],
                        "fetched": result.fetched,
                        "upserts": asdict(result.upserts),
                        "extraction": asdict(result.extraction),
                    }
                )
            )
    if failed:
        logger.error("sources failed", extra={"sources": failed})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
