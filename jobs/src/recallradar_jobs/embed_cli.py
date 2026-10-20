"""`recallradar-embed`: compute embeddings for recall products that don't have one yet.

Products are flagged for re-embedding when their name, brand, or category changes (see
recallradar_ingest.store), so running this after every sync keeps semantic search current.
With VECTOR_DATABASE_URL set, the vectors go to that database (its table is created if needed).
"""

import argparse
import sys
import time

from recallradar_core.db.session import (
    ensure_vector_schema,
    get_sessionmaker,
    get_vector_engine,
    get_vector_sessionmaker,
)
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_matching.embed import Embedder, embed_missing
from recallradar_matching.vectors import VectorStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    started = time.perf_counter()
    engine, vectors = get_vector_engine(), get_vector_sessionmaker()
    store = None
    if engine is not None and vectors is not None:
        ensure_vector_schema(engine)
        store = VectorStore(vectors)
    count = embed_missing(
        get_sessionmaker(),
        Embedder(settings.model_cache_dir),
        args.batch_size,
        args.limit,
        vector_store=store,
    )
    elapsed = time.perf_counter() - started
    print(f'{{"embedded": {count}, "seconds": {elapsed:.1f}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
