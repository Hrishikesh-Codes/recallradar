"""`recallradar-storage`: report database sizes and fail before Neon's free cap is reached.

Neon's free plan caps a database branch at 512 MiB and refuses writes past it (the daily sync
failed that way in October 2026). Neon counts a little more than `pg_database_size` (measured:
403 MB against 362 MB), so the default limit leaves room for that and for a few weeks' growth.
"""

import argparse
import json
import sys

from sqlalchemy import Engine, text

from recallradar_core.db.session import get_engine, get_vector_engine
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings

DEFAULT_MAX_MB = 430


def database_mb(engine: Engine) -> float:
    with engine.connect() as connection:
        size = connection.scalar(text("SELECT pg_database_size(current_database())"))
    return round(int(size or 0) / 1_000_000, 1)


def over_limit(sizes: dict[str, float], max_mb: float) -> list[str]:
    return [name for name, size in sizes.items() if size > max_mb]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-mb", type=float, default=DEFAULT_MAX_MB)
    args = parser.parse_args(argv)
    configure_logging(get_settings().log_level)
    sizes = {"main": database_mb(get_engine())}
    vectors = get_vector_engine()
    if vectors is not None:
        sizes["vectors"] = database_mb(vectors)
    full = over_limit(sizes, args.max_mb)
    print(json.dumps({"mb": sizes, "max_mb": args.max_mb, "over": full}))
    return 1 if full else 0


if __name__ == "__main__":
    sys.exit(main())
