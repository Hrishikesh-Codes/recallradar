# RecallRadar

Check whether something you own has been recalled. Scan a barcode, paste a product link,
describe it, or enter a VIN, and get a clear, evidence-backed verdict from official U.S. recall
notices (CPSC, FDA, USDA FSIS, NHTSA). RecallRadar then keeps watching your list and alerts you
if a recall is announced later.

> **Status: Milestone 0 (foundation).** The repo, database, API skeleton, design system, and CI
> are in place. Recall data, product checks, and accounts arrive in Milestone 1. No metrics are
> reported yet; numbers will appear here only once they're measured.

## What's here

- **Web** (`apps/web`): Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4. A dark,
  glass-and-hairline design system with a living gallery at `/dev`, tested for WCAG AA contrast,
  keyboard use, reduced motion, and phone layouts.
- **API** (`apps/api`): FastAPI on Python 3.12, with health and readiness endpoints, JSON logs,
  request IDs, and optional Sentry. Its OpenAPI schema generates the web app's TypeScript types.
- **Database** (`packages/core`): PostgreSQL with pgvector and pg_trgm; SQLAlchemy 2 models and
  Alembic migrations, tested against each other.
- **CI**: lint, strict type checks, Python and web unit tests, a production build, Playwright E2E
  (desktop, phone, reduced motion, with axe accessibility scans), a Docker image smoke test, and
  a secret scan on every push.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the system diagram and data model,
[docs/DESIGN.md](docs/DESIGN.md) for the design system, and
[docs/DECISIONS.md](docs/DECISIONS.md) for why things are the way they are.

## Run it locally

You need [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) and Node 24+, and Docker
(Docker Desktop, OrbStack, or Colima).

```bash
make install   # Python + web dependencies
make up        # Postgres, Mailpit, and the API (migrations run on start)
make web       # http://localhost:3000
```

The API is at http://localhost:8000 (`/healthz`, `/readyz`, `/docs`), and Mailpit's inbox (for
magic links and alerts, later) at http://localhost:8025.

| Command | What it does |
|---|---|
| `make check` | Lint, strict type checks, and all unit tests |
| `make e2e` | Production build + Playwright (desktop, mobile, reduced motion) |
| `make migrate` | Apply migrations to `DATABASE_URL` |
| `make openapi` | Regenerate the API schema and TypeScript types |
| `make help` | Everything else |

Copy `.env.example` to `.env` (and `apps/web/.env.example` to `apps/web/.env.local`) to override
defaults. Never commit real secrets.

## Repository layout

```
apps/web            Next.js PWA
apps/api            FastAPI service (+ Dockerfile, also used by Hugging Face Spaces)
packages/core       settings, logging, models, migrations
packages/ingest     recall ingesters + extraction            (M1)
packages/identify   inputs -> ProductQuery                   (M1–M2)
packages/matching   matching engine + evaluation             (M1, M3)
packages/ask        citation-grounded RAG                    (M4)
packages/earlywarn  complaint-surge backtest                 (M5)
jobs                scheduled sync -> match -> alert          (M1)
docs                architecture, decisions, design, evaluations
```

## Roadmap

| Milestone | Scope |
|---|---|
| **M0 — Foundation** ✅ | Monorepo, Docker Compose, migrations, CI, design system, docs |
| M1 — Thin slice | CPSC + FDA ingestion on a schedule; typed/link/barcode input; baseline matcher with tiers; verdict screen; radar landing; magic-link sign-in, My List, email alerts; live demo |
| M2 — Full coverage | USDA FSIS + NHTSA + VIN; label photo and order screenshot input; web push; installable PWA |
| M3 — Matching v2 | Labelled test set, trained and calibrated scorer, benchmark, EVAL.md |
| M4 — Ask | RAG with citations, verification, abstention, and an ablation study |
| M5 — Early warning | Do complaint surges predict recalls? A strictly out-of-time backtest |
| M6 — Launch | Load test, admin health page, demo video, launch |

## Disclaimer

RecallRadar is an independent project, not affiliated with CPSC, FDA, USDA, or NHTSA. Always
confirm with the official recall notice. "No recall found" never means a product is safe.
