#!/usr/bin/env bash
# Copy the recall data from a local database into production (Neon), compactly.
#
#   scripts/seed-database.sh [--replace] SOURCE_URL TARGET_URL [TARGET_VECTOR_URL]
#
# TARGET_VECTOR_URL is the database for embeddings (production: a second Neon project, since
# Neon's free plan caps a database at 512 MiB). Without it the vectors go to TARGET_URL.
#
# --replace empties the target's recall tables first. A full Neon database can't be compacted
# in place (VACUUM FULL needs room for a copy), so this is how a bloated one is rebuilt. It
# refuses if the target has any user accounts: their watch lists reference recalls.
#
# Why not run the backfill against Neon: embedding 80k products takes ~25 minutes of CPU, and
# embedding in place leaves a dead row per product. Restoring finished rows is fast and compact,
# and the vector index is built once, after the rows are in.
#
# pg_dump/psql run inside the Postgres container so the client matches Postgres 17: the local
# compose service by default, or set PG_EXEC (CI: "docker exec -i <container id>").
set -euo pipefail

replace=false
if [[ ${1:-} == --replace ]]; then
  replace=true
  shift
fi
# libpq wants postgresql://; SQLAlchemy URLs name the driver.
libpq() { printf '%s' "${1/postgresql+psycopg:\/\//postgresql://}"; }
source_url=$(libpq "${1:?source database URL}")
target_url=$(libpq "${2:?target database URL}")
vector_url=$(libpq "${3:-$target_url}")
tables=(recall recall_product sync_run)
read -r -a pg_exec <<<"${PG_EXEC:-docker compose exec -T db}"

psql_at() { "${pg_exec[@]}" psql "$@"; }

if $replace; then
  users=$(psql_at "$target_url" -At -c \
    "SELECT CASE WHEN to_regclass('auth_user') IS NULL THEN 0 ELSE (SELECT count(*) FROM auth_user) END")
  if [[ $users != 0 ]]; then
    echo "The target has $users user accounts; not replacing its recall data." >&2
    exit 1
  fi
  if [[ $(psql_at "$target_url" -At -c "SELECT to_regclass('recall') IS NOT NULL") == t ]]; then
    echo "Emptying the target's recall tables…"
    psql_at "$target_url" -v ON_ERROR_STOP=1 -c \
      "TRUNCATE $(IFS=,; echo "${tables[*]}") RESTART IDENTITY CASCADE"
  fi
fi

echo "Migrating the target to the latest schema…"
DATABASE_URL="$target_url" uv run alembic -c packages/core/alembic.ini upgrade head

echo "Preparing the vector table…"
DATABASE_URL="$target_url" VECTOR_DATABASE_URL="$vector_url" uv run python -c \
  "from recallradar_core.db.session import ensure_vector_schema, get_vector_engine as e; ensure_vector_schema(e())"
psql_at "$vector_url" -v ON_ERROR_STOP=1 \
  -c "TRUNCATE product_vector" -c "DROP INDEX IF EXISTS ix_product_vector_embedding_hnsw"

echo "Copying ${tables[*]}…"
"${pg_exec[@]}" pg_dump "$source_url" --data-only --no-owner \
  $(printf -- '--table=%s ' "${tables[@]}") \
  | psql_at "$target_url" -v ON_ERROR_STOP=1 --single-transaction --quiet

echo "Copying the vectors…"
"${pg_exec[@]}" pg_dump "$source_url" --data-only --no-owner --table=product_vector \
  | psql_at "$vector_url" -v ON_ERROR_STOP=1 --single-transaction --quiet

echo "Building the vector index…"
psql_at "$vector_url" -v ON_ERROR_STOP=1 \
  -c "SET maintenance_work_mem = '512MB'" -c "SET max_parallel_maintenance_workers = 0" \
  -c "CREATE INDEX ix_product_vector_embedding_hnsw ON product_vector USING hnsw (embedding halfvec_cosine_ops) WITH (m = 16, ef_construction = 64)" \
  -c "ANALYZE product_vector"
psql_at "$target_url" -v ON_ERROR_STOP=1 -c "ANALYZE recall" -c "ANALYZE recall_product"

psql_at "$target_url" -At \
  -c "SELECT 'recalls: ' || count(*) FROM recall" \
  -c "SELECT 'products: ' || count(*) FROM recall_product" \
  -c "SELECT 'database size: ' || pg_size_pretty(pg_database_size(current_database()))"
psql_at "$vector_url" -At \
  -c "SELECT 'vectors: ' || count(*) FROM product_vector" \
  -c "SELECT 'vector database size: ' || pg_size_pretty(pg_database_size(current_database()))"
