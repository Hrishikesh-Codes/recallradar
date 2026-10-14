"""`recallradar-embed`: compute embeddings for recall products that don't have one yet.

Products lose their embedding when their text changes (see recallradar_ingest.store), so running
this after every sync keeps semantic search current.
"""

import argparse
import logging
import sys
import time

from sqlalchemy import select, update

from recallradar_core.db import Recall, RecallProduct
from recallradar_core.db.session import get_sessionmaker
from recallradar_core.logs import configure_logging
from recallradar_core.settings import get_settings
from recallradar_matching.embed import Embedder, product_text

logger = logging.getLogger("recallradar.jobs.embed")


def embed_missing(embedder: Embedder, batch_size: int = 512, limit: int | None = None) -> int:
    sessions = get_sessionmaker()
    done = 0
    while limit is None or done < limit:
        with sessions.begin() as session:
            rows = session.execute(
                select(
                    RecallProduct.id,
                    RecallProduct.product_name,
                    RecallProduct.brand,
                    Recall.firm,
                    RecallProduct.category,
                )
                .join(Recall, Recall.id == RecallProduct.recall_id)
                .where(RecallProduct.embedding.is_(None))
                .order_by(RecallProduct.id)
                .limit(batch_size)
            ).all()
            if not rows:
                break
            vectors = embedder.passages(
                [
                    product_text(name, brand or firm, category)
                    for _, name, brand, firm, category in rows
                ]
            )
            session.execute(
                update(RecallProduct),
                [
                    {"id": row.id, "embedding": vector}
                    for row, vector in zip(rows, vectors, strict=True)
                ],
            )
            done += len(rows)
        logger.info("embedded", extra={"products": done})
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    started = time.perf_counter()
    count = embed_missing(Embedder(settings.model_cache_dir), args.batch_size, args.limit)
    elapsed = time.perf_counter() - started
    print(f'{{"embedded": {count}, "seconds": {elapsed:.1f}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
