# Architecture

RecallRadar is a Next.js PWA in front of a FastAPI service, backed by one Postgres database that
scheduled GitHub Actions jobs keep filled with official recall data. Everything runs on free tiers
(SPEC §3.2).

## System

Solid boxes exist as of M0; dashed boxes arrive in the milestone noted.

```mermaid
flowchart LR
  subgraph Browser
    PWA["Next.js PWA<br/>(Vercel)"]
  end

  subgraph Vercel
    BFF["Route handlers<br/>Better Auth (M1)"]
  end

  subgraph HF["Hugging Face Space (Docker, CPU)"]
    API["FastAPI<br/>/healthz /readyz /v1/meta"]
    MATCH["Matching engine (M1)<br/>embeddings + reranker"]
  end

  subgraph Neon["Neon Postgres"]
    DB[("recall · recall_product<br/>recall_chunk · sync_run · event<br/>pgvector · pg_trgm")]
  end

  subgraph GHA["GitHub Actions cron (M1)"]
    SYNC["sync → match → alert"]
  end

  SOURCES["CPSC · openFDA (M1)<br/>FSIS · NHTSA (M2)"]
  MAIL["Resend email (M1)"]
  LLM["Groq LLM (M4)"]

  PWA --> BFF
  BFF -->|"signed user token"| API
  PWA -.->|anonymous checks| API
  API --> DB
  API -.-> MATCH
  SYNC -.-> SOURCES
  SYNC -.-> DB
  SYNC -.-> MAIL
  API -.-> LLM

  classDef later stroke-dasharray: 5 5
  class BFF,MATCH,SYNC,SOURCES,MAIL,LLM later
```

### Request paths

- **Anonymous check** (M1): browser → FastAPI `/v1/check` → candidate generation and scoring in
  Postgres → verdict with evidence. No account needed.
- **Signed-in actions** (M1): browser → Next.js route handler (session via Better Auth) → FastAPI
  with a short-lived token naming the user. FastAPI never reads cookies.
- **Freshness** (M1): GitHub Actions cron runs the ingesters, which upsert into Postgres and log a
  `sync_run`; new recalls are reverse-matched against watched items and alerts go out by email.

### Why this shape

- The landing page and design system are static (prerendered) and don't need the API, so they
  stay fast even while the free Hugging Face Space is waking up.
- One database is the system of record: the API, jobs and evaluation scripts all read the same
  tables, and Alembic migrations in `packages/core` are the only way the schema changes.

## Data model (M0)

```mermaid
erDiagram
  recall ||--o{ recall_product : covers
  recall ||--o{ recall_chunk : "split into"
  recall {
    bigint id PK
    text source "cpsc | fda_food | fda_drug | fda_device | fsis | nhtsa"
    text source_recall_id "unique per source"
    text title
    text hazard
    text remedy
    date recall_date
    jsonb raw "compact source record, so parsing can be re-run"
    text content_hash "unchanged hash = no-op upsert"
    timestamptz first_seen_at "freshness metric"
  }
  recall_product {
    bigint id PK
    bigint recall_id FK
    text product_name
    text brand
    text_array model_numbers
    text_array upcs
    text_array lot_codes
    date sold_start_date
    date sold_end_date
    tsvector search_text "generated"
    halfvec embedding "384-dim"
  }
  recall_chunk {
    bigint id PK
    bigint recall_id FK
    text section
    text text
    tsvector search_text "generated"
    halfvec embedding "384-dim"
  }
  sync_run {
    bigint id PK
    text source
    text mode "backfill | incremental"
    text status
    int inserted
    int updated
  }
  event {
    bigint id PK
    text name
    jsonb properties
  }
```

The schema follows SPEC §4.3 and will change once ingesters see real data. For example, openFDA's
records are per product and group into a recall by `event_id`.

## Repository layout

| Path | What lives there |
|---|---|
| `apps/web` | Next.js app: pages, design system (`src/design`, `src/components`), Vitest + Playwright |
| `apps/api` | FastAPI service and its Dockerfile (also the Hugging Face Space image) |
| `packages/core` | Settings, JSON logging, SQLAlchemy models, Alembic migrations |
| `packages/ingest` | Source ingesters, normalisation, identifier extraction (M1) |
| `packages/identify` | Input handling → `ProductQuery` (M1–M2) |
| `packages/matching` | Candidate generation, scoring, tiers, evaluation (M1, M3) |
| `packages/ask` | RAG pipeline and evaluation (M4) |
| `packages/earlywarn` | Complaint-surge backtest (M5) |
| `jobs` | Scheduled job entrypoints (M1) |
| `tests` | Cross-package fixtures and integration tests |
| `data/labels` | Hand-labelled evaluation data, no personal data (M3) |
| `docs` | This file, DECISIONS, DESIGN, and evaluation write-ups |
