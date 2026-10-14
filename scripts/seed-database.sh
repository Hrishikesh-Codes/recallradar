#!/usr/bin/env bash
# Copy the recall data from a local database into a fresh one (e.g. Neon), compactly.
#
#   scripts/seed-database.sh "postgresql://...local..." "postgresql://...neon...?sslmode=require"
#
# Why not just run the backfill against Neon: embedding 75k products takes ~25 minutes of CPU,
# and embedding in place leaves a dead row per product (489 MB instead of 427 MB). Restoring
# finished rows is fast and compact. The vector index is built once, after the rows are in.
#
# Runs pg_dump/psql inside the local Postgres container, so the client matches Postgres 17.
set -euo pipefail

source_url=${1:?source database URL}
target_url=${2:?target database URL}
tables=(recall recall_product sync_run)

psql_in_db() { docker compose exec -T db psql "$@"; }

echo "Migrating the target to the latest schema…"
DATABASE_URL="$target_url" uv run alembic -c packages/core/alembic.ini upgrade head

echo "Dropping the vector index on the target (rebuilt after the copy)…"
psql_in_db "$target_url" -v ON_ERROR_STOP=1 -c "DROP INDEX IF EXISTS ix_recall_product_embedding_hnsw"

echo "Copying ${tables[*]}…"
docker compose exec -T db pg_dump "$source_url" --data-only --no-owner \
  $(printf -- '--table=%s ' "${tables[@]}") \
  | psql_in_db "$target_url" -v ON_ERROR_STOP=1 --single-transaction --quiet

echo "Building the vector index…"
psql_in_db "$target_url" -v ON_ERROR_STOP=1 \
  -c "SET maintenance_work_mem = '512MB'" -c "SET max_parallel_maintenance_workers = 0" \
  -c "CREATE INDEX ix_recall_product_embedding_hnsw ON recall_product USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)" \
  -c "ANALYZE recall; ANALYZE recall_product"

psql_in_db "$target_url" -At \
  -c "SELECT 'recalls: ' || count(*) FROM recall" \
  -c "SELECT 'products: ' || count(*) FROM recall_product" \
  -c "SELECT 'database size: ' || pg_size_pretty(pg_database_size(current_database()))"
