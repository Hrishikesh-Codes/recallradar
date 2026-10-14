"""`recallradar-embed`: compute embeddings for recall products that don't have one yet.

Products lose their embedding when their name, brand, or category changes (see
recallradar_ingest.store), so running this after every sync keeps semantic search current.
"""

import argparse
import sys
import time

from recallradar_core.db.session import get_sessionmaker
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_matching.embed import Embedder, embed_missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    started = time.perf_counter()
    count = embed_missing(
        get_sessionmaker(), Embedder(settings.model_cache_dir), args.batch_size, args.limit
    )
    elapsed = time.perf_counter() - started
    print(f'{{"embedded": {count}, "seconds": {elapsed:.1f}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
